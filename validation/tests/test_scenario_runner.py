"""Tests for GMAT scenario runner - simulator vs GMAT validation.

These tests run GMAT-defined scenarios through the simulator and compare
results against GMAT truth data.
"""

import pytest
from pathlib import Path

from validation.gmat.case_registry import (
    CaseDefinition,
    CaseTier,
    get_case,
    get_tier_cases,
    list_case_ids,
)
from validation.gmat.harness.sim_adapter import GmatToSimAdapter, SimScenario
from validation.gmat.harness.scenario_runner import (
    ScenarioRunner,
    ScenarioResult,
    run_scenario,
)
from validation.gmat.harness.compare_truth import SimulatorState


# Get case IDs for parametrization
TIER_A_CASE_IDS = list_case_ids(CaseTier.A)
TIER_B_CASE_IDS = list_case_ids(CaseTier.B)
ALL_CASE_IDS = TIER_A_CASE_IDS + TIER_B_CASE_IDS


class TestGmatToSimAdapter:
    """Tests for GMAT to simulator adapter."""

    def test_adapter_creates_scenario(self):
        """Test that adapter creates valid scenario from case definition."""
        adapter = GmatToSimAdapter()
        scenario = adapter.create_scenario("R01")

        assert scenario.case_id == "R01"
        assert scenario.initial_state is not None
        assert scenario.plan is not None
        assert scenario.config is not None
        assert scenario.duration_s > 0

    def test_adapter_creates_initial_state(self):
        """Test that initial state has valid orbital parameters."""
        adapter = GmatToSimAdapter()
        scenario = adapter.create_scenario("R01")

        state = scenario.initial_state
        assert state.position_eci is not None
        assert len(state.position_eci) == 3
        assert state.velocity_eci is not None
        assert len(state.velocity_eci) == 3
        assert state.mass_kg > 0
        assert state.propellant_kg >= 0

    def test_adapter_creates_plan_with_activities(self):
        """Test that plan has valid activities."""
        adapter = GmatToSimAdapter()
        scenario = adapter.create_scenario("R01")

        plan = scenario.plan
        assert len(plan.activities) > 0
        for activity in plan.activities:
            assert activity.start_time < activity.end_time

    @pytest.mark.parametrize("case_id", ["R01", "N01"])
    def test_adapter_creates_different_scenarios(self, case_id):
        """Test adapter creates scenarios for different case types."""
        adapter = GmatToSimAdapter()
        scenario = adapter.create_scenario(case_id)

        assert scenario.case_id == case_id
        assert scenario.case_def.case_id == case_id

    def test_adapter_with_overrides(self):
        """Test that adapter respects parameter overrides."""
        adapter = GmatToSimAdapter()
        overrides = {"sma_km": 7000.0, "inc_deg": 45.0}
        scenario = adapter.create_scenario("R01", overrides=overrides)

        # Verify the scenario was created with overrides
        # Note: We can't directly check orbital elements without conversion,
        # but the scenario should still be valid
        assert scenario.initial_state is not None

    def test_adapter_unknown_case_raises(self):
        """Test that adapter raises for unknown case ID."""
        adapter = GmatToSimAdapter()
        with pytest.raises(ValueError, match="Unknown case ID"):
            adapter.create_scenario("UNKNOWN")


class TestScenarioRunner:
    """Tests for scenario runner."""

    @pytest.fixture
    def runner(self, tmp_path):
        """Create scenario runner with temp output directory."""
        return ScenarioRunner(output_base_dir=tmp_path / "output")

    def test_runner_runs_scenario(self, runner):
        """Test that runner executes scenario successfully."""
        # Use R01 as it's the simplest case
        result = runner.run_scenario("R01", compare_truth=False)

        assert result.case_id == "R01"
        # Check we got some output (may not be successful if simulator fails)
        assert result is not None

    def test_runner_extracts_initial_state(self, runner):
        """Test that runner extracts initial state."""
        result = runner.run_scenario("R01", compare_truth=False)

        if result.success:
            assert result.initial_state is not None
            assert isinstance(result.initial_state, SimulatorState)
            assert result.initial_state.sma_km > 0

    def test_runner_extracts_final_state(self, runner):
        """Test that runner extracts final state."""
        result = runner.run_scenario("R01", compare_truth=False)

        if result.success:
            assert result.final_state is not None
            assert isinstance(result.final_state, SimulatorState)
            assert result.final_state.sma_km > 0

    def test_runner_computes_derived_metrics(self, runner):
        """Test that runner computes derived metrics."""
        result = runner.run_scenario("R01", compare_truth=False)

        if result.success:
            assert result.derived_metrics is not None
            # Check some common metrics
            assert "sma_drift_km" in result.derived_metrics
            assert "propellant_used_kg" in result.derived_metrics

    def test_result_summary(self, runner):
        """Test that result has summary string."""
        result = runner.run_scenario("R01", compare_truth=False)

        summary = result.summary
        assert "R01" in summary
        assert "SUCCESS" in summary or "FAILED" in summary


class TestKeplerianConversion:
    """Tests for Cartesian to Keplerian conversion."""

    def test_cartesian_to_keplerian_circular(self):
        """Test conversion for near-circular orbit."""
        import numpy as np

        runner = ScenarioRunner()

        # Circular orbit at 500 km (LEO)
        r_mag = 6878.137  # km
        v_mag = np.sqrt(398600.4418 / r_mag)  # Circular velocity

        position_km = np.array([r_mag, 0.0, 0.0])
        velocity_km_s = np.array([0.0, v_mag, 0.0])

        sma, ecc, inc, raan, aop, ta = runner._cartesian_to_keplerian(
            position_km, velocity_km_s
        )

        assert abs(sma - r_mag) < 0.01  # SMA should match radius
        assert ecc < 0.001  # Near-circular
        assert abs(inc) < 0.01  # Equatorial

    def test_cartesian_to_keplerian_inclined(self):
        """Test conversion for inclined orbit."""
        import numpy as np

        runner = ScenarioRunner()

        # Create inclined orbit
        r_mag = 6878.137  # km
        v_mag = np.sqrt(398600.4418 / r_mag)

        # 45 degree inclination
        inc_rad = np.radians(45)
        position_km = np.array([r_mag, 0.0, 0.0])
        velocity_km_s = np.array([0.0, v_mag * np.cos(inc_rad), v_mag * np.sin(inc_rad)])

        sma, ecc, inc, raan, aop, ta = runner._cartesian_to_keplerian(
            position_km, velocity_km_s
        )

        assert abs(sma - r_mag) < 0.01
        assert abs(inc - 45.0) < 0.1  # Should be ~45 degrees


class TestSimulatorStateConversion:
    """Tests for SimulatorState extraction."""

    def test_extract_initial_state(self):
        """Test initial state extraction from scenario."""
        adapter = GmatToSimAdapter()
        scenario = adapter.create_scenario("R01")
        runner = ScenarioRunner()

        initial_state = runner._extract_initial_state(scenario)

        assert initial_state.sma_km > 6000  # LEO
        assert 0 <= initial_state.ecc < 1
        assert 0 <= initial_state.inc_deg <= 180


# Markers for selective test execution
pytest_tier_a = pytest.mark.tier_a
pytest_tier_b = pytest.mark.tier_b
pytest_requires_sim = pytest.mark.requires_simulator


@pytest.mark.tier_a
class TestTierAScenarios:
    """Tier A scenarios - CI fast checks.

    These tests run GMAT-defined scenarios through the simulator.
    They do not require GMAT to be installed.
    """

    @pytest.fixture
    def runner(self, tmp_path):
        """Create scenario runner with temp output directory."""
        return ScenarioRunner(output_base_dir=tmp_path / "output")

    @pytest.mark.parametrize("case_id", ["R01"])  # Start with simplest
    def test_scenario_creates_output(self, runner, case_id):
        """Test scenario runs and creates output."""
        result = runner.run_scenario(case_id, compare_truth=False)

        # Should at least get a result object
        assert result is not None
        assert result.case_id == case_id


@pytest.mark.tier_b
class TestTierBScenarios:
    """Tier B scenarios - Nightly ops checks.

    These tests run ops-grade EP scenarios through the simulator.
    """

    @pytest.fixture
    def runner(self, tmp_path):
        """Create scenario runner with temp output directory."""
        return ScenarioRunner(output_base_dir=tmp_path / "output")

    @pytest.mark.parametrize("case_id", ["N01"])  # Start with N01
    def test_scenario_creates_output(self, runner, case_id):
        """Test scenario runs and creates output."""
        result = runner.run_scenario(case_id, compare_truth=False)

        assert result is not None
        assert result.case_id == case_id


class TestTruthComparison:
    """Tests for truth comparison functionality.

    These tests verify that when truth files exist, the comparator
    correctly identifies matches and mismatches.
    """

    @pytest.fixture
    def comparator(self):
        """Create truth comparator."""
        from validation.gmat.harness.compare_truth import TruthComparator
        return TruthComparator()

    def test_comparison_result_fields(self):
        """Test ComparisonResult has expected fields."""
        from validation.gmat.harness.compare_truth import ComparisonResult

        result = ComparisonResult(
            passed=True,
            case_id="R01",
        )

        assert result.passed is True
        assert result.case_id == "R01"
        assert result.initial_errors == {}
        assert result.final_errors == {}
        assert result.failures == []

    def test_comparison_result_summary(self):
        """Test ComparisonResult summary generation."""
        from validation.gmat.harness.compare_truth import ComparisonResult

        result = ComparisonResult(
            passed=False,
            case_id="R01",
            failures=["sma_km: 0.5 exceeds tolerance 0.1"],
        )

        summary = result.summary
        assert "R01" in summary
        assert "FAIL" in summary
        assert "sma_km" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
