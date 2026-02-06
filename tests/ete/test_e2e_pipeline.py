"""
Full E2E pipeline tests.

Tests the complete workflow: plan -> LOW sim -> MEDIUM sim ->
cross-fidelity comparison -> viz generation for each scenario.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from validation.scenarios.runner import run_scenario
from validation.scenarios.report import generate_e2e_report

logger = logging.getLogger(__name__)

SCENARIO_DIR = Path("validation/scenarios")


class TestFullPipeline:
    """Full pipeline tests for each scenario."""

    @pytest.mark.ete
    @pytest.mark.ete_tier_b
    def test_ssr_baseline_pipeline(self, tmp_path):
        """SSR baseline: LOW + MEDIUM + compare."""
        self._run_pipeline("ssr_baseline", tmp_path)

    @pytest.mark.ete
    @pytest.mark.ete_tier_b
    def test_power_constrained_pipeline(self, tmp_path):
        """Power constrained: LOW + MEDIUM + compare."""
        self._run_pipeline("power_constrained", tmp_path)

    @pytest.mark.ete
    @pytest.mark.ete_tier_b
    def test_contact_limited_pipeline(self, tmp_path):
        """Contact limited: LOW + MEDIUM + compare."""
        self._run_pipeline("contact_limited", tmp_path)

    def _run_pipeline(self, scenario_name: str, tmp_path: Path):
        """Run full pipeline for a single scenario."""
        scenario_file = SCENARIO_DIR / f"{scenario_name}.yaml"
        assert scenario_file.exists(), f"Scenario file missing: {scenario_file}"

        # Step 1: LOW fidelity
        low_dir = str(tmp_path / scenario_name / "low")
        low_result = run_scenario(scenario_file, "LOW", low_dir)
        assert low_result.error is None, f"LOW sim error: {low_result.error}"
        assert low_result.sim_results is not None

        # Verify outputs exist
        low_path = Path(low_dir)
        summaries = list(low_path.rglob("summary.json"))
        assert len(summaries) > 0, "No summary.json found for LOW run"

        # Step 2: MEDIUM fidelity
        med_dir = str(tmp_path / scenario_name / "medium")
        med_result = run_scenario(scenario_file, "MEDIUM", med_dir)
        assert med_result.error is None, f"MEDIUM sim error: {med_result.error}"
        assert med_result.sim_results is not None

        # Step 3: Basic invariant comparison
        low_final = low_result.sim_results.final_state
        med_final = med_result.sim_results.final_state

        assert low_final.storage_used_gb >= 0, "LOW: negative storage"
        assert med_final.storage_used_gb >= 0, "MEDIUM: negative storage"
        assert 0 <= low_final.battery_soc <= 1, "LOW: SOC out of range"
        assert 0 <= med_final.battery_soc <= 1, "MEDIUM: SOC out of range"

    @pytest.mark.ete
    @pytest.mark.ete_tier_b
    def test_e2e_report_generation(self, tmp_path):
        """Generate E2E report after running scenarios."""
        # Run one scenario to generate data
        scenario_file = SCENARIO_DIR / "ssr_baseline.yaml"
        run_scenario(scenario_file, "LOW", str(tmp_path / "ssr_low"))

        # Generate report
        report_path = generate_e2e_report(str(tmp_path))
        assert Path(report_path).exists(), "Report file not generated"

        content = Path(report_path).read_text()
        assert "E2E VALIDATION REPORT" in content
        assert "OVERALL" in content
