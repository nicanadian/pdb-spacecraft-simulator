"""Momentum desaturation activity handler for reaction wheel unloading."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from sim.activities.base import ActivityHandler, ActivityResult
from sim.core.types import Activity, Event, EventType, InitialState
from sim.models.power import PowerConfig, PowerModel


@dataclass
class MomentumDesatParams:
    """Parameters for momentum desaturation."""

    wheel_momentum_nms: float = 0.0  # Current wheel momentum in N-m-s
    target_momentum_nms: float = 0.0  # Target momentum after desat
    mtq_dipole_am2: float = 1.0  # Magnetorquer dipole moment
    desat_power_w: float = 20.0  # Power for magnetorquers
    max_desat_rate_nms_per_s: float = 0.01  # Maximum desaturation rate

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MomentumDesatParams":
        """Create from dictionary."""
        return cls(
            wheel_momentum_nms=d.get("wheel_momentum_nms", 0.0),
            target_momentum_nms=d.get("target_momentum_nms", 0.0),
            mtq_dipole_am2=d.get("mtq_dipole_am2", 1.0),
            desat_power_w=d.get("desat_power_w", 20.0),
            max_desat_rate_nms_per_s=d.get("max_desat_rate_nms_per_s", 0.01),
        )


class MomentumDesatHandler(ActivityHandler):
    """
    Handler for reaction wheel momentum desaturation.

    Uses magnetorquers to dump accumulated momentum from reaction wheels.
    This is a regular maintenance activity required to prevent wheel
    saturation.

    Based on CubeSat ADCS operations:
    - Magnetorquer controllers handle momentum desaturation
    - Desaturation rate depends on magnetic field strength
    - Best performed over high-latitude regions (stronger B-field)
    """

    @property
    def activity_type(self) -> str:
        return "momentum_desat"

    def validate(self, activity: Activity) -> List[Event]:
        """Validate momentum desat parameters."""
        events = []
        params = activity.parameters

        wheel_momentum = params.get("wheel_momentum_nms", 0.0)
        if wheel_momentum < 0:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.WARNING,
                category="validation",
                message="Negative wheel momentum specified",
                details={"activity_id": activity.activity_id},
            ))

        return events

    def get_power_consumption(self, activity: Activity) -> float:
        """Get power consumption for magnetorquers."""
        return activity.parameters.get("desat_power_w", 20.0)

    def _estimate_magnetic_field(self, position_eci: np.ndarray, time: datetime) -> float:
        """
        Estimate Earth's magnetic field strength at position.

        Simplified dipole model - field is stronger at higher latitudes.

        Args:
            position_eci: Position in ECI (km)
            time: Current time

        Returns:
            Magnetic field strength in Tesla
        """
        from sim.models.orbit import EARTH_RADIUS_KM

        r = np.linalg.norm(position_eci)
        # Simplified: use z-component to estimate latitude effect
        sin_lat = position_eci[2] / r

        # Earth's dipole field at equator surface ~ 30 microTesla
        B0 = 30e-6  # Tesla

        # Field strength scales as (R_earth/r)^3 and is stronger at poles
        latitude_factor = np.sqrt(1 + 3 * sin_lat**2)
        B = B0 * (EARTH_RADIUS_KM / r) ** 3 * latitude_factor

        return B

    def process(
        self,
        activity: Activity,
        state: InitialState,
        ephemeris: list,
        config: Any,
    ) -> ActivityResult:
        """
        Process momentum desaturation activity.

        Args:
            activity: Momentum desat activity
            state: Current spacecraft state
            ephemeris: Ephemeris for activity duration
            config: Simulation configuration

        Returns:
            ActivityResult with desat details
        """
        params = MomentumDesatParams.from_dict(activity.parameters)

        # Initialize power model
        power_config = PowerConfig(
            battery_capacity_wh=config.spacecraft.battery_capacity_wh,
            solar_panel_area_m2=config.spacecraft.solar_panel_area_m2,
            solar_efficiency=config.spacecraft.solar_efficiency,
            base_power_w=config.spacecraft.base_power_w,
        )
        power_model = PowerModel(power_config)

        events: List[Event] = []
        current_soc = state.battery_soc
        current_momentum = params.wheel_momentum_nms
        time_step_s = config.time_step_s
        total_momentum_dumped = 0.0

        events.append(self.create_info_event(
            timestamp=activity.start_time,
            category="adcs",
            message=f"Starting momentum desaturation: {current_momentum:.3f} N-m-s",
            details={"initial_momentum": current_momentum},
        ))

        for point in ephemeris:
            if abs(current_momentum - params.target_momentum_nms) < 0.001:
                # Target reached
                break

            # Estimate magnetic field at current position
            B = self._estimate_magnetic_field(point.position_eci, point.time)

            # Torque from magnetorquer: T = M x B
            # Maximum torque magnitude: T_max = M * B
            max_torque = params.mtq_dipole_am2 * B

            # Desaturation rate limited by max torque and configured limit
            # dH/dt = T, so dH = T * dt
            desat_rate = min(max_torque, params.max_desat_rate_nms_per_s)

            # Calculate momentum change this step
            momentum_to_dump = current_momentum - params.target_momentum_nms
            momentum_change = min(abs(momentum_to_dump), desat_rate * time_step_s)

            if momentum_to_dump > 0:
                current_momentum -= momentum_change
            else:
                current_momentum += momentum_change

            total_momentum_dumped += momentum_change

            # Update power
            in_eclipse = power_model.is_in_eclipse(point.position_eci)
            generation = power_model.compute_solar_generation(in_eclipse)
            total_power = power_config.base_power_w + params.desat_power_w

            current_soc, power_limited = power_model.update_soc(
                current_soc, generation, total_power, time_step_s
            )

            if power_limited:
                events.append(self.create_warning_event(
                    timestamp=point.time,
                    category="power",
                    message="Power limited during desaturation",
                    details={"soc": current_soc},
                ))

        # Check completion
        completed = abs(current_momentum - params.target_momentum_nms) < 0.01
        efficiency = total_momentum_dumped / max(0.001, params.wheel_momentum_nms - params.target_momentum_nms)

        events.append(self.create_info_event(
            timestamp=activity.end_time,
            category="adcs",
            message=f"Desaturation complete: {current_momentum:.3f} N-m-s remaining",
            details={
                "final_momentum": current_momentum,
                "momentum_dumped": total_momentum_dumped,
            },
        ))

        return ActivityResult(
            activity_id=activity.activity_id,
            success=completed,
            events=events,
            state_updates={
                "battery_soc": max(0.0, min(1.0, current_soc)),
            },
            artifacts={
                "initial_momentum_nms": params.wheel_momentum_nms,
                "final_momentum_nms": current_momentum,
                "target_momentum_nms": params.target_momentum_nms,
                "momentum_dumped_nms": total_momentum_dumped,
                "completed": completed,
            },
            message=(
                f"Momentum desat: {params.wheel_momentum_nms:.3f} -> {current_momentum:.3f} N-m-s, "
                f"dumped={total_momentum_dumped:.3f} N-m-s"
            ),
        )
