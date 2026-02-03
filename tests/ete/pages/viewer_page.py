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

    # === Enhanced UI Verification Methods ===

    def get_kpi_values(self) -> Dict[str, str]:
        """
        Get all KPI card values from Mission Overview.

        Returns:
            Dictionary mapping KPI labels to their values
        """
        kpis = {}
        try:
            cards = self.page.query_selector_all(".kpi-card")
            for card in cards:
                label_el = card.query_selector(".kpi-label")
                value_el = card.query_selector(".kpi-value")
                if label_el and value_el:
                    label = label_el.inner_text().strip().lower()
                    value = value_el.inner_text().strip()
                    kpis[label] = value
        except Exception:
            pass
        return kpis

    def get_context_chips(self) -> Dict[str, str]:
        """
        Get header context chips (plan, fidelity, duration).

        Returns:
            Dictionary with plan_id, fidelity, duration
        """
        chips = {}
        try:
            elements = self.page.query_selector_all(".context-chips .chip")
            # Order in HeaderBar: Plan ID, Fidelity, Duration
            keys = ["plan_id", "fidelity", "duration"]
            for key, el in zip(keys, elements):
                chips[key] = el.inner_text().strip()
        except Exception:
            pass
        return chips

    def get_timeline_contacts(self) -> List[Dict]:
        """
        Get contact blocks from timeline visualization.

        Returns:
            List of contact dictionaries with station, position info
        """
        contacts = []
        try:
            blocks = self.page.query_selector_all(".contact-block")
            for block in blocks:
                contact = {
                    "station": block.get_attribute("title") or "",
                    "left_pct": self._get_style_percent(block, "left"),
                    "width_pct": self._get_style_percent(block, "width"),
                }
                contacts.append(contact)
        except Exception:
            pass
        return contacts

    def _get_style_percent(self, element, prop: str) -> float:
        """Extract percentage value from element style property."""
        try:
            value = element.evaluate(f"el => el.style.{prop}")
            if value and "%" in value:
                return float(value.replace("%", ""))
        except Exception:
            pass
        return 0.0

    def get_timeline_event_markers(self) -> List[Dict]:
        """
        Get event markers from timeline visualization.

        Returns:
            List of event dictionaries with severity, position
        """
        events = []
        try:
            markers = self.page.query_selector_all(".event-marker")
            for marker in markers:
                class_attr = marker.get_attribute("class") or ""
                severity_classes = class_attr.split()
                severity = next(
                    (c for c in ["failure", "warning", "info"] if c in severity_classes),
                    "info"
                )
                events.append({
                    "severity": severity,
                    "left_pct": self._get_style_percent(marker, "left"),
                })
        except Exception:
            pass
        return events

    def get_alerts_by_severity(self, severity: str) -> List[Dict]:
        """
        Get alerts filtered by severity level.

        Args:
            severity: One of "failure", "warning", "info"

        Returns:
            List of alert dictionaries
        """
        alerts = []
        try:
            items = self.page.query_selector_all(
                f".alert-summary-item.{severity}, .alert-card.{severity}"
            )
            for item in items:
                title_el = item.query_selector(".alert-title, .item-title")
                alerts.append({
                    "title": title_el.inner_text() if title_el else "",
                    "severity": severity,
                })
        except Exception:
            pass
        return alerts

    def get_alert_thread_structure(self) -> List[Dict]:
        """
        Get alert thread structure with root causes and consequences.

        Returns:
            List of thread dictionaries with root and consequence info
        """
        threads = []
        try:
            thread_els = self.page.query_selector_all(".alert-thread")
            for thread in thread_els:
                root = thread.query_selector(".thread-root .alert-card")
                consequences = thread.query_selector_all(".thread-consequences .alert-card")
                root_title = None
                if root:
                    title_el = root.query_selector(".alert-title")
                    root_title = title_el.inner_text() if title_el else None
                threads.append({
                    "root_title": root_title,
                    "consequence_count": len(consequences),
                })
        except Exception:
            pass
        return threads

    # === Playback Control Methods ===

    def get_playback_state(self) -> Dict:
        """
        Get current playback state.

        Returns:
            Dictionary with is_playing, current_time, speed
        """
        state = {
            "is_playing": False,
            "current_time": "0:00 / 0:00",
            "speed": "1",
        }
        try:
            play_btn = self.page.query_selector(".play-button")
            if play_btn:
                class_attr = play_btn.get_attribute("class") or ""
                state["is_playing"] = "playing" in class_attr

            time_display = self.page.query_selector(".time-display")
            if time_display:
                state["current_time"] = time_display.inner_text()

            speed_select = self.page.query_selector(".speed-control select")
            if speed_select:
                state["speed"] = speed_select.input_value()
        except Exception:
            pass
        return state

    def click_playback_control(self, control: str) -> None:
        """
        Click a playback control button.

        Args:
            control: One of "start", "back", "play", "forward", "end"
        """
        index_map = {"start": 0, "back": 1, "play": 2, "forward": 3, "end": 4}
        if control == "play":
            self.page.click(".play-button")
        else:
            btns = self.page.query_selector_all(".playback-controls button")
            if len(btns) > index_map.get(control, 0):
                btns[index_map[control]].click()

    def set_playback_speed(self, speed: str) -> None:
        """
        Set playback speed.

        Args:
            speed: One of "1", "10", "60", "300", "1000"
        """
        try:
            self.page.select_option(".speed-control select", speed)
        except Exception:
            pass

    # === Cesium 3D Verification Methods ===

    def get_cesium_entities(self) -> List[str]:
        """
        Get list of entity IDs in Cesium viewer.

        Returns:
            List of entity ID strings
        """
        try:
            return self.page.evaluate("""() => {
                if (!window.cesiumViewer) return [];
                return window.cesiumViewer.entities.values.map(e => e.id);
            }""") or []
        except Exception:
            return []

    def select_cesium_entity(self, entity_id: str) -> bool:
        """
        Select an entity in the 3D viewer by ID.

        Args:
            entity_id: Entity ID to select

        Returns:
            True if entity was found and selected
        """
        try:
            return self.page.evaluate(f"""() => {{
                if (!window.cesiumViewer) return false;
                const entity = window.cesiumViewer.entities.getById('{entity_id}');
                if (!entity) return false;
                window.cesiumViewer.selectedEntity = entity;
                return true;
            }}""")
        except Exception:
            return False

    def get_telemetry_inspector_data(self) -> Optional[Dict]:
        """
        Get data from the telemetry inspector panel.

        Returns:
            Dictionary with inspector content or None if not visible
        """
        try:
            inspector = self.page.query_selector(".inspector-wrapper")
            if not inspector or not inspector.is_visible():
                return None
            return {
                "visible": True,
                "content": inspector.inner_text(),
            }
        except Exception:
            return None

    # === State Transition Helpers ===

    def wait_for_data_loaded(self, timeout_ms: int = 10000) -> bool:
        """
        Wait for simulation data to be fully loaded.

        Args:
            timeout_ms: Maximum wait time

        Returns:
            True if data loaded successfully
        """
        try:
            # Wait for KPI cards to have non-empty values
            self.page.wait_for_function("""() => {
                const values = document.querySelectorAll('.kpi-value');
                return values.length >= 4 && Array.from(values).every(v => v.textContent.trim() !== '');
            }""", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def wait_for_alerts_loaded(self, timeout_ms: int = 5000) -> bool:
        """
        Wait for alerts to be loaded and rendered.

        Args:
            timeout_ms: Maximum wait time

        Returns:
            True if alerts loaded
        """
        try:
            self.page.wait_for_function("""() => {
                return document.querySelector('.alert-summary-item') !== null ||
                       document.querySelector('.no-alerts') !== null;
            }""", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def wait_for_timeline_populated(self, timeout_ms: int = 5000) -> bool:
        """
        Wait for timeline lanes to have content.

        Args:
            timeout_ms: Maximum wait time

        Returns:
            True if timeline has content
        """
        try:
            self.page.wait_for_function("""() => {
                return document.querySelectorAll('.contact-block, .event-marker').length > 0;
            }""", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def wait_for_workspace_transition(
        self, target_workspace: str, timeout_ms: int = 3000
    ) -> bool:
        """
        Wait for workspace transition to complete.

        Args:
            target_workspace: Target workspace ID
            timeout_ms: Maximum wait time

        Returns:
            True if transition completed
        """
        workspace_indices = {
            "mission-overview": 0,
            "maneuver-planning": 1,
            "vleo-drag": 2,
            "anomaly-response": 3,
            "payload-ops": 4,
        }
        target_idx = workspace_indices.get(target_workspace, 0)

        try:
            self.page.wait_for_function(f"""() => {{
                const active = document.querySelector('.workspace-item.active');
                if (!active) return false;
                const items = Array.from(document.querySelectorAll('.workspace-item'));
                return items.indexOf(active) === {target_idx};
            }}""", timeout=timeout_ms)
            self.page.wait_for_load_state("networkidle", timeout=timeout_ms)
            return True
        except Exception:
            return False

    # === Artifact Capture Methods ===

    def capture_failure_artifacts(self, test_name: str, output_dir) -> Dict[str, str]:
        """
        Capture diagnostic artifacts on test failure.

        Args:
            test_name: Name of the failing test
            output_dir: Directory to save artifacts (Path object)

        Returns:
            Dictionary mapping artifact names to file paths
        """
        import json
        from pathlib import Path

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        artifacts = {}

        try:
            # Screenshot
            screenshot_path = output_dir / f"{test_name}_screenshot.png"
            self.page.screenshot(path=str(screenshot_path), full_page=True)
            artifacts["screenshot"] = str(screenshot_path)
        except Exception:
            pass

        try:
            # DOM snapshot of key elements
            dom_path = output_dir / f"{test_name}_dom.json"
            dom_content = self.page.evaluate("""() => {
                return {
                    kpis: document.querySelector('.kpi-grid')?.outerHTML || null,
                    alerts: document.querySelector('.alerts-summary')?.outerHTML || null,
                    timeline: document.querySelector('.timeline-panel')?.outerHTML || null,
                    header: document.querySelector('.header-bar')?.outerHTML || null,
                };
            }""")
            with open(dom_path, "w") as f:
                json.dump(dom_content, f, indent=2)
            artifacts["dom_snapshot"] = str(dom_path)
        except Exception:
            pass

        try:
            # Page URL and title
            meta_path = output_dir / f"{test_name}_meta.json"
            meta = {
                "url": self.page.url,
                "title": self.page.title(),
            }
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)
            artifacts["meta"] = str(meta_path)
        except Exception:
            pass

        return artifacts
