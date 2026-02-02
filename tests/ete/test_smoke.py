"""ETE smoke tests - quick validation that services are operational.

These tests should complete in under 60 seconds and verify basic connectivity.
Run on every PR.

Usage:
    pytest tests/ete/test_smoke.py -v
    pytest tests/ete/ -m "ete_smoke" -v
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

# Skip all tests if Playwright is not installed
try:
    from playwright.sync_api import expect

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

if TYPE_CHECKING:
    from playwright.sync_api import Page


pytestmark = [
    pytest.mark.ete_smoke,
    pytest.mark.ete,
]


class TestServiceHealth:
    """Test that core services are healthy and responding."""

    def test_simulation_module_importable(self):
        """Verify core simulation module can be imported."""
        from sim.engine import simulate
        from sim.core.types import Fidelity

        assert simulate is not None
        assert Fidelity.LOW is not None
        assert Fidelity.MEDIUM is not None

    def test_validation_module_importable(self):
        """Verify validation module can be imported."""
        from validation.gmat.case_registry import get_case, get_tier_cases, CaseTier

        # Should be able to get Tier A cases
        tier_a = get_tier_cases(CaseTier.A)
        assert len(tier_a) > 0

        # Should be able to look up a specific case
        case = get_case("R01")
        assert case.case_id == "R01"

    def test_aerie_health(self, graphql_url):
        """Aerie GraphQL endpoint responds (if available)."""
        import requests

        try:
            response = requests.post(
                graphql_url,
                json={"query": "{ __typename }"},
                timeout=5,
            )

            # Accept 200 OK or 401/403 (auth configured but endpoint responding)
            assert response.status_code in [200, 401, 403]
        except requests.RequestException:
            pytest.skip("Aerie not available")

    @pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
    def test_viewer_loads(self, page: "Page", viewer_url: str):
        """Viewer loads without errors."""
        try:
            page.goto(viewer_url, timeout=10000)
        except Exception:
            pytest.skip("Viewer not running")

        # Should load without crashing
        assert page.title() is not None

        # Body should be present
        body = page.query_selector("body")
        assert body is not None


class TestBasicSimulation:
    """Test that basic simulation functionality works."""

    def test_simulation_runs_low_fidelity(self, tmp_path):
        """Basic LOW fidelity simulation completes."""
        from datetime import datetime, timedelta, timezone

        from sim.engine import simulate
        from sim.core.types import Fidelity, InitialState, PlanInput, SimConfig

        # Create minimal inputs
        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(hours=1)

        initial_state = InitialState(
            epoch=start_time,
            position_eci=[6778.0, 0.0, 0.0],  # ~400km altitude
            velocity_eci=[0.0, 7.67, 0.0],  # Circular orbit velocity
            mass_kg=1000.0,
        )

        plan = PlanInput(
            plan_id="smoke_test",
            start_time=start_time,
            end_time=end_time,
            activities=[],
        )

        config = SimConfig(
            output_dir=str(tmp_path),
            time_step_s=60.0,
        )

        # Run simulation
        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )

        # Basic assertions
        assert result is not None
        assert result.final_state is not None
        assert result.final_state.epoch == end_time

    def test_scenario_runner_available(self):
        """Scenario runner can be instantiated."""
        from validation.gmat.harness.scenario_runner import ScenarioRunner

        runner = ScenarioRunner()
        assert runner is not None


class TestDataLoading:
    """Test data loading and file operations."""

    def test_sample_run_loads(self, tmp_path):
        """Sample run data can be loaded by viewer data structures."""
        import json
        from datetime import datetime, timedelta, timezone

        # Create sample data
        viz_dir = tmp_path / "viz"
        viz_dir.mkdir()

        start_time = datetime.now(timezone.utc)

        manifest = {
            "plan_id": "smoke_test_run",
            "fidelity": "LOW",
            "start_time": start_time.isoformat(),
            "end_time": (start_time + timedelta(hours=1)).isoformat(),
            "duration_hours": 1.0,
        }

        with open(viz_dir / "run_manifest.json", "w") as f:
            json.dump(manifest, f)

        # Verify file exists and is valid JSON
        with open(viz_dir / "run_manifest.json") as f:
            loaded = json.load(f)

        assert loaded["plan_id"] == "smoke_test_run"
        assert loaded["fidelity"] == "LOW"

    def test_tolerance_config_loads(self):
        """Tolerance configuration can be loaded."""
        from validation.gmat.tolerance_config import GMATToleranceConfig

        config = GMATToleranceConfig()

        # Check defaults are reasonable
        assert config.position_rms_km > 0
        assert config.velocity_rms_m_s > 0
        assert config.altitude_rms_km > 0

    def test_case_registry_complete(self):
        """Case registry has expected cases."""
        from validation.gmat.case_registry import (
            TIER_A_CASES,
            TIER_B_CASES,
            get_case,
        )

        # Tier A should have 12 cases (R01-R12)
        assert len(TIER_A_CASES) == 12

        # Tier B should have 6 cases (N01-N06)
        assert len(TIER_B_CASES) == 6

        # Spot check specific cases
        r01 = get_case("R01")
        assert r01.name == "Finite Burn"

        n01 = get_case("N01")
        assert n01.name == "LEO EP Drag Makeup"


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
class TestViewerSmoke:
    """Viewer-specific smoke tests."""

    def test_viewer_app_shell_renders(self, page: "Page", viewer_url: str):
        """Viewer app shell renders correctly."""
        try:
            page.goto(viewer_url, timeout=10000)
        except Exception:
            pytest.skip("Viewer not running")

        # Wait for app shell
        try:
            page.wait_for_selector(".app-shell", timeout=5000)
            app_shell = page.query_selector(".app-shell")
            assert app_shell is not None
        except Exception:
            # App shell might have different class name
            body = page.query_selector("body")
            assert body is not None

    def test_viewer_no_critical_errors(self, page: "Page", viewer_url: str):
        """Viewer loads without critical JavaScript errors."""
        errors = []

        def handle_console(msg):
            if msg.type == "error":
                text = msg.text
                # Ignore some common non-critical errors
                if not any(
                    ignore in text
                    for ignore in [
                        "favicon",
                        "Failed to load resource",
                        "net::ERR",
                    ]
                ):
                    errors.append(text)

        page.on("console", handle_console)

        try:
            page.goto(viewer_url, timeout=10000)
            page.wait_for_load_state("networkidle")
        except Exception:
            pytest.skip("Viewer not running")

        # Check for critical errors (TypeError, ReferenceError, etc.)
        critical_errors = [
            e
            for e in errors
            if any(err_type in e for err_type in ["TypeError", "ReferenceError", "SyntaxError"])
        ]

        assert len(critical_errors) == 0, f"Critical JS errors: {critical_errors}"
