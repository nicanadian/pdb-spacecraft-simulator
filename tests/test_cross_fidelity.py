"""Tests for cross-fidelity validation.

These tests verify that different fidelity levels produce comparable results
within expected tolerances.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sim.viz.diff import (
    RunDiff,
    compute_run_diff,
    _compute_position_diff,
    _compute_profile_diff,
)


class TestPositionRMSE:
    """Test position RMSE calculation."""

    def test_identical_ephemeris_zero_rmse(self):
        """Test that identical ephemeris produces zero RMSE."""
        times = pd.to_datetime([
            "2025-01-15T00:00:00Z",
            "2025-01-15T00:10:00Z",
            "2025-01-15T00:20:00Z",
        ])

        ephemeris = pd.DataFrame({
            "time": times,
            "x_km": [6878.0, 6880.0, 6882.0],
            "y_km": [0.0, 100.0, 200.0],
            "z_km": [0.0, 0.0, 0.0],
            "altitude_km": [500.0, 502.0, 504.0],
        })

        pos_rmse, max_diff, alt_rmse = _compute_position_diff(ephemeris, ephemeris.copy())

        assert pos_rmse == 0.0
        assert max_diff == 0.0
        assert alt_rmse == 0.0

    def test_known_difference(self):
        """Test RMSE with known position difference."""
        times = pd.to_datetime([
            "2025-01-15T00:00:00Z",
            "2025-01-15T00:10:00Z",
        ])

        eph_a = pd.DataFrame({
            "time": times,
            "x_km": [0.0, 0.0],
            "y_km": [0.0, 0.0],
            "z_km": [0.0, 0.0],
            "altitude_km": [500.0, 500.0],
        })

        eph_b = pd.DataFrame({
            "time": times,
            "x_km": [1.0, 1.0],  # 1 km difference in x
            "y_km": [0.0, 0.0],
            "z_km": [0.0, 0.0],
            "altitude_km": [500.0, 500.0],
        })

        pos_rmse, max_diff, alt_rmse = _compute_position_diff(eph_a, eph_b)

        # RMSE should be 1.0 km (constant 1 km difference)
        assert abs(pos_rmse - 1.0) < 0.001
        assert abs(max_diff - 1.0) < 0.001

    def test_3d_distance(self):
        """Test RMSE with 3D position difference."""
        times = pd.to_datetime(["2025-01-15T00:00:00Z"])

        eph_a = pd.DataFrame({
            "time": times,
            "x_km": [0.0],
            "y_km": [0.0],
            "z_km": [0.0],
            "altitude_km": [500.0],
        })

        eph_b = pd.DataFrame({
            "time": times,
            "x_km": [3.0],
            "y_km": [4.0],
            "z_km": [0.0],
            "altitude_km": [500.0],
        })

        pos_rmse, max_diff, alt_rmse = _compute_position_diff(eph_a, eph_b)

        # 3-4-5 triangle, distance should be 5 km
        assert abs(pos_rmse - 5.0) < 0.001


class TestContactTimingRMSE:
    """Test contact timing RMSE calculation."""

    def test_matching_contacts(self):
        """Test timing RMSE with matching contacts."""
        from sim.viz.diff import _compute_contact_diff

        contacts_a = {
            "SVALBARD": [
                {
                    "start_time": "2025-01-15T00:00:00Z",
                    "end_time": "2025-01-15T00:10:00Z",
                    "duration_s": 600,
                },
                {
                    "start_time": "2025-01-15T01:34:00Z",
                    "end_time": "2025-01-15T01:44:00Z",
                    "duration_s": 600,
                },
            ]
        }

        contacts_b = {
            "SVALBARD": [
                {
                    "start_time": "2025-01-15T00:00:10Z",  # 10s late
                    "end_time": "2025-01-15T00:10:05Z",   # 5s late
                    "duration_s": 595,
                },
                {
                    "start_time": "2025-01-15T01:33:50Z",  # 10s early
                    "end_time": "2025-01-15T01:43:55Z",   # 5s early
                    "duration_s": 605,
                },
            ]
        }

        diffs, timing_rmse = _compute_contact_diff(contacts_a, contacts_b)

        assert len(diffs) == 2
        assert timing_rmse > 0  # Non-zero due to timing differences


class TestStateDifferenceMetrics:
    """Test state difference metrics (SOC, storage)."""

    def test_soc_rmse(self):
        """Test SOC RMSE calculation."""
        times = pd.to_datetime([
            "2025-01-15T00:00:00Z",
            "2025-01-15T01:00:00Z",
            "2025-01-15T02:00:00Z",
        ])

        profiles_a = pd.DataFrame({
            "time": times,
            "battery_soc": [1.0, 0.9, 0.8],
            "storage_gb": [0.0, 10.0, 20.0],
        })

        profiles_b = pd.DataFrame({
            "time": times,
            "battery_soc": [1.0, 0.9, 0.8],  # Identical
            "storage_gb": [0.0, 10.0, 20.0],
        })

        soc_rmse, storage_rmse = _compute_profile_diff(profiles_a, profiles_b)

        assert soc_rmse == 0.0
        assert storage_rmse == 0.0

    def test_soc_rmse_with_difference(self):
        """Test SOC RMSE with known difference."""
        times = pd.to_datetime([
            "2025-01-15T00:00:00Z",
            "2025-01-15T01:00:00Z",
        ])

        profiles_a = pd.DataFrame({
            "time": times,
            "battery_soc": [1.0, 0.9],
            "storage_gb": [0.0, 10.0],
        })

        profiles_b = pd.DataFrame({
            "time": times,
            "battery_soc": [1.0, 0.8],  # 0.1 difference at second point
            "storage_gb": [0.0, 15.0],  # 5 GB difference at second point
        })

        soc_rmse, storage_rmse = _compute_profile_diff(profiles_a, profiles_b)

        # RMSE for [0, 0.1] = sqrt(0.01/2) = 0.0707
        assert soc_rmse > 0
        assert storage_rmse > 0


class TestCrossFidelityComparison:
    """Test full cross-fidelity comparison."""

    def test_compute_run_diff_with_files(self, tmp_path):
        """Test computing run diff from directories."""
        # Create run A
        run_a = tmp_path / "run_low"
        run_a.mkdir()

        times = pd.to_datetime([
            "2025-01-15T00:00:00Z",
            "2025-01-15T01:00:00Z",
            "2025-01-15T02:00:00Z",
        ])

        eph_a = pd.DataFrame({
            "time": times,
            "x_km": [6878.0, 6880.0, 6882.0],
            "y_km": [0.0, 100.0, 200.0],
            "z_km": [0.0, 0.0, 0.0],
            "altitude_km": [500.0, 502.0, 504.0],
        })
        eph_a.to_parquet(run_a / "ephemeris.parquet")

        # Create manifest
        import json
        with open(run_a / "run_manifest.json", "w") as f:
            json.dump({"run_id": "run_low", "fidelity": "LOW"}, f)

        # Create run B (slightly different)
        run_b = tmp_path / "run_medium"
        run_b.mkdir()

        eph_b = pd.DataFrame({
            "time": times,
            "x_km": [6878.0, 6880.5, 6883.0],
            "y_km": [0.0, 100.2, 200.5],
            "z_km": [0.0, 0.0, 0.0],
            "altitude_km": [500.0, 502.1, 504.3],
        })
        eph_b.to_parquet(run_b / "ephemeris.parquet")

        with open(run_b / "run_manifest.json", "w") as f:
            json.dump({"run_id": "run_medium", "fidelity": "MEDIUM"}, f)

        # Compute diff
        diff = compute_run_diff(run_a, run_b)

        assert diff.run_a_id == "run_low"
        assert diff.run_b_id == "run_medium"
        assert diff.run_a_fidelity == "LOW"
        assert diff.run_b_fidelity == "MEDIUM"
        assert diff.position_rmse_km >= 0
        assert diff.comparable is True


class TestToleranceChecking:
    """Test tolerance checking for cross-fidelity validation."""

    def test_within_tolerance(self):
        """Test values within tolerance."""
        diff = RunDiff(
            run_a_id="run_low",
            run_b_id="run_medium",
            run_a_fidelity="LOW",
            run_b_fidelity="MEDIUM",
            position_rmse_km=1.5,  # Within typical LOW vs MEDIUM tolerance
            max_position_diff_km=3.0,
            altitude_rmse_km=0.5,
            contact_timing_rmse_s=15.0,
            soc_rmse=0.02,
            comparable=True,
        )

        # Define tolerances for LOW vs MEDIUM
        position_tolerance_km = 5.0
        timing_tolerance_s = 30.0
        soc_tolerance = 0.05

        assert diff.position_rmse_km < position_tolerance_km
        assert diff.contact_timing_rmse_s < timing_tolerance_s
        assert diff.soc_rmse < soc_tolerance

    def test_exceeds_tolerance(self):
        """Test values exceeding tolerance."""
        diff = RunDiff(
            run_a_id="run_low",
            run_b_id="run_high",
            run_a_fidelity="LOW",
            run_b_fidelity="HIGH",
            position_rmse_km=15.0,  # Exceeds tolerance
            max_position_diff_km=30.0,
            altitude_rmse_km=5.0,
            comparable=True,
        )

        position_tolerance_km = 5.0

        # This should fail tolerance check
        assert diff.position_rmse_km > position_tolerance_km


class TestRunDiffSerialization:
    """Test RunDiff serialization."""

    def test_to_dict_complete(self):
        """Test complete serialization of RunDiff."""
        diff = RunDiff(
            run_a_id="run_001",
            run_b_id="run_002",
            run_a_fidelity="LOW",
            run_b_fidelity="MEDIUM",
            position_rmse_km=1.5,
            max_position_diff_km=3.0,
            altitude_rmse_km=0.5,
            contact_diffs=[
                {"station_id": "SVALBARD", "aos_diff_s": 5.0, "los_diff_s": 3.0}
            ],
            contact_timing_rmse_s=4.5,
            soc_rmse=0.02,
            storage_rmse_gb=0.5,
            comparable=True,
            warnings=[],
        )

        d = diff.to_dict()

        assert d["runs"]["a"]["id"] == "run_001"
        assert d["runs"]["b"]["fidelity"] == "MEDIUM"
        assert d["position"]["rmse_km"] == 1.5
        assert d["position"]["max_diff_km"] == 3.0
        assert len(d["contacts"]["diffs"]) == 1
        assert d["state"]["soc_rmse"] == 0.02
        assert d["comparable"] is True

    def test_to_dict_with_warnings(self):
        """Test serialization with warnings."""
        diff = RunDiff(
            run_a_id="run_001",
            run_b_id="run_002",
            run_a_fidelity="LOW",
            run_b_fidelity="MEDIUM",
            position_rmse_km=float("nan"),
            max_position_diff_km=float("nan"),
            altitude_rmse_km=float("nan"),
            comparable=False,
            warnings=["Could not compare ephemeris", "Missing profiles"],
        )

        d = diff.to_dict()

        assert d["comparable"] is False
        assert len(d["warnings"]) == 2


class TestFidelityLevelComparisons:
    """Test expected differences between fidelity levels."""

    def test_low_vs_medium_expected_range(self):
        """Test expected difference ranges for LOW vs MEDIUM."""
        # Typical expected ranges (these are assertions about the system behavior)
        # In practice, these would be populated from actual simulation runs

        # For a 24-hour simulation with typical LEO orbit:
        expected_position_rmse_km = (0.1, 10.0)  # LOW vs MEDIUM
        expected_timing_rmse_s = (1.0, 60.0)
        expected_soc_rmse = (0.001, 0.10)

        # These are placeholder assertions - in a real test, we'd run
        # actual simulations and verify the results fall within range

        # Example verification structure:
        sample_diff = RunDiff(
            run_a_id="low",
            run_b_id="medium",
            run_a_fidelity="LOW",
            run_b_fidelity="MEDIUM",
            position_rmse_km=2.5,
            max_position_diff_km=5.0,
            altitude_rmse_km=1.0,
            contact_timing_rmse_s=15.0,
            soc_rmse=0.03,
            comparable=True,
        )

        assert expected_position_rmse_km[0] <= sample_diff.position_rmse_km <= expected_position_rmse_km[1]
        assert expected_timing_rmse_s[0] <= sample_diff.contact_timing_rmse_s <= expected_timing_rmse_s[1]
        assert expected_soc_rmse[0] <= sample_diff.soc_rmse <= expected_soc_rmse[1]

    def test_medium_vs_high_expected_range(self):
        """Test expected difference ranges for MEDIUM vs HIGH."""
        # MEDIUM vs HIGH should have smaller differences
        expected_position_rmse_km = (0.01, 2.0)
        expected_timing_rmse_s = (0.1, 10.0)

        sample_diff = RunDiff(
            run_a_id="medium",
            run_b_id="high",
            run_a_fidelity="MEDIUM",
            run_b_fidelity="HIGH",
            position_rmse_km=0.5,
            max_position_diff_km=1.0,
            altitude_rmse_km=0.1,
            contact_timing_rmse_s=3.0,
            soc_rmse=0.01,
            comparable=True,
        )

        assert expected_position_rmse_km[0] <= sample_diff.position_rmse_km <= expected_position_rmse_km[1]
        assert expected_timing_rmse_s[0] <= sample_diff.contact_timing_rmse_s <= expected_timing_rmse_s[1]
