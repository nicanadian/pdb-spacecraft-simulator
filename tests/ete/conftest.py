"""Pytest configuration for ETE (end-to-end) validation tests.

Provides fixtures for service orchestration, browser testing, and test data.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

import pytest

from .fixtures.services import (
    AerieServiceManager,
    ViewerServerManager,
    MCPClientManager,
    ServiceConfig,
)
from .fixtures.data import (
    ScenarioData,
    CompletedRunData,
    get_tier_a_case_ids,
    get_tier_b_case_ids,
)


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================


def pytest_configure(config):
    """Configure pytest markers for ETE tests."""
    config.addinivalue_line("markers", "ete_smoke: ETE smoke tests (<60s)")
    config.addinivalue_line("markers", "ete_tier_a: ETE Tier A tests (<300s)")
    config.addinivalue_line("markers", "ete_tier_b: ETE Tier B tests (<1800s)")
    config.addinivalue_line("markers", "ete: All ETE tests")


def pytest_collection_modifyitems(config, items):
    """Mark all tests in ete directory with ete marker."""
    for item in items:
        if "ete" in str(item.fspath):
            item.add_marker(pytest.mark.ete)


# =============================================================================
# SERVICE FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def service_config() -> ServiceConfig:
    """Get service configuration from environment or defaults."""
    return ServiceConfig(
        aerie_graphql_url=os.environ.get(
            "AERIE_GRAPHQL_URL", "http://localhost:8080/v1/graphql"
        ),
        aerie_ui_url=os.environ.get("AERIE_UI_URL", "http://localhost"),
        viewer_url=os.environ.get("VIEWER_URL", "http://localhost:3002"),
        mcp_server_url=os.environ.get("MCP_SERVER_URL", "http://localhost:8765"),
    )


@pytest.fixture(scope="session")
def aerie_services(service_config) -> Generator[AerieServiceManager, None, None]:
    """
    Start Aerie via docker-compose, wait for health.

    Session-scoped to avoid repeated start/stop overhead.
    If Aerie is already running, uses existing instance.
    """
    manager = AerieServiceManager()

    # Check if already running
    if AerieServiceManager.is_running():
        yield manager
        return

    # Try to start Aerie
    try:
        manager.start()
        yield manager
    except FileNotFoundError:
        # No docker-compose file - skip tests requiring Aerie
        pytest.skip("Aerie docker-compose file not found")
    finally:
        # Don't stop if it was already running before
        pass


@pytest.fixture(scope="session")
def viewer_server(service_config) -> Generator[ViewerServerManager, None, None]:
    """
    Start viewer dev server on configured port.

    Session-scoped to avoid repeated start/stop overhead.
    If viewer is already running, uses existing instance.
    """
    port = int(service_config.viewer_url.split(":")[-1])
    manager = ViewerServerManager(port=port)

    # Check if already running
    if ViewerServerManager.is_running(port):
        yield manager
        return

    # Try to start viewer
    try:
        manager.start()
        yield manager
    except FileNotFoundError:
        # No viewer directory
        pytest.skip("Viewer directory not found")
    finally:
        manager.stop()


@pytest.fixture(scope="session")
def mcp_client(service_config) -> Generator[MCPClientManager, None, None]:
    """
    MCP server client for tool invocations.

    Session-scoped to maintain connection across tests.
    """
    manager = MCPClientManager(server_url=service_config.mcp_server_url)

    # MCP client doesn't need to start a server - just provides client methods
    yield manager


# =============================================================================
# BROWSER FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for Playwright."""
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
        "record_video_dir": "test-results/videos/",
    }


@pytest.fixture
def viewer_page(page, service_config):
    """
    Get a configured ViewerPage instance.

    Requires playwright fixture 'page' to be available.
    """
    from .pages.viewer_page import ViewerPage

    return ViewerPage(page, base_url=service_config.viewer_url)


# =============================================================================
# URL FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def aerie_url(service_config) -> str:
    """Get Aerie UI URL."""
    return service_config.aerie_ui_url


@pytest.fixture(scope="session")
def graphql_url(service_config) -> str:
    """Get GraphQL endpoint URL."""
    return service_config.aerie_graphql_url


@pytest.fixture(scope="session")
def viewer_url(service_config) -> str:
    """Get viewer URL."""
    return service_config.viewer_url


# =============================================================================
# GMAT/VALIDATION FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def tolerance_config():
    """
    Load ETE tolerance configuration.

    Tries ETE-specific tolerances first, falls back to default validation config.
    """
    from validation.gmat.tolerance_config import GMATToleranceConfig

    # Try ETE-specific config first
    ete_config_path = Path("validation/config/ete_tolerances.yaml")
    if ete_config_path.exists():
        return GMATToleranceConfig.from_yaml(ete_config_path)

    # Fall back to default validation config
    default_config_path = Path("validation/config/validation_config.yaml")
    if default_config_path.exists():
        return GMATToleranceConfig.from_yaml(default_config_path)

    # Return defaults
    return GMATToleranceConfig(
        position_rms_km=10.0,
        velocity_rms_m_s=10.0,
        altitude_rms_km=5.0,
    )


@pytest.fixture(scope="session")
def scenario_runner():
    """
    Get scenario runner for GMAT comparison tests.

    Returns a ScenarioRunner instance configured for ETE tests.
    """
    try:
        from validation.gmat.harness.scenario_runner import ScenarioRunner

        output_dir = Path("validation/output/ete_scenarios")
        output_dir.mkdir(parents=True, exist_ok=True)

        return ScenarioRunner(output_base_dir=output_dir)
    except ImportError:
        pytest.skip("Validation module not available")


@pytest.fixture
def gmat_comparator():
    """Get GMAT truth comparator."""
    try:
        from validation.gmat.harness.compare_truth import TruthComparator

        return TruthComparator()
    except ImportError:
        pytest.skip("GMAT comparator not available")


# =============================================================================
# TEST DATA FIXTURES
# =============================================================================


@pytest.fixture
def completed_run(tmp_path) -> CompletedRunData:
    """
    Create a completed run with sample data for viewer tests.

    Creates minimal required files in a temp directory.
    """
    import json
    from datetime import datetime, timedelta, timezone

    # Create directory structure
    viz_dir = tmp_path / "viz"
    viz_dir.mkdir()

    # Create manifest
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(hours=24)

    manifest = {
        "plan_id": "test_run_001",
        "fidelity": "MEDIUM",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_hours": 24.0,
        "spacecraft_id": "SC-001",
    }

    with open(viz_dir / "run_manifest.json", "w") as f:
        json.dump(manifest, f)

    # Create events
    events = [
        {
            "id": "evt_001",
            "type": "soc_warning",
            "time": (start_time + timedelta(hours=2)).isoformat(),
            "message": "Battery SOC below 30%",
            "severity": "warning",
        },
        {
            "id": "evt_002",
            "type": "soc_violation",
            "time": (start_time + timedelta(hours=4)).isoformat(),
            "message": "Battery SOC below 20%",
            "severity": "failure",
        },
    ]

    with open(viz_dir / "events.json", "w") as f:
        json.dump(events, f)

    # Create minimal CZML for Cesium
    czml = [
        {"id": "document", "version": "1.0"},
        {
            "id": "spacecraft",
            "name": "SC-001",
            "position": {
                "cartographicDegrees": [
                    0,
                    -122.0,
                    37.0,
                    400000,  # 400km altitude
                ]
            },
        },
    ]

    with open(viz_dir / "scene.czml", "w") as f:
        json.dump(czml, f)

    return CompletedRunData(
        path=str(tmp_path),
        case_id="test_001",
        event_count=2,
        constraint_violations=1,
        manifest=manifest,
    )


@pytest.fixture
def tier_a_cases() -> list:
    """Get list of Tier A case IDs."""
    return get_tier_a_case_ids()


@pytest.fixture
def tier_b_cases() -> list:
    """Get list of Tier B case IDs."""
    return get_tier_b_case_ids()


# =============================================================================
# AERIE CLIENT FIXTURE
# =============================================================================


@pytest.fixture
def aerie_client(graphql_url):
    """
    Get an Aerie GraphQL client.

    Returns a client for interacting with Aerie API.
    """
    try:
        from sim.aerie.client import AerieClient

        return AerieClient(graphql_url=graphql_url)
    except ImportError:
        # Return a mock client for tests that don't need real Aerie
        class MockAerieClient:
            def __init__(self, url):
                self.graphql_url = url

            def health_check(self):
                return True

        return MockAerieClient(graphql_url)
