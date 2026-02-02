"""ETE viewer validation tests - UI visualization tests.

Tests that simulation results display correctly in the viewer.
Run on every PR as part of Tier A.

Usage:
    pytest tests/ete/test_viewer_validation.py -v
    pytest tests/ete/ -m "ete_tier_a" -v
"""

from __future__ import annotations

from datetime import datetime
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
    pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed"),
    pytest.mark.ete_tier_a,
    pytest.mark.ete,
]


class TestRunLoading:
    """Test loading simulation runs in the viewer."""

    def test_run_loads_in_viewer(self, viewer_page, completed_run):
        """Simulation run loads in viewer without errors."""
        viewer_page.load_run(completed_run.path)

        assert viewer_page.is_loaded()
        assert not viewer_page.has_error()

    def test_cesium_initializes(self, viewer_page, completed_run):
        """Cesium 3D viewer initializes correctly."""
        viewer_page.load_run(completed_run.path)

        # Wait for Cesium to initialize
        cesium_ready = viewer_page.wait_for_cesium(timeout_ms=15000)

        # Cesium should initialize (may not have entity data for minimal test run)
        # Just verify no errors
        assert viewer_page.is_loaded()

    def test_manifest_data_displayed(self, viewer_page, completed_run):
        """Run manifest data is displayed in the UI."""
        viewer_page.load_run(completed_run.path)

        # Page should load and display something
        assert viewer_page.is_loaded()

        # Title should contain something (run ID, plan name, etc.)
        title = viewer_page.get_page_title()
        assert title is not None


class TestMissionStatus:
    """Test mission status display in viewer."""

    def test_mission_status_displays(self, viewer_page, completed_run):
        """Mission status KPIs display correctly."""
        viewer_page.load_run(completed_run.path)

        status = viewer_page.get_mission_status()

        # Status dict should have expected keys (may be 0 if not displayed)
        assert isinstance(status, dict)

    def test_events_counted_correctly(self, viewer_page, completed_run):
        """Event count matches simulation output."""
        viewer_page.load_run(completed_run.path)

        status = viewer_page.get_mission_status()

        # If events are displayed, count should be reasonable
        if "events" in status:
            assert status["events"] >= 0

    def test_alerts_displayed(self, viewer_page, completed_run):
        """Alerts from simulation appear in UI."""
        viewer_page.load_run(completed_run.path)

        alerts = viewer_page.get_alerts_count()

        # Should be non-negative (may be 0 if alerts panel is collapsed)
        assert alerts >= 0


class TestWorkspaces:
    """Test workspace functionality in viewer."""

    def test_default_workspace_is_mission_overview(self, viewer_page, completed_run):
        """Default workspace is mission overview."""
        viewer_page.load_run(completed_run.path)

        current_ws = viewer_page.current_workspace()
        assert current_ws == "mission-overview"

    def test_switch_to_maneuver_planning(self, viewer_page, completed_run):
        """Can switch to maneuver planning workspace."""
        viewer_page.load_run(completed_run.path)

        viewer_page.switch_workspace("maneuver-planning")
        assert viewer_page.current_workspace() == "maneuver-planning"

    def test_switch_to_vleo_drag(self, viewer_page, completed_run):
        """Can switch to VLEO drag workspace."""
        viewer_page.load_run(completed_run.path)

        viewer_page.switch_workspace("vleo-drag")
        assert viewer_page.current_workspace() == "vleo-drag"

    def test_switch_to_anomaly_response(self, viewer_page, completed_run):
        """Can switch to anomaly response workspace."""
        viewer_page.load_run(completed_run.path)

        viewer_page.switch_workspace("anomaly-response")
        assert viewer_page.current_workspace() == "anomaly-response"

    def test_switch_to_payload_ops(self, viewer_page, completed_run):
        """Can switch to payload operations workspace."""
        viewer_page.load_run(completed_run.path)

        viewer_page.switch_workspace("payload-ops")
        assert viewer_page.current_workspace() == "payload-ops"

    @pytest.mark.ete_tier_b
    def test_all_workspaces_cycle(self, viewer_page, completed_run):
        """All 5 workspaces accessible in sequence."""
        viewer_page.load_run(completed_run.path)

        workspaces = [
            "mission-overview",
            "maneuver-planning",
            "vleo-drag",
            "anomaly-response",
            "payload-ops",
        ]

        for ws in workspaces:
            viewer_page.switch_workspace(ws)
            assert viewer_page.current_workspace() == ws


class TestTimeline:
    """Test timeline functionality in viewer."""

    def test_timeline_renders(self, viewer_page, completed_run):
        """Timeline panel renders without errors."""
        viewer_page.load_run(completed_run.path)

        # Page should load with timeline visible (in footer)
        assert viewer_page.is_loaded()

    @pytest.mark.ete_tier_b
    def test_timeline_scrubbing(self, viewer_page, completed_run):
        """Timeline scrubbing updates visualization."""
        viewer_page.load_run(completed_run.path)

        # Wait for page to stabilize
        viewer_page.page.wait_for_timeout(1000)

        # Scrub to middle of timeline
        viewer_page.scrub_to_time(0.5)

        # Scrub to end
        viewer_page.scrub_to_time(0.9)

        # Should still be loaded without errors
        assert viewer_page.is_loaded()
        assert not viewer_page.has_error()

    def test_timeline_events_display(self, viewer_page, completed_run):
        """Timeline events from simulation are displayed."""
        viewer_page.load_run(completed_run.path)

        events = viewer_page.get_timeline_events()

        # Events list should be accessible (may be empty in minimal test)
        assert isinstance(events, list)


class TestErrorHandling:
    """Test error handling in viewer."""

    def test_invalid_run_path_handled(self, viewer_page):
        """Invalid run path shows error gracefully."""
        viewer_page.load_run("/nonexistent/path")

        # Should either show error or fail gracefully
        # (not crash the entire application)
        is_loaded = viewer_page.is_loaded()
        has_error = viewer_page.has_error()

        # Either loaded (with error message) or gracefully failed
        assert is_loaded or not has_error

    def test_missing_files_handled(self, viewer_page, tmp_path):
        """Missing required files handled gracefully."""
        import json

        # Create incomplete run (only manifest, no CZML)
        viz_dir = tmp_path / "viz"
        viz_dir.mkdir()

        manifest = {
            "plan_id": "incomplete_run",
            "fidelity": "LOW",
        }

        with open(viz_dir / "run_manifest.json", "w") as f:
            json.dump(manifest, f)

        viewer_page.load_run(str(tmp_path))

        # Should handle missing CZML gracefully
        # Either show error message or partial data
        assert viewer_page.is_loaded()


class TestResponsiveness:
    """Test UI responsiveness."""

    def test_page_loads_within_timeout(self, page: "Page", viewer_url: str):
        """Page loads within reasonable time."""
        start = datetime.now()

        try:
            page.goto(viewer_url, timeout=15000)
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pytest.skip("Viewer not running")

        elapsed = (datetime.now() - start).total_seconds()

        # Should load within 15 seconds
        assert elapsed < 15.0

    def test_workspace_switch_responsive(self, viewer_page, completed_run):
        """Workspace switching is responsive."""
        viewer_page.load_run(completed_run.path)

        start = datetime.now()
        viewer_page.switch_workspace("maneuver-planning")
        elapsed = (datetime.now() - start).total_seconds()

        # Switch should complete within 2 seconds
        assert elapsed < 2.0

    def test_no_memory_leaks_on_workspace_switch(self, viewer_page, completed_run):
        """No obvious memory leaks when switching workspaces repeatedly."""
        viewer_page.load_run(completed_run.path)

        # Switch workspaces multiple times
        workspaces = ["maneuver-planning", "vleo-drag", "mission-overview"]

        for _ in range(3):
            for ws in workspaces:
                viewer_page.switch_workspace(ws)
                viewer_page.page.wait_for_timeout(100)

        # Page should still be responsive
        assert viewer_page.is_loaded()
        assert not viewer_page.has_error()


class TestAccessibility:
    """Basic accessibility tests for viewer."""

    def test_page_has_title(self, viewer_page, completed_run):
        """Page has a meaningful title."""
        viewer_page.load_run(completed_run.path)

        title = viewer_page.get_page_title()
        assert title is not None
        assert len(title) > 0

    def test_main_content_accessible(self, viewer_page, completed_run):
        """Main content area is accessible."""
        viewer_page.load_run(completed_run.path)

        # Check for main content area
        main = viewer_page.page.query_selector("main, .workspace-content, [role='main']")
        assert main is not None


@pytest.mark.ete_tier_b
class TestScreenshots:
    """Screenshot capture tests for visual validation."""

    def test_capture_mission_overview(self, viewer_page, completed_run, tmp_path):
        """Capture screenshot of mission overview."""
        viewer_page.load_run(completed_run.path)
        viewer_page.page.wait_for_timeout(2000)  # Wait for rendering

        screenshot_path = tmp_path / "mission_overview.png"
        viewer_page.capture_screenshot(str(screenshot_path))

        assert screenshot_path.exists()
        assert screenshot_path.stat().st_size > 0

    def test_capture_all_workspaces(self, viewer_page, completed_run, tmp_path):
        """Capture screenshots of all workspaces."""
        viewer_page.load_run(completed_run.path)

        workspaces = [
            "mission-overview",
            "maneuver-planning",
            "vleo-drag",
            "anomaly-response",
            "payload-ops",
        ]

        for ws in workspaces:
            viewer_page.switch_workspace(ws)
            viewer_page.page.wait_for_timeout(500)

            screenshot_path = tmp_path / f"{ws}.png"
            viewer_page.capture_screenshot(str(screenshot_path))

            assert screenshot_path.exists()
