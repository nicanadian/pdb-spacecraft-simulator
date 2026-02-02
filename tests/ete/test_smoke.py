"""ETE smoke tests - quick validation that services are operational.

These tests should complete in under 60 seconds and verify basic connectivity
and functionality. Run on every PR.

Key improvements over previous version:
- Deterministic epochs (no datetime.now())
- Meaningful assertions (not just `>= 0` or `is not None`)
- Fail-fast on missing dependencies
- Clear subsystem identification in failure messages

Usage:
    pytest tests/ete/test_smoke.py -v
    pytest tests/ete/ -m "ete_smoke" -v
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from .conftest import (
    REFERENCE_EPOCH,
    create_test_plan,
    create_test_initial_state,
    create_test_config,
)

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


class TestCoreModules:
    """Test that core modules are functional (not just importable)."""

    def test_simulation_engine_functional(self, reference_epoch, tmp_path):
        """
        Verify simulation engine can execute a basic scenario.

        This is more than an import test - it validates the core simulation
        pipeline is functional.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=1)

        # Deterministic initial state
        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id="smoke_test_engine",
            start_time=start_time,
            end_time=end_time,
        )

        config = create_test_config(
            output_dir=str(tmp_path),
            time_step_s=60.0,
        )

        # Run with minimal config
        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )

        # Meaningful assertions
        assert result is not None, "Simulation returned None"
        assert result.final_state is not None, "Final state is None"
        assert result.final_state.epoch == end_time, (
            f"Final epoch mismatch: expected {end_time}, got {result.final_state.epoch}"
        )
        assert result.final_state.mass_kg > 0, "Final mass is non-positive"
        assert result.final_state.mass_kg <= initial_state.mass_kg, (
            "Final mass exceeds initial mass (mass cannot increase)"
        )

    def test_validation_module_functional(self):
        """
        Verify validation module can look up cases and provide tolerances.

        Validates the GMAT case registry and tolerance system are working.
        """
        from validation.gmat.case_registry import get_case, get_tier_cases, CaseTier
        from validation.gmat.tolerance_config import GMATToleranceConfig

        # Verify case registry
        tier_a = get_tier_cases(CaseTier.A)
        assert len(tier_a) == 12, f"Expected 12 Tier A cases, got {len(tier_a)}"

        tier_b = get_tier_cases(CaseTier.B)
        assert len(tier_b) == 6, f"Expected 6 Tier B cases, got {len(tier_b)}"

        # Verify specific case lookup
        r01 = get_case("R01")
        assert r01.case_id == "R01", "Case ID mismatch"
        assert r01.name == "Finite Burn", f"Case name mismatch: {r01.name}"
        assert r01.duration_hours > 0, "Case duration must be positive"

        # Verify tolerance config
        config = GMATToleranceConfig()
        assert config.position_rms_km > 0, "Position tolerance must be positive"
        assert config.velocity_rms_m_s > 0, "Velocity tolerance must be positive"

    def test_scenario_runner_functional(self):
        """Verify scenario runner can be instantiated and configured."""
        from validation.gmat.harness.scenario_runner import ScenarioRunner

        runner = ScenarioRunner()

        # Verify runner has required methods
        assert hasattr(runner, "run_scenario"), "Runner missing run_scenario method"
        assert callable(runner.run_scenario), "run_scenario is not callable"


class TestServiceConnectivity:
    """Test connectivity to external services."""

    def test_aerie_health_check(self, graphql_url):
        """
        Aerie GraphQL endpoint health check.

        Validates Aerie is reachable and responding. Does NOT accept
        error codes as "healthy" - only 200 OK passes.
        """
        import requests

        try:
            response = requests.post(
                graphql_url,
                json={"query": "{ __typename }"},
                timeout=5,
            )
        except requests.ConnectionError:
            pytest.skip(
                f"Aerie not reachable at {graphql_url} - "
                "start Aerie with 'make aerie-up' or set AERIE_GRAPHQL_URL"
            )
        except requests.Timeout:
            pytest.fail(f"Aerie timeout at {graphql_url} - service may be overloaded")

        # Only 200 is healthy - 401/403 means auth is broken
        assert response.status_code == 200, (
            f"Aerie health check failed: HTTP {response.status_code}\n"
            f"Response: {response.text[:500]}"
        )

    @pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
    def test_viewer_health_check(self, page: "Page", viewer_url: str):
        """
        Viewer application health check.

        Validates the viewer dev server is running and serving the app.
        """
        try:
            response = page.goto(viewer_url, timeout=10000)
        except Exception as e:
            pytest.skip(
                f"Viewer not reachable at {viewer_url} - "
                f"start with 'cd viewer && npm run dev': {e}"
            )

        # Check response status
        assert response is not None, "No response from viewer"
        assert response.status == 200, (
            f"Viewer returned HTTP {response.status}, expected 200"
        )

        # Check page has content
        title = page.title()
        assert title, "Viewer page has no title"

        # Check app shell renders
        page.wait_for_selector("body", timeout=5000)
        body = page.query_selector("body")
        assert body is not None, "Page body not found"


class TestPhysicsInvariants:
    """Test basic physics invariants in simulation output."""

    def test_orbit_remains_bound(self, reference_epoch, physics_validator, tmp_path):
        """
        Verify spacecraft remains in bound orbit (negative energy).

        A spacecraft in LEO should have negative specific orbital energy
        throughout the simulation.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=2)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        result = simulate(
            plan=create_test_plan(
                plan_id="bound_orbit_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        # Compute specific orbital energy
        final_pos = result.final_state.position_eci
        final_vel = result.final_state.velocity_eci

        energy = physics_validator.compute_specific_energy(final_pos, final_vel)

        assert energy < 0, (
            f"Spacecraft has escaped (positive energy: {energy:.6f} km²/s²)\n"
            "This indicates a propagation error or incorrect initial conditions"
        )

    def test_mass_conservation(self, reference_epoch, tmp_path):
        """
        Verify mass is conserved when no propulsion is active.

        Without active thrust, spacecraft mass should remain constant.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=1)

        initial_mass = 500.0
        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=initial_mass,
        )

        result = simulate(
            plan=create_test_plan(
                plan_id="mass_conservation_test",
                start_time=start_time,
                end_time=end_time,
                # No activities = no propulsion
            ),
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        final_mass = result.final_state.mass_kg

        # Mass should be exactly preserved (within floating point tolerance)
        assert abs(final_mass - initial_mass) < 1e-6, (
            f"Mass changed without propulsion: {initial_mass} -> {final_mass}\n"
            f"Delta: {final_mass - initial_mass} kg"
        )


class TestDataStructures:
    """Test data structure validity and integrity."""

    def test_case_registry_integrity(self):
        """Verify case registry has no duplicate IDs and valid data."""
        from validation.gmat.case_registry import CASE_REGISTRY, get_case

        # Check for duplicates (should be caught by dict, but verify)
        case_ids = list(CASE_REGISTRY.keys())
        assert len(case_ids) == len(set(case_ids)), "Duplicate case IDs in registry"

        # Verify each case has required fields
        for case_id, case in CASE_REGISTRY.items():
            assert case.case_id == case_id, f"Case ID mismatch for {case_id}"
            assert case.name, f"Case {case_id} has no name"
            assert case.duration_hours > 0, f"Case {case_id} has invalid duration"
            assert case.expected_runtime_s > 0, f"Case {case_id} has invalid runtime"

    def test_tolerance_config_validity(self):
        """Verify tolerance configuration has valid values."""
        from validation.gmat.tolerance_config import GMATToleranceConfig

        config = GMATToleranceConfig()

        # All tolerances must be positive
        assert config.position_rms_km > 0
        assert config.velocity_rms_m_s > 0
        assert config.altitude_rms_km > 0

        # Tolerances should be reasonable (not too large or too small)
        assert 0.001 < config.position_rms_km < 1000, (
            f"Position tolerance {config.position_rms_km} km seems unreasonable"
        )
        assert 0.001 < config.velocity_rms_m_s < 1000, (
            f"Velocity tolerance {config.velocity_rms_m_s} m/s seems unreasonable"
        )


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
class TestViewerSmoke:
    """Viewer-specific smoke tests."""

    def test_viewer_no_critical_js_errors(self, page: "Page", viewer_url: str):
        """
        Viewer loads without critical JavaScript errors.

        Critical errors (TypeError, ReferenceError, SyntaxError) indicate
        fundamental bugs that will break functionality.
        """
        critical_errors = []

        def handle_console(msg):
            if msg.type == "error":
                text = msg.text
                # Only track critical JS errors
                if any(
                    err_type in text
                    for err_type in ["TypeError", "ReferenceError", "SyntaxError"]
                ):
                    critical_errors.append(text)

        page.on("console", handle_console)

        try:
            page.goto(viewer_url, timeout=10000)
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception as e:
            pytest.skip(f"Viewer not available: {e}")

        assert len(critical_errors) == 0, (
            f"Critical JavaScript errors detected:\n"
            + "\n".join(f"  - {e}" for e in critical_errors)
        )

    def test_viewer_renders_app_shell(self, page: "Page", viewer_url: str):
        """
        Viewer renders the application shell structure.

        Verifies the core UI structure is present, not just that the page loads.
        """
        try:
            page.goto(viewer_url, timeout=10000)
        except Exception as e:
            pytest.skip(f"Viewer not available: {e}")

        # Wait for app to render
        page.wait_for_load_state("domcontentloaded")

        # Check for app shell - try multiple selectors
        app_shell = page.query_selector(
            ".app-shell, #app, #root, [data-testid='app-shell']"
        )

        if app_shell is None:
            # Fallback: check that body has meaningful content
            body = page.query_selector("body")
            assert body is not None, "Page has no body element"

            body_html = body.inner_html()
            assert len(body_html) > 100, (
                "Page body has minimal content - app may not have rendered"
            )
        else:
            assert app_shell.is_visible(), "App shell exists but is not visible"
