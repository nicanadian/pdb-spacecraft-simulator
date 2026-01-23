"""Collision avoidance maneuver (CAM) activity handler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

from sim.activities.base import ActivityHandler, ActivityResult
from sim.core.types import Activity, Event, EventType, InitialState
from sim.models.propulsion import EPConfig, EPModel


@dataclass
class CAMParams:
    """Parameters for collision avoidance maneuver."""

    delta_v_m_s: float  # Required delta-V in m/s
    direction: str = "along_track"  # along_track, cross_track, radial
    tca: Optional[str] = None  # Time of closest approach (ISO format)
    miss_distance_m: float = 0.0  # Predicted miss distance before CAM
    object_id: str = ""  # ID of threatening object
    probability_of_collision: float = 0.0  # Pc before CAM

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CAMParams":
        """Create from dictionary."""
        return cls(
            delta_v_m_s=d.get("delta_v_m_s", 0.0),
            direction=d.get("direction", "along_track"),
            tca=d.get("tca"),
            miss_distance_m=d.get("miss_distance_m", 0.0),
            object_id=d.get("object_id", ""),
            probability_of_collision=d.get("probability_of_collision", 0.0),
        )


class CollisionAvoidanceHandler(ActivityHandler):
    """
    Handler for collision avoidance maneuvers.

    Implements rapid response maneuvers to avoid conjunctions with
    debris or other spacecraft. Uses available propulsion system
    (chemical or electric) based on urgency and delta-V requirements.
    """

    @property
    def activity_type(self) -> str:
        return "collision_avoidance"

    def validate(self, activity: Activity) -> List[Event]:
        """Validate CAM parameters."""
        events = []
        params = activity.parameters

        if "delta_v_m_s" not in params:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.ERROR,
                category="validation",
                message="Missing required parameter: delta_v_m_s",
                details={"activity_id": activity.activity_id},
            ))

        delta_v = params.get("delta_v_m_s", 0)
        if delta_v > 10.0:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.WARNING,
                category="validation",
                message=f"Large CAM delta-V requested: {delta_v} m/s",
                details={"activity_id": activity.activity_id},
            ))

        direction = params.get("direction", "along_track")
        if direction not in ["along_track", "cross_track", "radial"]:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.WARNING,
                category="validation",
                message=f"Unknown maneuver direction: {direction}",
                details={"activity_id": activity.activity_id},
            ))

        return events

    def get_power_consumption(self, activity: Activity) -> float:
        """Get power consumption during CAM."""
        # Use EP thruster power
        return activity.parameters.get("thrust_power_w", 1500.0)

    def process(
        self,
        activity: Activity,
        state: InitialState,
        ephemeris: list,
        config: Any,
    ) -> ActivityResult:
        """
        Process collision avoidance maneuver.

        Args:
            activity: CAM activity
            state: Current spacecraft state
            ephemeris: Ephemeris for activity duration
            config: Simulation configuration

        Returns:
            ActivityResult with maneuver details
        """
        params = CAMParams.from_dict(activity.parameters)

        # Initialize EP model for thrust calculations
        ep_config = EPConfig(
            thrust_n=activity.parameters.get("thrust_n", 0.1),
            isp_s=activity.parameters.get("isp_s", 1500.0),
            power_w=activity.parameters.get("thrust_power_w", 1500.0),
        )
        ep_model = EPModel(ep_config)

        events: List[Event] = []

        # Log CAM initiation
        events.append(self.create_info_event(
            timestamp=activity.start_time,
            category="cam",
            message=f"Initiating CAM: {params.delta_v_m_s:.2f} m/s {params.direction}",
            details={
                "object_id": params.object_id,
                "miss_distance_m": params.miss_distance_m,
                "pc": params.probability_of_collision,
            },
        ))

        # Calculate required thrust duration
        delta_v_km_s = params.delta_v_m_s / 1000.0
        thrust_duration_s = ep_model.compute_thrust_duration_for_delta_v(
            delta_v_km_s, state.mass_kg
        )

        # Check if we have time to complete the maneuver
        available_time_s = activity.duration_s
        if thrust_duration_s > available_time_s:
            events.append(self.create_warning_event(
                timestamp=activity.start_time,
                category="cam",
                message=f"CAM requires {thrust_duration_s:.0f}s but only {available_time_s:.0f}s available",
                details={"required_s": thrust_duration_s, "available_s": available_time_s},
            ))
            thrust_duration_s = available_time_s

        # Calculate propellant usage
        propellant_used = ep_model.compute_propellant_used(delta_v_km_s, state.mass_kg)

        # Check propellant availability
        if propellant_used > state.propellant_kg:
            events.append(self.create_violation_event(
                timestamp=activity.start_time,
                category="propellant",
                message="Insufficient propellant for CAM",
                details={
                    "required_kg": propellant_used,
                    "available_kg": state.propellant_kg,
                },
            ))
            # Execute partial maneuver
            propellant_used = state.propellant_kg
            # Recalculate achieved delta-V
            achieved_delta_v = propellant_used / state.mass_kg * ep_config.exhaust_velocity_km_s * 1000
        else:
            achieved_delta_v = params.delta_v_m_s

        # Calculate power usage
        power_wh = ep_model.compute_power_used(thrust_duration_s)

        # Update state
        final_propellant = state.propellant_kg - propellant_used
        final_mass = state.mass_kg - propellant_used

        # Estimate new miss distance (simplified model)
        # For along-track maneuvers, miss distance improvement scales with delta-V
        if params.miss_distance_m > 0 and params.delta_v_m_s > 0:
            improvement_factor = achieved_delta_v / params.delta_v_m_s
            estimated_new_miss = params.miss_distance_m + (achieved_delta_v * 1000)  # Rough estimate
        else:
            estimated_new_miss = 0.0

        events.append(self.create_info_event(
            timestamp=activity.end_time,
            category="cam",
            message=f"CAM complete: achieved {achieved_delta_v:.2f} m/s",
            details={
                "achieved_delta_v_m_s": achieved_delta_v,
                "propellant_used_kg": propellant_used,
                "estimated_new_miss_m": estimated_new_miss,
            },
        ))

        # Create result
        success = achieved_delta_v >= params.delta_v_m_s * 0.95  # 95% of target
        if not success:
            events.append(self.create_warning_event(
                timestamp=activity.end_time,
                category="cam",
                message=f"CAM incomplete: only achieved {achieved_delta_v:.2f}/{params.delta_v_m_s:.2f} m/s",
                details={},
            ))

        return ActivityResult(
            activity_id=activity.activity_id,
            success=success,
            events=events,
            state_updates={
                "propellant_kg": max(0.0, final_propellant),
                "mass_kg": final_mass,
            },
            artifacts={
                "requested_delta_v_m_s": params.delta_v_m_s,
                "achieved_delta_v_m_s": achieved_delta_v,
                "direction": params.direction,
                "propellant_used_kg": propellant_used,
                "power_used_wh": power_wh,
                "thrust_duration_s": thrust_duration_s,
                "object_id": params.object_id,
            },
            message=(
                f"CAM: {achieved_delta_v:.2f} m/s {params.direction}, "
                f"propellant={propellant_used:.3f} kg"
            ),
        )
