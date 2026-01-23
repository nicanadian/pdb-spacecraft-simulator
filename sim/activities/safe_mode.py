"""Safe mode and survival operations activity handler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from sim.activities.base import ActivityHandler, ActivityResult
from sim.core.types import Activity, Event, EventType, InitialState
from sim.models.power import PowerConfig, PowerModel


@dataclass
class SafeModeParams:
    """Parameters for safe mode operation."""

    reason: str = "anomaly"  # anomaly, low_power, thermal, commanded
    min_soc_exit: float = 0.5  # Minimum SOC to exit safe mode
    base_power_w: float = 100.0  # Reduced power consumption in safe mode
    sun_pointing: bool = True  # Whether to maintain sun pointing

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SafeModeParams":
        """Create from dictionary."""
        return cls(
            reason=d.get("reason", "anomaly"),
            min_soc_exit=d.get("min_soc_exit", 0.5),
            base_power_w=d.get("base_power_w", 100.0),
            sun_pointing=d.get("sun_pointing", True),
        )


class SafeModeHandler(ActivityHandler):
    """
    Handler for safe mode / survival operations.

    Safe mode is entered when the spacecraft experiences an anomaly or
    low-power condition. The spacecraft reduces power consumption to
    minimum levels and attempts to maintain sun-pointing for battery
    charging.

    Based on Phoenix CubeSat ConOps:
    - Idle mode: charge battery, collect heartbeat
    - Safe mode: restricted operations until healthy
    """

    @property
    def activity_type(self) -> str:
        return "safe_mode"

    def validate(self, activity: Activity) -> List[Event]:
        """Validate safe mode parameters."""
        events = []
        params = activity.parameters

        min_soc = params.get("min_soc_exit", 0.5)
        if not 0.0 < min_soc <= 1.0:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.WARNING,
                category="validation",
                message=f"Invalid min_soc_exit: {min_soc}, using 0.5",
                details={"activity_id": activity.activity_id},
            ))

        return events

    def get_power_consumption(self, activity: Activity) -> float:
        """Get power consumption in safe mode (minimal)."""
        return activity.parameters.get("base_power_w", 100.0)

    def process(
        self,
        activity: Activity,
        state: InitialState,
        ephemeris: list,
        config: Any,
    ) -> ActivityResult:
        """
        Process safe mode activity.

        In safe mode:
        - Power consumption reduced to minimum
        - All payloads disabled
        - Sun-pointing maintained for charging
        - Exit when SOC reaches threshold

        Args:
            activity: Safe mode activity
            state: Current spacecraft state
            ephemeris: Ephemeris for activity duration
            config: Simulation configuration

        Returns:
            ActivityResult with power recovery details
        """
        params = SafeModeParams.from_dict(activity.parameters)

        # Initialize power model with reduced consumption
        power_config = PowerConfig(
            battery_capacity_wh=config.spacecraft.battery_capacity_wh,
            solar_panel_area_m2=config.spacecraft.solar_panel_area_m2,
            solar_efficiency=config.spacecraft.solar_efficiency,
            base_power_w=params.base_power_w,  # Reduced power
        )
        power_model = PowerModel(power_config)

        events: List[Event] = []
        current_soc = state.battery_soc
        time_step_s = config.time_step_s

        # Log safe mode entry
        events.append(self.create_info_event(
            timestamp=activity.start_time,
            category="safe_mode",
            message=f"Entering safe mode: {params.reason}",
            details={
                "initial_soc": current_soc,
                "reason": params.reason,
            },
        ))

        min_soc_reached = current_soc
        max_soc_reached = current_soc
        exit_time = None
        time_in_eclipse = 0.0
        time_in_sun = 0.0

        for point in ephemeris:
            in_eclipse = power_model.is_in_eclipse(point.position_eci)

            # In safe mode with sun-pointing, assume optimal solar angle when in sun
            if params.sun_pointing and not in_eclipse:
                generation = power_model.compute_solar_generation(in_eclipse, sun_angle_deg=0.0)
            else:
                generation = power_model.compute_solar_generation(in_eclipse)

            # Update SOC with minimal power consumption
            current_soc, _ = power_model.update_soc(
                current_soc, generation, params.base_power_w, time_step_s
            )

            min_soc_reached = min(min_soc_reached, current_soc)
            max_soc_reached = max(max_soc_reached, current_soc)

            if in_eclipse:
                time_in_eclipse += time_step_s
            else:
                time_in_sun += time_step_s

            # Check exit condition
            if current_soc >= params.min_soc_exit and exit_time is None:
                exit_time = point.time
                events.append(self.create_info_event(
                    timestamp=point.time,
                    category="safe_mode",
                    message=f"SOC threshold reached: {current_soc:.1%}",
                    details={"soc": current_soc},
                ))

        # Log safe mode exit
        events.append(self.create_info_event(
            timestamp=activity.end_time,
            category="safe_mode",
            message=f"Exiting safe mode: SOC={current_soc:.1%}",
            details={
                "final_soc": current_soc,
                "min_soc": min_soc_reached,
                "max_soc": max_soc_reached,
            },
        ))

        # Check if we recovered
        recovered = current_soc >= params.min_soc_exit

        if not recovered:
            events.append(self.create_warning_event(
                timestamp=activity.end_time,
                category="safe_mode",
                message=f"Safe mode exit threshold not reached: {current_soc:.1%} < {params.min_soc_exit:.1%}",
                details={},
            ))

        return ActivityResult(
            activity_id=activity.activity_id,
            success=recovered,
            events=events,
            state_updates={
                "battery_soc": max(0.0, min(1.0, current_soc)),
            },
            artifacts={
                "reason": params.reason,
                "initial_soc": state.battery_soc,
                "final_soc": current_soc,
                "min_soc": min_soc_reached,
                "max_soc": max_soc_reached,
                "time_in_eclipse_s": time_in_eclipse,
                "time_in_sun_s": time_in_sun,
                "recovered": recovered,
            },
            message=(
                f"Safe mode ({params.reason}): SOC {state.battery_soc:.1%} -> {current_soc:.1%}, "
                f"{'recovered' if recovered else 'not recovered'}"
            ),
        )
