"""Tests for MCP visualization tools."""

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from sim_mcp.tools.viz import (
    generate_viz,
    compare_runs,
    _format_events_for_viewer,
)


class TestGenerateViz:
    """Test generate_viz tool."""

    def test_generate_viz_run_not_found(self, tmp_path):
        """Test generate_viz with non-existent run."""
        result = asyncio.run(generate_viz(
            run_id="nonexistent",
            runs_dir=tmp_path,
        ))

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_generate_viz_success(self, tmp_path):
        """Test successful visualization generation."""
        # Create run directory with required files
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()
        viz_dir = run_dir / "viz"
        viz_dir.mkdir()

        # Create summary
        summary = {
            "start_time": "2025-01-15T00:00:00Z",
            "end_time": "2025-01-16T00:00:00Z",
        }
        with open(run_dir / "summary.json", "w") as f:
            json.dump(summary, f)

        # Create events
        events = [
            {"event_type": "INFO", "timestamp": "2025-01-15T01:00:00Z", "message": "Test", "category": "test"},
        ]
        with open(run_dir / "events.json", "w") as f:
            json.dump(events, f)

        # Mock generate_czml
        with patch("sim.viz.czml_generator.generate_czml") as mock_czml:
            mock_czml.return_value = viz_dir / "scene.czml"

            with patch("sim.viz.manifest_generator.generate_viz_manifest") as mock_manifest:
                mock_manifest.return_value = MagicMock(artifacts=[])

                result = asyncio.run(generate_viz(
                    run_id="test_run",
                    runs_dir=tmp_path,
                ))

        assert result["success"] is True
        assert "czml" in result["artifacts"]
        assert "viewer_events" in result["artifacts"]

    def test_generate_viz_partial_failure(self, tmp_path):
        """Test generate_viz with partial failures."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()

        # No ephemeris or other files - CZML generation will fail

        with patch("sim.viz.czml_generator.generate_czml") as mock_czml:
            mock_czml.side_effect = FileNotFoundError("No ephemeris")

            with patch("sim.viz.manifest_generator.generate_viz_manifest") as mock_manifest:
                mock_manifest.return_value = MagicMock(artifacts=[])

                result = asyncio.run(generate_viz(
                    run_id="test_run",
                    runs_dir=tmp_path,
                ))

        # Should still succeed but with errors
        assert result["success"] is False
        assert result["errors"] is not None
        assert len(result["errors"]) > 0


class TestCompareRuns:
    """Test compare_runs tool."""

    def test_compare_runs_a_not_found(self, tmp_path):
        """Test compare_runs when run A doesn't exist."""
        run_b = tmp_path / "run_b"
        run_b.mkdir()

        result = asyncio.run(compare_runs(
            run_a_id="nonexistent",
            run_b_id="run_b",
            runs_dir=tmp_path,
        ))

        assert result["success"] is False
        assert "Run A not found" in result["error"]

    def test_compare_runs_b_not_found(self, tmp_path):
        """Test compare_runs when run B doesn't exist."""
        run_a = tmp_path / "run_a"
        run_a.mkdir()

        result = asyncio.run(compare_runs(
            run_a_id="run_a",
            run_b_id="nonexistent",
            runs_dir=tmp_path,
        ))

        assert result["success"] is False
        assert "Run B not found" in result["error"]

    def test_compare_runs_success(self, tmp_path):
        """Test successful run comparison."""
        # Create run A
        run_a = tmp_path / "run_a"
        run_a.mkdir()
        with open(run_a / "run_manifest.json", "w") as f:
            json.dump({"run_id": "run_a", "fidelity": "LOW"}, f)

        # Create run B
        run_b = tmp_path / "run_b"
        run_b.mkdir()
        with open(run_b / "run_manifest.json", "w") as f:
            json.dump({"run_id": "run_b", "fidelity": "MEDIUM"}, f)

        # Create mock diff
        mock_diff = MagicMock()
        mock_diff.run_a_fidelity = "LOW"
        mock_diff.run_b_fidelity = "MEDIUM"
        mock_diff.position_rmse_km = 1.5
        mock_diff.max_position_diff_km = 3.0
        mock_diff.altitude_rmse_km = 0.5
        mock_diff.contact_timing_rmse_s = 10.0
        mock_diff.soc_rmse = 0.02
        mock_diff.storage_rmse_gb = 0.5
        mock_diff.comparable = True
        mock_diff.warnings = []
        mock_diff.to_dict.return_value = {"runs": {}}

        with patch("sim.viz.diff.compute_run_diff", return_value=mock_diff):
            with patch("sim.viz.diff.generate_compare_czml") as mock_czml:
                mock_czml.return_value = tmp_path / "compare.czml"

                result = asyncio.run(compare_runs(
                    run_a_id="run_a",
                    run_b_id="run_b",
                    runs_dir=tmp_path,
                ))

        assert result["success"] is True
        assert result["run_a"]["fidelity"] == "LOW"
        assert result["run_b"]["fidelity"] == "MEDIUM"
        assert result["position_rmse_km"] == 1.5
        assert result["comparable"] is True


class TestFormatEventsForViewer:
    """Test _format_events_for_viewer helper."""

    def test_format_events_empty(self):
        """Test formatting empty events list."""
        result = _format_events_for_viewer([])

        assert result["violations"] == []
        assert result["warnings"] == []
        assert result["info"] == []
        assert result["timeline"] == []

    def test_format_events_categorized(self):
        """Test events are categorized correctly."""
        events = [
            {"event_type": "VIOLATION", "timestamp": "2025-01-15T01:00:00Z", "message": "SOC too low", "category": "power"},
            {"event_type": "WARNING", "timestamp": "2025-01-15T02:00:00Z", "message": "High storage", "category": "storage"},
            {"event_type": "INFO", "timestamp": "2025-01-15T03:00:00Z", "message": "Mode changed", "category": "mode"},
        ]

        result = _format_events_for_viewer(events)

        assert len(result["violations"]) == 1
        assert len(result["warnings"]) == 1
        assert len(result["info"]) == 1
        assert len(result["timeline"]) == 3

    def test_format_events_timeline_sorted(self):
        """Test timeline is sorted by timestamp."""
        events = [
            {"event_type": "INFO", "timestamp": "2025-01-15T03:00:00Z", "message": "Third"},
            {"event_type": "INFO", "timestamp": "2025-01-15T01:00:00Z", "message": "First"},
            {"event_type": "INFO", "timestamp": "2025-01-15T02:00:00Z", "message": "Second"},
        ]

        result = _format_events_for_viewer(events)

        assert result["timeline"][0]["message"] == "First"
        assert result["timeline"][1]["message"] == "Second"
        assert result["timeline"][2]["message"] == "Third"

    def test_format_events_preserves_details(self):
        """Test that event details are preserved."""
        events = [
            {
                "event_type": "VIOLATION",
                "timestamp": "2025-01-15T01:00:00Z",
                "message": "SOC too low",
                "category": "power",
                "details": {"current_soc": 0.05, "threshold": 0.10},
            },
        ]

        result = _format_events_for_viewer(events)

        assert result["violations"][0]["details"]["current_soc"] == 0.05
        assert result["violations"][0]["details"]["threshold"] == 0.10
