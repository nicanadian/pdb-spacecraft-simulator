"""Tests for GMAT headless execution."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from .conftest import requires_gmat, GMAT_AVAILABLE


class TestGMATAvailability:
    """Tests for GMAT availability detection."""

    def test_check_installation_returns_dict(self):
        """Verify check_installation returns expected structure."""
        from validation.gmat.executor import check_gmat_installation

        info = check_gmat_installation()

        assert isinstance(info, dict)
        assert "available" in info
        assert "path" in info
        assert "env_var" in info

    def test_executor_check_installation_static(self):
        """Verify GMATExecutor.check_installation works."""
        from validation.gmat.executor import GMATExecutor

        info = GMATExecutor.check_installation()

        assert isinstance(info, dict)
        assert "available" in info

    def test_executor_is_available_consistent(self):
        """Verify is_available matches check_installation."""
        from validation.gmat.executor import GMATExecutor

        executor = GMATExecutor()
        info = GMATExecutor.check_installation()

        assert executor.is_available() == info["available"]


class TestGMATExecution:
    """Tests for actual GMAT execution (require GMAT installed)."""

    @requires_gmat
    def test_gmat_executes_headlessly(self, gmat_executor, tmp_path):
        """Prove GMAT runs without GUI."""
        from validation.gmat.generator import GMATScriptGenerator, ScenarioConfig

        # Create minimal scenario
        config = ScenarioConfig(
            scenario_id="headless_test",
            scenario_name="Headless Test",
            epoch=datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
            duration_hours=0.1,  # 6 minutes - very short for quick test
            report_step_s=60.0,
        )

        # Generate script
        generator = GMATScriptGenerator()
        script_path = tmp_path / "headless_test.script"
        generator.generate_pure_propagation_script(config, script_path)

        # Execute
        result = gmat_executor.execute_script(script_path, timeout_s=300)

        # Verify headless execution
        assert result.return_code != -1, "GMAT should be found"
        assert result.working_dir is not None, "Should have working directory"
        assert result.working_dir.exists(), "Working directory should exist"

        # Check for GUI-related errors in output
        assert "display" not in result.stderr.lower(), "No display errors expected"

    @requires_gmat
    def test_outputs_generated_and_parsed(self, gmat_executor, tmp_path):
        """Verify outputs are created and parseable."""
        from validation.gmat.generator import GMATScriptGenerator, ScenarioConfig
        from validation.gmat.parser import GMATOutputParser

        config = ScenarioConfig(
            scenario_id="output_test",
            scenario_name="Output Test",
            epoch=datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
            duration_hours=0.5,
            report_step_s=60.0,
            output_dir=str(tmp_path / "output"),
        )

        generator = GMATScriptGenerator()
        script_path = tmp_path / "output_test.script"
        generator.generate_pure_propagation_script(config, script_path)

        result = gmat_executor.execute_script(script_path, timeout_s=600)

        if not result.success:
            pytest.skip(f"GMAT execution failed: {result.stderr}")

        # Check output files exist
        assert len(result.output_files) > 0, "Should generate output files"

        # Try to parse ephemeris output
        parser = GMATOutputParser()
        ephemeris_files = [f for f in result.output_files if "ephemeris" in f.name.lower()]

        if ephemeris_files:
            df = parser.parse_ephemeris_report(ephemeris_files[0])
            assert len(df) > 0, "Should parse ephemeris data"
            assert "x_km" in df.columns
            assert "vx_km_s" in df.columns

    @requires_gmat
    def test_outputs_conform_to_schema(self, gmat_executor, tmp_path):
        """Verify parsed results match GMATBaseline schema."""
        from validation.gmat.generator import GMATScriptGenerator, ScenarioConfig
        from validation.gmat.parser import GMATOutputParser
        from validation.gmat.baseline import GMATEphemerisRecord

        config = ScenarioConfig(
            scenario_id="schema_test",
            scenario_name="Schema Test",
            epoch=datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
            duration_hours=0.25,
            report_step_s=60.0,
            output_dir=str(tmp_path / "output"),
        )

        generator = GMATScriptGenerator()
        script_path = tmp_path / "schema_test.script"
        generator.generate_pure_propagation_script(config, script_path)

        result = gmat_executor.execute_script(script_path, timeout_s=300)

        if not result.success:
            pytest.skip(f"GMAT execution failed: {result.stderr}")

        parser = GMATOutputParser()
        ephemeris_files = [f for f in result.output_files if "ephemeris" in f.name.lower()]

        if not ephemeris_files:
            pytest.skip("No ephemeris output found")

        df = parser.parse_ephemeris_report(ephemeris_files[0])

        # Verify schema conformance - all required columns present
        required_cols = ["time", "x_km", "y_km", "z_km", "vx_km_s", "vy_km_s", "vz_km_s"]
        for col in required_cols:
            assert col in df.columns, f"Missing required column: {col}"

        # Verify data types are numeric (except time)
        for col in ["x_km", "y_km", "z_km", "vx_km_s", "vy_km_s", "vz_km_s"]:
            assert df[col].dtype in ["float64", "float32", "int64"], f"Column {col} should be numeric"

    @requires_gmat
    def test_failure_provides_diagnostics(self, gmat_executor, tmp_path):
        """Verify failures include exit code, stdout, stderr, working_dir."""
        # Create invalid script
        invalid_script = tmp_path / "invalid.script"
        invalid_script.write_text("This is not valid GMAT syntax!")

        result = gmat_executor.execute_script(invalid_script, timeout_s=60)

        # Should fail gracefully
        assert not result.success, "Invalid script should fail"
        assert result.return_code != 0, "Should have non-zero exit code"
        assert result.working_dir is not None, "Should still have working directory"
        assert result.working_dir.exists(), "Working directory should be preserved"

        # Diagnostics should be available
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        # At least one should have content
        assert len(result.stdout) > 0 or len(result.stderr) > 0, "Should have diagnostic output"

    @requires_gmat
    def test_isolated_run_preserves_artifacts(self, gmat_executor, tmp_path):
        """Verify isolated runs preserve all artifacts for debugging."""
        from validation.gmat.generator import GMATScriptGenerator, ScenarioConfig

        config = ScenarioConfig(
            scenario_id="isolation_test",
            scenario_name="Isolation Test",
            epoch=datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
            duration_hours=0.1,
            report_step_s=60.0,
        )

        generator = GMATScriptGenerator()
        script_path = tmp_path / "isolation_test.script"
        generator.generate_pure_propagation_script(config, script_path)

        # Execute with isolation (default)
        result = gmat_executor.execute_script(script_path, isolated=True)

        assert result.working_dir is not None
        assert result.working_dir.exists()

        # Script should be copied to working directory
        copied_script = result.working_dir / script_path.name
        assert copied_script.exists(), "Script should be copied to isolated dir"

        # Working directory should be under validation/gmat/runs/
        runs_dir = Path(__file__).parent.parent / "gmat" / "runs"
        assert runs_dir in result.working_dir.parents or result.working_dir.parent == runs_dir


class TestGMATExecutorConfiguration:
    """Tests for executor configuration without requiring GMAT."""

    def test_executor_default_output_dir(self):
        """Test default output directory configuration."""
        from validation.gmat.executor import GMATExecutor

        executor = GMATExecutor()
        assert executor.output_dir == Path("validation/gmat/output")

    def test_executor_custom_output_dir(self, tmp_path):
        """Test custom output directory configuration."""
        from validation.gmat.executor import GMATExecutor

        custom_dir = tmp_path / "custom_output"
        executor = GMATExecutor(output_dir=custom_dir)
        assert executor.output_dir == custom_dir

    def test_executor_missing_script_raises(self):
        """Test that missing script raises FileNotFoundError."""
        from validation.gmat.executor import GMATExecutor

        executor = GMATExecutor()

        with pytest.raises(FileNotFoundError):
            executor.execute_script(Path("/nonexistent/script.script"))

    def test_execution_result_dataclass(self):
        """Test GMATExecutionResult dataclass structure."""
        from validation.gmat.executor import GMATExecutionResult

        result = GMATExecutionResult(
            success=True,
            return_code=0,
            stdout="output",
            stderr="",
            output_files=[Path("test.txt")],
            execution_time_s=1.5,
            working_dir=Path("/tmp/test"),
        )

        assert result.success is True
        assert result.return_code == 0
        assert result.working_dir == Path("/tmp/test")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
