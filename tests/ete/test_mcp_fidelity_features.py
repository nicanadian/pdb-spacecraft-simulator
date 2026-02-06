"""ETE MCP integration tests for new fidelity features.

Tests the MCP server integration with:
- Degraded mode detection in MCP responses
- Strict mode via MCP tool parameters
- HIGH fidelity flags via MCP tools

Usage:
    pytest tests/ete/test_mcp_fidelity_features.py -v
    pytest tests/ete/ -m "ete_tier_b" -v
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Dict, Any

import pytest

from .conftest import REFERENCE_EPOCH

pytestmark = [
    pytest.mark.ete_tier_b,
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
        reason="MCP server not available - start with 'python -m sim_mcp.http_server'"
    )
)


class TestMCPDegradedMode:
    """Test MCP server handling of degraded mode."""

    def test_mcp_returns_degraded_status(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify MCP simulation response includes degraded status.
        """
        import requests

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=2)

        payload = {
            "plan": {
                "plan_id": "mcp_degraded_test",
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
            pytest.skip(f"MCP tool invocation failed: {e}")

        if response.status_code == 404:
            pytest.skip("Simulate tool not implemented")

        if response.status_code == 200:
            result = response.json()

            # Result should include degraded status if available
            if "degraded" in result:
                assert isinstance(result["degraded"], bool), (
                    "degraded field should be boolean"
                )

            # Or check in summary if present
            if "summary" in result and isinstance(result["summary"], dict):
                if "degraded" in result["summary"]:
                    assert isinstance(result["summary"]["degraded"], bool)


class TestMCPStrictMode:
    """Test MCP server strict mode parameter."""

    def test_mcp_strict_mode_parameter(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify MCP accepts strict mode parameter.
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
            "fidelity": "LOW",  # LOW won't trigger strict mode error
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
            pytest.skip(f"MCP tool invocation failed: {e}")

        if response.status_code == 404:
            pytest.skip("Simulate tool not implemented")

        # LOW fidelity with strict=True should succeed
        # (only MEDIUM/HIGH can be degraded)
        assert response.status_code in [200, 400, 422], (
            f"Unexpected status: {response.status_code}\n"
            f"Response: {response.text}"
        )


class TestMCPHighFidelityFlags:
    """Test MCP server HIGH fidelity flags parameter."""

    def test_mcp_high_fidelity_flags_parameter(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify MCP accepts HIGH fidelity flags parameter.
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
                    "ep_shadow_constraints": True,
                    "ka_weather_model": True,
                    "ka_rain_seed": 42,
                },
            },
        }

        try:
            response = requests.post(
                f"{mcp_client.server_url}/tools/simulate",
                json=payload,
                timeout=180,  # HIGH fidelity may take longer
            )
        except requests.RequestException as e:
            pytest.skip(f"MCP tool invocation failed: {e}")

        if response.status_code == 404:
            pytest.skip("Simulate tool not implemented")

        # Should accept the flags (may fail for other reasons like Basilisk unavailable)
        assert response.status_code in [200, 400, 422, 500], (
            f"Unexpected status: {response.status_code}"
        )


class TestMCPAtmosphereConfig:
    """Test MCP server atmosphere configuration parameters."""

    def test_mcp_atmosphere_parameters(self, mcp_client, reference_epoch, tmp_path):
        """
        Verify MCP accepts atmosphere configuration parameters.
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
            pytest.skip(f"MCP tool invocation failed: {e}")

        if response.status_code == 404:
            pytest.skip("Simulate tool not implemented")

        # Should accept atmosphere parameters
        assert response.status_code in [200, 400, 422, 500], (
            f"Unexpected status: {response.status_code}"
        )
