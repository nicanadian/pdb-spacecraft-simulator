"""Tests for GMAT regression comparison."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from .conftest import requires_gmat, GMAT_AVAILABLE


class TestBaselineSchema:
    """Tests for baseline data structures."""

    def test_ephemeris_record_creation(self):
        """Test GMATEphemerisRecord creation and serialization."""
        from validation.gmat.baseline import GMATEphemerisRecord

        record = GMATEphemerisRecord(
            epoch_utc="2025-01-15T00:00:00+00:00",
            epoch_jd=2460690.5,
            x_km=6878.137,
            y_km=0.0,
            z_km=0.0,
            vx_km_s=0.0,
            vy_km_s=7.612,
            vz_km_s=0.0,
        )

        assert record.x_km == 6878.137
        assert record.epoch_jd == pytest.approx(2460690.5)

        # Test serialization
        d = record.to_dict()
        assert d["x_km"] == 6878.137

        # Test deserialization
        record2 = GMATEphemerisRecord.from_dict(d)
        assert record2.x_km == record.x_km

    def test_baseline_metadata_creation(self):
        """Test GMATBaselineMetadata creation."""
        from validation.gmat.baseline import GMATBaselineMetadata

        metadata = GMATBaselineMetadata(
            scenario_id="test",
            scenario_hash="abc123",
            gmat_version="R2022a",
            execution_timestamp="2025-01-15T00:00:00Z",
        )

        assert metadata.scenario_id == "test"
        assert metadata.frame == "EarthMJ2000Eq"
        assert "position" in metadata.units

    def test_baseline_creation_and_json(self, tmp_path, sample_baseline):
        """Test GMATBaseline creation and JSON serialization."""
        # Write to JSON
        json_path = tmp_path / "test_baseline.json"
        sample_baseline.to_json(json_path)

        assert json_path.exists()

        # Read back
        from validation.gmat.baseline import GMATBaseline
        loaded = GMATBaseline.from_json(json_path)

        assert loaded.metadata.scenario_id == sample_baseline.metadata.scenario_id
        assert loaded.num_points == sample_baseline.num_points
        assert loaded.schema_version == "1.0"

    def test_baseline_to_dataframe(self, sample_baseline):
        """Test conversion to pandas DataFrame."""
        df = sample_baseline.to_dataframe()

        assert len(df) == sample_baseline.num_points
        assert "time" in df.columns
        assert "x_km" in df.columns
        assert "vz_km_s" in df.columns


class TestBaselineManager:
    """Tests for baseline storage and retrieval."""

    def test_store_and_load_baseline(self, baseline_manager, sample_baseline):
        """Test storing and loading a baseline."""
        # Store
        path = baseline_manager.store_baseline("test_scenario", sample_baseline)
        assert path.exists()

        # Load
        loaded = baseline_manager.load_baseline("test_scenario")
        assert loaded.metadata.scenario_id == sample_baseline.metadata.scenario_id
        assert loaded.num_points == sample_baseline.num_points

    def test_list_baselines(self, baseline_manager, sample_baseline):
        """Test listing available baselines."""
        baseline_manager.store_baseline("scenario_a", sample_baseline)
        baseline_manager.store_baseline("scenario_b", sample_baseline)

        baselines = baseline_manager.list_baselines()

        assert len(baselines) == 2
        scenario_ids = [b["scenario_id"] for b in baselines]
        assert "scenario_a" in scenario_ids
        assert "scenario_b" in scenario_ids

    def test_version_management(self, baseline_manager, sample_baseline):
        """Test baseline versioning."""
        # Store v1
        baseline_manager.store_baseline("versioned", sample_baseline)

        # Store v2
        baseline_manager.store_baseline("versioned", sample_baseline)

        # Latest should be v2
        loaded = baseline_manager.load_baseline("versioned", "latest")
        assert loaded is not None

        # Can load specific version
        loaded_v1 = baseline_manager.load_baseline("versioned", "v1")
        assert loaded_v1 is not None

    def test_has_baseline(self, baseline_manager, sample_baseline):
        """Test baseline existence check."""
        assert not baseline_manager.has_baseline("nonexistent")

        baseline_manager.store_baseline("exists", sample_baseline)
        assert baseline_manager.has_baseline("exists")

    def test_scenario_hash(self, baseline_manager, sample_scenario_config):
        """Test scenario hash computation."""
        hash1 = baseline_manager.compute_scenario_hash(sample_scenario_config)

        # Same config should produce same hash
        hash2 = baseline_manager.compute_scenario_hash(sample_scenario_config)
        assert hash1 == hash2

        # Modified config should produce different hash
        from validation.gmat.generator import ScenarioConfig
        modified_config = ScenarioConfig(
            scenario_id="modified",
            scenario_name="Modified",
            epoch=sample_scenario_config.epoch,
            duration_hours=sample_scenario_config.duration_hours + 1,
            sma_km=sample_scenario_config.sma_km,
        )
        hash3 = baseline_manager.compute_scenario_hash(modified_config)
        assert hash1 != hash3

    def test_load_nonexistent_raises(self, baseline_manager):
        """Test that loading nonexistent baseline raises error."""
        with pytest.raises(FileNotFoundError):
            baseline_manager.load_baseline("nonexistent")


class TestToleranceConfig:
    """Tests for tolerance configuration."""

    def test_default_tolerances(self, tolerance_config):
        """Test default tolerance values."""
        assert tolerance_config.position_rms_km == 5.0
        assert tolerance_config.velocity_rms_m_s == 5.0

    def test_get_tolerance_global(self, tolerance_config):
        """Test getting global tolerance."""
        tol = tolerance_config.get_tolerance("position_rms_km")
        assert tol == 5.0

    def test_get_tolerance_with_override(self):
        """Test getting tolerance with scenario override."""
        from validation.gmat.tolerance_config import GMATToleranceConfig

        config = GMATToleranceConfig(
            position_rms_km=5.0,
            scenario_overrides={
                "strict_scenario": {"position_rms_km": 1.0}
            }
        )

        # Global
        assert config.get_tolerance("position_rms_km") == 5.0

        # Override
        assert config.get_tolerance("position_rms_km", "strict_scenario") == 1.0

        # Non-overridden scenario uses global
        assert config.get_tolerance("position_rms_km", "other_scenario") == 5.0

    def test_load_from_yaml(self, tmp_path):
        """Test loading from YAML file."""
        from validation.gmat.tolerance_config import GMATToleranceConfig

        yaml_content = """
tolerances:
  global:
    position_rms_km: 3.0
    velocity_rms_m_s: 2.0
  scenarios:
    tight:
      position_rms_km: 0.5
"""
        yaml_path = tmp_path / "test_config.yaml"
        yaml_path.write_text(yaml_content)

        config = GMATToleranceConfig.from_yaml(yaml_path)

        assert config.position_rms_km == 3.0
        assert config.velocity_rms_m_s == 2.0
        assert config.get_tolerance("position_rms_km", "tight") == 0.5


class TestRegressionComparator:
    """Tests for regression comparison logic."""

    def test_regression_with_stored_baseline(
        self,
        baseline_manager,
        sample_baseline,
        sample_ephemeris_df,
        tolerance_config,
    ):
        """Compare against pre-stored baseline (no GMAT needed)."""
        from validation.gmat.regression import GMATRegressionComparator

        # Store baseline
        baseline_manager.store_baseline("test_scenario", sample_baseline)

        # Create comparator
        comparator = GMATRegressionComparator(
            baseline_manager=baseline_manager,
            tolerance_config=tolerance_config,
        )

        # Compare identical data
        result = comparator.compare_ephemeris("test_scenario", sample_ephemeris_df)

        assert result.passed, f"Identical data should pass: {result.failures}"
        assert result.metrics["position_rms_km"] == pytest.approx(0.0, abs=1e-10)
        assert result.scenario_id == "test_scenario"
        assert result.num_points_compared > 0

    def test_regression_with_error(
        self,
        baseline_manager,
        sample_baseline,
        sample_ephemeris_df,
    ):
        """Test regression with known position error."""
        from validation.gmat.regression import GMATRegressionComparator
        from validation.gmat.tolerance_config import GMATToleranceConfig

        # Store baseline
        baseline_manager.store_baseline("error_test", sample_baseline)

        # Modify simulator data to have error
        modified_df = sample_ephemeris_df.copy()
        modified_df["x_km"] = modified_df["x_km"] + 1.0  # 1 km offset

        # Use tight tolerances to catch the error
        tight_config = GMATToleranceConfig(position_rms_km=0.5)

        comparator = GMATRegressionComparator(
            baseline_manager=baseline_manager,
            tolerance_config=tight_config,
        )

        result = comparator.compare_ephemeris("error_test", modified_df)

        assert not result.passed, "Should fail with 1 km error and 0.5 km tolerance"
        assert result.metrics["position_rms_km"] > 0.5
        assert len(result.failures) > 0

    def test_regression_no_overlap_fails(
        self,
        baseline_manager,
        sample_baseline,
        tolerance_config,
    ):
        """Test that non-overlapping time ranges fail gracefully."""
        from validation.gmat.regression import GMATRegressionComparator

        baseline_manager.store_baseline("overlap_test", sample_baseline)

        # Create simulator data with completely different time range
        different_times = [
            datetime(2025, 2, 15, 0, i, 0, tzinfo=timezone.utc)  # February, not January
            for i in range(10)
        ]
        non_overlapping_df = pd.DataFrame({
            "time": different_times,
            "x_km": [6878.0] * 10,
            "y_km": [0.0] * 10,
            "z_km": [0.0] * 10,
            "vx_km_s": [0.0] * 10,
            "vy_km_s": [7.6] * 10,
            "vz_km_s": [0.0] * 10,
        })

        comparator = GMATRegressionComparator(
            baseline_manager=baseline_manager,
            tolerance_config=tolerance_config,
        )

        result = comparator.compare_ephemeris("overlap_test", non_overlapping_df)

        assert not result.passed
        assert "No overlapping" in result.failures[0]

    def test_regression_missing_baseline(
        self,
        baseline_manager,
        sample_ephemeris_df,
        tolerance_config,
    ):
        """Test handling of missing baseline."""
        from validation.gmat.regression import GMATRegressionComparator

        comparator = GMATRegressionComparator(
            baseline_manager=baseline_manager,
            tolerance_config=tolerance_config,
        )

        with pytest.raises(FileNotFoundError):
            comparator.compare_ephemeris("nonexistent", sample_ephemeris_df)

    def test_regression_result_summary(
        self,
        baseline_manager,
        sample_baseline,
        sample_ephemeris_df,
        tolerance_config,
    ):
        """Test regression result summary generation."""
        from validation.gmat.regression import GMATRegressionComparator

        baseline_manager.store_baseline("summary_test", sample_baseline)

        comparator = GMATRegressionComparator(
            baseline_manager=baseline_manager,
            tolerance_config=tolerance_config,
        )

        result = comparator.compare_ephemeris("summary_test", sample_ephemeris_df)
        summary = result.summary

        assert "PASS" in summary or "FAIL" in summary
        assert "summary_test" in summary
        assert "position_rms_km" in summary

    def test_run_all_regressions(
        self,
        baseline_manager,
        sample_baseline,
        sample_ephemeris_df,
        tolerance_config,
    ):
        """Test running multiple regressions."""
        from validation.gmat.regression import GMATRegressionComparator

        # Store baselines for multiple scenarios
        baseline_manager.store_baseline("scenario_a", sample_baseline)
        baseline_manager.store_baseline("scenario_b", sample_baseline)

        comparator = GMATRegressionComparator(
            baseline_manager=baseline_manager,
            tolerance_config=tolerance_config,
        )

        sim_results = {
            "scenario_a": sample_ephemeris_df,
            "scenario_b": sample_ephemeris_df,
            "scenario_c": sample_ephemeris_df,  # No baseline
        }

        results = comparator.run_all_regressions(sim_results)

        assert len(results) == 3
        assert results["scenario_a"].passed
        assert results["scenario_b"].passed
        assert not results["scenario_c"].passed  # No baseline


class TestGMATRegressionWithExecution:
    """Tests that require actual GMAT execution."""

    @requires_gmat
    def test_generate_and_compare_baseline(self, gmat_executor, tmp_path):
        """Generate fresh GMAT data and compare to stored baseline."""
        from validation.gmat.generator import GMATScriptGenerator, ScenarioConfig
        from validation.gmat.parser import GMATOutputParser
        from validation.gmat.baseline_manager import GMATBaselineManager, create_baseline_from_ephemeris
        from validation.gmat.regression import GMATRegressionComparator
        from validation.gmat.tolerance_config import GMATToleranceConfig

        # Create scenario
        config = ScenarioConfig(
            scenario_id="live_regression",
            scenario_name="Live Regression Test",
            epoch=datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
            duration_hours=0.5,
            report_step_s=60.0,
            output_dir=str(tmp_path / "output"),
        )

        # Generate and execute script
        generator = GMATScriptGenerator()
        script_path = tmp_path / "live_test.script"
        generator.generate_pure_propagation_script(config, script_path)

        result = gmat_executor.execute_script(script_path, timeout_s=600)

        if not result.success:
            pytest.skip(f"GMAT execution failed: {result.stderr}")

        # Parse output
        parser = GMATOutputParser()
        ephemeris_files = [f for f in result.output_files if "ephemeris" in f.name.lower()]

        if not ephemeris_files:
            pytest.skip("No ephemeris output generated")

        ephemeris_df = parser.parse_ephemeris_report(ephemeris_files[0])

        # Create and store baseline from this execution
        baseline_manager = GMATBaselineManager(tmp_path / "baselines")
        baseline = create_baseline_from_ephemeris(
            scenario_id="live_regression",
            scenario_config=config,
            ephemeris_df=ephemeris_df,
            gmat_version=gmat_executor.check_installation().get("version"),
        )
        baseline_manager.store_baseline("live_regression", baseline)

        # Now compare the same data against itself (should pass)
        comparator = GMATRegressionComparator(
            baseline_manager=baseline_manager,
            tolerance_config=GMATToleranceConfig(),
        )

        regression_result = comparator.compare_ephemeris("live_regression", ephemeris_df)

        assert regression_result.passed, f"Self-comparison should pass: {regression_result.failures}"
        assert regression_result.metrics["position_rms_km"] < 1e-6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
