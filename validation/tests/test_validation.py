"""
Tests for the GMAT validation framework.

These tests verify:
1. Reference data loading and parsing
2. Ephemeris comparison metrics
3. Access window comparison metrics
4. End-to-end validation pipeline
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestGMATParser:
    """Tests for GMAT output parsing."""

    def test_parse_datetime_gmat_format(self):
        """Test parsing GMAT datetime format."""
        from validation.gmat.parser import GMATOutputParser

        parser = GMATOutputParser()

        # Standard GMAT format
        dt = parser.parse_datetime("15 Jan 2025 00:00:00.000")
        assert dt.year == 2025
        assert dt.month == 1
        assert dt.day == 15
        assert dt.tzinfo == timezone.utc

    def test_parse_ephemeris_report(self):
        """Test parsing ephemeris CSV file."""
        from validation.gmat.parser import GMATOutputParser

        parser = GMATOutputParser()

        # Check if reference file exists
        ref_path = Path(__file__).parent.parent / "reference" / "pure_propagation" / "ephemeris_pure_prop_12h.csv"
        if not ref_path.exists():
            pytest.skip("Reference file not found")

        # Parse as CSV (our generated format)
        df = pd.read_csv(ref_path)
        df["time"] = pd.to_datetime(df["time"], utc=True)

        assert len(df) > 0
        assert "x_km" in df.columns
        assert "vy_km_s" in df.columns
        assert "altitude_km" in df.columns

    def test_load_reference_access(self):
        """Test loading reference access windows."""
        import json

        ref_path = Path(__file__).parent.parent / "reference" / "access_windows" / "access_fairbanks_access_24h.json"
        if not ref_path.exists():
            pytest.skip("Reference file not found")

        with open(ref_path) as f:
            windows = json.load(f)

        assert isinstance(windows, list)
        if len(windows) > 0:
            assert "start_time" in windows[0]
            assert "end_time" in windows[0]


class TestEphemerisMetrics:
    """Tests for ephemeris comparison metrics."""

    def test_compute_ephemeris_metrics_identical(self):
        """Test metrics when comparing identical data."""
        from validation.comparison.metrics import compute_ephemeris_metrics

        # Create identical test data
        times = [datetime(2025, 1, 15, i, 0, 0, tzinfo=timezone.utc) for i in range(12)]

        data = {
            "time": times,
            "x_km": [6878.0 + i for i in range(12)],
            "y_km": [0.0] * 12,
            "z_km": [0.0] * 12,
            "vx_km_s": [0.0] * 12,
            "vy_km_s": [7.6] * 12,
            "vz_km_s": [0.0] * 12,
        }

        sim_df = pd.DataFrame(data)
        ref_df = pd.DataFrame(data)

        metrics = compute_ephemeris_metrics(sim_df, ref_df)

        # Identical data should have zero errors
        assert metrics.position_rms_km == pytest.approx(0.0, abs=1e-10)
        assert metrics.velocity_rms_m_s == pytest.approx(0.0, abs=1e-10)
        assert metrics.all_passed

    def test_compute_ephemeris_metrics_with_error(self):
        """Test metrics with known position error."""
        from validation.comparison.metrics import compute_ephemeris_metrics

        times = [datetime(2025, 1, 15, i, 0, 0, tzinfo=timezone.utc) for i in range(12)]

        sim_data = {
            "time": times,
            "x_km": [6878.0 + 1.0] * 12,  # 1 km offset
            "y_km": [0.0] * 12,
            "z_km": [0.0] * 12,
            "vx_km_s": [0.0] * 12,
            "vy_km_s": [7.6] * 12,
            "vz_km_s": [0.0] * 12,
        }

        ref_data = {
            "time": times,
            "x_km": [6878.0] * 12,
            "y_km": [0.0] * 12,
            "z_km": [0.0] * 12,
            "vx_km_s": [0.0] * 12,
            "vy_km_s": [7.6] * 12,
            "vz_km_s": [0.0] * 12,
        }

        sim_df = pd.DataFrame(sim_data)
        ref_df = pd.DataFrame(ref_data)

        metrics = compute_ephemeris_metrics(sim_df, ref_df)

        # Should have 1 km position error
        assert metrics.position_rms_km == pytest.approx(1.0, abs=0.01)
        assert metrics.position_max_km == pytest.approx(1.0, abs=0.01)
        assert metrics.position_passed  # < 5 km threshold

    def test_compute_ephemeris_metrics_threshold_fail(self):
        """Test that large errors fail thresholds."""
        from validation.comparison.metrics import compute_ephemeris_metrics

        times = [datetime(2025, 1, 15, i, 0, 0, tzinfo=timezone.utc) for i in range(12)]

        sim_data = {
            "time": times,
            "x_km": [6878.0 + 10.0] * 12,  # 10 km offset - should fail
            "y_km": [0.0] * 12,
            "z_km": [0.0] * 12,
            "vx_km_s": [0.0] * 12,
            "vy_km_s": [7.6] * 12,
            "vz_km_s": [0.0] * 12,
        }

        ref_data = {
            "time": times,
            "x_km": [6878.0] * 12,
            "y_km": [0.0] * 12,
            "z_km": [0.0] * 12,
            "vx_km_s": [0.0] * 12,
            "vy_km_s": [7.6] * 12,
            "vz_km_s": [0.0] * 12,
        }

        sim_df = pd.DataFrame(sim_data)
        ref_df = pd.DataFrame(ref_data)

        metrics = compute_ephemeris_metrics(sim_df, ref_df, position_threshold_km=5.0)

        assert metrics.position_rms_km == pytest.approx(10.0, abs=0.01)
        assert not metrics.position_passed
        assert not metrics.all_passed


class TestAccessMetrics:
    """Tests for access window comparison metrics."""

    def test_compute_access_metrics_identical(self):
        """Test metrics when comparing identical access windows."""
        from validation.comparison.metrics import compute_access_metrics

        windows = [
            {
                "start_time": datetime(2025, 1, 15, 6, 0, 0, tzinfo=timezone.utc),
                "end_time": datetime(2025, 1, 15, 6, 10, 0, tzinfo=timezone.utc),
            },
            {
                "start_time": datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
                "end_time": datetime(2025, 1, 15, 12, 8, 0, tzinfo=timezone.utc),
            },
        ]

        metrics = compute_access_metrics(windows, windows)

        assert metrics.aos_rms_s == pytest.approx(0.0, abs=0.1)
        assert metrics.los_rms_s == pytest.approx(0.0, abs=0.1)
        assert metrics.num_matched_windows == 2
        assert metrics.all_passed

    def test_compute_access_metrics_with_timing_error(self):
        """Test metrics with timing errors in access windows."""
        from validation.comparison.metrics import compute_access_metrics

        sim_windows = [
            {
                "start_time": datetime(2025, 1, 15, 6, 0, 30, tzinfo=timezone.utc),  # 30s late
                "end_time": datetime(2025, 1, 15, 6, 10, 0, tzinfo=timezone.utc),
            },
        ]

        ref_windows = [
            {
                "start_time": datetime(2025, 1, 15, 6, 0, 0, tzinfo=timezone.utc),
                "end_time": datetime(2025, 1, 15, 6, 10, 0, tzinfo=timezone.utc),
            },
        ]

        metrics = compute_access_metrics(sim_windows, ref_windows)

        assert metrics.aos_rms_s == pytest.approx(30.0, abs=0.1)
        assert metrics.num_matched_windows == 1
        assert metrics.timing_passed  # < 60s threshold


class TestTimeAlignment:
    """Tests for time alignment functions."""

    def test_time_align_dataframes(self):
        """Test time alignment of DataFrames."""
        from validation.comparison.metrics import time_align_dataframes

        # Create DataFrames with slightly different times
        times1 = [datetime(2025, 1, 15, 0, i, 0, tzinfo=timezone.utc) for i in range(10)]
        times2 = [datetime(2025, 1, 15, 0, i, 30, tzinfo=timezone.utc) for i in range(10)]  # 30s offset

        df1 = pd.DataFrame({
            "time": times1,
            "x_km": list(range(10)),
            "y_km": [0.0] * 10,
            "z_km": [0.0] * 10,
            "vx_km_s": [0.0] * 10,
            "vy_km_s": [0.0] * 10,
            "vz_km_s": [0.0] * 10,
        })

        df2 = pd.DataFrame({
            "time": times2,
            "x_km": list(range(10)),
            "y_km": [0.0] * 10,
            "z_km": [0.0] * 10,
            "vx_km_s": [0.0] * 10,
            "vy_km_s": [0.0] * 10,
            "vz_km_s": [0.0] * 10,
        })

        aligned1, aligned2 = time_align_dataframes(df1, df2)

        # Should have same length
        assert len(aligned1) == len(aligned2)
        assert len(aligned1) > 0


class TestValidationComparator:
    """Tests for the validation comparator."""

    def test_comparator_initialization(self):
        """Test comparator initialization."""
        from validation.comparison.comparator import ValidationComparator

        comparator = ValidationComparator()
        assert comparator.thresholds["position_rms_km"] == 5.0

    def test_comparator_custom_thresholds(self):
        """Test comparator with custom thresholds."""
        from validation.comparison.comparator import ValidationComparator

        comparator = ValidationComparator(thresholds={"position_rms_km": 10.0})
        assert comparator.thresholds["position_rms_km"] == 10.0

    @pytest.mark.skipif(
        not (Path(__file__).parent.parent / "reference" / "pure_propagation").exists(),
        reason="Reference data not generated"
    )
    def test_validate_propagation_with_reference(self):
        """Test propagation validation against reference data."""
        from validation.comparison.comparator import ValidationComparator
        from sim.core.types import InitialState
        import numpy as np

        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        initial_state = InitialState(
            epoch=epoch,
            position_eci=np.array([6878.137, 0.0, 0.0]),
            velocity_eci=np.array([0.0, 7.612, 0.0]),
        )

        comparator = ValidationComparator()
        result = comparator.validate_propagation(
            scenario_id="pure_prop_12h",
            initial_state=initial_state,
            duration_hours=12.0,
        )

        # Should return a result (pass or fail)
        assert result.scenario_id == "pure_prop_12h"
        assert result.scenario_type == "propagation"


class TestGMATScriptGenerator:
    """Tests for GMAT script generation."""

    def test_generator_initialization(self):
        """Test generator initialization."""
        from validation.gmat.generator import GMATScriptGenerator

        generator = GMATScriptGenerator()
        assert generator.template_dir.exists()

    def test_scenario_config_creation(self):
        """Test scenario configuration creation."""
        from validation.gmat.generator import ScenarioConfig

        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        config = ScenarioConfig(
            scenario_id="test",
            scenario_name="Test Scenario",
            epoch=epoch,
            duration_hours=12.0,
        )

        assert config.duration_s == 12.0 * 3600
        assert config.sma_km == 6878.137

    def test_generate_pure_propagation_script(self):
        """Test pure propagation script generation."""
        from validation.gmat.generator import GMATScriptGenerator, ScenarioConfig

        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        config = ScenarioConfig(
            scenario_id="test_prop",
            scenario_name="Test Propagation",
            epoch=epoch,
            duration_hours=1.0,
        )

        generator = GMATScriptGenerator()
        script = generator.generate_pure_propagation_script(config)

        # Script should contain key GMAT elements
        assert "Create Spacecraft" in script
        assert "Propagate" in script
        assert "Report" in script


class TestReportGeneration:
    """Tests for validation report generation."""

    def test_json_report_generation(self, tmp_path):
        """Test JSON report generation."""
        from validation.comparison.reports import ValidationReportGenerator
        from validation.comparison.comparator import ValidationResult

        result = ValidationResult(
            scenario_id="test",
            scenario_type="propagation",
            timestamp=datetime.now(timezone.utc),
            passed=True,
            metrics={"position_rms_km": 1.0},
        )

        generator = ValidationReportGenerator(output_dir=tmp_path)
        output_path = generator.generate_json_report([result], "test_report.json")

        assert output_path.exists()
        import json
        with open(output_path) as f:
            report = json.load(f)

        assert "summary" in report
        assert "results" in report
        assert report["summary"]["passed"] == 1

    def test_console_report_generation(self):
        """Test console report generation."""
        from validation.comparison.reports import ValidationReportGenerator
        from validation.comparison.comparator import ValidationResult

        result = ValidationResult(
            scenario_id="test",
            scenario_type="propagation",
            timestamp=datetime.now(timezone.utc),
            passed=True,
            metrics={"position_rms_km": 1.0},
        )

        generator = ValidationReportGenerator()
        console_output = generator.generate_console_report([result])

        assert "GMAT VALIDATION REPORT" in console_output
        assert "PASS" in console_output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
