"""Base activity handler class."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from sim.core.types import Activity, Event, EventType, InitialState


@dataclass
class ActivityResult:
    """Result of processing an activity."""

    activity_id: str
    success: bool
    events: List[Event] = field(default_factory=list)
    state_updates: Dict[str, Any] = field(default_factory=dict)
    profile_updates: Dict[str, List[float]] = field(default_factory=dict)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    message: str = ""


class ActivityHandler(ABC):
    """
    Base class for activity handlers.

    Each activity type (orbit_lower, eo_collect, etc.) has a handler
    that processes the activity and updates simulation state.
    """

    @property
    @abstractmethod
    def activity_type(self) -> str:
        """Return the activity type this handler processes."""
        pass

    @abstractmethod
    def process(
        self,
        activity: Activity,
        state: InitialState,
        ephemeris: list,
        config: Any,
    ) -> ActivityResult:
        """
        Process an activity.

        Args:
            activity: The activity to process
            state: Current spacecraft state
            ephemeris: Ephemeris points for the activity duration
            config: Simulation configuration

        Returns:
            ActivityResult with state updates and events
        """
        pass

    def validate(self, activity: Activity) -> List[Event]:
        """
        Validate activity parameters.

        Args:
            activity: Activity to validate

        Returns:
            List of validation events (errors/warnings)
        """
        return []

    def get_power_consumption(self, activity: Activity) -> float:
        """
        Get power consumption for this activity in Watts.

        Args:
            activity: Activity

        Returns:
            Power consumption in Watts
        """
        return 0.0

    def create_info_event(
        self,
        timestamp: datetime,
        category: str,
        message: str,
        details: Optional[Dict] = None,
    ) -> Event:
        """Create an info event."""
        return Event(
            timestamp=timestamp,
            event_type=EventType.INFO,
            category=category,
            message=message,
            details=details or {},
        )

    def create_warning_event(
        self,
        timestamp: datetime,
        category: str,
        message: str,
        details: Optional[Dict] = None,
    ) -> Event:
        """Create a warning event."""
        return Event(
            timestamp=timestamp,
            event_type=EventType.WARNING,
            category=category,
            message=message,
            details=details or {},
        )

    def create_violation_event(
        self,
        timestamp: datetime,
        category: str,
        message: str,
        details: Optional[Dict] = None,
    ) -> Event:
        """Create a violation event."""
        return Event(
            timestamp=timestamp,
            event_type=EventType.VIOLATION,
            category=category,
            message=message,
            details=details or {},
        )


class IdleHandler(ActivityHandler):
    """Handler for idle periods (no active operations)."""

    @property
    def activity_type(self) -> str:
        return "idle"

    def process(
        self,
        activity: Activity,
        state: InitialState,
        ephemeris: list,
        config: Any,
    ) -> ActivityResult:
        """Process idle period - just updates power state."""
        from sim.models.power import PowerModel, PowerConfig

        power_config = PowerConfig(
            battery_capacity_wh=config.spacecraft.battery_capacity_wh,
            solar_panel_area_m2=config.spacecraft.solar_panel_area_m2,
            solar_efficiency=config.spacecraft.solar_efficiency,
            base_power_w=config.spacecraft.base_power_w,
        )
        power_model = PowerModel(power_config)

        # Track SOC over time
        current_soc = state.battery_soc
        time_step_s = config.time_step_s

        for i, point in enumerate(ephemeris[:-1]):
            in_eclipse = power_model.is_in_eclipse(point.position_eci)
            generation = power_model.compute_solar_generation(in_eclipse)
            consumption = power_config.base_power_w

            current_soc, _ = power_model.update_soc(
                current_soc, generation, consumption, time_step_s
            )

        return ActivityResult(
            activity_id=activity.activity_id,
            success=True,
            state_updates={"battery_soc": current_soc},
            message="Idle period completed",
        )


# Registry of activity handlers
_handlers: Dict[str, ActivityHandler] = {}


def register_handler(handler: ActivityHandler):
    """Register an activity handler."""
    _handlers[handler.activity_type] = handler


def get_handler(activity_type: str) -> Optional[ActivityHandler]:
    """Get handler for an activity type."""
    return _handlers.get(activity_type)


def get_all_handlers() -> Dict[str, ActivityHandler]:
    """Get all registered handlers."""
    return _handlers.copy()
