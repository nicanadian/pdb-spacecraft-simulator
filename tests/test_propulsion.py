"""Tests for electric propulsion model."""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from sim.models.propulsion import (
    EPConfig,
    EPModel,
    ThrustArc,
    compute_thrust_direction,
)


class TestEPConfig:
    """Test EP configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = EPConfig()

        assert config.thrust_n == 0.1
        assert config.isp_s == 1500.0
        assert config.power_w == 1500.0

    def test_exhaust_velocity(self):
        """Test exhaust velocity calculation."""
        config = EPConfig(isp_s=1500.0)
        ve = config.exhaust_velocity_km_s

        # ve = Isp * g0 = 1500 * 0.00980665 = ~14.7 km/s
        assert 14.0 < ve < 15.0


class TestEPModel:
    """Test EP model calculations."""

    @pytest.fixture
    def ep_model(self):
        """Create EP model for testing."""
        config = EPConfig(
            thrust_n=0.1,
            isp_s=1500.0,
            power_w=1500.0,
        )
        return EPModel(config)

    def test_compute_delta_v(self, ep_model):
        """Test delta-V calculation."""
        # 1 hour of thrust at 0.1 N on 500 kg spacecraft
        dv = ep_model.compute_delta_v(
            thrust_duration_s=3600.0,
            spacecraft_mass_kg=500.0,
        )

        # F*t/m = 0.1 * 3600 / 500 = 0.72 m/s
        # Converting to km/s: 0.00072 km/s
        expected = 0.1 * 3600 / (500 * 1e6)  # km/s
        assert abs(dv - expected) < 1e-8

    def test_compute_propellant_used(self, ep_model):
        """Test propellant calculation using rocket equation."""
        # For small delta-V, propellant ~ m * dv / ve
        dv = 0.001  # 1 m/s in km/s
        mass = 500.0  # kg

        propellant = ep_model.compute_propellant_used(dv, mass)

        # Approximate: dm = m * dv / ve
        ve = ep_model.config.exhaust_velocity_km_s
        expected_approx = mass * dv / ve

        # Should be close to linear approximation for small dv
        assert abs(propellant - expected_approx) / expected_approx < 0.01

    def test_compute_power_used(self, ep_model):
        """Test power consumption calculation."""
        # 1 hour at 1500 W
        power_wh = ep_model.compute_power_used(3600.0)

        assert power_wh == 1500.0  # 1500 W * 1 h = 1500 Wh

    def test_check_power_available(self, ep_model):
        """Test power availability check."""
        # With 50% SOC and 5000 Wh capacity, have 2500 Wh available
        # Need ~25 Wh for 1 minute thrust (1500 W * 60/3600)
        assert ep_model.check_power_available(0.5, 5000.0)

        # With very low SOC, should fail
        assert not ep_model.check_power_available(0.001, 5000.0)

    def test_schedule_thrust_arcs(self, ep_model):
        """Test thrust arc scheduling."""
        start = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        orbit_period = 5640.0  # ~94 minutes

        arcs = ep_model.schedule_thrust_arcs(
            orbit_period_s=orbit_period,
            start_time=start,
            num_orbits=2,
        )

        # Should have 4 arcs (2 per orbit * 2 orbits)
        assert len(arcs) == 4

        # Check arc positions
        positions = [arc[2] for arc in arcs]
        assert 0.0 in positions
        assert 180.0 in positions


class TestThrustDirection:
    """Test thrust direction calculations."""

    def test_prograde(self):
        """Test prograde thrust direction."""
        position = np.array([6878.0, 0.0, 0.0])  # On x-axis
        velocity = np.array([0.0, 7.6, 0.0])  # Moving in +y

        direction = compute_thrust_direction(position, velocity, "prograde")

        # Should be aligned with velocity
        np.testing.assert_array_almost_equal(direction, [0.0, 1.0, 0.0])

    def test_retrograde(self):
        """Test retrograde thrust direction."""
        position = np.array([6878.0, 0.0, 0.0])
        velocity = np.array([0.0, 7.6, 0.0])

        direction = compute_thrust_direction(position, velocity, "retrograde")

        # Should be opposite to velocity
        np.testing.assert_array_almost_equal(direction, [0.0, -1.0, 0.0])

    def test_radial_out(self):
        """Test radial-out thrust direction."""
        position = np.array([6878.0, 0.0, 0.0])
        velocity = np.array([0.0, 7.6, 0.0])

        direction = compute_thrust_direction(position, velocity, "radial_out")

        # Should be radially outward
        np.testing.assert_array_almost_equal(direction, [1.0, 0.0, 0.0])
