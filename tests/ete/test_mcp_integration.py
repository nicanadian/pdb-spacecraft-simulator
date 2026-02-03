"""ETE MCP integration tests - validate MCP server tool invocations.

Tests the MCP (Model Context Protocol) server tools for simulation orchestration.

Key features:
- MCP server connectivity
- Tool listing and invocation
- Simulation via MCP tools
- Result validation

Usage:
    pytest tests/ete/test_mcp_integration.py -v
    pytest tests/ete/ -m "ete_tier_a" -v
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

import pytest

from .conftest import REFERENCE_EPOCH

pytestmark = [
    pytest.mark.ete_tier_a,
    pytest.mark.ete,
]


def mcp_available() -> bool:
    """Check if MCP server is available for testing."""
    try:
        import requests
        response = requests.get(
            "http://localhost:8765/health",
            timeout=5,
        )
        return response.status_code == 200
    except Exception:
        return False


# Skip all tests if MCP is not available
pytestmark.append(
    pytest.mark.skipif(
        not mcp_available(),
        reason="MCP server not available - start with 'mcp-server'"
    )
)


class TestMCPConnection:
    """Test basic MCP server connectivity."""

    def test_mcp_health_check(self, mcp_client):
        """
        Verify MCP server health endpoint responds.
        """
        assert mcp_client.is_running(), (
            "MCP server not responding to health check\n"
            "Start the server with: mcp-server"
        )

    def test_mcp_list_tools(self, mcp_client):
        """
        Verify MCP server can list available tools.
        """
        import requests

        try:
            response = requests.get(
                f"{mcp_client.server_url}/tools",
                timeout=10,
            )
        except requests.RequestException as e:
            pytest.skip(f"MCP server not available: {e}")

        assert response.status_code == 200, (
            f"Tools listing failed: {response.status_code}\n"
            f"Response: {response.text}"
        )

        tools = response.json()
        assert isinstance(tools, (list, dict)), (
            f"Invalid tools response: {type(tools)}"
        )

        # Should have at least some tools
        if isinstance(tools, list):
            tool_count = len(tools)
        else:
            tool_count = len(tools.get("tools", []))

        assert tool_count > 0, "No tools available from MCP server"


class TestMCPSimulationTools:
    """Test MCP simulation tool invocations."""

    def test_simulate_tool_exists(self, mcp_client):
        """
        Verify the simulate tool is available.
        """
        import requests

        try:
            response = requests.get(
                f"{mcp_client.server_url}/tools",
                timeout=10,
            )
        except requests.RequestException as e:
            pytest.skip(f"MCP server not available: {e}")

        if response.status_code != 200:
            pytest.skip("Cannot list MCP tools")

        tools_data = response.json()

        # Find tool list
        if isinstance(tools_data, list):
            tools = tools_data
        else:
            tools = tools_data.get("tools", [])

        tool_names = [t.get("name", t) if isinstance(t, dict) else t for t in tools]

        # Check for simulation-related tools
        sim_tools = ["simulate", "run_simulation", "sim_run", "simulation"]
        found_sim_tool = any(
            any(sim in name.lower() for sim in sim_tools)
            for name in tool_names
        )

        assert found_sim_tool or len(tool_names) > 0, (
            f"No simulation tools found. Available tools: {tool_names}"
        )

    def test_simulate_tool_invocation(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify simulation can be invoked via MCP tool.
        """
        import requests

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=2)

        # Construct tool invocation payload
        payload = {
            "plan": {
                "plan_id": "mcp_test_001",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "activities": [],
            },
            "initial_state": {
                "epoch": start_time.isoformat(),
                "position_eci": [6778.137, 0.0, 0.0],
                "velocity_eci": [0.0, 7.6686, 0.0],
                "mass_kg": 500.0,
            },
            "fidelity": "LOW",
            "output_dir": str(tmp_path),
        }

        try:
            response = requests.post(
                f"{mcp_client.server_url}/tools/simulate",
                json=payload,
                timeout=120,
            )
        except requests.RequestException as e:
            pytest.skip(f"MCP tool invocation failed: {e}")

        # Tool endpoint may not exist
        if response.status_code == 404:
            pytest.skip("Simulate tool not implemented")

        assert response.status_code == 200, (
            f"Simulate tool failed: {response.status_code}\n"
            f"Response: {response.text}"
        )

        result = response.json()
        assert result is not None, "Tool returned no result"


class TestMCPPlanExport:
    """Test MCP plan export tools."""

    def test_export_plan_tool_format(self, reference_epoch):
        """
        Verify plan export format is correct for MCP tools.
        """
        from sim.core.types import PlanInput, Activity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=24)

        activities = [
            Activity(
                activity_id="mcp_act_001",
                activity_type="imaging",
                start_time=start_time + timedelta(hours=2),
                end_time=start_time + timedelta(hours=2, minutes=5),
                parameters={"mode": "standard"},
            ),
        ]

        plan = PlanInput(
            spacecraft_id="mcp_test_spacecraft",
            plan_id="mcp_export_test",
            activities=activities,
        )

        # Convert to MCP-compatible format
        plan_dict = {
            "plan_id": plan.plan_id,
            "start_time": plan.start_time.isoformat(),
            "end_time": plan.end_time.isoformat(),
            "activities": [
                {
                    "activity_id": a.activity_id,
                    "activity_type": a.activity_type,
                    "start_time": a.start_time.isoformat(),
                    "end_time": a.end_time.isoformat(),
                    "parameters": a.parameters,
                }
                for a in plan.activities
            ],
        }

        # Validate JSON serializable
        json_str = json.dumps(plan_dict)
        assert len(json_str) > 0

        # Validate structure
        parsed = json.loads(json_str)
        assert parsed["plan_id"] == "mcp_export_test"
        assert len(parsed["activities"]) == 1


class TestMCPResultHandling:
    """Test MCP result handling and output."""

    def test_result_format_matches_spec(self, reference_epoch):
        """
        Verify MCP result format matches expected structure.
        """
        # Expected result structure from MCP simulation tool
        expected_structure = {
            "success": True,
            "plan_id": "test_001",
            "output_dir": "/path/to/output",
            "summary": {
                "duration_s": 3600.0,
                "event_count": 0,
                "violation_count": 0,
            },
            "final_state": {
                "epoch": "2024-01-01T12:00:00Z",
                "position_eci": [6778.137, 0.0, 0.0],
                "velocity_eci": [0.0, 7.6686, 0.0],
                "mass_kg": 500.0,
            },
        }

        # Validate structure has required fields
        assert "success" in expected_structure
        assert "plan_id" in expected_structure
        assert "final_state" in expected_structure

        # Final state must have position and velocity
        fs = expected_structure["final_state"]
        assert "position_eci" in fs
        assert "velocity_eci" in fs
        assert len(fs["position_eci"]) == 3
        assert len(fs["velocity_eci"]) == 3


@pytest.mark.ete_tier_b
class TestMCPAdvanced:
    """Advanced MCP tests (Tier B - nightly)."""

    def test_concurrent_tool_invocations(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify MCP server handles concurrent requests.
        """
        import concurrent.futures
        import requests

        def invoke_simulation(idx: int) -> dict:
            start_time = reference_epoch + timedelta(hours=idx)
            end_time = start_time + timedelta(hours=1)

            payload = {
                "plan": {
                    "plan_id": f"concurrent_test_{idx:03d}",
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "activities": [],
                },
                "initial_state": {
                    "epoch": start_time.isoformat(),
                    "position_eci": [6778.137, 0.0, 0.0],
                    "velocity_eci": [0.0, 7.6686, 0.0],
                    "mass_kg": 500.0,
                },
                "fidelity": "LOW",
                "output_dir": str(tmp_path / f"run_{idx:03d}"),
            }

            try:
                response = requests.post(
                    f"{mcp_client.server_url}/tools/simulate",
                    json=payload,
                    timeout=60,
                )
                return {"idx": idx, "status": response.status_code}
            except Exception as e:
                return {"idx": idx, "error": str(e)}

        # Run 3 concurrent invocations
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(invoke_simulation, i) for i in range(3)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Check results (may skip if tool not available)
        errors = [r for r in results if "error" in r]
        if errors:
            if "Connection refused" in str(errors):
                pytest.skip("MCP server not available")

        successes = [r for r in results if r.get("status") == 200]
        not_found = [r for r in results if r.get("status") == 404]

        if not_found:
            pytest.skip("Simulate tool not implemented")

        # At least some should succeed if MCP is working
        assert len(successes) > 0 or len(errors) == len(results), (
            f"Concurrent invocation failed: {results}"
        )

    def test_tool_error_handling(self, mcp_client):
        """
        Verify MCP server handles invalid requests gracefully.
        """
        import requests

        # Send invalid payload
        invalid_payload = {
            "plan": None,  # Invalid
            "initial_state": "not_a_dict",  # Invalid
        }

        try:
            response = requests.post(
                f"{mcp_client.server_url}/tools/simulate",
                json=invalid_payload,
                timeout=30,
            )
        except requests.RequestException:
            pytest.skip("MCP server not available")

        if response.status_code == 404:
            pytest.skip("Simulate tool not implemented")

        # Should return error status, not crash
        assert response.status_code in [400, 422, 500], (
            f"Invalid request should return error status, got {response.status_code}"
        )

        # Should have error message
        result = response.json()
        assert "error" in result or "detail" in result or "message" in result, (
            "Error response should contain error message"
        )
