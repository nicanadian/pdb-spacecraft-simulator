"""Tests for MCP Aerie tools."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sim_mcp.tools.aerie import (
    aerie_status,
    create_plan,
    run_scheduler,
    export_plan,
)


class TestAerieStatus:
    """Test aerie_status tool."""

    def test_aerie_status_healthy(self):
        """Test aerie_status when Aerie is healthy."""
        mock_client = MagicMock()
        mock_client.list_mission_models.return_value = [
            {"id": 1, "name": "Model A"},
            {"id": 2, "name": "Model B"},
        ]

        with patch("sim.io.aerie_client.AerieClient", return_value=mock_client):
            result = asyncio.run(aerie_status())

        assert result["healthy"] is True
        assert result["mission_models"] == 2
        assert "graphql_url" in result

    def test_aerie_status_connection_error(self):
        """Test aerie_status when connection fails."""
        from sim.io.aerie_client import AerieConnectionError

        mock_client = MagicMock()
        mock_client.list_mission_models.side_effect = AerieConnectionError("Connection refused")

        with patch("sim.io.aerie_client.AerieClient", return_value=mock_client):
            result = asyncio.run(aerie_status())

        assert result["healthy"] is False
        assert "Connection refused" in result["error"]

    def test_aerie_status_unexpected_error(self):
        """Test aerie_status with unexpected error."""
        mock_client = MagicMock()
        mock_client.list_mission_models.side_effect = RuntimeError("Unexpected")

        with patch("sim.io.aerie_client.AerieClient", return_value=mock_client):
            result = asyncio.run(aerie_status())

        assert result["healthy"] is False
        assert "Unexpected" in result["error"]


class TestCreatePlan:
    """Test create_plan tool."""

    def test_create_plan_file_not_found(self, tmp_path):
        """Test create_plan with non-existent scenario file."""
        result = asyncio.run(create_plan(
            scenario_path=Path("/nonexistent/scenario.json"),
            plan_name="Test Plan",
            model_id=1,
        ))

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_create_plan_success(self, tmp_path):
        """Test successful plan creation."""
        # Create scenario file
        scenario = {
            "start_time": "2025-01-15T00:00:00Z",
            "duration_hours": 24,
            "activities": [
                {"type": "eo_collect", "start_offset_s": 3600, "arguments": {"target_id": "T001"}},
            ],
        }
        scenario_file = tmp_path / "scenario.json"
        with open(scenario_file, "w") as f:
            json.dump(scenario, f)

        mock_client = MagicMock()
        mock_client.find_plan_by_name.return_value = None
        mock_client.create_plan.return_value = 42
        mock_client.insert_activities_batch.return_value = [100]

        with patch("sim.io.aerie_client.AerieClient", return_value=mock_client):
            result = asyncio.run(create_plan(
                scenario_path=scenario_file,
                plan_name="Test Plan",
                model_id=1,
            ))

        assert result["success"] is True
        assert result["plan_id"] == 42
        assert result["activities_created"] == 1

    def test_create_plan_already_exists(self, tmp_path):
        """Test create_plan when plan already exists."""
        scenario_file = tmp_path / "scenario.json"
        with open(scenario_file, "w") as f:
            json.dump({"start_time": "2025-01-15T00:00:00Z"}, f)

        mock_client = MagicMock()
        mock_client.find_plan_by_name.return_value = {"id": 99, "name": "Test Plan"}

        with patch("sim.io.aerie_client.AerieClient", return_value=mock_client):
            result = asyncio.run(create_plan(
                scenario_path=scenario_file,
                plan_name="Test Plan",
                model_id=1,
            ))

        assert result["success"] is False
        assert "already exists" in result["error"]
        assert result["existing_plan_id"] == 99


class TestRunScheduler:
    """Test run_scheduler tool."""

    def test_run_scheduler_plan_not_found(self):
        """Test run_scheduler when plan doesn't exist."""
        mock_client = MagicMock()
        mock_client.get_plan.return_value = None

        with patch("sim.io.aerie_client.AerieClient", return_value=mock_client):
            result = asyncio.run(run_scheduler(plan_id=999))

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_run_scheduler_success_existing_spec(self):
        """Test run_scheduler with existing specification."""
        mock_client = MagicMock()
        mock_client.get_plan.return_value = {
            "id": 42,
            "name": "Test Plan",
            "start_time": "2025-01-15T00:00:00Z",
            "duration": "24:00:00",
        }
        mock_client.get_scheduling_specification.return_value = {"id": 10}
        mock_client.run_scheduler.return_value = (5, "Started")

        with patch("sim.io.aerie_client.AerieClient", return_value=mock_client):
            result = asyncio.run(run_scheduler(plan_id=42))

        assert result["success"] is True
        assert result["specification_id"] == 10
        assert result["analysis_id"] == 5

    def test_run_scheduler_creates_spec(self):
        """Test run_scheduler creates specification if missing."""
        mock_client = MagicMock()
        mock_client.get_plan.return_value = {
            "id": 42,
            "name": "Test Plan",
            "start_time": "2025-01-15T00:00:00Z",
            "duration": "24:00:00",
            "revision": 1,
        }
        mock_client.get_scheduling_specification.return_value = None
        mock_client.create_scheduling_specification.return_value = 20
        mock_client.run_scheduler.return_value = (5, "Started")

        with patch("sim.io.aerie_client.AerieClient", return_value=mock_client):
            result = asyncio.run(run_scheduler(plan_id=42))

        assert result["success"] is True
        mock_client.create_scheduling_specification.assert_called_once()


class TestExportPlan:
    """Test export_plan tool."""

    def test_export_plan_not_found(self, tmp_path):
        """Test export_plan when plan doesn't exist."""
        mock_client = MagicMock()
        mock_client.export_plan.return_value = None

        with patch("sim.io.aerie_client.AerieClient", return_value=mock_client):
            result = asyncio.run(export_plan(
                plan_id=999,
                output_dir=tmp_path,
            ))

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_export_plan_success(self, tmp_path):
        """Test successful plan export."""
        plan_data = {
            "id": 42,
            "name": "Test_Plan",
            "activity_directives": [
                {"id": 1, "type": "eo_collect"},
                {"id": 2, "type": "eo_collect"},
                {"id": 3, "type": "downlink"},
            ],
        }

        mock_client = MagicMock()
        mock_client.export_plan.return_value = plan_data

        with patch("sim.io.aerie_client.AerieClient", return_value=mock_client):
            result = asyncio.run(export_plan(
                plan_id=42,
                output_dir=tmp_path,
            ))

        assert result["success"] is True
        assert result["plan_id"] == 42
        assert result["plan_name"] == "Test_Plan"
        assert result["activity_count"] == 3
        assert result["activity_types"]["eo_collect"] == 2
        assert result["activity_types"]["downlink"] == 1

        # Check file was created
        plan_file = tmp_path / "Test_Plan.json"
        assert plan_file.exists()
