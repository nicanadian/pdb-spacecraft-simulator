"""Tests for MCP simulation tools."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sim_mcp.tools.simulation import (
    run_simulation,
    get_run_status,
    get_run_results,
    list_runs,
)


class TestRunSimulation:
    """Test run_simulation tool."""

    def test_run_simulation_file_not_found(self, tmp_path):
        """Test run_simulation with non-existent plan file."""
        result = asyncio.run(run_simulation(
            plan_path=Path("/nonexistent/plan.json"),
            runs_dir=tmp_path,
        ))

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_run_simulation_invalid_plan(self, tmp_path):
        """Test run_simulation with invalid plan file."""
        # Create invalid plan file
        plan_file = tmp_path / "invalid_plan.json"
        plan_file.write_text("not valid json")

        result = asyncio.run(run_simulation(
            plan_path=plan_file,
            runs_dir=tmp_path / "runs",
        ))

        assert result["success"] is False
        assert "Failed to load" in result["error"]


class TestGetRunStatus:
    """Test get_run_status tool."""

    def test_get_run_status_not_found(self, tmp_path):
        """Test get_run_status with non-existent run."""
        result = asyncio.run(get_run_status(
            run_id="nonexistent",
            runs_dir=tmp_path,
        ))

        assert result["found"] is False
        assert "not found" in result["error"]

    def test_get_run_status_with_manifest(self, tmp_path):
        """Test get_run_status with valid run."""
        # Create run directory with manifest
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()

        manifest = {
            "run_id": "test_run",
            "status": "complete",
            "fidelity": "LOW",
            "created_at": "2025-01-15T00:00:00Z",
            "has_violations": False,
        }
        with open(run_dir / "run_manifest.json", "w") as f:
            json.dump(manifest, f)

        result = asyncio.run(get_run_status(
            run_id="test_run",
            runs_dir=tmp_path,
        ))

        assert result["found"] is True
        assert result["status"] == "complete"
        assert result["fidelity"] == "LOW"
        assert result["has_violations"] is False

    def test_get_run_status_incomplete(self, tmp_path):
        """Test get_run_status with incomplete run (no manifest)."""
        # Create run directory without manifest
        run_dir = tmp_path / "incomplete_run"
        run_dir.mkdir()

        result = asyncio.run(get_run_status(
            run_id="incomplete_run",
            runs_dir=tmp_path,
        ))

        assert result["found"] is True
        assert result["status"] == "incomplete"


class TestGetRunResults:
    """Test get_run_results tool."""

    def test_get_run_results_not_found(self, tmp_path):
        """Test get_run_results with non-existent run."""
        result = asyncio.run(get_run_results(
            run_id="nonexistent",
            runs_dir=tmp_path,
        ))

        assert result["found"] is False

    def test_get_run_results_with_artifacts(self, tmp_path):
        """Test get_run_results with various artifacts."""
        # Create run directory with artifacts
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()
        viz_dir = run_dir / "viz"
        viz_dir.mkdir()

        # Create manifest
        manifest = {"run_id": "test_run", "fidelity": "LOW"}
        with open(run_dir / "run_manifest.json", "w") as f:
            json.dump(manifest, f)

        # Create summary
        summary = {"activities": {"count": 5}, "events": {"violations": 0}}
        with open(run_dir / "summary.json", "w") as f:
            json.dump(summary, f)

        # Create events
        events = [{"event_type": "INFO", "message": "Test event"}]
        with open(run_dir / "events.json", "w") as f:
            json.dump(events, f)

        # Create viz artifact
        with open(viz_dir / "scene.czml", "w") as f:
            json.dump([], f)

        result = asyncio.run(get_run_results(
            run_id="test_run",
            runs_dir=tmp_path,
        ))

        assert result["found"] is True
        assert result["manifest"]["run_id"] == "test_run"
        assert result["summary"]["activities"]["count"] == 5
        assert len(result["events"]) == 1
        assert "viz/scene.czml" in result["artifacts"]


class TestListRuns:
    """Test list_runs tool."""

    def test_list_runs_empty_directory(self, tmp_path):
        """Test list_runs with empty runs directory."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()

        result = asyncio.run(list_runs(runs_dir=runs_dir))

        assert result["runs"] == []
        assert result["total"] == 0

    def test_list_runs_nonexistent_directory(self, tmp_path):
        """Test list_runs with non-existent directory."""
        result = asyncio.run(list_runs(runs_dir=tmp_path / "nonexistent"))

        assert result["runs"] == []
        assert result["total"] == 0

    def test_list_runs_with_manifests(self, tmp_path):
        """Test list_runs with multiple runs."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()

        # Create multiple runs
        for i in range(3):
            run_dir = runs_dir / f"run_{i:03d}"
            run_dir.mkdir()

            manifest = {
                "run_id": f"run_{i:03d}",
                "status": "complete",
                "fidelity": "LOW" if i % 2 == 0 else "MEDIUM",
                "created_at": f"2025-01-{15+i}T00:00:00Z",
            }
            with open(run_dir / "run_manifest.json", "w") as f:
                json.dump(manifest, f)

        result = asyncio.run(list_runs(runs_dir=runs_dir))

        assert result["total"] == 3
        assert len(result["runs"]) == 3

    def test_list_runs_respects_limit(self, tmp_path):
        """Test list_runs respects limit parameter."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()

        # Create 5 runs
        for i in range(5):
            run_dir = runs_dir / f"run_{i:03d}"
            run_dir.mkdir()

        result = asyncio.run(list_runs(runs_dir=runs_dir, limit=2))

        assert len(result["runs"]) == 2
        assert result["limit"] == 2
