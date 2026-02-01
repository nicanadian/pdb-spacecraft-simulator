"""Tests for spacecraft mode state machine."""

from datetime import datetime, timedelta, timezone

import pytest

from sim.core.types import EventType
from sim.models.spacecraft_mode import (
    DEFAULT_MODE_CONFIGS,
    VALID_TRANSITIONS,
    ModeConfig,
    ModeStateMachine,
    ModeTransition,
    SpacecraftMode,
)


class TestSpacecraftMode:
    """Test SpacecraftMode enum."""

    def test_mode_values(self):
        """Test all expected modes exist."""
        expected_modes = [
            "SAFE",
            "STANDBY",
            "IMAGING",
            "DOWNLINK",
            "THRUST",
            "ECLIPSE_SAFE",
            "COMMISSIONING",
            "MAINTENANCE",
        ]
        for mode_name in expected_modes:
            assert hasattr(SpacecraftMode, mode_name)


class TestModeConfig:
    """Test ModeConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ModeConfig()

        assert config.power_multiplier == 1.0
        assert config.max_duration_s is None
        assert config.min_soc_entry == 0.0
        assert config.min_soc_maintain == 0.0
        assert config.allowed_in_eclipse is True
        assert config.transition_time_s == 0.0

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ModeConfig(
            power_multiplier=2.5,
            max_duration_s=3600,
            min_soc_entry=0.40,
            min_soc_maintain=0.25,
            allowed_in_eclipse=False,
            transition_time_s=30.0,
        )

        assert config.power_multiplier == 2.5
        assert config.max_duration_s == 3600
        assert config.min_soc_entry == 0.40
        assert config.min_soc_maintain == 0.25
        assert config.allowed_in_eclipse is False
        assert config.transition_time_s == 30.0


class TestDefaultModeConfigs:
    """Test default mode configurations."""

    def test_all_modes_have_config(self):
        """Test that all modes have a default configuration."""
        for mode in SpacecraftMode:
            assert mode in DEFAULT_MODE_CONFIGS

    def test_safe_mode_config(self):
        """Test SAFE mode configuration."""
        config = DEFAULT_MODE_CONFIGS[SpacecraftMode.SAFE]

        assert config.power_multiplier == 0.5
        assert config.min_soc_entry == 0.0
        assert config.allowed_in_eclipse is True

    def test_imaging_mode_config(self):
        """Test IMAGING mode configuration."""
        config = DEFAULT_MODE_CONFIGS[SpacecraftMode.IMAGING]

        assert config.power_multiplier == 2.0
        assert config.max_duration_s == 3600
        assert config.min_soc_entry == 0.30
        assert config.allowed_in_eclipse is False

    def test_thrust_mode_config(self):
        """Test THRUST mode configuration."""
        config = DEFAULT_MODE_CONFIGS[SpacecraftMode.THRUST]

        assert config.power_multiplier == 3.0
        assert config.max_duration_s == 1800
        assert config.min_soc_entry == 0.40


class TestValidTransitions:
    """Test valid mode transitions."""

    def test_safe_transitions(self):
        """Test transitions from SAFE mode."""
        allowed = VALID_TRANSITIONS[SpacecraftMode.SAFE]

        assert SpacecraftMode.STANDBY in allowed
        assert SpacecraftMode.COMMISSIONING in allowed
        assert SpacecraftMode.IMAGING not in allowed

    def test_standby_transitions(self):
        """Test transitions from STANDBY mode."""
        allowed = VALID_TRANSITIONS[SpacecraftMode.STANDBY]

        assert SpacecraftMode.SAFE in allowed
        assert SpacecraftMode.IMAGING in allowed
        assert SpacecraftMode.DOWNLINK in allowed
        assert SpacecraftMode.THRUST in allowed

    def test_all_modes_have_transitions(self):
        """Test that all modes have defined transitions."""
        for mode in SpacecraftMode:
            assert mode in VALID_TRANSITIONS


class TestModeStateMachine:
    """Test ModeStateMachine."""

    @pytest.fixture
    def state_machine(self):
        """Create state machine for testing."""
        return ModeStateMachine(initial_mode=SpacecraftMode.STANDBY)

    @pytest.fixture
    def timestamp(self):
        """Create timestamp for testing."""
        return datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    def test_initial_state(self, state_machine):
        """Test initial state machine state."""
        assert state_machine.current_mode == SpacecraftMode.STANDBY
        assert state_machine.power_multiplier == 1.0
        assert len(state_machine.transition_history) == 0

    def test_can_transition_valid(self, state_machine):
        """Test valid transition check."""
        can, reason = state_machine.can_transition(SpacecraftMode.IMAGING)
        assert can is True
        assert reason == "OK"

    def test_can_transition_invalid_mode(self, state_machine):
        """Test invalid transition check."""
        can, reason = state_machine.can_transition(SpacecraftMode.COMMISSIONING)
        assert can is False
        assert "not allowed" in reason

    def test_can_transition_low_soc(self, state_machine):
        """Test transition blocked by low SOC."""
        # IMAGING requires SOC >= 0.30
        can, reason = state_machine.can_transition(
            SpacecraftMode.IMAGING,
            current_soc=0.20,
        )
        assert can is False
        assert "SOC" in reason

    def test_can_transition_eclipse_constraint(self, state_machine):
        """Test transition blocked by eclipse constraint."""
        # IMAGING not allowed in eclipse
        can, reason = state_machine.can_transition(
            SpacecraftMode.IMAGING,
            current_soc=0.50,
            in_eclipse=True,
        )
        assert can is False
        assert "eclipse" in reason

    def test_transition_success(self, state_machine, timestamp):
        """Test successful mode transition."""
        success, events = state_machine.transition(
            target_mode=SpacecraftMode.IMAGING,
            timestamp=timestamp,
            reason="Imaging activity start",
            current_soc=0.50,
        )

        assert success is True
        assert state_machine.current_mode == SpacecraftMode.IMAGING
        assert len(state_machine.transition_history) == 1

        # Check for INFO event
        info_events = [e for e in events if e.event_type == EventType.INFO]
        assert len(info_events) == 1

    def test_transition_failure(self, state_machine, timestamp):
        """Test failed mode transition."""
        success, events = state_machine.transition(
            target_mode=SpacecraftMode.IMAGING,
            timestamp=timestamp,
            reason="Imaging activity start",
            current_soc=0.10,  # Too low
        )

        assert success is False
        assert state_machine.current_mode == SpacecraftMode.STANDBY
        assert len(state_machine.transition_history) == 0

        # Check for WARNING event
        warning_events = [e for e in events if e.event_type == EventType.WARNING]
        assert len(warning_events) == 1

    def test_transition_same_mode(self, state_machine, timestamp):
        """Test transition to same mode (no-op)."""
        success, events = state_machine.transition(
            target_mode=SpacecraftMode.STANDBY,
            timestamp=timestamp,
            reason="Same mode",
        )

        assert success is True
        assert len(events) == 0
        assert len(state_machine.transition_history) == 0

    def test_transition_force(self, state_machine, timestamp):
        """Test forced transition overriding constraints."""
        success, events = state_machine.transition(
            target_mode=SpacecraftMode.SAFE,
            timestamp=timestamp,
            reason="Emergency",
            current_soc=0.01,
            force=True,
        )

        assert success is True
        assert state_machine.current_mode == SpacecraftMode.SAFE

    def test_check_mode_constraints_soc(self, state_machine, timestamp):
        """Test constraint checking for low SOC."""
        # Transition to IMAGING
        state_machine.transition(
            SpacecraftMode.IMAGING,
            timestamp,
            "Start imaging",
            current_soc=0.50,
        )

        # Now check constraints with low SOC
        events = state_machine.check_mode_constraints(
            timestamp=timestamp + timedelta(minutes=30),
            current_soc=0.15,  # Below IMAGING min_soc_maintain (0.20)
            in_eclipse=False,
        )

        # Should have violation event
        violations = [e for e in events if e.event_type == EventType.VIOLATION]
        assert len(violations) == 1

        # Should have auto-transitioned to SAFE
        assert state_machine.current_mode == SpacecraftMode.SAFE

    def test_check_mode_constraints_eclipse(self, state_machine, timestamp):
        """Test constraint checking for eclipse entry."""
        # Transition to IMAGING
        state_machine.transition(
            SpacecraftMode.IMAGING,
            timestamp,
            "Start imaging",
            current_soc=0.50,
        )

        # Enter eclipse
        events = state_machine.check_mode_constraints(
            timestamp=timestamp + timedelta(minutes=30),
            current_soc=0.40,
            in_eclipse=True,  # IMAGING not allowed in eclipse
        )

        # Should have warning event
        warnings = [e for e in events if e.event_type == EventType.WARNING]
        assert len(warnings) >= 1

        # Should have auto-transitioned to ECLIPSE_SAFE
        assert state_machine.current_mode == SpacecraftMode.ECLIPSE_SAFE

    def test_check_mode_constraints_max_duration(self, state_machine, timestamp):
        """Test constraint checking for max duration exceeded."""
        # Transition to IMAGING (max 3600s)
        state_machine.transition(
            SpacecraftMode.IMAGING,
            timestamp,
            "Start imaging",
            current_soc=0.50,
        )

        # Check after 2 hours (exceeds 1 hour max)
        events = state_machine.check_mode_constraints(
            timestamp=timestamp + timedelta(hours=2),
            current_soc=0.40,
            in_eclipse=False,
        )

        # Should have warning event
        warnings = [e for e in events if e.event_type == EventType.WARNING]
        assert len(warnings) >= 1

        # Should have auto-transitioned to STANDBY
        assert state_machine.current_mode == SpacecraftMode.STANDBY

    def test_get_mode_for_activity(self, state_machine):
        """Test activity type to mode mapping."""
        assert state_machine.get_mode_for_activity("eo_collect") == SpacecraftMode.IMAGING
        assert state_machine.get_mode_for_activity("downlink") == SpacecraftMode.DOWNLINK
        assert state_machine.get_mode_for_activity("orbit_lower") == SpacecraftMode.THRUST
        assert state_machine.get_mode_for_activity("safe_mode") == SpacecraftMode.SAFE
        assert state_machine.get_mode_for_activity("idle") == SpacecraftMode.STANDBY
        assert state_machine.get_mode_for_activity("unknown") == SpacecraftMode.STANDBY

    def test_get_summary(self, state_machine, timestamp):
        """Test summary generation."""
        state_machine.transition(SpacecraftMode.IMAGING, timestamp, "Start", current_soc=0.50)
        state_machine.transition(
            SpacecraftMode.STANDBY,
            timestamp + timedelta(minutes=30),
            "End",
            current_soc=0.40,
            force=True,
        )

        summary = state_machine.get_summary()

        assert summary["current_mode"] == "STANDBY"
        assert summary["power_multiplier"] == 1.0
        assert summary["transition_count"] == 2

    def test_power_multiplier_updates(self, state_machine, timestamp):
        """Test power multiplier changes with mode."""
        assert state_machine.power_multiplier == 1.0  # STANDBY

        state_machine.transition(SpacecraftMode.IMAGING, timestamp, "Start", current_soc=0.50)
        assert state_machine.power_multiplier == 2.0  # IMAGING

        state_machine.transition(
            SpacecraftMode.SAFE,
            timestamp + timedelta(minutes=5),
            "Emergency",
            force=True,
        )
        assert state_machine.power_multiplier == 0.5  # SAFE


class TestModeTransition:
    """Test ModeTransition dataclass."""

    def test_create_transition(self):
        """Test transition record creation."""
        timestamp = datetime(2025, 1, 15, tzinfo=timezone.utc)
        transition = ModeTransition(
            timestamp=timestamp,
            from_mode=SpacecraftMode.STANDBY,
            to_mode=SpacecraftMode.IMAGING,
            reason="Activity start",
            duration_s=30.0,
            success=True,
        )

        assert transition.from_mode == SpacecraftMode.STANDBY
        assert transition.to_mode == SpacecraftMode.IMAGING
        assert transition.duration_s == 30.0
        assert transition.success is True

    def test_transition_defaults(self):
        """Test transition default values."""
        timestamp = datetime(2025, 1, 15, tzinfo=timezone.utc)
        transition = ModeTransition(
            timestamp=timestamp,
            from_mode=SpacecraftMode.STANDBY,
            to_mode=SpacecraftMode.SAFE,
            reason="Test",
        )

        assert transition.duration_s == 0.0
        assert transition.success is True


class TestCustomModeConfigs:
    """Test state machine with custom mode configurations."""

    def test_custom_configs(self):
        """Test state machine with custom mode configs."""
        custom_configs = {
            SpacecraftMode.SAFE: ModeConfig(power_multiplier=0.3),
            SpacecraftMode.STANDBY: ModeConfig(
                power_multiplier=0.8,
                min_soc_entry=0.10,
            ),
        }

        sm = ModeStateMachine(
            initial_mode=SpacecraftMode.STANDBY,
            mode_configs=custom_configs,
        )

        assert sm.power_multiplier == 0.8

    def test_missing_custom_config_uses_default(self):
        """Test that missing configs use default ModeConfig."""
        custom_configs = {
            SpacecraftMode.STANDBY: ModeConfig(power_multiplier=0.9),
        }

        sm = ModeStateMachine(
            initial_mode=SpacecraftMode.STANDBY,
            mode_configs=custom_configs,
        )

        timestamp = datetime(2025, 1, 15, tzinfo=timezone.utc)
        sm.transition(SpacecraftMode.SAFE, timestamp, "Test", force=True)

        # SAFE not in custom configs, should get default ModeConfig
        assert sm.mode_config.power_multiplier == 1.0
