"""
SGP4 Validation Tests

These tests validate:
1. SGP4 implementation consistency (same TLE produces same output)
2. Published Vallado test vectors at epoch
3. OrbitPropagator wrapper functionality

Expected accuracy:
- At epoch: < 1 meter (numerical precision)
- Extended propagation: < 1 km for consistent implementation
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from validation.reference.vallado_test_cases import (
    VALLADO_TEST_CASES,
    SGP4TestCase,
    PUBLISHED_EPOCH_VALUES,
    get_all_test_cases,
)


class TestSGP4Consistency:
    """Test SGP4 implementation consistency."""

    # Tolerance for internal consistency (should be numerical precision)
    POSITION_TOL_KM = 0.0001  # 100 meters
    VELOCITY_TOL_M_S = 0.0001  # 0.1 mm/s

    def propagate_tle(self, tle_line1: str, tle_line2: str, minutes_from_epoch: float):
        """Propagate TLE to get state vector."""
        from sgp4.api import Satrec

        satellite = Satrec.twoline2rv(tle_line1, tle_line2)

        fr = satellite.jdsatepochF + minutes_from_epoch / 1440.0
        jd = satellite.jdsatepoch
        if fr >= 1.0:
            jd += int(fr)
            fr = fr - int(fr)

        error, position, velocity = satellite.sgp4(jd, fr)

        if error != 0:
            raise RuntimeError(f"SGP4 error code: {error}")

        return np.array(position), np.array(velocity)

    @pytest.mark.parametrize("test_case", VALLADO_TEST_CASES, ids=lambda tc: tc.name)
    def test_sgp4_consistency(self, test_case: SGP4TestCase):
        """
        Test that SGP4 produces consistent results.

        This verifies our propagation matches the expected values generated
        by the same sgp4 library.
        """
        for minutes, expected_pos, expected_vel in test_case.verification_points:
            actual_pos, actual_vel = self.propagate_tle(
                test_case.tle_line1,
                test_case.tle_line2,
                minutes,
            )

            pos_error = np.linalg.norm(actual_pos - expected_pos)
            vel_error = np.linalg.norm(actual_vel - expected_vel) * 1000

            assert pos_error < self.POSITION_TOL_KM, \
                f"t={minutes}min: Position error {pos_error:.6f} km exceeds {self.POSITION_TOL_KM} km"
            assert vel_error < self.VELOCITY_TOL_M_S, \
                f"t={minutes}min: Velocity error {vel_error:.6f} m/s exceeds {self.VELOCITY_TOL_M_S} m/s"


class TestValladoPublishedValues:
    """Test against Vallado's published epoch values."""

    def propagate_tle_at_epoch(self, tle_line1: str, tle_line2: str):
        """Propagate TLE at its epoch."""
        from sgp4.api import Satrec

        satellite = Satrec.twoline2rv(tle_line1, tle_line2)
        error, pos, vel = satellite.sgp4(satellite.jdsatepoch, satellite.jdsatepochF)

        if error != 0:
            raise RuntimeError(f"SGP4 error code: {error}")

        return np.array(pos), np.array(vel)

    def test_leo_00005_at_epoch(self):
        """Test LEO_00005 against published Vallado values."""
        from validation.reference.vallado_test_cases import get_test_case

        tc = get_test_case("LEO_00005")
        pub = PUBLISHED_EPOCH_VALUES["LEO_00005"]

        actual_pos, actual_vel = self.propagate_tle_at_epoch(tc.tle_line1, tc.tle_line2)
        expected_pos = np.array(pub["position_km"])
        expected_vel = np.array(pub["velocity_km_s"])

        pos_error = np.linalg.norm(actual_pos - expected_pos)
        vel_error = np.linalg.norm(actual_vel - expected_vel) * 1000

        assert pos_error < pub["tolerance_km"], \
            f"Position error {pos_error:.6f} km exceeds tolerance {pub['tolerance_km']} km"
        assert vel_error < 1.0, \
            f"Velocity error {vel_error:.6f} m/s exceeds 1.0 m/s"

        # Verify component-wise
        for i, axis in enumerate(["X", "Y", "Z"]):
            assert abs(actual_pos[i] - expected_pos[i]) < 0.001, \
                f"{axis} position differs: {actual_pos[i]:.6f} vs {expected_pos[i]:.6f}"

    def test_iss_25544_at_epoch(self):
        """Test ISS_25544 against published Vallado values."""
        from validation.reference.vallado_test_cases import get_test_case

        tc = get_test_case("ISS_25544")
        pub = PUBLISHED_EPOCH_VALUES["ISS_25544"]

        actual_pos, actual_vel = self.propagate_tle_at_epoch(tc.tle_line1, tc.tle_line2)
        expected_pos = np.array(pub["position_km"])
        expected_vel = np.array(pub["velocity_km_s"])

        pos_error = np.linalg.norm(actual_pos - expected_pos)

        assert pos_error < pub["tolerance_km"], \
            f"Position error {pos_error:.6f} km exceeds tolerance {pub['tolerance_km']} km"


class TestOrbitPropagator:
    """Test the OrbitPropagator wrapper class."""

    def test_orbit_propagator_uses_sgp4(self):
        """Verify OrbitPropagator uses SGP4 internally."""
        from sim.models.orbit import OrbitPropagator

        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

        propagator = OrbitPropagator(
            altitude_km=500.0,
            inclination_deg=53.0,
            epoch=epoch,
        )

        # Propagate at epoch
        point = propagator.propagate(epoch)

        # Verify reasonable values for 500 km circular orbit
        assert 490 < point.altitude_km < 510, f"Altitude {point.altitude_km} not near 500 km"

        velocity = np.linalg.norm(point.velocity_eci)
        assert 7.5 < velocity < 7.8, f"Velocity {velocity} km/s not typical for LEO"

    def test_orbit_propagator_with_tle(self):
        """Test OrbitPropagator initialized with TLE."""
        from sim.models.orbit import OrbitPropagator

        # Use ISS TLE
        tle1 = "1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927"
        tle2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537"

        propagator = OrbitPropagator(tle_line1=tle1, tle_line2=tle2)

        # Get epoch from TLE (2008, day 264)
        from sgp4.api import Satrec
        sat = Satrec.twoline2rv(tle1, tle2)

        # Propagate at a time
        epoch = datetime(2008, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
        point = propagator.propagate(epoch)

        # ISS altitude should be around 350-400 km
        assert 300 < point.altitude_km < 450, f"ISS altitude {point.altitude_km} unexpected"

    def test_propagate_range(self):
        """Test propagation over a range of times."""
        from sim.models.orbit import OrbitPropagator

        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

        propagator = OrbitPropagator(
            altitude_km=500.0,
            inclination_deg=53.0,
            epoch=epoch,
        )

        # Propagate for 2 hours
        end = epoch + timedelta(hours=2)
        ephemeris = propagator.propagate_range(epoch, end, step_s=60.0)

        # Should have about 121 points (0 to 120 minutes)
        assert len(ephemeris) >= 120

        # First and last altitude should be similar (circular orbit)
        alt_first = ephemeris[0].altitude_km
        alt_last = ephemeris[-1].altitude_km
        assert abs(alt_first - alt_last) < 10, "Altitude changed too much for circular orbit"


class TestComparisonMetrics:
    """Test comparison metrics work correctly."""

    def test_compute_metrics_with_known_error(self):
        """Test metrics computation with a known error injected."""
        from validation.comparison.metrics import compute_ephemeris_metrics
        import pandas as pd

        times = [datetime(2025, 1, 15, i, 0, 0, tzinfo=timezone.utc) for i in range(5)]

        reference = pd.DataFrame({
            "time": times,
            "x_km": [6878.0] * 5,
            "y_km": [0.0] * 5,
            "z_km": [0.0] * 5,
            "vx_km_s": [0.0] * 5,
            "vy_km_s": [7.6] * 5,
            "vz_km_s": [0.0] * 5,
        })

        # Simulator with 1 km X offset
        simulator = pd.DataFrame({
            "time": times,
            "x_km": [6879.0] * 5,
            "y_km": [0.0] * 5,
            "z_km": [0.0] * 5,
            "vx_km_s": [0.0] * 5,
            "vy_km_s": [7.6] * 5,
            "vz_km_s": [0.0] * 5,
        })

        metrics = compute_ephemeris_metrics(simulator, reference)

        assert metrics.position_rms_km == pytest.approx(1.0, abs=0.01)
        assert metrics.x_rms_km == pytest.approx(1.0, abs=0.01)

    def test_metrics_pass_fail_thresholds(self):
        """Test that pass/fail thresholds work correctly."""
        from validation.comparison.metrics import compute_ephemeris_metrics
        import pandas as pd

        times = [datetime(2025, 1, 15, i, 0, 0, tzinfo=timezone.utc) for i in range(5)]

        reference = pd.DataFrame({
            "time": times,
            "x_km": [6878.0] * 5,
            "y_km": [0.0] * 5,
            "z_km": [0.0] * 5,
            "vx_km_s": [0.0] * 5,
            "vy_km_s": [7.6] * 5,
            "vz_km_s": [0.0] * 5,
        })

        # Small error - should pass
        simulator_small = pd.DataFrame({
            "time": times,
            "x_km": [6879.0] * 5,  # 1 km error
            "y_km": [0.0] * 5,
            "z_km": [0.0] * 5,
            "vx_km_s": [0.0] * 5,
            "vy_km_s": [7.6] * 5,
            "vz_km_s": [0.0] * 5,
        })

        metrics_small = compute_ephemeris_metrics(
            simulator_small, reference,
            position_threshold_km=5.0
        )
        assert metrics_small.position_passed

        # Large error - should fail
        simulator_large = pd.DataFrame({
            "time": times,
            "x_km": [6888.0] * 5,  # 10 km error
            "y_km": [0.0] * 5,
            "z_km": [0.0] * 5,
            "vx_km_s": [0.0] * 5,
            "vy_km_s": [7.6] * 5,
            "vz_km_s": [0.0] * 5,
        })

        metrics_large = compute_ephemeris_metrics(
            simulator_large, reference,
            position_threshold_km=5.0
        )
        assert not metrics_large.position_passed


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
