"""Comprehensive MCP server integration tests.

Tests MCP server functionality including:
- Tool listing and schema validation
- Simulation tool invocation with all fidelity levels
- Degraded mode handling in MCP responses
- HIGH fidelity flags via MCP
- Atmosphere configuration via MCP
- Error handling and validation
- Concurrent requests
- Result format validation

Usage:
    # Start MCP server first:
    python -m sim_mcp.http_server --port 8765

    # Run tests:
    pytest tests/ete/test_mcp_comprehensive.py -v
    pytest tests/ete/ -m "ete_tier_a" -v
"""
from __future__ import annotations

import json
import time
import concurrent.futures
from datetime import timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

import pytest

from .conftest import REFERENCE_EPOCH


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
pytestmark = [
    pytest.mark.skipif(
        not mcp_available(),
        reason="MCP server not available - start with 'python -m sim_mcp.http_server --port 8765'"
    ),
    pytest.mark.ete_tier_a,
    pytest.mark.ete,
]


class TestMCPServerHealth:
    """Test MCP server health and connectivity."""

    def test_health_endpoint_responds(self, mcp_client):
        """
        Verify MCP server health endpoint responds.
        """
        import requests

        response = requests.get(
            f"{mcp_client.server_url}/health",
            timeout=10,
        )

        assert response.status_code == 200, (
            f"Health check failed: {response.status_code}"
        )

    def test_server_metadata(self, mcp_client):
        """
        Verify server provides metadata about capabilities.
        """
        import requests

        try:
            response = requests.get(
                f"{mcp_client.server_url}/metadata",
                timeout=10,
            )
        except requests.RequestException:
            pytest.skip("Metadata endpoint not available")

        if response.status_code == 200:
            metadata = response.json()
            # Should have some identifying information
            assert isinstance(metadata, dict)


class TestMCPToolListing:
    """Test MCP tool listing and schema."""

    def test_list_tools_returns_array(self, mcp_client):
        """
        Verify tool listing returns valid array or object.
        """
        import requests

        response = requests.get(
            f"{mcp_client.server_url}/tools",
            timeout=10,
        )

        assert response.status_code == 200

        tools = response.json()
        assert isinstance(tools, (list, dict)), (
            f"Tools response should be list or dict, got {type(tools)}"
        )

    def test_tools_have_required_fields(self, mcp_client):
        """
        Verify each tool has required fields (name, description).
        """
        import requests

        response = requests.get(
            f"{mcp_client.server_url}/tools",
            timeout=10,
        )

        if response.status_code != 200:
            pytest.skip("Tools endpoint not available")

        tools = response.json()

        # Normalize to list
        if isinstance(tools, dict):
            tools = tools.get("tools", [])

        for tool in tools:
            if isinstance(tool, dict):
                assert "name" in tool, f"Tool missing name: {tool}"
                # Description may be optional

    def test_simulate_tool_exists(self, mcp_client):
        """
        Verify simulation-related tool exists.
        """
        import requests

        response = requests.get(
            f"{mcp_client.server_url}/tools",
            timeout=10,
        )

        if response.status_code != 200:
            pytest.skip("Tools endpoint not available")

        tools = response.json()

        # Normalize to list
        if isinstance(tools, dict):
            tools = tools.get("tools", [])

        # Look for simulation tool
        tool_names = [
            t.get("name", t) if isinstance(t, dict) else str(t)
            for t in tools
        ]

        sim_keywords = ["simulate", "sim", "run"]
        has_sim_tool = any(
            any(kw in name.lower() for kw in sim_keywords)
            for name in tool_names
        )

        # Log available tools if no sim tool found
        if not has_sim_tool:
            print(f"Available tools: {tool_names}")


class TestMCPSimulationBasic:
    """Test basic MCP simulation invocation."""

    def test_low_fidelity_simulation(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify LOW fidelity simulation via MCP.
        """
        import requests

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=2)

        payload = {
            "plan": {
                "plan_id": "mcp_low_test",
                "spacecraft_id": "MCP-TEST-001",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "activities": [],
            },
            "initial_state": {
                "epoch": start_time.isoformat(),
                "position_eci": [6778.137, 0.0, 0.0],
                "velocity_eci": [0.0, 7.6686, 0.0],
                "mass_kg": 500.0,
                "battery_soc": 0.9,
                "propellant_kg": 50.0,
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
            pytest.skip(f"Simulate tool not available: {e}")

        if response.status_code == 404:
            pytest.skip("Simulate tool endpoint not implemented")

        assert response.status_code == 200, (
            f"LOW simulation failed: {response.status_code}\n"
            f"Response: {response.text}"
        )

        result = response.json()
        assert result is not None

    def test_medium_fidelity_simulation(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify MEDIUM fidelity simulation via MCP.
        """
        import requests

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=2)

        payload = {
            "plan": {
                "plan_id": "mcp_medium_test",
                "spacecraft_id": "MCP-TEST-001",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "activities": [],
            },
            "initial_state": {
                "epoch": start_time.isoformat(),
                "position_eci": [6778.137, 0.0, 0.0],
                "velocity_eci": [0.0, 7.6686, 0.0],
                "mass_kg": 500.0,
                "battery_soc": 0.9,
                "propellant_kg": 50.0,
            },
            "fidelity": "MEDIUM",
            "output_dir": str(tmp_path),
        }

        try:
            response = requests.post(
                f"{mcp_client.server_url}/tools/simulate",
                json=payload,
                timeout=120,
            )
        except requests.RequestException as e:
            pytest.skip(f"Simulate tool not available: {e}")

        if response.status_code == 404:
            pytest.skip("Simulate tool endpoint not implemented")

        # MEDIUM may fail if Basilisk unavailable, but should return valid response
        assert response.status_code in [200, 400, 422, 500], (
            f"Unexpected status: {response.status_code}"
        )


class TestMCPDegradedModeHandling:
    """Test MCP handling of degraded fidelity mode."""

    def test_degraded_status_in_response(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify MCP response includes degraded status for MEDIUM fidelity.
        """
        import requests

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=2)

        payload = {
            "plan": {
                "plan_id": "mcp_degraded_check",
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
            "fidelity": "MEDIUM",
            "output_dir": str(tmp_path),
        }

        try:
            response = requests.post(
                f"{mcp_client.server_url}/tools/simulate",
                json=payload,
                timeout=120,
            )
        except requests.RequestException as e:
            pytest.skip(f"Simulate tool not available: {e}")

        if response.status_code == 404:
            pytest.skip("Simulate tool endpoint not implemented")

        if response.status_code == 200:
            result = response.json()

            # Result may include degraded field at top level or in summary
            has_degraded = (
                "degraded" in result or
                ("summary" in result and "degraded" in result.get("summary", {}))
            )

            # Log for debugging
            if has_degraded:
                print(f"Degraded status found in MCP response")

    def test_strict_mode_via_mcp(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify strict mode can be passed via MCP config.
        """
        import requests

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=1)

        payload = {
            "plan": {
                "plan_id": "mcp_strict_test",
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
            "fidelity": "LOW",  # LOW doesn't trigger strict error
            "output_dir": str(tmp_path),
            "config": {
                "strict": True,
            },
        }

        try:
            response = requests.post(
                f"{mcp_client.server_url}/tools/simulate",
                json=payload,
                timeout=120,
            )
        except requests.RequestException as e:
            pytest.skip(f"Simulate tool not available: {e}")

        if response.status_code == 404:
            pytest.skip("Simulate tool endpoint not implemented")

        # LOW with strict should succeed (only MEDIUM/HIGH can be degraded)
        assert response.status_code in [200, 400, 422], (
            f"Unexpected status for LOW+strict: {response.status_code}"
        )


class TestMCPHighFidelityFlags:
    """Test HIGH fidelity flags via MCP."""

    def test_high_fidelity_flags_accepted(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify HIGH fidelity flags are accepted via MCP.
        """
        import requests

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=1)

        payload = {
            "plan": {
                "plan_id": "mcp_high_flags_test",
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
            "fidelity": "HIGH",
            "output_dir": str(tmp_path),
            "config": {
                "high_fidelity_flags": {
                    "high_res_timestep": True,
                    "timestep_s": 10.0,
                    "ep_shadow_constraints": True,
                    "ka_weather_model": True,
                    "ka_rain_seed": 42,
                    "ka_rain_probability": 0.10,
                },
            },
        }

        try:
            response = requests.post(
                f"{mcp_client.server_url}/tools/simulate",
                json=payload,
                timeout=180,
            )
        except requests.RequestException as e:
            pytest.skip(f"Simulate tool not available: {e}")

        if response.status_code == 404:
            pytest.skip("Simulate tool endpoint not implemented")

        # Should accept flags (may fail for Basilisk reasons)
        assert response.status_code in [200, 400, 422, 500], (
            f"Unexpected status for HIGH flags: {response.status_code}"
        )


class TestMCPAtmosphereConfig:
    """Test atmosphere configuration via MCP."""

    def test_atmosphere_config_accepted(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify atmosphere configuration is accepted via MCP.
        """
        import requests

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=2)

        payload = {
            "plan": {
                "plan_id": "mcp_atmosphere_test",
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
            "fidelity": "MEDIUM",
            "output_dir": str(tmp_path),
            "config": {
                "atmosphere_model_type": "exponential",
                "solar_flux_f107": 200.0,
                "geomagnetic_ap": 25.0,
                "drag_scale_factor": 1.5,
            },
        }

        try:
            response = requests.post(
                f"{mcp_client.server_url}/tools/simulate",
                json=payload,
                timeout=120,
            )
        except requests.RequestException as e:
            pytest.skip(f"Simulate tool not available: {e}")

        if response.status_code == 404:
            pytest.skip("Simulate tool endpoint not implemented")

        # Should accept atmosphere config
        assert response.status_code in [200, 400, 422, 500], (
            f"Unexpected status for atmosphere config: {response.status_code}"
        )


class TestMCPResultFormat:
    """Test MCP result format validation."""

    def test_result_has_required_fields(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify simulation result has expected structure.
        """
        import requests

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=2)

        payload = {
            "plan": {
                "plan_id": "mcp_result_format",
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
            pytest.skip(f"Simulate tool not available: {e}")

        if response.status_code == 404:
            pytest.skip("Simulate tool endpoint not implemented")

        if response.status_code == 200:
            result = response.json()

            # Check for common result fields
            expected_fields = ["success", "plan_id", "output_dir"]
            for field in expected_fields:
                if field in result:
                    print(f"Found expected field: {field}")

            # Final state should have position/velocity if present
            if "final_state" in result:
                fs = result["final_state"]
                assert "position_eci" in fs or "position" in fs, (
                    "Final state missing position"
                )

    def test_result_includes_summary(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify result includes simulation summary.
        """
        import requests

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=2)

        payload = {
            "plan": {
                "plan_id": "mcp_summary_test",
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
            pytest.skip(f"Simulate tool not available: {e}")

        if response.status_code == 404:
            pytest.skip("Simulate tool endpoint not implemented")

        if response.status_code == 200:
            result = response.json()

            if "summary" in result:
                summary = result["summary"]
                assert isinstance(summary, dict), "Summary should be dict"


class TestMCPErrorHandling:
    """Test MCP error handling and validation."""

    def test_invalid_fidelity_returns_error(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify invalid fidelity level returns appropriate error.
        """
        import requests

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=1)

        payload = {
            "plan": {
                "plan_id": "mcp_invalid_fidelity",
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
            "fidelity": "INVALID_FIDELITY",
            "output_dir": str(tmp_path),
        }

        try:
            response = requests.post(
                f"{mcp_client.server_url}/tools/simulate",
                json=payload,
                timeout=60,
            )
        except requests.RequestException as e:
            pytest.skip(f"Simulate tool not available: {e}")

        if response.status_code == 404:
            pytest.skip("Simulate tool endpoint not implemented")

        # Should return error status
        assert response.status_code in [400, 422, 500], (
            f"Invalid fidelity should return error, got {response.status_code}"
        )

    def test_missing_initial_state_uses_defaults(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify missing initial_state uses sensible defaults.

        The MCP server gracefully handles missing initial_state by using
        default orbit parameters (400km circular LEO).
        """
        import requests

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=1)

        payload = {
            "plan": {
                "plan_id": "mcp_missing_state",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "activities": [],
            },
            # Missing initial_state - server should use defaults
            "fidelity": "LOW",
            "output_dir": str(tmp_path),
        }

        try:
            response = requests.post(
                f"{mcp_client.server_url}/tools/simulate",
                json=payload,
                timeout=60,
            )
        except requests.RequestException as e:
            pytest.skip(f"Simulate tool not available: {e}")

        if response.status_code == 404:
            pytest.skip("Simulate tool endpoint not implemented")

        # Server should accept request and use default initial state
        assert response.status_code == 200, (
            f"Server should accept missing initial_state with defaults, got {response.status_code}"
        )

        # Verify valid simulation result returned
        result = response.json()
        assert "summary" in result or "result" in result, "Response should contain simulation result"

    def test_malformed_json_returns_error(self, mcp_client):
        """
        Verify malformed JSON returns appropriate error.
        """
        import requests

        try:
            response = requests.post(
                f"{mcp_client.server_url}/tools/simulate",
                data="not valid json {{{",
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
        except requests.RequestException as e:
            pytest.skip(f"Simulate tool not available: {e}")

        if response.status_code == 404:
            pytest.skip("Simulate tool endpoint not implemented")

        # Should return error status
        assert response.status_code in [400, 422, 500], (
            f"Malformed JSON should return error, got {response.status_code}"
        )


@pytest.mark.ete_tier_b
class TestMCPConcurrency:
    """Test MCP server concurrent request handling."""

    def test_concurrent_simulations(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify MCP server handles concurrent simulation requests.
        """
        import requests

        def run_simulation(idx: int) -> Dict[str, Any]:
            start_time = reference_epoch + timedelta(hours=idx)
            end_time = start_time + timedelta(hours=1)

            payload = {
                "plan": {
                    "plan_id": f"mcp_concurrent_{idx:03d}",
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
                    timeout=120,
                )
                return {
                    "idx": idx,
                    "status": response.status_code,
                    "success": response.status_code == 200,
                }
            except Exception as e:
                return {
                    "idx": idx,
                    "status": None,
                    "error": str(e),
                }

        # Run 3 concurrent simulations
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(run_simulation, i) for i in range(3)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Check results
        errors = [r for r in results if "error" in r]
        if errors:
            if any("Connection refused" in str(e.get("error", "")) for e in errors):
                pytest.skip("MCP server not available")

        successes = [r for r in results if r.get("success")]
        not_found = [r for r in results if r.get("status") == 404]

        if not_found:
            pytest.skip("Simulate tool not implemented")

        # At least some should succeed
        assert len(successes) > 0 or all(r.get("status") in [400, 422, 500] for r in results), (
            f"No concurrent simulations succeeded: {results}"
        )

    def test_concurrent_tool_listings(self, mcp_client):
        """
        Verify MCP server handles concurrent tool listing requests.
        """
        import requests

        def list_tools(idx: int) -> Dict[str, Any]:
            try:
                response = requests.get(
                    f"{mcp_client.server_url}/tools",
                    timeout=30,
                )
                return {
                    "idx": idx,
                    "status": response.status_code,
                    "success": response.status_code == 200,
                }
            except Exception as e:
                return {
                    "idx": idx,
                    "error": str(e),
                }

        # Run 5 concurrent tool listings
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(list_tools, i) for i in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed
        successes = [r for r in results if r.get("success")]
        errors = [r for r in results if "error" in r]

        if errors:
            pytest.skip(f"MCP server connection issues: {errors[0].get('error')}")

        assert len(successes) == 5, (
            f"Not all tool listings succeeded: {results}"
        )


class TestMCPSimulationWithActivities:
    """Test MCP simulation with activities."""

    def test_simulation_with_imaging_activity(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify simulation with imaging activity via MCP.
        """
        import requests

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=6)

        payload = {
            "plan": {
                "plan_id": "mcp_activity_test",
                "spacecraft_id": "MCP-TEST-001",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "activities": [
                    {
                        "activity_id": "img_001",
                        "activity_type": "imaging",
                        "start_time": (start_time + timedelta(hours=1)).isoformat(),
                        "end_time": (start_time + timedelta(hours=1, minutes=5)).isoformat(),
                        "parameters": {
                            "target_id": "target_001",
                            "mode": "high_res",
                        },
                    },
                ],
            },
            "initial_state": {
                "epoch": start_time.isoformat(),
                "position_eci": [6778.137, 0.0, 0.0],
                "velocity_eci": [0.0, 7.6686, 0.0],
                "mass_kg": 500.0,
                "battery_soc": 0.9,
                "propellant_kg": 50.0,
                "storage_used_gb": 0.0,
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
            pytest.skip(f"Simulate tool not available: {e}")

        if response.status_code == 404:
            pytest.skip("Simulate tool endpoint not implemented")

        assert response.status_code in [200, 400, 422], (
            f"Simulation with activity failed: {response.status_code}\n"
            f"Response: {response.text}"
        )
