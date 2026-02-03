"""Page object model for Viewer UI.

Provides methods for interacting with the spacecraft mission visualization viewer.
Follows the same pattern as tests/e2e/pages/aerie.py.
"""

from __future__ import annotations

from typing import Dict, List, Optional

try:
    from playwright.sync_api import Page, expect

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = None


class ViewerPage:
    """
    Page object for the Viewer UI.

    Provides methods for navigating and interacting with the spacecraft
    mission visualization viewer for ETE testing.
    """

    # Workspace IDs matching viewer/src/types/index.ts
    WORKSPACES = [
        "mission-overview",
        "maneuver-planning",
        "vleo-drag",
        "anomaly-response",
        "payload-ops",
    ]

    def __init__(self, page: Page, base_url: str = "http://localhost:3002"):
        """
        Initialize viewer page object.

        Args:
            page: Playwright page instance
            base_url: Viewer base URL
        """
        self.page = page
        self.base_url = base_url

    def goto_home(self) -> None:
        """Navigate to viewer home page."""
        self.page.goto(self.base_url)
        self.page.wait_for_load_state("networkidle")

    def load_run(self, run_path: str) -> None:
        """
        Load a simulation run in the viewer.

        Args:
            run_path: Path or URL to run data
        """
        # Construct URL with run parameter
        url = f"{self.base_url}?run={run_path}"
        self.page.goto(url)
        self.wait_for_ready()

    def wait_for_ready(self, timeout_ms: int = 30000) -> None:
        """
        Wait for the app to fully load.

        Args:
            timeout_ms: Maximum wait time in milliseconds
        """
        # Wait for app to finish loading - look for any content besides the initial loader
        # The app removes the .initial-loader when it's ready
        try:
            # First, wait for the page to load
            self.page.wait_for_load_state("networkidle", timeout=timeout_ms)

            # Then check that we're not on the initial loader anymore
            # This is done by waiting for the loading spinner to disappear
            # or by waiting for specific app content to appear
            self.page.wait_for_function(
                """() => {
                    const loader = document.querySelector('.initial-loader');
                    const root = document.getElementById('root');
                    // App is ready when initial loader is gone or root has substantial content
                    return !loader || (root && root.children.length > 1);
                }""",
                timeout=timeout_ms,
            )
        except Exception:
            # If specific checks fail, just ensure page is loaded
            self.page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)

    def cesium_ready(self) -> bool:
        """
        Check if Cesium viewer has initialized.

        Returns:
            True if Cesium viewer is ready
        """
        try:
            result = self.page.evaluate(
                "() => window.cesiumViewer ? true : false"
            )
            return bool(result)
        except Exception:
            return False

    def wait_for_cesium(self, timeout_ms: int = 30000) -> bool:
        """
        Wait for Cesium viewer to initialize.

        Args:
            timeout_ms: Maximum wait time

        Returns:
            True if Cesium initialized, False if timeout
        """
        try:
            self.page.wait_for_function(
                "() => window.cesiumViewer !== undefined",
                timeout=timeout_ms,
            )
            return True
        except Exception:
            return False

    def get_mission_status(self) -> Dict:
        """
        Get mission status KPIs from the UI.

        Returns:
            Dictionary with mission status information
        """
        status = {}

        # Try to get event count from alerts summary or mission overview
        try:
            events_el = self.page.query_selector(
                "[data-testid='event-count'], .alerts-count, .event-count"
            )
            if events_el:
                text = events_el.inner_text()
                # Extract number from text like "5 Events" or just "5"
                import re

                match = re.search(r"\d+", text)
                if match:
                    status["events"] = int(match.group())
        except Exception:
            status["events"] = 0

        # Try to get constraint violations
        try:
            violations_el = self.page.query_selector(
                "[data-testid='violation-count'], .violations-count"
            )
            if violations_el:
                text = violations_el.inner_text()
                import re

                match = re.search(r"\d+", text)
                if match:
                    status["violations"] = int(match.group())
        except Exception:
            status["violations"] = 0

        return status

    def get_alerts_count(self) -> int:
        """
        Get the number of alerts displayed in the UI.

        Returns:
            Number of alerts
        """
        try:
            # Check for alert count in header badge
            badge = self.page.query_selector(
                "[data-testid='alerts-badge'], .alerts-badge, .badge"
            )
            if badge:
                text = badge.inner_text()
                import re

                match = re.search(r"\d+", text)
                if match:
                    return int(match.group())

            # Count alert items in alert center
            alerts = self.page.query_selector_all(
                "[data-testid='alert-item'], .alert-item"
            )
            return len(alerts)

        except Exception:
            return 0

    def get_timeline_events(self) -> List[Dict]:
        """
        Get events from the timeline panel.

        Returns:
            List of event dictionaries
        """
        events = []

        try:
            event_els = self.page.query_selector_all(
                "[data-testid='timeline-event'], .timeline-event"
            )
            for el in event_els:
                event = {
                    "id": el.get_attribute("data-event-id"),
                    "type": el.get_attribute("data-event-type"),
                    "text": el.inner_text(),
                }
                events.append(event)
        except Exception:
            pass

        return events

    def get_current_workspace(self) -> str:
        """
        Get the currently active workspace ID.

        Returns:
            Workspace ID string
        """
        try:
            # Check for active nav item
            active = self.page.query_selector(
                ".nav-item.active, [data-workspace].active"
            )
            if active:
                workspace_id = active.get_attribute("data-workspace")
                if workspace_id:
                    return workspace_id

            # Fall back to checking which workspace content is visible
            for ws in self.WORKSPACES:
                ws_content = self.page.query_selector(
                    f"[data-workspace-content='{ws}']"
                )
                if ws_content and ws_content.is_visible():
                    return ws

        except Exception:
            pass

        return "mission-overview"  # Default

    def switch_workspace(self, workspace_id: str) -> bool:
        """
        Switch to a different workspace.

        Args:
            workspace_id: Workspace ID to switch to

        Returns:
            True if switch succeeded, False if elements not found
        """
        if workspace_id not in self.WORKSPACES:
            raise ValueError(
                f"Unknown workspace: {workspace_id}. "
                f"Valid options: {self.WORKSPACES}"
            )

        try:
            # Try multiple selectors for workspace navigation
            selectors = [
                f"[data-workspace='{workspace_id}']",
                f".nav-item:has-text('{workspace_id.replace('-', ' ')}')",
                f"button:has-text('{workspace_id.replace('-', ' ')}')",
                f"a:has-text('{workspace_id.replace('-', ' ')}')",
            ]

            for selector in selectors:
                try:
                    el = self.page.query_selector(selector)
                    if el and el.is_visible():
                        el.click()
                        self.page.wait_for_timeout(500)  # Wait for transition
                        return True
                except Exception:
                    continue

            # Workspace switching not available in this viewer version
            return False
        except Exception:
            return False

    def current_workspace(self) -> str:
        """Alias for get_current_workspace for test compatibility."""
        return self.get_current_workspace()

    def scrub_to_time(self, time_fraction: float) -> None:
        """
        Scrub the timeline to a position.

        Args:
            time_fraction: Position on timeline (0.0 = start, 1.0 = end)
        """
        if not 0.0 <= time_fraction <= 1.0:
            raise ValueError(f"time_fraction must be between 0 and 1, got {time_fraction}")

        # Find the timeline scrubber/slider
        timeline = self.page.query_selector(
            "[data-testid='timeline-slider'], .timeline-slider, .footer-timeline"
        )

        if timeline:
            # Get timeline bounds
            box = timeline.bounding_box()
            if box:
                # Calculate click position
                x = box["x"] + (box["width"] * time_fraction)
                y = box["y"] + (box["height"] / 2)

                # Click at position
                self.page.mouse.click(x, y)

                # Wait for update
                self.page.wait_for_timeout(500)

    def get_spacecraft_position(self) -> Optional[Dict]:
        """
        Get current spacecraft position from Cesium viewer.

        Returns:
            Dictionary with position data or None
        """
        try:
            result = self.page.evaluate(
                """
                () => {
                    if (!window.cesiumViewer) return null;
                    const viewer = window.cesiumViewer;
                    const entity = viewer.entities.getById('spacecraft');
                    if (!entity) return null;

                    const time = viewer.clock.currentTime;
                    const position = entity.position?.getValue(time);
                    if (!position) return null;

                    const cartographic = Cesium.Cartographic.fromCartesian(position);
                    return {
                        longitude: Cesium.Math.toDegrees(cartographic.longitude),
                        latitude: Cesium.Math.toDegrees(cartographic.latitude),
                        altitude: cartographic.height / 1000  // km
                    };
                }
                """
            )
            return result
        except Exception:
            return None

    def is_loaded(self) -> bool:
        """
        Check if the viewer has loaded.

        Returns:
            True if viewer is loaded
        """
        try:
            # Check that the page has loaded and isn't showing the initial loader
            result = self.page.evaluate(
                """() => {
                    const loader = document.querySelector('.initial-loader');
                    const root = document.getElementById('root');
                    return !loader || (root && root.children.length > 1);
                }"""
            )
            return bool(result)
        except Exception:
            return False

    def has_error(self) -> bool:
        """
        Check if an error message is displayed.

        Returns:
            True if an error is shown
        """
        try:
            error = self.page.query_selector(
                "[data-testid='error-message'], .error-message, .load-error"
            )
            return error is not None and error.is_visible()
        except Exception:
            return False

    def get_error_message(self) -> Optional[str]:
        """
        Get the error message if displayed.

        Returns:
            Error message string or None
        """
        try:
            error = self.page.query_selector(
                "[data-testid='error-message'], .error-message, .load-error"
            )
            if error and error.is_visible():
                return error.inner_text()
        except Exception:
            pass
        return None

    def get_page_title(self) -> str:
        """Get the current page title."""
        return self.page.title()

    def capture_screenshot(self, path: str) -> None:
        """
        Capture a screenshot of the current view.

        Args:
            path: File path to save screenshot
        """
        self.page.screenshot(path=path)

    def check_console_errors(self) -> List[str]:
        """
        Check for JavaScript console errors.

        Note: Must be called before navigating to capture errors.

        Returns:
            List of error messages
        """
        errors = []

        def handle_console(msg):
            if msg.type == "error":
                errors.append(msg.text)

        self.page.on("console", handle_console)
        return errors
