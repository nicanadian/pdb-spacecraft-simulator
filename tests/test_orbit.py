"""Tests for orbit propagation model."""

from datetime import datetime, timezone

import numpy as np
import pytest

from sim.models.orbit import (
    EARTH_RADIUS_KM,
    MU_EARTH,
    OrbitPropagator,
    compute_lowering_delta_v,
    circular_velocity,
    generate_synthetic_tle,
    orbital_period,
)


class TestOrbitalMechanics:
    """Test basic orbital mechanics calculations."""

    def test_circular_velocity_leo(self):
        """Test circular velocity at 500 km altitude."""
        v = circular_velocity(500.0)
        # Expected: ~7.6 km/s for 500 km
        assert 7.5 < v < 7.7

    def test_circular_velocity_higher_altitude_slower(self):
        """Higher altitude should have lower velocity."""
        v_500 = circular_velocity(500.0)
        v_400 = circular_velocity(400.0)
        assert v_400 > v_500

    def test_orbital_period_leo(self):
        """Test orbital period at 500 km altitude."""
        period = orbital_period(500.0)
        # Expected: ~94 minutes for 500 km
        period_min = period / 60
        assert 90 < period_min < 100

    def test_lowering_delta_v(self):
        """Test delta-V for 500 km to 400 km lowering."""
        dv = compute_lowering_delta_v(500.0, 400.0)
        # Expected: ~56 m/s
        dv_ms = dv * 1000
        assert 50 < dv_ms < 60

    def test_lowering_delta_v_symmetric(self):
        """Delta-V magnitude should be same for raising or lowering."""
        dv_lower = compute_lowering_delta_v(500.0, 400.0)
        dv_raise = compute_lowering_delta_v(400.0, 500.0)
        assert abs(dv_lower - dv_raise) < 1e-10


class TestSyntheticTLE:
    """Test synthetic TLE generation."""

    def test_generate_tle_format(self):
        """Test TLE format is valid."""
        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        line1, line2 = generate_synthetic_tle(
            altitude_km=500.0,
            inclination_deg=53.0,
            epoch=epoch,
        )

        # Check line lengths
        assert len(line1) == 69
        assert len(line2) == 69

        # Check line numbers
        assert line1.startswith("1")
        assert line2.startswith("2")

    def test_generate_tle_propagates(self):
        """Test that generated TLE can be propagated."""
        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        line1, line2 = generate_synthetic_tle(
            altitude_km=500.0,
            inclination_deg=53.0,
            epoch=epoch,
        )

        propagator = OrbitPropagator(tle_line1=line1, tle_line2=line2)
        point = propagator.propagate(epoch)

        # Check altitude is approximately correct
        altitude = point.altitude_km
        assert 490 < altitude < 510  # Allow some tolerance


class TestOrbitPropagator:
    """Test orbit propagator."""

    @pytest.fixture
    def propagator(self):
        """Create a propagator for testing."""
        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        return OrbitPropagator(
            altitude_km=500.0,
            inclination_deg=53.0,
            epoch=epoch,
        )

    def test_propagate_single_point(self, propagator):
        """Test single point propagation."""
        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        point = propagator.propagate(epoch)

        assert point.time == epoch
        assert len(point.position_eci) == 3
        assert len(point.velocity_eci) == 3

    def test_propagate_range(self, propagator):
        """Test range propagation."""
        start = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2025, 1, 15, 1, 0, 0, tzinfo=timezone.utc)

        ephemeris = propagator.propagate_range(start, end, step_s=60.0)

        # Should have ~61 points (60 minutes + 1)
        assert 55 < len(ephemeris) < 65

        # Times should be monotonically increasing
        for i in range(1, len(ephemeris)):
            assert ephemeris[i].time > ephemeris[i - 1].time

    def test_altitude_stable(self, propagator):
        """Test that altitude stays approximately constant for short propagation."""
        start = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2025, 1, 15, 2, 0, 0, tzinfo=timezone.utc)

        ephemeris = propagator.propagate_range(start, end, step_s=60.0)

        altitudes = [p.altitude_km for p in ephemeris]
        # Altitude should stay within ~20 km of nominal
        assert all(480 < alt < 520 for alt in altitudes)

    def test_get_orbital_elements(self, propagator):
        """Test orbital elements extraction."""
        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        elements = propagator.get_orbital_elements(epoch)

        # Check inclination is approximately correct
        assert 50 < elements.inclination_deg < 56

        # Check altitude is approximately correct
        assert 490 < elements.altitude_km < 510

    def test_get_period(self, propagator):
        """Test orbital period calculation."""
        period = propagator.get_period_s()
        period_min = period / 60

        # Should be ~94 minutes for 500 km
        assert 90 < period_min < 100
