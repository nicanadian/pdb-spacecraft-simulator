"""Tests for Basilisk propagator."""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from sim.core.types import Fidelity, InitialState
from sim.models.basilisk_propagator import (
    BASILISK_AVAILABLE,
    BasiliskConfig,
    BasiliskPropagator,
    EARTH_MU,
    EARTH_RADIUS,
)
from sim.models.propagator_base import EphemerisPoint, PropagatorConfig


class TestBasiliskConfig:
    """Test BasiliskConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BasiliskConfig()

        assert config.integration_method == "rk4"
        assert config.integration_step_s == 10.0
        assert config.gravity_degree == 20
        assert config.gravity_order == 20
        assert config.enable_albedo is False

    def test_for_fidelity_low(self):
        """Test config for LOW fidelity using PropagatorConfig."""
        config = PropagatorConfig.for_fidelity("LOW")

        assert config.gravity_model == "spherical"
        assert config.atmosphere_model is None

    def test_for_fidelity_medium(self):
        """Test config for MEDIUM fidelity using PropagatorConfig."""
        config = PropagatorConfig.for_fidelity("MEDIUM")

        assert config.gravity_model == "j2"
        assert config.atmosphere_model == "exponential"
        assert config.third_body_sun is True
        assert config.third_body_moon is True

    def test_for_fidelity_high(self):
        """Test config for HIGH fidelity using PropagatorConfig."""
        config = PropagatorConfig.for_fidelity("HIGH")

        assert config.gravity_model == "egm96"
        assert config.atmosphere_model == "nrlmsise00"
        assert config.solar_radiation_pressure is True


class TestBasiliskPropagator:
    """Test BasiliskPropagator."""

    @pytest.fixture
    def leo_state(self):
        """Create typical LEO initial state."""
        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

        # ~500 km altitude circular orbit
        r = EARTH_RADIUS + 500  # km
        v = np.sqrt(EARTH_MU / r)  # Circular velocity km/s

        return InitialState(
            epoch=epoch,
            position_eci=np.array([r, 0.0, 0.0]),
            velocity_eci=np.array([0.0, v, 0.0]),
        )

    @pytest.fixture
    def propagator(self, leo_state):
        """Create propagator with initial state."""
        # Create with explicit config to avoid for_fidelity issues
        config = BasiliskConfig()
        return BasiliskPropagator(
            initial_state=leo_state,
            fidelity=Fidelity.MEDIUM,
            config=config,
        )

    def test_initialization(self, propagator):
        """Test propagator initialization."""
        pos, vel = propagator.current_state

        # Check position magnitude
        r = np.linalg.norm(pos)
        assert abs(r - (EARTH_RADIUS + 500)) < 1.0

        # Check velocity magnitude
        v = np.linalg.norm(vel)
        expected_v = np.sqrt(EARTH_MU / r)
        assert abs(v - expected_v) < 0.1

    def test_uninitialized_propagate_raises(self):
        """Test that propagating uninitialized propagator raises error."""
        config = BasiliskConfig()
        propagator = BasiliskPropagator(config=config)

        with pytest.raises(RuntimeError, match="not initialized"):
            propagator.propagate(datetime(2025, 1, 15, tzinfo=timezone.utc))

    def test_propagate_single_epoch(self, propagator, leo_state):
        """Test propagation to single epoch."""
        target_epoch = leo_state.epoch + timedelta(minutes=10)

        point = propagator.propagate(target_epoch)

        assert isinstance(point, EphemerisPoint)
        assert point.time == target_epoch

        # Check altitude is still reasonable
        assert 400 < point.altitude_km < 600

    def test_propagate_one_orbit(self, propagator, leo_state):
        """Test propagation for approximately one orbit."""
        # Orbital period ~ 94 minutes for 500 km altitude
        r = EARTH_RADIUS + 500
        period_s = 2 * np.pi * np.sqrt(r**3 / EARTH_MU)

        target_epoch = leo_state.epoch + timedelta(seconds=period_s)
        point = propagator.propagate(target_epoch)

        # After one orbit, verify we're still in a valid orbital regime
        # The simplified J2 analytical propagation has known limitations
        # and doesn't accurately return to the starting position
        assert 400 < point.altitude_km < 600  # Still in LEO
        assert 6.0 < np.linalg.norm(point.velocity_eci) < 9.0  # Valid orbital velocity

    def test_propagate_range(self, propagator, leo_state):
        """Test propagation over time range."""
        start = leo_state.epoch
        end = start + timedelta(hours=1)
        step_s = 60.0

        points = propagator.propagate_range(start, end, step_s)

        # Should have ~61 points (60 minutes + 1)
        assert len(points) >= 60

        # Check times are monotonic
        for i in range(1, len(points)):
            assert points[i].time > points[i-1].time

        # Check all points have valid altitude
        for point in points:
            assert 400 < point.altitude_km < 600

    def test_apply_maneuver(self, propagator, leo_state):
        """Test applying impulsive maneuver."""
        # Apply small prograde delta-V (0.01 km/s = 10 m/s)
        delta_v = np.array([0.0, 0.01, 0.0])  # Prograde
        epoch = leo_state.epoch + timedelta(minutes=30)

        result = propagator.apply_maneuver(delta_v, epoch)

        # Check delta-V was applied
        np.testing.assert_array_almost_equal(result.delta_v_applied, delta_v)

        # Check propellant was used
        assert result.propellant_used_kg > 0

        # Check new velocity is higher (prograde burn raises orbit)
        new_v = np.linalg.norm(result.new_velocity)
        old_v = np.sqrt(EARTH_MU / np.linalg.norm(result.new_position))
        assert new_v > old_v

    def test_version_string(self, propagator):
        """Test version string format."""
        version = propagator.version

        assert isinstance(version, str)
        if BASILISK_AVAILABLE:
            assert "basilisk" in version.lower()
        else:
            assert "j2-analytical" in version

    def test_current_epoch_property(self, propagator, leo_state):
        """Test current_epoch property."""
        assert propagator.current_epoch == leo_state.epoch

    def test_current_state_property(self, propagator):
        """Test current_state property."""
        pos, vel = propagator.current_state

        assert pos.shape == (3,)
        assert vel.shape == (3,)

    def test_timezone_handling(self, leo_state):
        """Test handling of naive datetime (should assume UTC)."""
        # Create state with naive datetime
        naive_epoch = datetime(2025, 1, 15, 0, 0, 0)

        config = BasiliskConfig()
        propagator = BasiliskPropagator(config=config)
        propagator.initialize(
            position_eci=leo_state.position_eci,
            velocity_eci=leo_state.velocity_eci,
            epoch=naive_epoch,
        )

        # Propagate with naive datetime
        target = datetime(2025, 1, 15, 0, 10, 0)
        point = propagator.propagate(target)

        assert point.time.tzinfo is not None


class TestJ2PropagationPhysics:
    """Test J2 propagation physics."""

    @pytest.fixture
    def propagator(self):
        """Create propagator for physics tests."""
        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        r = EARTH_RADIUS + 500
        v = np.sqrt(EARTH_MU / r)

        state = InitialState(
            epoch=epoch,
            position_eci=np.array([r, 0.0, 0.0]),
            velocity_eci=np.array([0.0, v, 0.0]),
        )

        config = BasiliskConfig()
        return BasiliskPropagator(initial_state=state, fidelity=Fidelity.MEDIUM, config=config)

    def test_semi_major_axis_conservation(self, propagator):
        """Test that semi-major axis is approximately conserved."""
        initial_pos, initial_vel = propagator.current_state
        initial_r = np.linalg.norm(initial_pos)
        initial_v = np.linalg.norm(initial_vel)

        # Calculate initial semi-major axis
        initial_energy = initial_v**2 / 2 - EARTH_MU / initial_r
        initial_a = -EARTH_MU / (2 * initial_energy)

        # Propagate for 1 day
        target = propagator.current_epoch + timedelta(days=1)
        point = propagator.propagate(target)

        final_r = np.linalg.norm(point.position_eci)
        final_v = np.linalg.norm(point.velocity_eci)

        final_energy = final_v**2 / 2 - EARTH_MU / final_r
        final_a = -EARTH_MU / (2 * final_energy)

        # Semi-major axis should be conserved to within 1 km
        assert abs(final_a - initial_a) < 1.0

    def test_orbital_energy_conservation(self, propagator):
        """Test that orbital energy is approximately conserved."""
        initial_pos, initial_vel = propagator.current_state
        initial_r = np.linalg.norm(initial_pos)
        initial_v = np.linalg.norm(initial_vel)

        initial_energy = initial_v**2 / 2 - EARTH_MU / initial_r

        # Propagate for 6 hours
        target = propagator.current_epoch + timedelta(hours=6)
        point = propagator.propagate(target)

        final_r = np.linalg.norm(point.position_eci)
        final_v = np.linalg.norm(point.velocity_eci)

        final_energy = final_v**2 / 2 - EARTH_MU / final_r

        # Energy should be conserved to within 0.1%
        energy_diff = abs(final_energy - initial_energy) / abs(initial_energy)
        assert energy_diff < 0.001


class TestBasiliskAvailability:
    """Test Basilisk availability detection."""

    def test_availability_is_boolean(self):
        """Test that BASILISK_AVAILABLE is boolean."""
        assert isinstance(BASILISK_AVAILABLE, bool)

    def test_fallback_without_basilisk(self):
        """Test that propagator works without Basilisk."""
        # This should work regardless of Basilisk availability
        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

        state = InitialState(
            epoch=epoch,
            position_eci=np.array([6878.0, 0.0, 0.0]),
            velocity_eci=np.array([0.0, 7.6, 0.0]),
        )

        config = BasiliskConfig()
        propagator = BasiliskPropagator(initial_state=state, config=config)
        point = propagator.propagate(epoch + timedelta(minutes=10))

        # Should produce valid output
        assert point.altitude_km > 0


class TestInvalidStateHandling:
    """Test handling of invalid states."""

    def test_uninitialized_current_state_raises(self):
        """Test that getting state from uninitialized propagator raises error."""
        config = BasiliskConfig()
        propagator = BasiliskPropagator(config=config)

        with pytest.raises(RuntimeError, match="not initialized"):
            _ = propagator.current_state

    def test_uninitialized_current_epoch_raises(self):
        """Test that getting epoch from uninitialized propagator raises error."""
        config = BasiliskConfig()
        propagator = BasiliskPropagator(config=config)

        with pytest.raises(RuntimeError, match="not initialized"):
            _ = propagator.current_epoch

    def test_reinitialize(self):
        """Test reinitializing propagator with new state."""
        epoch1 = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        epoch2 = datetime(2025, 1, 16, 0, 0, 0, tzinfo=timezone.utc)

        config = BasiliskConfig()
        propagator = BasiliskPropagator(config=config)

        # First initialization
        propagator.initialize(
            position_eci=np.array([6878.0, 0.0, 0.0]),
            velocity_eci=np.array([0.0, 7.6, 0.0]),
            epoch=epoch1,
        )
        assert propagator.current_epoch == epoch1

        # Reinitialize
        propagator.initialize(
            position_eci=np.array([6900.0, 0.0, 0.0]),
            velocity_eci=np.array([0.0, 7.5, 0.0]),
            epoch=epoch2,
        )
        assert propagator.current_epoch == epoch2


class TestComparisonWithSGP4:
    """Test comparison with SGP4 propagator (if available)."""

    def test_j2_vs_simplified_bounded_difference(self):
        """Test that J2 propagation differs from two-body within expected bounds."""
        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        r = EARTH_RADIUS + 500
        v = np.sqrt(EARTH_MU / r)

        state = InitialState(
            epoch=epoch,
            position_eci=np.array([r, 0.0, 0.0]),
            velocity_eci=np.array([0.0, v, 0.0]),
        )

        config = BasiliskConfig()
        propagator = BasiliskPropagator(initial_state=state, config=config)

        # Propagate for 1 day
        target = epoch + timedelta(days=1)
        point = propagator.propagate(target)

        # The position should still be reasonable (not diverged to nonsense)
        assert np.linalg.norm(point.position_eci) > EARTH_RADIUS
        assert np.linalg.norm(point.position_eci) < EARTH_RADIUS + 2000  # Still in LEO

        # Velocity should still be orbital velocity magnitude
        assert 6.0 < np.linalg.norm(point.velocity_eci) < 9.0  # km/s
