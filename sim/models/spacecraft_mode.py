"""
Spacecraft mode state machine.

Models spacecraft operational modes and transitions including:
- Mode-dependent power consumption
- Valid mode transitions
- Mode change timing constraints
- Autonomous mode changes (e.g., safe mode entry)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple

from sim.core.types import Event, EventType


logger = logging.getLogger(__name__)


class SpacecraftMode(Enum):
    """Spacecraft operational modes."""

    SAFE = auto()           # Minimum power, sun-pointing, no payload
    STANDBY = auto()        # Ready for operations, nadir-pointing
    IMAGING = auto()        # Payload active, target-pointing
    DOWNLINK = auto()       # Transmitter active, station-tracking
    THRUST = auto()         # Propulsion active
    ECLIPSE_SAFE = auto()   # Reduced operations during eclipse
    COMMISSIONING = auto()  # Post-launch checkout
    MAINTENANCE = auto()    # Software updates, calibration


@dataclass
class ModeConfig:
    """Configuration for a spacecraft mode."""

    power_multiplier: float = 1.0  # Multiplier on base power
    max_duration_s: Optional[float] = None  # Max continuous time in mode
    min_soc_entry: float = 0.0  # Minimum SOC to enter mode
    min_soc_maintain: float = 0.0  # Minimum SOC to stay in mode
    allowed_in_eclipse: bool = True
    transition_time_s: float = 0.0  # Time to transition into mode


# Default mode configurations
DEFAULT_MODE_CONFIGS: Dict[SpacecraftMode, ModeConfig] = {
    SpacecraftMode.SAFE: ModeConfig(
        power_multiplier=0.5,
        min_soc_entry=0.0,
        min_soc_maintain=0.0,
        allowed_in_eclipse=True,
    ),
    SpacecraftMode.STANDBY: ModeConfig(
        power_multiplier=1.0,
        min_soc_entry=0.15,
        min_soc_maintain=0.10,
        allowed_in_eclipse=True,
    ),
    SpacecraftMode.IMAGING: ModeConfig(
        power_multiplier=2.0,
        max_duration_s=3600,  # 1 hour max continuous imaging
        min_soc_entry=0.30,
        min_soc_maintain=0.20,
        allowed_in_eclipse=False,
        transition_time_s=30,
    ),
    SpacecraftMode.DOWNLINK: ModeConfig(
        power_multiplier=1.8,
        min_soc_entry=0.25,
        min_soc_maintain=0.15,
        allowed_in_eclipse=True,
        transition_time_s=20,
    ),
    SpacecraftMode.THRUST: ModeConfig(
        power_multiplier=3.0,
        max_duration_s=1800,  # 30 min max continuous thrust
        min_soc_entry=0.40,
        min_soc_maintain=0.25,
        allowed_in_eclipse=True,
        transition_time_s=60,
    ),
    SpacecraftMode.ECLIPSE_SAFE: ModeConfig(
        power_multiplier=0.7,
        min_soc_entry=0.10,
        min_soc_maintain=0.05,
        allowed_in_eclipse=True,
    ),
    SpacecraftMode.COMMISSIONING: ModeConfig(
        power_multiplier=1.5,
        min_soc_entry=0.50,
        min_soc_maintain=0.30,
    ),
    SpacecraftMode.MAINTENANCE: ModeConfig(
        power_multiplier=1.2,
        min_soc_entry=0.40,
        min_soc_maintain=0.25,
    ),
}


# Valid mode transitions (from -> set of allowed to modes)
VALID_TRANSITIONS: Dict[SpacecraftMode, Set[SpacecraftMode]] = {
    SpacecraftMode.SAFE: {
        SpacecraftMode.STANDBY,
        SpacecraftMode.COMMISSIONING,
    },
    SpacecraftMode.STANDBY: {
        SpacecraftMode.SAFE,
        SpacecraftMode.IMAGING,
        SpacecraftMode.DOWNLINK,
        SpacecraftMode.THRUST,
        SpacecraftMode.ECLIPSE_SAFE,
        SpacecraftMode.MAINTENANCE,
    },
    SpacecraftMode.IMAGING: {
        SpacecraftMode.STANDBY,
        SpacecraftMode.SAFE,
        SpacecraftMode.ECLIPSE_SAFE,
    },
    SpacecraftMode.DOWNLINK: {
        SpacecraftMode.STANDBY,
        SpacecraftMode.SAFE,
        SpacecraftMode.ECLIPSE_SAFE,
    },
    SpacecraftMode.THRUST: {
        SpacecraftMode.STANDBY,
        SpacecraftMode.SAFE,
    },
    SpacecraftMode.ECLIPSE_SAFE: {
        SpacecraftMode.STANDBY,
        SpacecraftMode.SAFE,
    },
    SpacecraftMode.COMMISSIONING: {
        SpacecraftMode.STANDBY,
        SpacecraftMode.SAFE,
    },
    SpacecraftMode.MAINTENANCE: {
        SpacecraftMode.STANDBY,
        SpacecraftMode.SAFE,
    },
}


@dataclass
class ModeTransition:
    """Record of a mode transition."""

    timestamp: datetime
    from_mode: SpacecraftMode
    to_mode: SpacecraftMode
    reason: str
    duration_s: float = 0.0  # Time spent in transition
    success: bool = True


class ModeStateMachine:
    """
    Spacecraft mode state machine.

    Manages spacecraft operational modes, validates transitions,
    and tracks mode history.
    """

    def __init__(
        self,
        initial_mode: SpacecraftMode = SpacecraftMode.STANDBY,
        mode_configs: Optional[Dict[SpacecraftMode, ModeConfig]] = None,
    ):
        self._current_mode = initial_mode
        self._mode_configs = mode_configs or DEFAULT_MODE_CONFIGS.copy()
        self._mode_entry_time: Optional[datetime] = None
        self._transition_history: List[ModeTransition] = []

    @property
    def current_mode(self) -> SpacecraftMode:
        """Get current mode."""
        return self._current_mode

    @property
    def mode_config(self) -> ModeConfig:
        """Get configuration for current mode."""
        return self._mode_configs.get(self._current_mode, ModeConfig())

    @property
    def power_multiplier(self) -> float:
        """Get power multiplier for current mode."""
        return self.mode_config.power_multiplier

    @property
    def transition_history(self) -> List[ModeTransition]:
        """Get mode transition history."""
        return self._transition_history.copy()

    def can_transition(
        self,
        target_mode: SpacecraftMode,
        current_soc: float = 1.0,
        in_eclipse: bool = False,
    ) -> Tuple[bool, str]:
        """
        Check if transition to target mode is valid.

        Args:
            target_mode: Desired mode
            current_soc: Current battery state of charge
            in_eclipse: Whether spacecraft is in eclipse

        Returns:
            Tuple of (can_transition, reason)
        """
        # Check if transition is allowed
        allowed = VALID_TRANSITIONS.get(self._current_mode, set())
        if target_mode not in allowed:
            return False, f"Transition from {self._current_mode.name} to {target_mode.name} not allowed"

        # Check target mode constraints
        target_config = self._mode_configs.get(target_mode, ModeConfig())

        if current_soc < target_config.min_soc_entry:
            return False, f"SOC {current_soc:.1%} below minimum {target_config.min_soc_entry:.1%} for {target_mode.name}"

        if in_eclipse and not target_config.allowed_in_eclipse:
            return False, f"Mode {target_mode.name} not allowed in eclipse"

        return True, "OK"

    def transition(
        self,
        target_mode: SpacecraftMode,
        timestamp: datetime,
        reason: str,
        current_soc: float = 1.0,
        in_eclipse: bool = False,
        force: bool = False,
    ) -> Tuple[bool, List[Event]]:
        """
        Attempt to transition to a new mode.

        Args:
            target_mode: Desired mode
            timestamp: Time of transition
            reason: Reason for transition
            current_soc: Current battery SOC
            in_eclipse: Whether in eclipse
            force: Force transition even if invalid

        Returns:
            Tuple of (success, events)
        """
        events = []

        if target_mode == self._current_mode:
            return True, []

        can_do, fail_reason = self.can_transition(target_mode, current_soc, in_eclipse)

        if not can_do and not force:
            events.append(Event(
                timestamp=timestamp,
                event_type=EventType.WARNING,
                category="mode",
                message=f"Mode transition rejected: {fail_reason}",
                details={
                    "from_mode": self._current_mode.name,
                    "to_mode": target_mode.name,
                    "reason": fail_reason,
                },
            ))
            return False, events

        # Record transition
        target_config = self._mode_configs.get(target_mode, ModeConfig())
        transition = ModeTransition(
            timestamp=timestamp,
            from_mode=self._current_mode,
            to_mode=target_mode,
            reason=reason,
            duration_s=target_config.transition_time_s,
            success=True,
        )
        self._transition_history.append(transition)

        # Update state
        old_mode = self._current_mode
        self._current_mode = target_mode
        self._mode_entry_time = timestamp

        events.append(Event(
            timestamp=timestamp,
            event_type=EventType.INFO,
            category="mode",
            message=f"Mode transition: {old_mode.name} -> {target_mode.name}",
            details={
                "from_mode": old_mode.name,
                "to_mode": target_mode.name,
                "reason": reason,
                "transition_time_s": target_config.transition_time_s,
            },
        ))

        logger.info(f"Mode transition: {old_mode.name} -> {target_mode.name} ({reason})")
        return True, events

    def check_mode_constraints(
        self,
        timestamp: datetime,
        current_soc: float,
        in_eclipse: bool,
    ) -> List[Event]:
        """
        Check if current mode constraints are still satisfied.

        Returns events for any violations and may trigger automatic
        mode changes (e.g., to safe mode).
        """
        events = []
        config = self.mode_config

        # Check SOC
        if current_soc < config.min_soc_maintain:
            events.append(Event(
                timestamp=timestamp,
                event_type=EventType.VIOLATION,
                category="mode",
                message=f"SOC {current_soc:.1%} below minimum {config.min_soc_maintain:.1%} for {self._current_mode.name}",
                details={"current_soc": current_soc, "minimum_soc": config.min_soc_maintain},
            ))

            # Auto-transition to safe mode
            _, transition_events = self.transition(
                target_mode=SpacecraftMode.SAFE,
                timestamp=timestamp,
                reason="Low SOC auto-transition",
                force=True,
            )
            events.extend(transition_events)

        # Check eclipse constraint
        if in_eclipse and not config.allowed_in_eclipse:
            events.append(Event(
                timestamp=timestamp,
                event_type=EventType.WARNING,
                category="mode",
                message=f"Mode {self._current_mode.name} not allowed in eclipse",
                details={},
            ))

            # Auto-transition to eclipse safe
            _, transition_events = self.transition(
                target_mode=SpacecraftMode.ECLIPSE_SAFE,
                timestamp=timestamp,
                reason="Eclipse entry auto-transition",
                force=True,
            )
            events.extend(transition_events)

        # Check max duration
        if config.max_duration_s and self._mode_entry_time:
            time_in_mode = (timestamp - self._mode_entry_time).total_seconds()
            if time_in_mode > config.max_duration_s:
                events.append(Event(
                    timestamp=timestamp,
                    event_type=EventType.WARNING,
                    category="mode",
                    message=f"Exceeded max duration in {self._current_mode.name}",
                    details={
                        "time_in_mode_s": time_in_mode,
                        "max_duration_s": config.max_duration_s,
                    },
                ))

                # Auto-transition to standby
                _, transition_events = self.transition(
                    target_mode=SpacecraftMode.STANDBY,
                    timestamp=timestamp,
                    reason="Max duration exceeded",
                    force=True,
                )
                events.extend(transition_events)

        return events

    def get_mode_for_activity(self, activity_type: str) -> SpacecraftMode:
        """Get the appropriate mode for an activity type."""
        mode_map = {
            "eo_collect": SpacecraftMode.IMAGING,
            "downlink": SpacecraftMode.DOWNLINK,
            "orbit_lower": SpacecraftMode.THRUST,
            "station_keeping": SpacecraftMode.THRUST,
            "collision_avoidance": SpacecraftMode.THRUST,
            "momentum_desat": SpacecraftMode.STANDBY,
            "safe_mode": SpacecraftMode.SAFE,
            "idle": SpacecraftMode.STANDBY,
        }
        return mode_map.get(activity_type, SpacecraftMode.STANDBY)

    def get_summary(self) -> Dict[str, Any]:
        """Get mode state summary."""
        time_in_modes: Dict[str, float] = {}
        for i, transition in enumerate(self._transition_history):
            if i > 0:
                prev = self._transition_history[i - 1]
                duration = (transition.timestamp - prev.timestamp).total_seconds()
                mode_name = prev.from_mode.name
                time_in_modes[mode_name] = time_in_modes.get(mode_name, 0) + duration

        return {
            "current_mode": self._current_mode.name,
            "power_multiplier": self.power_multiplier,
            "transition_count": len(self._transition_history),
            "time_in_modes_s": time_in_modes,
        }
