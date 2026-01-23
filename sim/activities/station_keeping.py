"""Station keeping and ground track maintenance activity handler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from sim.activities.base import ActivityHandler, ActivityResult
from sim.core.types import Activity, Event, EventType, InitialState
from sim.models.orbit import EARTH_RADIUS_KM, MU_EARTH, orbital_period
from sim.models.propulsion import EPConfig, EPModel
from sim.models.power import PowerConfig, PowerModel


@dataclass
class StationKeepingParams:
    """Parameters for station keeping maneuver."""

    maneuver_type: str = "altitude"  # altitude, inclination, raan, ground_track
    target_altitude_km: Optional[float] = None
    altitude_tolerance_km: float = 5.0  # Acceptable altitude deviation
    ground_track_tolerance_km: float = 2.0  # Acceptable ground track deviation
    thrust_n: float = 0.1
    isp_s: float = 1500.0
    power_w: float = 1500.0

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StationKeepingParams":
        """Create from dictionary."""
        return cls(
            maneuver_type=d.get("maneuver_type", "altitude"),
            target_altitude_km=d.get("target_altitude_km"),
            altitude_tolerance_km=d.get("altitude_tolerance_km", 5.0),
            ground_track_tolerance_km=d.get("ground_track_tolerance_km", 2.0),
            thrust_n=d.get("thrust_n", 0.1),
            isp_s=d.get("isp_s", 1500.0),
            power_w=d.get("power_w", 1500.0),
        )


class StationKeepingHandler(ActivityHandler):
    """
    Handler for station keeping maneuvers.

    Maintains orbital parameters within specified tolerances:
    - Altitude maintenance (compensate for drag decay)
    - Ground track maintenance (for repeat-track missions)
    - Inclination maintenance

    Based on research showing LEO satellites require regular
    station-keeping to maintain mission requirements, especially
    for imaging satellites with ground track constraints.
    """

    @property
    def activity_type(self) -> str:
        return "station_keeping"

    def validate(self, activity: Activity) -> List[Event]:
        """Validate station keeping parameters."""
        events = []
        params = activity.parameters

        maneuver_type = params.get("maneuver_type", "altitude")
        if maneuver_type not in ["altitude", "inclination", "raan", "ground_track"]:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.WARNING,
                category="validation",
                message=f"Unknown maneuver type: {maneuver_type}",
                details={"activity_id": activity.activity_id},
            ))

        return events

    def get_power_consumption(self, activity: Activity) -> float:
        """Get power consumption during station keeping."""
        return activity.parameters.get("power_w", 1500.0)

    def _compute_altitude_maintenance_dv(
        self,
        current_altitude_km: float,
        target_altitude_km: float,
    ) -> float:
        """
        Compute delta-V needed to raise altitude.

        For drag compensation, we typically need to raise the orbit
        periodically to maintain altitude.

        Args:
            current_altitude_km: Current altitude
            target_altitude_km: Target altitude

        Returns:
            Delta-V in km/s
        """
        if current_altitude_km >= target_altitude_km:
            return 0.0

        # Hohmann-like delta-V for altitude raise
        r1 = EARTH_RADIUS_KM + current_altitude_km
        r2 = EARTH_RADIUS_KM + target_altitude_km

        # For small altitude changes, use approximation
        delta_a = r2 - r1
        v_circ = np.sqrt(MU_EARTH / r1)

        # dV ≈ (dA / 2a) * v for small changes
        dv = (delta_a / (2 * r1)) * v_circ

        return dv

    def process(
        self,
        activity: Activity,
        state: InitialState,
        ephemeris: list,
        config: Any,
    ) -> ActivityResult:
        """
        Process station keeping activity.

        Args:
            activity: Station keeping activity
            state: Current spacecraft state
            ephemeris: Ephemeris for activity duration
            config: Simulation configuration

        Returns:
            ActivityResult with maneuver details
        """
        params = StationKeepingParams.from_dict(activity.parameters)

        # Initialize models
        ep_config = EPConfig(
            thrust_n=params.thrust_n,
            isp_s=params.isp_s,
            power_w=params.power_w,
        )
        ep_model = EPModel(ep_config)

        power_config = PowerConfig(
            battery_capacity_wh=config.spacecraft.battery_capacity_wh,
            solar_panel_area_m2=config.spacecraft.solar_panel_area_m2,
            solar_efficiency=config.spacecraft.solar_efficiency,
            base_power_w=config.spacecraft.base_power_w,
        )
        power_model = PowerModel(power_config)

        events: List[Event] = []

        # Get current altitude from ephemeris
        if ephemeris:
            current_altitude = ephemeris[0].altitude_km
        else:
            current_altitude = np.linalg.norm(state.position_eci) - EARTH_RADIUS_KM

        # Determine target altitude
        target_altitude = params.target_altitude_km
        if target_altitude is None:
            # Default: maintain current altitude
            target_altitude = current_altitude + params.altitude_tolerance_km

        events.append(self.create_info_event(
            timestamp=activity.start_time,
            category="station_keeping",
            message=f"Station keeping: {params.maneuver_type}",
            details={
                "current_altitude_km": current_altitude,
                "target_altitude_km": target_altitude,
            },
        ))

        # Calculate required delta-V
        delta_v_km_s = 0.0
        if params.maneuver_type == "altitude":
            delta_v_km_s = self._compute_altitude_maintenance_dv(
                current_altitude, target_altitude
            )
        elif params.maneuver_type == "ground_track":
            # For ground track maintenance, need to adjust semi-major axis
            # to correct accumulated drift
            drift_correction = params.ground_track_tolerance_km / 1000.0  # km to adjustment
            delta_v_km_s = drift_correction * 0.001  # Approximate

        if delta_v_km_s <= 0:
            events.append(self.create_info_event(
                timestamp=activity.end_time,
                category="station_keeping",
                message="No maneuver required - within tolerance",
                details={},
            ))
            return ActivityResult(
                activity_id=activity.activity_id,
                success=True,
                events=events,
                state_updates={},
                artifacts={"delta_v_m_s": 0, "maneuver_required": False},
                message="Station keeping: no maneuver required",
            )

        delta_v_m_s = delta_v_km_s * 1000.0

        # Calculate thrust duration and propellant
        thrust_duration_s = ep_model.compute_thrust_duration_for_delta_v(
            delta_v_km_s, state.mass_kg
        )
        propellant_used = ep_model.compute_propellant_used(delta_v_km_s, state.mass_kg)

        # Check propellant
        if propellant_used > state.propellant_kg:
            events.append(self.create_warning_event(
                timestamp=activity.start_time,
                category="propellant",
                message="Insufficient propellant for full maneuver",
                details={
                    "required_kg": propellant_used,
                    "available_kg": state.propellant_kg,
                },
            ))
            propellant_used = state.propellant_kg
            achieved_dv = propellant_used / state.mass_kg * ep_config.exhaust_velocity_km_s
            delta_v_m_s = achieved_dv * 1000.0

        # Update power over maneuver duration
        current_soc = state.battery_soc
        power_wh = ep_model.compute_power_used(min(thrust_duration_s, activity.duration_s))

        # Simplified: check if we have enough power
        available_wh = current_soc * config.spacecraft.battery_capacity_wh
        if power_wh > available_wh:
            events.append(self.create_warning_event(
                timestamp=activity.start_time,
                category="power",
                message="Insufficient power for full maneuver",
                details={"required_wh": power_wh, "available_wh": available_wh},
            ))

        # Update state
        final_propellant = state.propellant_kg - propellant_used
        final_mass = state.mass_kg - propellant_used
        current_soc -= power_wh / config.spacecraft.battery_capacity_wh

        events.append(self.create_info_event(
            timestamp=activity.end_time,
            category="station_keeping",
            message=f"Maneuver complete: {delta_v_m_s:.2f} m/s",
            details={
                "delta_v_m_s": delta_v_m_s,
                "propellant_kg": propellant_used,
            },
        ))

        return ActivityResult(
            activity_id=activity.activity_id,
            success=True,
            events=events,
            state_updates={
                "battery_soc": max(0.0, min(1.0, current_soc)),
                "propellant_kg": max(0.0, final_propellant),
                "mass_kg": final_mass,
            },
            artifacts={
                "maneuver_type": params.maneuver_type,
                "delta_v_m_s": delta_v_m_s,
                "propellant_used_kg": propellant_used,
                "thrust_duration_s": thrust_duration_s,
                "initial_altitude_km": current_altitude,
                "target_altitude_km": target_altitude,
            },
            message=(
                f"Station keeping ({params.maneuver_type}): "
                f"{delta_v_m_s:.2f} m/s, propellant={propellant_used:.3f} kg"
            ),
        )
