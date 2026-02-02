"""ETE GMAT comparison tests - validate simulator against GMAT truth.

Tests position and velocity accuracy against GMAT reference data.
Run on every PR as part of Tier A.

Usage:
    pytest tests/ete/test_gmat_comparison.py -v
    pytest tests/ete/ -m "ete_tier_a" -v
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import pytest

from .fixtures.data import get_tier_a_case_ids, get_tier_b_case_ids


pytestmark = [
    pytest.mark.ete_tier_a,
    pytest.mark.ete,
]


# Tier A cases for accuracy testing
TIER_A_CASES = get_tier_a_case_ids()

# Subset for quick testing
QUICK_TEST_CASES = ["R01", "R05", "R09"]


class TestPositionAccuracy:
    """Test position accuracy against GMAT truth."""

    @pytest.mark.parametrize("case_id", QUICK_TEST_CASES)
    def test_position_rms_within_tolerance(
        self, case_id: str, scenario_runner, tolerance_config
    ):
        """
        Position RMS error within tolerance vs GMAT truth.

        Args:
            case_id: GMAT case identifier
            scenario_runner: Scenario runner fixture
            tolerance_config: Tolerance configuration fixture
        """
        # Run scenario with truth comparison
        result = scenario_runner.run_scenario(
            case_id=case_id,
            compare_truth=True,
        )

        # Check if comparison was performed
        if result.comparison is None:
            pytest.skip(f"No GMAT truth data available for {case_id}")

        # Get tolerance for this case
        tolerance_km = tolerance_config.get_tolerance("position_rms_km", case_id)

        # Check position RMS
        if "position_rms_km" in result.comparison.metrics:
            position_rms = result.comparison.metrics["position_rms_km"]
            assert position_rms < tolerance_km, (
                f"Position RMS {position_rms:.3f} km exceeds "
                f"tolerance {tolerance_km:.3f} km for {case_id}"
            )

    @pytest.mark.parametrize("case_id", QUICK_TEST_CASES)
    def test_position_max_within_tolerance(
        self, case_id: str, scenario_runner, tolerance_config
    ):
        """
        Maximum position error within tolerance vs GMAT truth.

        Args:
            case_id: GMAT case identifier
        """
        result = scenario_runner.run_scenario(
            case_id=case_id,
            compare_truth=True,
        )

        if result.comparison is None:
            pytest.skip(f"No GMAT truth data available for {case_id}")

        tolerance_km = tolerance_config.get_tolerance("position_max_km", case_id)

        if "position_max_km" in result.comparison.metrics:
            position_max = result.comparison.metrics["position_max_km"]
            assert position_max < tolerance_km, (
                f"Position max {position_max:.3f} km exceeds "
                f"tolerance {tolerance_km:.3f} km for {case_id}"
            )


class TestVelocityAccuracy:
    """Test velocity accuracy against GMAT truth."""

    @pytest.mark.parametrize("case_id", QUICK_TEST_CASES)
    def test_velocity_rms_within_tolerance(
        self, case_id: str, scenario_runner, tolerance_config
    ):
        """
        Velocity RMS error within tolerance vs GMAT truth.

        Args:
            case_id: GMAT case identifier
        """
        result = scenario_runner.run_scenario(
            case_id=case_id,
            compare_truth=True,
        )

        if result.comparison is None:
            pytest.skip(f"No GMAT truth data available for {case_id}")

        tolerance_m_s = tolerance_config.get_tolerance("velocity_rms_m_s", case_id)

        if "velocity_rms_m_s" in result.comparison.metrics:
            velocity_rms = result.comparison.metrics["velocity_rms_m_s"]
            assert velocity_rms < tolerance_m_s, (
                f"Velocity RMS {velocity_rms:.3f} m/s exceeds "
                f"tolerance {tolerance_m_s:.3f} m/s for {case_id}"
            )

    @pytest.mark.parametrize("case_id", QUICK_TEST_CASES)
    def test_velocity_max_within_tolerance(
        self, case_id: str, scenario_runner, tolerance_config
    ):
        """
        Maximum velocity error within tolerance vs GMAT truth.

        Args:
            case_id: GMAT case identifier
        """
        result = scenario_runner.run_scenario(
            case_id=case_id,
            compare_truth=True,
        )

        if result.comparison is None:
            pytest.skip(f"No GMAT truth data available for {case_id}")

        tolerance_m_s = tolerance_config.get_tolerance("velocity_max_m_s", case_id)

        if "velocity_max_m_s" in result.comparison.metrics:
            velocity_max = result.comparison.metrics["velocity_max_m_s"]
            assert velocity_max < tolerance_m_s, (
                f"Velocity max {velocity_max:.3f} m/s exceeds "
                f"tolerance {tolerance_m_s:.3f} m/s for {case_id}"
            )


class TestOrbitalElementAccuracy:
    """Test orbital element accuracy against GMAT truth."""

    @pytest.mark.parametrize("case_id", QUICK_TEST_CASES)
    def test_sma_drift_reasonable(
        self, case_id: str, scenario_runner, tolerance_config
    ):
        """
        Semi-major axis drift is within expected range.

        Args:
            case_id: GMAT case identifier
        """
        result = scenario_runner.run_scenario(
            case_id=case_id,
            compare_truth=True,
        )

        if result.comparison is None:
            pytest.skip(f"No GMAT truth data available for {case_id}")

        # SMA drift should be within comparison metrics
        if "sma_drift_km" in result.derived_metrics:
            sma_drift = result.derived_metrics["sma_drift_km"]

            # For cases without thrust, SMA drift should be primarily from drag
            # Allow generous tolerance for ETE tests
            max_drift_km = 50.0  # Very generous for ETE

            assert abs(sma_drift) < max_drift_km, (
                f"SMA drift {sma_drift:.3f} km exceeds max {max_drift_km:.3f} km"
            )

    @pytest.mark.parametrize("case_id", QUICK_TEST_CASES)
    def test_altitude_accuracy(
        self, case_id: str, scenario_runner, tolerance_config
    ):
        """
        Altitude accuracy within tolerance.

        Args:
            case_id: GMAT case identifier
        """
        result = scenario_runner.run_scenario(
            case_id=case_id,
            compare_truth=True,
        )

        if result.comparison is None:
            pytest.skip(f"No GMAT truth data available for {case_id}")

        tolerance_km = tolerance_config.get_tolerance("altitude_rms_km", case_id)

        if "altitude_rms_km" in result.comparison.metrics:
            altitude_rms = result.comparison.metrics["altitude_rms_km"]
            assert altitude_rms < tolerance_km, (
                f"Altitude RMS {altitude_rms:.3f} km exceeds "
                f"tolerance {tolerance_km:.3f} km for {case_id}"
            )


class TestMassAccuracy:
    """Test mass/propellant accuracy for maneuver cases."""

    @pytest.mark.parametrize("case_id", ["R01", "R04"])  # Maneuver cases
    def test_propellant_consumption_reasonable(
        self, case_id: str, scenario_runner
    ):
        """
        Propellant consumption is within reasonable bounds.

        Args:
            case_id: GMAT case identifier
        """
        result = scenario_runner.run_scenario(
            case_id=case_id,
            compare_truth=True,
        )

        if result.derived_metrics and "propellant_used_kg" in result.derived_metrics:
            propellant_used = result.derived_metrics["propellant_used_kg"]

            # Propellant used should be non-negative
            assert propellant_used >= 0, "Propellant used cannot be negative"

            # For short duration cases, should not exceed initial mass
            if result.initial_state:
                assert propellant_used < result.initial_state.mass_kg, (
                    "Propellant used exceeds initial spacecraft mass"
                )


@pytest.mark.ete_tier_b
class TestTierBComparison:
    """Extended GMAT comparison tests for Tier B (nightly)."""

    TIER_B_CASES = get_tier_b_case_ids()

    @pytest.mark.parametrize("case_id", TIER_B_CASES[:2])  # Subset for testing
    def test_tier_b_position_accuracy(
        self, case_id: str, scenario_runner, tolerance_config
    ):
        """
        Position accuracy for Tier B cases.

        Args:
            case_id: GMAT case identifier
        """
        result = scenario_runner.run_scenario(
            case_id=case_id,
            compare_truth=True,
        )

        if result.comparison is None:
            pytest.skip(f"No GMAT truth data available for {case_id}")

        tolerance_km = tolerance_config.get_tolerance("position_rms_km", case_id)

        if "position_rms_km" in result.comparison.metrics:
            position_rms = result.comparison.metrics["position_rms_km"]
            assert position_rms < tolerance_km

    @pytest.mark.parametrize("case_id", ["N01"])  # LEO drag case
    def test_drag_modeling_accuracy(
        self, case_id: str, scenario_runner, tolerance_config
    ):
        """
        Drag modeling accuracy for VLEO/LEO cases.

        Args:
            case_id: GMAT case identifier
        """
        result = scenario_runner.run_scenario(
            case_id=case_id,
            compare_truth=True,
        )

        if result.comparison is None:
            pytest.skip(f"No GMAT truth data available for {case_id}")

        # Check altitude accuracy (sensitive to drag modeling)
        tolerance_km = tolerance_config.get_tolerance("altitude_rms_km", case_id)

        if "altitude_rms_km" in result.comparison.metrics:
            altitude_rms = result.comparison.metrics["altitude_rms_km"]
            assert altitude_rms < tolerance_km


class TestComparisonReporting:
    """Test comparison result reporting."""

    def test_comparison_result_structure(self, scenario_runner):
        """Test comparison result has expected structure."""
        result = scenario_runner.run_scenario(
            case_id="R01",
            compare_truth=True,
        )

        # ScenarioResult should have expected attributes
        assert hasattr(result, "case_id")
        assert hasattr(result, "success")
        assert hasattr(result, "initial_state")
        assert hasattr(result, "final_state")
        assert hasattr(result, "derived_metrics")
        assert hasattr(result, "comparison")

    def test_comparison_metrics_available(self, scenario_runner):
        """Test comparison metrics are computed."""
        result = scenario_runner.run_scenario(
            case_id="R01",
            compare_truth=True,
        )

        if result.comparison:
            # Comparison should have metrics dict
            assert hasattr(result.comparison, "metrics")
            assert isinstance(result.comparison.metrics, dict)

            # Should have passed attribute
            assert hasattr(result.comparison, "passed")

    def test_summary_generation(self, scenario_runner):
        """Test summary can be generated for results."""
        result = scenario_runner.run_scenario(
            case_id="R01",
            compare_truth=False,
        )

        # Summary should be available
        summary = result.summary
        assert isinstance(summary, str)
        assert result.case_id in summary
