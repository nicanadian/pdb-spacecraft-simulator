"""Orbit lowering activity handler using electric propulsion."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

from sim.activities.base import ActivityHandler, ActivityResult
from sim.core.types import Activity, Event, EventType, InitialState
from sim.models.orbit import (
    EARTH_RADIUS_KM,
    MU_EARTH,
    compute_lowering_delta_v,
    orbital_period,
)
from sim.models.propulsion import EPConfig, EPModel, ThrustArc, ThrustPlan
from sim.models.power import PowerConfig, PowerModel


@dataclass
class OrbitLoweringParams:
    """Parameters for orbit lowering activity."""

    target_altitude_km: float
    thrust_n: float = 0.1
    isp_s: float = 1500.0
    power_w: float = 1500.0
    thrusts_per_orbit: int = 2
    thrust_arc_deg: float = 30.0

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OrbitLoweringParams":
        """Create from dictionary."""
        return cls(
            target_altitude_km=d.get("target_altitude_km", 400.0),
            thrust_n=d.get("thrust_n", 0.1),
            isp_s=d.get("isp_s", 1500.0),
            power_w=d.get("power_w", 1500.0),
            thrusts_per_orbit=d.get("thrusts_per_orbit", 2),
            thrust_arc_deg=d.get("thrust_arc_deg", 30.0),
        )


class OrbitLoweringHandler(ActivityHandler):
    """
    Handler for orbit lowering maneuvers using electric propulsion.

    Implements duty-cycled thrusting with power constraints.
    """

    @property
    def activity_type(self) -> str:
        return "orbit_lower"

    def validate(self, activity: Activity) -> List[Event]:
        """Validate orbit lowering parameters."""
        events = []
        params = activity.parameters

        if "target_altitude_km" not in params:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.ERROR,
                category="validation",
                message="Missing required parameter: target_altitude_km",
                details={"activity_id": activity.activity_id},
            ))

        target_alt = params.get("target_altitude_km", 0)
        if target_alt < 150:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.WARNING,
                category="validation",
                message=f"Target altitude {target_alt} km is very low (VLEO)",
                details={"activity_id": activity.activity_id},
            ))

        return events

    def get_power_consumption(self, activity: Activity) -> float:
        """Get power consumption during thrust."""
        return activity.parameters.get("power_w", 1500.0)

    def process(
        self,
        activity: Activity,
        state: InitialState,
        ephemeris: list,
        config: Any,
    ) -> ActivityResult:
        """
        Process orbit lowering activity.

        Args:
            activity: Orbit lowering activity
            state: Current spacecraft state
            ephemeris: Ephemeris for activity duration
            config: Simulation configuration

        Returns:
            ActivityResult with delta-V, propellant use, altitude change
        """
        params = OrbitLoweringParams.from_dict(activity.parameters)

        # Initialize models
        ep_config = EPConfig(
            thrust_n=params.thrust_n,
            isp_s=params.isp_s,
            power_w=params.power_w,
            thrusts_per_orbit=params.thrusts_per_orbit,
            thrust_arc_deg=params.thrust_arc_deg,
        )
        ep_model = EPModel(ep_config)

        power_config = PowerConfig(
            battery_capacity_wh=config.spacecraft.battery_capacity_wh,
            solar_panel_area_m2=config.spacecraft.solar_panel_area_m2,
            solar_efficiency=config.spacecraft.solar_efficiency,
            base_power_w=config.spacecraft.base_power_w,
        )
        power_model = PowerModel(power_config)

        # Get current altitude
        if ephemeris:
            current_altitude = ephemeris[0].altitude_km
        else:
            current_altitude = np.linalg.norm(state.position_eci) - EARTH_RADIUS_KM

        target_altitude = params.target_altitude_km

        # Calculate required delta-V
        total_dv_required = compute_lowering_delta_v(current_altitude, target_altitude)

        # Get orbital period
        period_s = orbital_period(current_altitude)

        # Plan thrust arcs
        thrust_plan = ep_model.plan_orbit_lowering(
            start_altitude_km=current_altitude,
            end_altitude_km=target_altitude,
            spacecraft_mass_kg=state.mass_kg,
            start_time=activity.start_time,
            orbit_period_s=period_s,
            battery_capacity_wh=config.spacecraft.battery_capacity_wh,
            initial_soc=state.battery_soc,
        )

        # Process thrust arcs with power constraints
        events: List[Event] = []
        executed_arcs: List[ThrustArc] = []
        current_soc = state.battery_soc
        current_mass = state.mass_kg
        current_propellant = state.propellant_kg
        total_dv_achieved = 0.0
        total_propellant_used = 0.0
        skipped_arcs = 0

        time_step_s = config.time_step_s
        last_time = activity.start_time

        for arc in thrust_plan.arcs:
            # Check if arc is within activity window
            if arc.end_time > activity.end_time:
                break

            # Update power state from last time to arc start
            # (simulate idle period with base power consumption)
            idle_duration = (arc.start_time - last_time).total_seconds()
            if idle_duration > 0:
                # Find ephemeris point for this time
                for point in ephemeris:
                    if point.time >= last_time and point.time < arc.start_time:
                        in_eclipse = power_model.is_in_eclipse(point.position_eci)
                        generation = power_model.compute_solar_generation(in_eclipse)
                        current_soc, _ = power_model.update_soc(
                            current_soc, generation, power_config.base_power_w, time_step_s
                        )

            # Check power availability
            if not ep_model.check_power_available(
                current_soc, config.spacecraft.battery_capacity_wh
            ):
                events.append(self.create_warning_event(
                    timestamp=arc.start_time,
                    category="power",
                    message=f"Skipping thrust arc due to low battery ({current_soc:.1%})",
                    details={"arc_start": arc.start_time.isoformat()},
                ))
                skipped_arcs += 1
                last_time = arc.end_time
                continue

            # Check propellant availability
            if current_propellant < arc.propellant_used_kg:
                events.append(self.create_violation_event(
                    timestamp=arc.start_time,
                    category="propellant",
                    message="Insufficient propellant for thrust arc",
                    details={
                        "required_kg": arc.propellant_used_kg,
                        "available_kg": current_propellant,
                    },
                ))
                break

            # Execute thrust arc
            executed_arcs.append(arc)
            total_dv_achieved += arc.delta_v_km_s
            total_propellant_used += arc.propellant_used_kg
            current_propellant -= arc.propellant_used_kg
            current_mass -= arc.propellant_used_kg

            # Update power during thrust
            thrust_duration = arc.duration_s
            total_power = power_config.base_power_w + params.power_w
            current_soc, power_limited = power_model.update_soc(
                current_soc, 0.0, total_power, thrust_duration  # Assume thrust in eclipse worst case
            )

            if power_limited:
                events.append(self.create_warning_event(
                    timestamp=arc.start_time,
                    category="power",
                    message="Power limited during thrust arc",
                    details={"soc_after": current_soc},
                ))

            events.append(self.create_info_event(
                timestamp=arc.start_time,
                category="thrust",
                message=f"Executed thrust arc: dV={arc.delta_v_km_s*1000:.1f} m/s",
                details={
                    "delta_v_m_s": arc.delta_v_km_s * 1000,
                    "propellant_kg": arc.propellant_used_kg,
                    "power_wh": arc.power_used_wh,
                },
            ))

            last_time = arc.end_time

        # Calculate final altitude (approximation for low-thrust spiral)
        # For circular orbit: v = sqrt(mu/r), so dv maps to altitude change
        if total_dv_achieved > 0:
            # Estimate new altitude based on achieved delta-V
            progress_fraction = total_dv_achieved / total_dv_required
            altitude_change = (target_altitude - current_altitude) * progress_fraction
            final_altitude = current_altitude + altitude_change
        else:
            final_altitude = current_altitude

        # Validate constraints
        if current_soc < 0:
            events.append(self.create_violation_event(
                timestamp=activity.end_time,
                category="power",
                message="Battery SOC went negative",
                details={"final_soc": current_soc},
            ))
            current_soc = 0.0

        if current_propellant < 0:
            events.append(self.create_violation_event(
                timestamp=activity.end_time,
                category="propellant",
                message="Propellant went negative",
                details={"final_propellant": current_propellant},
            ))
            current_propellant = 0.0

        # Create result
        success = total_dv_achieved > 0 and not any(
            e.event_type == EventType.VIOLATION for e in events
        )

        return ActivityResult(
            activity_id=activity.activity_id,
            success=success,
            events=events,
            state_updates={
                "battery_soc": max(0.0, min(1.0, current_soc)),
                "propellant_kg": max(0.0, current_propellant),
                "mass_kg": current_mass,
            },
            artifacts={
                "thrust_arcs": [
                    {
                        "start_time": arc.start_time.isoformat(),
                        "end_time": arc.end_time.isoformat(),
                        "delta_v_m_s": arc.delta_v_km_s * 1000,
                        "propellant_kg": arc.propellant_used_kg,
                    }
                    for arc in executed_arcs
                ],
            },
            message=(
                f"Orbit lowering: {current_altitude:.1f} -> {final_altitude:.1f} km, "
                f"dV={total_dv_achieved*1000:.1f} m/s, "
                f"propellant={total_propellant_used:.2f} kg, "
                f"arcs executed={len(executed_arcs)}, skipped={skipped_arcs}"
            ),
        )
