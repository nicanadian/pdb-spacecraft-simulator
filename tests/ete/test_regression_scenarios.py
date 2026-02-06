"""
Regression scenario tests.

Runs the 3 validation scenarios (ssr_baseline, power_constrained, contact_limited)
at LOW and MEDIUM fidelity and validates invariants.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from validation.scenarios.runner import (
    load_scenario,
    run_scenario,
    scenario_to_plan,
    scenario_to_config,
    scenario_to_initial_state,
    validate_invariants,
)

logger = logging.getLogger(__name__)

# Scenario files
SCENARIO_DIR = Path("validation/scenarios")
SCENARIO_FILES = [
    SCENARIO_DIR / "ssr_baseline.yaml",
    SCENARIO_DIR / "power_constrained.yaml",
    SCENARIO_DIR / "contact_limited.yaml",
]


@pytest.fixture(params=SCENARIO_FILES, ids=[p.stem for p in SCENARIO_FILES])
def scenario_path(request):
    """Parametrize over scenario files."""
    return request.param


class TestRegressionScenarios:
    """Run each scenario at LOW fidelity and verify it completes."""

    @pytest.mark.ete
    @pytest.mark.ete_tier_a
    def test_scenario_low_fidelity(self, scenario_path, tmp_path):
        """Each scenario should complete at LOW fidelity without errors."""
        result = run_scenario(
            path=scenario_path,
            fidelity="LOW",
            output_dir=str(tmp_path / scenario_path.stem / "low"),
        )
        assert result.error is None, f"Scenario error: {result.error}"
        assert result.sim_results is not None

    @pytest.mark.ete
    @pytest.mark.ete_tier_a
    def test_scenario_medium_fidelity(self, scenario_path, tmp_path):
        """Each scenario should complete at MEDIUM fidelity without errors."""
        result = run_scenario(
            path=scenario_path,
            fidelity="MEDIUM",
            output_dir=str(tmp_path / scenario_path.stem / "medium"),
        )
        assert result.error is None, f"Scenario error: {result.error}"
        assert result.sim_results is not None


class TestInvariants:
    """Validate invariants for each scenario at LOW fidelity."""

    @pytest.mark.ete
    @pytest.mark.ete_tier_a
    def test_storage_never_negative(self, scenario_path, tmp_path):
        """Storage should never go negative in any scenario."""
        result = run_scenario(
            path=scenario_path,
            fidelity="LOW",
            output_dir=str(tmp_path / scenario_path.stem / "inv"),
        )
        assert result.sim_results is not None
        assert result.sim_results.final_state.storage_used_gb >= 0, \
            f"Storage went negative: {result.sim_results.final_state.storage_used_gb}"

    @pytest.mark.ete
    @pytest.mark.ete_tier_a
    def test_soc_in_valid_range(self, scenario_path, tmp_path):
        """SOC should be in [0, 1] in any scenario."""
        result = run_scenario(
            path=scenario_path,
            fidelity="LOW",
            output_dir=str(tmp_path / scenario_path.stem / "soc"),
        )
        assert result.sim_results is not None
        soc = result.sim_results.final_state.battery_soc
        assert 0.0 <= soc <= 1.0, f"SOC out of range: {soc}"


class TestCrossFidelityScenarios:
    """Both fidelities should pass invariants for each scenario."""

    @pytest.mark.ete
    @pytest.mark.ete_tier_a
    @pytest.mark.parametrize("fidelity", ["LOW", "MEDIUM"])
    def test_invariants_pass(self, scenario_path, fidelity, tmp_path):
        """Invariants should pass at both LOW and MEDIUM fidelity."""
        result = run_scenario(
            path=scenario_path,
            fidelity=fidelity,
            output_dir=str(tmp_path / scenario_path.stem / fidelity.lower()),
        )
        assert result.error is None, f"Scenario error at {fidelity}: {result.error}"
        assert result.sim_results is not None

        # Check basic invariants
        final = result.sim_results.final_state
        assert final.storage_used_gb >= 0, "Storage negative"
        assert 0.0 <= final.battery_soc <= 1.0, f"SOC out of range: {final.battery_soc}"
        assert final.propellant_kg >= 0, "Propellant negative"
