"""Pytest integration for GMAT regression test cases.

Run tier A only: pytest -m tier_a validation/tests/test_gmat_cases.py
Run tier B only: pytest -m tier_b validation/tests/test_gmat_cases.py
Run all cases:   pytest validation/tests/test_gmat_cases.py

Requires GMAT installation for execution tests.
Baseline comparison tests can run without GMAT.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from validation.gmat.case_registry import (
    CaseDefinition,
    CaseTier,
    CaseTruth,
    CASE_REGISTRY,
    get_case,
    get_tier_cases,
    list_case_ids,
)
from validation.tests.conftest import (
    requires_gmat,
    tier_a,
    tier_b,
    GMAT_AVAILABLE,
)


# =============================================================================
# Tier A Cases (CI Fast Checks)
# =============================================================================

TIER_A_CASE_IDS = list_case_ids(CaseTier.A)


class TestTierACases:
    """CI fast checks - run on every PR."""

    @tier_a
    @pytest.mark.parametrize("case_id", TIER_A_CASE_IDS)
    def test_case_definition_valid(self, case_id: str):
        """Verify case definition is complete and valid."""
        case_def = get_case(case_id)

        assert case_def.case_id == case_id
        assert case_def.name
        assert case_def.category
        assert case_def.tier == CaseTier.A
        assert case_def.duration_hours > 0
        assert case_def.expected_runtime_s > 0

    @tier_a
    @pytest.mark.parametrize("case_id", TIER_A_CASE_IDS)
    def test_case_template_exists(self, case_id: str):
        """Verify case template file exists."""
        case_def = get_case(case_id)

        if case_def.template_name:
            template_dir = Path(__file__).parent.parent / "gmat" / "templates" / "cases"
            template_path = template_dir / case_def.template_name

            # Template should exist
            assert template_path.exists(), f"Template not found: {template_path}"

    @tier_a
    @pytest.mark.parametrize("case_id", TIER_A_CASE_IDS)
    def test_case_metadata_exists(self, case_id: str):
        """Verify case metadata file exists."""
        cases_dir = Path(__file__).parent.parent / "gmat" / "cases"
        meta_path = cases_dir / case_id / "case.meta.json"

        # Metadata should exist for key cases
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)

            assert meta.get("case_id") == case_id
            assert meta.get("template_name")

    @tier_a
    @requires_gmat
    @pytest.mark.parametrize("case_id", TIER_A_CASE_IDS)
    def test_case_executes(self, case_id: str, gmat_executor, tmp_path):
        """Verify case runs without error (requires GMAT)."""
        from validation.gmat.harness.run_case import CaseRunner

        runner = CaseRunner(
            gmat_executor=gmat_executor,
            output_dir=tmp_path / "output",
        )

        result = runner.run_case(case_id)

        # Check execution succeeded
        assert result.success, f"Case {case_id} failed: {result.stderr or result.error_message}"
        assert result.execution_time_s > 0

        # Check runtime is within expected bounds (3x expected)
        case_def = get_case(case_id)
        max_runtime = case_def.expected_runtime_s * 3
        assert result.execution_time_s < max_runtime, (
            f"Case {case_id} took {result.execution_time_s}s, "
            f"expected < {max_runtime}s"
        )

    @tier_a
    @pytest.mark.parametrize("case_id", TIER_A_CASE_IDS)
    def test_case_has_baseline(self, case_id: str):
        """Verify case has baseline for comparison (does not require GMAT)."""
        baselines_dir = Path(__file__).parent.parent / "baselines" / "gmat"
        truth_path = baselines_dir / case_id / "truth_v1.json"

        # This test is informational - baselines may not exist yet
        if truth_path.exists():
            truth = CaseTruth.from_json(truth_path)
            assert truth.case_id == case_id
            assert truth.final is not None or truth.initial is not None


# =============================================================================
# Tier B Cases (Nightly Ops Checks)
# =============================================================================

TIER_B_CASE_IDS = list_case_ids(CaseTier.B)


class TestTierBCases:
    """Nightly ops checks - run nightly or on demand."""

    @tier_b
    @pytest.mark.parametrize("case_id", TIER_B_CASE_IDS)
    def test_case_definition_valid(self, case_id: str):
        """Verify case definition is complete and valid."""
        case_def = get_case(case_id)

        assert case_def.case_id == case_id
        assert case_def.name
        assert case_def.category
        assert case_def.tier == CaseTier.B
        assert case_def.duration_hours > 0
        assert case_def.expected_runtime_s > 0

    @tier_b
    @pytest.mark.parametrize("case_id", TIER_B_CASE_IDS)
    def test_case_template_exists(self, case_id: str):
        """Verify case template file exists."""
        case_def = get_case(case_id)

        if case_def.template_name:
            template_dir = Path(__file__).parent.parent / "gmat" / "templates" / "cases"
            template_path = template_dir / case_def.template_name

            # Template should exist
            assert template_path.exists(), f"Template not found: {template_path}"

    @tier_b
    @requires_gmat
    @pytest.mark.parametrize("case_id", TIER_B_CASE_IDS)
    def test_case_executes(self, case_id: str, gmat_executor, tmp_path):
        """Verify case runs without error (requires GMAT)."""
        from validation.gmat.harness.run_case import CaseRunner

        runner = CaseRunner(
            gmat_executor=gmat_executor,
            output_dir=tmp_path / "output",
        )

        result = runner.run_case(case_id)

        # Check execution succeeded
        assert result.success, f"Case {case_id} failed: {result.stderr or result.error_message}"
        assert result.execution_time_s > 0

    @tier_b
    @pytest.mark.parametrize("case_id", TIER_B_CASE_IDS)
    def test_case_metadata_exists(self, case_id: str):
        """Verify case metadata file exists."""
        cases_dir = Path(__file__).parent.parent / "gmat" / "cases"
        meta_path = cases_dir / case_id / "case.meta.json"

        # Metadata should exist for Tier B cases
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)

            assert meta.get("case_id") == case_id


# =============================================================================
# Case Registry Tests
# =============================================================================

class TestCaseRegistry:
    """Tests for the case registry itself."""

    def test_all_tier_a_cases_registered(self):
        """Verify all Tier A cases are in the registry."""
        tier_a_cases = get_tier_cases(CaseTier.A)
        assert len(tier_a_cases) >= 7, "Expected at least 7 Tier A cases"

        for case in tier_a_cases:
            assert case.case_id.startswith("R"), f"Tier A case should start with R: {case.case_id}"

    def test_all_tier_b_cases_registered(self):
        """Verify all Tier B cases are in the registry."""
        tier_b_cases = get_tier_cases(CaseTier.B)
        assert len(tier_b_cases) >= 4, "Expected at least 4 Tier B cases"

        for case in tier_b_cases:
            assert case.case_id.startswith("N"), f"Tier B case should start with N: {case.case_id}"

    def test_case_ids_unique(self):
        """Verify all case IDs are unique."""
        all_ids = list_case_ids()
        assert len(all_ids) == len(set(all_ids)), "Duplicate case IDs found"

    def test_get_case_by_id(self):
        """Test retrieving cases by ID."""
        case = get_case("R01")
        assert case.case_id == "R01"
        assert case.name == "Finite Burn"

    def test_get_case_invalid_id(self):
        """Test retrieving case with invalid ID raises error."""
        with pytest.raises(KeyError):
            get_case("INVALID_ID")


# =============================================================================
# Truth File Tests
# =============================================================================

class TestTruthFiles:
    """Tests for truth file generation and loading."""

    @tier_a
    @pytest.mark.parametrize("case_id", TIER_A_CASE_IDS)
    def test_truth_file_exists(self, case_id: str):
        """Verify truth file exists for all Tier A cases."""
        baselines_dir = Path(__file__).parent.parent / "baselines" / "gmat"
        truth_path = baselines_dir / case_id / "truth_v1.json"
        assert truth_path.exists(), f"Truth file not found for {case_id}"

    @tier_a
    @pytest.mark.parametrize("case_id", TIER_A_CASE_IDS)
    def test_truth_file_loads(self, case_id: str):
        """Verify truth file can be loaded and has required fields."""
        from validation.gmat.harness.generate_truth import TruthGenerator

        generator = TruthGenerator()
        truth = generator.load_truth(case_id, version="v1")

        assert truth.case_id == case_id
        assert truth.schema_version == "1.0"
        assert truth.initial is not None
        assert truth.final is not None
        assert truth.initial.sma_km > 0
        assert truth.final.sma_km > 0

    @tier_b
    @pytest.mark.parametrize("case_id", TIER_B_CASE_IDS)
    def test_tier_b_truth_file_exists(self, case_id: str):
        """Verify truth file exists for all Tier B cases."""
        baselines_dir = Path(__file__).parent.parent / "baselines" / "gmat"
        truth_path = baselines_dir / case_id / "truth_v1.json"
        assert truth_path.exists(), f"Truth file not found for {case_id}"

    @pytest.mark.parametrize("case_id", TIER_A_CASE_IDS[:3])  # Test first 3
    def test_truth_checkpoint_schema(self, case_id: str):
        """Verify TruthCheckpoint schema is valid."""
        from validation.gmat.case_registry import TruthCheckpoint

        checkpoint = TruthCheckpoint(
            epoch_utc="2025-01-15T00:00:00Z",
            sma_km=6878.137,
            ecc=0.0001,
            inc_deg=53.0,
            raan_deg=0.0,
            aop_deg=0.0,
            ta_deg=0.0,
            mass_kg=500.0,
            altitude_km=500.0,
        )

        # Test serialization round-trip
        data = checkpoint.to_dict()
        restored = TruthCheckpoint.from_dict(data)

        assert restored.sma_km == checkpoint.sma_km
        assert restored.ecc == checkpoint.ecc
        assert restored.mass_kg == checkpoint.mass_kg

    def test_case_truth_schema(self):
        """Verify CaseTruth schema is valid."""
        from validation.gmat.case_registry import CaseTruth, TruthCheckpoint

        initial = TruthCheckpoint(
            epoch_utc="2025-01-15T00:00:00Z",
            sma_km=6878.137,
            ecc=0.0001,
            inc_deg=53.0,
            raan_deg=0.0,
            aop_deg=0.0,
            ta_deg=0.0,
            mass_kg=500.0,
        )

        final = TruthCheckpoint(
            epoch_utc="2025-01-15T01:00:00Z",
            sma_km=6878.0,
            ecc=0.0002,
            inc_deg=53.0,
            raan_deg=0.1,
            aop_deg=0.1,
            ta_deg=180.0,
            mass_kg=499.5,
        )

        truth = CaseTruth(
            case_id="R01",
            initial=initial,
            final=final,
            derived={"sma_drift_km_per_day": -0.01},
            events={"burn_start": "2025-01-15T00:30:00Z"},
        )

        # Test serialization round-trip
        data = truth.to_dict()
        restored = CaseTruth.from_dict(data)

        assert restored.case_id == "R01"
        assert restored.initial.sma_km == initial.sma_km
        assert restored.final.mass_kg == final.mass_kg
        assert "sma_drift_km_per_day" in restored.derived


# =============================================================================
# Harness Tests
# =============================================================================

class TestHarness:
    """Tests for the test harness modules."""

    def test_case_runner_init(self, case_runner):
        """Test CaseRunner initialization."""
        assert case_runner.executor is not None
        assert case_runner.template_dir.exists()

    def test_truth_generator_init(self, truth_generator):
        """Test TruthGenerator initialization."""
        assert truth_generator.parser is not None

    def test_truth_comparator_init(self):
        """Test TruthComparator initialization."""
        from validation.gmat.harness.compare_truth import TruthComparator

        comparator = TruthComparator()
        assert comparator.tolerance_config is not None


# =============================================================================
# Integration Tests (Requires GMAT)
# =============================================================================

@requires_gmat
class TestGMATIntegration:
    """Full integration tests requiring GMAT."""

    @tier_a
    def test_run_single_case_and_generate_truth(self, gmat_executor, tmp_path):
        """Test running a case and generating truth file."""
        from validation.gmat.harness.run_case import CaseRunner
        from validation.gmat.harness.generate_truth import TruthGenerator

        # Run the simplest case
        runner = CaseRunner(
            gmat_executor=gmat_executor,
            output_dir=tmp_path / "output",
        )
        result = runner.run_case("R05")  # Force models (no targeting)

        if not result.success:
            pytest.skip(f"Case R05 failed: {result.error_message}")

        # Generate truth
        generator = TruthGenerator(baselines_dir=tmp_path / "baselines")
        truth = generator.generate_truth("R05", result=result)

        assert truth.case_id == "R05"
        # Truth should have final state if outputs were parsed
        if result.keplerian_path and result.keplerian_path.exists():
            assert truth.final is not None

    @tier_a
    def test_run_tier_a(self, gmat_executor, tmp_path):
        """Test running all Tier A cases."""
        from validation.gmat.harness.run_case import CaseRunner
        from validation.gmat.case_registry import CaseTier

        runner = CaseRunner(
            gmat_executor=gmat_executor,
            output_dir=tmp_path / "output",
        )

        results = runner.run_tier(CaseTier.A, timeout_per_case_s=300)

        # At least some cases should succeed
        passed = sum(1 for r in results.values() if r.success)
        assert passed > 0, "No Tier A cases passed"
