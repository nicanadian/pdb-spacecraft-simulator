"""Pytest configuration for ETE (end-to-end) validation tests.

Provides fixtures for service orchestration, browser testing, and test data.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator, Optional

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
# DETERMINISTIC REFERENCE EPOCH
# =============================================================================

# Fixed epoch for all tests - ensures determinism and repeatability
REFERENCE_EPOCH = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


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
# DETERMINISTIC TIME FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def reference_epoch() -> datetime:
    """
    Get the fixed reference epoch for deterministic tests.

    All tests should use this epoch instead of datetime.now() to ensure
    repeatability and determinism.
    """
    return REFERENCE_EPOCH


@pytest.fixture
def test_time_range(reference_epoch) -> tuple:
    """
    Get a deterministic time range for testing.

    Returns:
        Tuple of (start_time, end_time) with 24-hour duration
    """
    start_time = reference_epoch
    end_time = start_time + timedelta(hours=24)
    return start_time, end_time


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


def get_truth_file_path(case_id: str, version: str = "v1") -> Path:
    """
    Get path to GMAT truth file for a case.

    Args:
        case_id: Case identifier (e.g., "R01")
        version: Truth file version

    Returns:
        Path to truth file
    """
    return Path(f"validation/reference/truth/{case_id}_truth_{version}.json")


@pytest.fixture
def require_truth_file():
    """
    Factory fixture to require truth file existence.

    Usage:
        def test_something(require_truth_file):
            require_truth_file("R01")  # Fails if truth file doesn't exist
    """
    def _require(case_id: str, version: str = "v1"):
        truth_path = get_truth_file_path(case_id, version)
        if not truth_path.exists():
            pytest.fail(
                f"GMAT truth file not found: {truth_path}\n"
                f"Generate truth data with: python -m validation.gmat.harness.generate_truth {case_id}"
            )
        return truth_path
    return _require


# =============================================================================
# SIMULATION FIXTURES - REAL OUTPUT (NOT SYNTHETIC)
# =============================================================================


@pytest.fixture
def real_simulation_run(tmp_path, reference_epoch) -> CompletedRunData:
    """
    Run an actual simulation and return the completed run data.

    This fixture runs a real simulation (not synthetic data) to ensure
    viewer tests validate actual simulator output.
    """
    from sim.engine import simulate
    from sim.core.types import Fidelity, InitialState, PlanInput, SimConfig, Activity

    start_time = reference_epoch
    end_time = start_time + timedelta(hours=6)

    # Deterministic initial state for ~400km circular orbit
    initial_state = InitialState(
        epoch=start_time,
        position_eci=[6778.137, 0.0, 0.0],  # km, exactly Earth radius + 400km
        velocity_eci=[0.0, 7.6686, 0.0],    # km/s, circular orbit velocity
        mass_kg=500.0,
        soc=0.85,
    )

    # Add realistic activities
    activities = [
        Activity(
            activity_id="act_001",
            activity_type="imaging",
            start_time=start_time + timedelta(hours=1),
            end_time=start_time + timedelta(hours=1, minutes=5),
            parameters={"target_id": "target_001", "mode": "high_res"},
        ),
        Activity(
            activity_id="act_002",
            activity_type="downlink",
            start_time=start_time + timedelta(hours=3),
            end_time=start_time + timedelta(hours=3, minutes=10),
            parameters={"station_id": "SVALBARD", "data_volume_gb": 2.5},
        ),
    ]

    plan = PlanInput(
        plan_id="ete_real_sim_001",
        start_time=start_time,
        end_time=end_time,
        activities=activities,
    )

    config = SimConfig(
        output_dir=str(tmp_path),
        time_step_s=60.0,
    )

    # Run actual simulation
    result = simulate(
        plan=plan,
        initial_state=initial_state,
        fidelity=Fidelity.LOW,
        config=config,
    )

    # Count actual events from output
    events_path = tmp_path / "viz" / "events.json"
    event_count = 0
    constraint_violations = 0

    if events_path.exists():
        with open(events_path) as f:
            events = json.load(f)
            if isinstance(events, list):
                event_count = len(events)
                constraint_violations = sum(
                    1 for e in events if "violation" in e.get("type", "")
                )

    # Load manifest
    manifest_path = tmp_path / "viz" / "run_manifest.json"
    manifest = {}
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)

    return CompletedRunData(
        path=str(tmp_path),
        case_id="ete_real_sim_001",
        event_count=event_count,
        constraint_violations=constraint_violations,
        manifest=manifest,
        initial_state=initial_state,
        final_state=result.final_state,
        sim_result=result,
    )


@pytest.fixture
def completed_run(real_simulation_run) -> CompletedRunData:
    """
    Alias for real_simulation_run for backward compatibility.

    This now uses REAL simulation output instead of synthetic fixtures.
    """
    return real_simulation_run


# =============================================================================
# SYNTHETIC FIXTURE (EXPLICITLY NAMED - USE SPARINGLY)
# =============================================================================


@pytest.fixture
def synthetic_run_data(tmp_path, reference_epoch) -> CompletedRunData:
    """
    Create synthetic run data for tests that specifically need mock data.

    WARNING: This creates fake data that was NOT produced by the simulator.
    Only use this for tests that specifically test data loading mechanics,
    not for tests that validate correctness.
    """
    start_time = reference_epoch
    end_time = start_time + timedelta(hours=24)

    # Create directory structure
    viz_dir = tmp_path / "viz"
    viz_dir.mkdir()

    manifest = {
        "plan_id": "synthetic_test_run",
        "fidelity": "LOW",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_hours": 24.0,
        "spacecraft_id": "SC-SYNTHETIC",
        "_synthetic": True,  # Mark as synthetic
    }

    with open(viz_dir / "run_manifest.json", "w") as f:
        json.dump(manifest, f)

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

    czml = [
        {"id": "document", "version": "1.0"},
        {
            "id": "spacecraft",
            "name": "SC-SYNTHETIC",
            "position": {
                "cartographicDegrees": [0, -122.0, 37.0, 400000]
            },
        },
    ]

    with open(viz_dir / "scene.czml", "w") as f:
        json.dump(czml, f)

    return CompletedRunData(
        path=str(tmp_path),
        case_id="synthetic_001",
        event_count=2,
        constraint_violations=1,
        manifest=manifest,
    )


# =============================================================================
# CASE FIXTURES
# =============================================================================


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


# =============================================================================
# PHYSICS VALIDATION HELPERS
# =============================================================================


@pytest.fixture
def physics_validator():
    """
    Get physics validation helper for checking invariants.
    """
    import numpy as np

    class PhysicsValidator:
        """Helper class for validating physics invariants."""

        MU_EARTH = 398600.4418  # km^3/s^2

        def compute_specific_energy(self, position_km, velocity_km_s) -> float:
            """Compute specific orbital energy (km^2/s^2)."""
            r = np.linalg.norm(position_km)
            v = np.linalg.norm(velocity_km_s)
            return v**2 / 2 - self.MU_EARTH / r

        def compute_angular_momentum(self, position_km, velocity_km_s) -> np.ndarray:
            """Compute specific angular momentum vector (km^2/s)."""
            return np.cross(position_km, velocity_km_s)

        def compute_sma(self, position_km, velocity_km_s) -> float:
            """Compute semi-major axis (km)."""
            energy = self.compute_specific_energy(position_km, velocity_km_s)
            if abs(energy) < 1e-10:
                return float('inf')  # Parabolic
            return -self.MU_EARTH / (2 * energy)

        def validate_energy_conservation(
            self,
            initial_pos, initial_vel,
            final_pos, final_vel,
            tolerance_pct: float = 0.01
        ) -> tuple:
            """
            Validate energy conservation.

            Returns:
                Tuple of (is_valid, energy_drift_pct, message)
            """
            e0 = self.compute_specific_energy(initial_pos, initial_vel)
            e1 = self.compute_specific_energy(final_pos, final_vel)

            if abs(e0) < 1e-10:
                return False, 0.0, "Initial energy too close to zero"

            drift_pct = abs(e1 - e0) / abs(e0) * 100
            is_valid = drift_pct < tolerance_pct

            msg = f"Energy drift: {drift_pct:.6f}% (tolerance: {tolerance_pct}%)"
            return is_valid, drift_pct, msg

        def validate_momentum_conservation(
            self,
            initial_pos, initial_vel,
            final_pos, final_vel,
            tolerance_pct: float = 0.01
        ) -> tuple:
            """
            Validate angular momentum conservation.

            Returns:
                Tuple of (is_valid, momentum_drift_pct, message)
            """
            h0 = self.compute_angular_momentum(initial_pos, initial_vel)
            h1 = self.compute_angular_momentum(final_pos, final_vel)

            h0_mag = np.linalg.norm(h0)
            if h0_mag < 1e-10:
                return False, 0.0, "Initial momentum too close to zero"

            drift_pct = np.linalg.norm(h1 - h0) / h0_mag * 100
            is_valid = drift_pct < tolerance_pct

            msg = f"Momentum drift: {drift_pct:.6f}% (tolerance: {tolerance_pct}%)"
            return is_valid, drift_pct, msg

    return PhysicsValidator()
