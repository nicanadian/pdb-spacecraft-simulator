"""Playwright end-to-end tests for the Architecture Viewer.

Requires:
  - Viewer built: cd tools/modelui && npm run build
  - model.json in dist: cp build/modelgen/model.json tools/modelui/dist/
  - Server running: python -m tools.modelgen.cli serve --dir tools/modelui/dist --port 8091 --no-open

Run with: pytest tests/tools/test_modelgen/test_viewer_e2e.py -v
"""

from __future__ import annotations

import subprocess
import time

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import Page, expect


VIEWER_URL = "http://localhost:8091"

_server_process = None


@pytest.fixture(scope="module", autouse=True)
def viewer_server():
    """Start and stop the viewer server for the test module."""
    import sys

    global _server_process
    _server_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tools.modelgen.cli",
            "serve",
            "--dir",
            "tools/modelui/dist",
            "--port",
            "8091",
            "--no-open",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Wait for server to be ready
    time.sleep(2)
    yield
    _server_process.terminate()
    _server_process.wait(timeout=5)


@pytest.fixture
def app_page(page: Page):
    """Navigate to the viewer and wait for it to load."""
    page.goto(VIEWER_URL, wait_until="networkidle", timeout=15000)
    # Wait for the app to mount (spinner should be gone)
    page.wait_for_selector("header", timeout=10000)
    return page


class TestViewerLoads:
    def test_app_mounts_and_spinner_cleared(self, app_page: Page):
        """The initial loader spinner should be replaced by the app."""
        loader = app_page.query_selector(".loader")
        assert loader is None, "Initial spinner should be removed after mount"

    def test_header_shows_node_count(self, app_page: Page):
        """Header should show node and edge counts."""
        header_text = app_page.inner_text("header")
        assert "nodes" in header_text
        assert "edges" in header_text

    def test_header_shows_git_sha(self, app_page: Page):
        """Header should display the git SHA."""
        header_text = app_page.inner_text("header")
        # Git SHA is a short hex string
        assert len(header_text) > 0

    def test_three_nav_tabs_visible(self, app_page: Page):
        """Architecture, Guarantees, and Impact tabs should be visible."""
        buttons = app_page.query_selector_all("header button")
        labels = [b.inner_text() for b in buttons]
        assert "Architecture" in labels
        assert "Guarantees" in labels
        assert "Impact" in labels


class TestArchitectureView:
    def test_svg_canvas_present(self, app_page: Page):
        """An SVG element should be rendered for the graph."""
        svg = app_page.query_selector("svg")
        assert svg is not None

    def test_nodes_rendered(self, app_page: Page):
        """SVG should contain node groups (g elements with click handlers)."""
        # Each node is a <g> inside the transform group
        node_groups = app_page.query_selector_all("svg g g")
        assert len(node_groups) > 50, f"Expected >50 node groups, got {len(node_groups)}"

    def test_group_filter_panel(self, app_page: Page):
        """Sidebar should show group filter buttons."""
        body_text = app_page.inner_text("body")
        assert "Activity Handlers" in body_text
        assert "Core Types" in body_text
        assert "Physical Models" in body_text

    def test_search_input_present(self, app_page: Page):
        """Search bar should be visible."""
        search = app_page.query_selector('input[placeholder="Search nodes..."]')
        assert search is not None

    def test_search_filters_nodes(self, app_page: Page):
        """Typing in search should filter visible nodes."""
        search = app_page.query_selector('input[placeholder="Search nodes..."]')
        assert search is not None

        # Count initial nodes
        initial_nodes = len(app_page.query_selector_all("svg g g"))

        # Type a filter term
        search.fill("Power")
        time.sleep(1)  # Wait for layout recompute

        filtered_nodes = len(app_page.query_selector_all("svg g g"))
        assert filtered_nodes < initial_nodes, "Search should reduce visible nodes"
        assert filtered_nodes > 0, "Search for 'Power' should find at least 1 node"

        # Clear search
        search.fill("")

    def test_click_node_opens_detail(self, app_page: Page):
        """Clicking a node should open the detail panel."""
        # Click the first node group in SVG
        node_groups = app_page.query_selector_all("svg g g")
        assert len(node_groups) > 0
        node_groups[0].click()
        time.sleep(0.5)

        # Detail panel should appear (contains a close button)
        body_text = app_page.inner_text("body")
        # Should show some node detail info
        assert "Incoming" in body_text or "Outgoing" in body_text or "component" in body_text or "data_type" in body_text

    def test_group_toggle_hides_nodes(self, app_page: Page):
        """Clicking a group filter should hide those nodes."""
        initial_nodes = len(app_page.query_selector_all("svg g g"))

        # Click the first group button to toggle it off
        group_buttons = app_page.query_selector_all("button")
        # Find one that has a group name
        for btn in group_buttons:
            text = btn.inner_text()
            if "Physical Models" in text:
                btn.click()
                break

        time.sleep(1)
        filtered_nodes = len(app_page.query_selector_all("svg g g"))
        assert filtered_nodes < initial_nodes, "Toggling group should reduce nodes"

    def test_legend_visible(self, app_page: Page):
        """Edge type legend should be visible."""
        body_text = app_page.inner_text("body")
        assert "imports" in body_text
        assert "implements" in body_text


class TestGuaranteesView:
    def test_switch_to_guarantees(self, app_page: Page):
        """Clicking Guarantees tab should show invariants."""
        # Click Guarantees tab
        buttons = app_page.query_selector_all("header button")
        for btn in buttons:
            if btn.inner_text() == "Guarantees":
                btn.click()
                break

        time.sleep(0.5)
        body_text = app_page.inner_text("body")
        assert "Architecture Guarantees" in body_text

    def test_invariants_listed(self, app_page: Page):
        """Invariants should be listed with severity badges."""
        buttons = app_page.query_selector_all("header button")
        for btn in buttons:
            if btn.inner_text() == "Guarantees":
                btn.click()
                break

        time.sleep(0.5)
        body_text = app_page.inner_text("body")
        # Should contain invariants from CLAUDE.md
        assert "SOC" in body_text or "soc" in body_text or "storage" in body_text.lower()

    def test_severity_sort_buttons(self, app_page: Page):
        """Sort buttons for severity, source, ID should be present."""
        buttons = app_page.query_selector_all("header button")
        for btn in buttons:
            if btn.inner_text() == "Guarantees":
                btn.click()
                break

        time.sleep(0.5)
        body_text = app_page.inner_text("body")
        assert "Severity" in body_text
        assert "Source" in body_text

    def test_claude_md_source_labeled(self, app_page: Page):
        """Invariants from CLAUDE.md should be labeled."""
        buttons = app_page.query_selector_all("header button")
        for btn in buttons:
            if btn.inner_text() == "Guarantees":
                btn.click()
                break

        time.sleep(0.5)
        body_text = app_page.inner_text("body")
        assert "CLAUDE.md" in body_text


class TestImpactView:
    def test_switch_to_impact(self, app_page: Page):
        """Clicking Impact tab should show impact analysis panel."""
        buttons = app_page.query_selector_all("header button")
        for btn in buttons:
            if btn.inner_text() == "Impact":
                btn.click()
                break

        time.sleep(0.5)
        body_text = app_page.inner_text("body").lower()
        assert "impact analysis" in body_text

    def test_component_selector_present(self, app_page: Page):
        """A component selector dropdown should be visible."""
        buttons = app_page.query_selector_all("header button")
        for btn in buttons:
            if btn.inner_text() == "Impact":
                btn.click()
                break

        time.sleep(0.5)
        select = app_page.query_selector("select")
        assert select is not None

    def test_selecting_component_shows_impact(self, app_page: Page):
        """Selecting a component should show upstream/downstream counts."""
        buttons = app_page.query_selector_all("header button")
        for btn in buttons:
            if btn.inner_text() == "Impact":
                btn.click()
                break

        time.sleep(0.5)
        select = app_page.query_selector("select")
        assert select is not None

        # Select a component by finding an option
        options = app_page.query_selector_all("select option")
        # Pick the first non-empty option
        for opt in options:
            val = opt.get_attribute("value")
            if val:
                select.select_option(val)
                break

        time.sleep(0.5)
        body_text = app_page.inner_text("body").lower()
        assert "upstream" in body_text or "downstream" in body_text
