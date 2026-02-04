"""Playwright tests for the Architecture Browser (modelui) 6 viewpoints.

Validates that each viewpoint renders readable, interactive content,
not just that the page loads.

Usage:
    # Serve the arch browser first:
    python3 -m http.server 8099 --directory build/modelgen

    # Run tests:
    pytest tests/ete/test_arch_browser.py -v
    pytest tests/ete/test_arch_browser.py -k "logical" -v
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

try:
    from playwright.sync_api import expect

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

if TYPE_CHECKING:
    from playwright.sync_api import Page

pytestmark = [
    pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed"),
    pytest.mark.ete,
]

ARCH_BROWSER_URL = os.environ.get("ARCH_BROWSER_URL", "http://localhost:8099")


@pytest.fixture
def arch_page(page):
    """Create and navigate to the architecture browser page."""
    from .pages.arch_browser_page import ArchBrowserPage

    ap = ArchBrowserPage(page, base_url=ARCH_BROWSER_URL)
    ap.goto()
    ap.wait_for_ready()
    return ap


# ─────────────────────────────────────────────────────────────────────────────
# App Loading & Header
# ─────────────────────────────────────────────────────────────────────────────


class TestAppLoading:
    """Verify the architecture browser loads model data correctly."""

    def test_app_loads_without_error(self, arch_page):
        """App loads model.json and renders without error."""
        assert not arch_page.has_error(), (
            f"App error: {arch_page.get_error_message()}"
        )

    def test_header_shows_title(self, arch_page):
        """Header displays 'Architecture Browser' title."""
        header = arch_page.get_header_title()
        assert "Architecture Browser" in header

    def test_header_shows_node_count(self, arch_page):
        """Header displays a non-zero node count."""
        count = arch_page.get_node_count()
        assert count is not None, "No node count in header"
        assert count > 10, f"Expected >10 nodes, got {count}"

    def test_header_shows_edge_count(self, arch_page):
        """Header displays a non-zero edge count."""
        count = arch_page.get_edge_count()
        assert count is not None, "No edge count in header"
        assert count > 10, f"Expected >10 edges, got {count}"

    def test_viewpoint_tabs_present(self, arch_page):
        """All 6 viewpoint tabs are visible in the header."""
        labels = arch_page.get_viewpoint_buttons()
        expected = ["Context", "Capabilities", "Logical", "Interfaces", "Technical", "Requirements"]
        for exp in expected:
            assert exp in labels, f"Missing viewpoint tab: {exp}"

    def test_no_js_errors_on_load(self, page):
        """No critical JS errors on initial load."""
        errors = []

        def on_console(msg):
            if msg.type == "error":
                text = msg.text
                # Ignore network/fetch errors for missing optional resources
                if "fetch" in text.lower() or "net::" in text.lower():
                    return
                errors.append(text)

        page.on("console", on_console)
        page.goto(ARCH_BROWSER_URL)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        critical = [e for e in errors if "TypeError" in e or "ReferenceError" in e]
        assert len(critical) == 0, (
            f"JS errors on load:\n" + "\n".join(f"  - {e}" for e in critical)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Viewpoint 1: Operational Context
# ─────────────────────────────────────────────────────────────────────────────


class TestOperationalContext:
    """Operational Context view (L0): external actors + system boundary."""

    def test_view_renders(self, arch_page):
        """Switching to Context view renders content."""
        arch_page.switch_viewpoint("operational-context")
        arch_page.page.wait_for_timeout(500)
        assert not arch_page.has_error()

    def test_enterprise_name_visible(self, arch_page):
        """The enterprise (system boundary) box shows a name."""
        arch_page.switch_viewpoint("operational-context")
        arch_page.page.wait_for_timeout(500)
        name = arch_page.get_context_enterprise_name()
        assert name is not None, "No enterprise name found in Context view"
        assert len(name) > 3, f"Enterprise name too short: '{name}'"

    def test_has_external_actors(self, arch_page):
        """At least one external actor is shown."""
        arch_page.switch_viewpoint("operational-context")
        arch_page.page.wait_for_timeout(500)
        # Check that the page contains actor boxes with ACT or SYS labels
        page_text = arch_page.page.evaluate(
            "() => document.getElementById('root')?.textContent ?? ''"
        )
        has_actors = "ACT" in page_text or "SYS" in page_text
        assert has_actors, "No external actors (ACT/SYS labels) found"

    def test_click_enterprise_navigates_to_capabilities(self, arch_page):
        """Clicking the enterprise boundary navigates to Capability Map."""
        arch_page.switch_viewpoint("operational-context")
        arch_page.page.wait_for_timeout(500)

        # Click the "Click to explore capabilities" area
        explore_el = arch_page.page.query_selector("div:has-text('Click to explore capabilities')")
        if explore_el:
            explore_el.click()
            arch_page.page.wait_for_timeout(500)
            # Should now be on capability map — verify SVG is present
            svg = arch_page.page.query_selector("svg")
            assert svg is not None, "Expected SVG canvas after navigating to capabilities"


# ─────────────────────────────────────────────────────────────────────────────
# Viewpoint 2: Capability Map
# ─────────────────────────────────────────────────────────────────────────────


class TestCapabilityMap:
    """Capability Map view (L1): swimlane layout of segments."""

    def test_view_renders_svg(self, arch_page):
        """Capability Map renders an SVG canvas."""
        arch_page.switch_viewpoint("capability-map")
        arch_page.page.wait_for_timeout(500)
        svg = arch_page.page.query_selector("svg")
        assert svg is not None, "No SVG canvas in Capability Map"

    def test_has_segment_columns(self, arch_page):
        """Swimlane has multiple columns for segments."""
        arch_page.switch_viewpoint("capability-map")
        arch_page.page.wait_for_timeout(500)
        labels = arch_page.get_svg_text_labels()
        # Should contain segment names like "Simulation Engine", "Physical Models"
        segment_keywords = ["Engine", "Models", "Activity", "Pipeline", "Visual", "Interface"]
        found = sum(1 for kw in segment_keywords if any(kw.lower() in lbl.lower() for lbl in labels))
        assert found >= 3, (
            f"Expected at least 3 segment names, found {found} in labels: {labels[:20]}"
        )

    def test_has_domain_nodes(self, arch_page):
        """Swimlane columns contain L2 domain nodes."""
        arch_page.switch_viewpoint("capability-map")
        arch_page.page.wait_for_timeout(500)
        count = arch_page.get_svg_node_count()
        # Should have segment header rects + domain rects
        assert count >= 10, f"Expected >=10 SVG rects, got {count}"


# ─────────────────────────────────────────────────────────────────────────────
# Viewpoint 3: Logical Architecture
# ─────────────────────────────────────────────────────────────────────────────


class TestLogicalArchitecture:
    """Logical Architecture view (L1+L2+L3): tree layout with collapse."""

    def test_view_renders_svg(self, arch_page):
        """Logical view renders an SVG tree canvas."""
        arch_page.switch_viewpoint("logical-architecture")
        arch_page.page.wait_for_timeout(500)
        svg = arch_page.page.query_selector("svg")
        assert svg is not None, "No SVG canvas in Logical Architecture"

    def test_tree_has_level_badges(self, arch_page):
        """Tree nodes have level badges (L1, L2, etc.)."""
        arch_page.switch_viewpoint("logical-architecture")
        arch_page.page.wait_for_timeout(500)
        badges = arch_page.get_tree_node_level_badges()
        assert len(badges) > 0, "No level badges found in tree"
        # Should have L1 and L2 visible (L0+L1 auto-expanded)
        level_set = set(badges)
        assert "L1" in level_set or "L2" in level_set, (
            f"Expected L1 or L2 badges, found: {level_set}"
        )

    def test_default_collapse_limits_visible_nodes(self, arch_page):
        """
        Default collapse state shows a manageable number of nodes.

        With L0+L1 auto-expanded, we should see L1 + L2 nodes (not all L3).
        This validates the fix for the '1000-car train' issue.
        """
        arch_page.switch_viewpoint("logical-architecture")
        arch_page.page.wait_for_timeout(500)
        count = arch_page.get_svg_node_count()
        # With proper collapse: should see ~20-40 nodes, not 100+
        assert count < 60, (
            f"Too many visible nodes ({count}). "
            f"Default collapse should limit visible tree to <60 nodes."
        )
        assert count >= 3, f"Too few nodes ({count}), tree may not have rendered"

    def test_tree_has_readable_bounds(self, arch_page):
        """
        Tree content fits within a reasonable bounding box.

        Validates that the tree isn't stretched into an unreadable line.
        """
        arch_page.switch_viewpoint("logical-architecture")
        arch_page.page.wait_for_timeout(500)
        bbox = arch_page.get_svg_viewbox_extent()
        if bbox is None:
            pytest.skip("No SVG bounding box available")

        # Aspect ratio should be reasonable (not a 50:1 train)
        # With L0+L1 expanded, a top-down tree with ~11 nodes may be 10:1
        if bbox["width"] > 0 and bbox["height"] > 0:
            aspect = bbox["width"] / bbox["height"]
            assert aspect < 15, (
                f"Tree aspect ratio {aspect:.1f}:1 is too wide. "
                f"Size: {bbox['width']:.0f}x{bbox['height']:.0f}"
            )

    def test_collapsed_nodes_show_chevron(self, arch_page):
        """Nodes with children show a collapse/expand chevron."""
        arch_page.switch_viewpoint("logical-architecture")
        arch_page.page.wait_for_timeout(500)
        labels = arch_page.get_svg_text_labels()
        # Chevrons are rendered as unicode characters
        has_chevrons = any("\u25B6" in lbl or "\u25BC" in lbl for lbl in labels)
        assert has_chevrons, "No collapse/expand chevrons found in tree nodes"


# ─────────────────────────────────────────────────────────────────────────────
# Viewpoint 4: Interface Contracts
# ─────────────────────────────────────────────────────────────────────────────


class TestInterfaceContracts:
    """Interface Contracts view: card-based layout grouped by domain."""

    def test_view_renders(self, arch_page):
        """Interface Contracts view renders without error."""
        arch_page.switch_viewpoint("interface-contracts")
        arch_page.page.wait_for_timeout(500)
        assert not arch_page.has_error()

    def test_has_interface_or_contract_cards(self, arch_page):
        """View displays INTERFACE or DATA cards."""
        arch_page.switch_viewpoint("interface-contracts")
        arch_page.page.wait_for_timeout(500)
        count = arch_page.get_interface_card_count()
        # Should have at least some interface/contract nodes
        assert count >= 1, "No INTERFACE or DATA cards found"

    def test_cards_grouped_by_domain(self, arch_page):
        """Cards are grouped under domain headings."""
        arch_page.switch_viewpoint("interface-contracts")
        arch_page.page.wait_for_timeout(500)
        groups = arch_page.get_interface_domain_groups()
        assert len(groups) >= 1, "No domain group headings found"

    def test_not_a_long_train(self, arch_page):
        """
        Interface view uses card layout, not a single-row tree.

        The view title and cards should be visible without horizontal scrolling.
        """
        arch_page.switch_viewpoint("interface-contracts")
        arch_page.page.wait_for_timeout(500)
        page_text = arch_page.page.evaluate(
            "() => document.getElementById('root')?.textContent ?? ''"
        )
        assert "Interface Contracts" in page_text, "View title not found"
        # Verify it's not using SVG tree (should be HTML cards)
        svg_in_main = arch_page.page.evaluate("""() => {
            const main = document.querySelector('div[style*="flex: 1"]') ||
                         document.querySelector('div[style*="flex:1"]');
            return main ? main.querySelector('svg') !== null : false;
        }""")
        assert not svg_in_main, "Interface view should use card layout, not SVG tree"


# ─────────────────────────────────────────────────────────────────────────────
# Viewpoint 5: Technical Deployment
# ─────────────────────────────────────────────────────────────────────────────


class TestTechnicalDeployment:
    """Technical Deployment view: force-directed graph."""

    def test_view_renders_svg(self, arch_page):
        """Technical view renders an SVG canvas."""
        arch_page.switch_viewpoint("technical-deployment")
        arch_page.page.wait_for_timeout(1000)  # Force layout needs time
        svg = arch_page.page.query_selector("svg")
        assert svg is not None, "No SVG canvas in Technical Deployment"

    def test_has_graph_nodes(self, arch_page):
        """Force-directed graph has visible nodes."""
        arch_page.switch_viewpoint("technical-deployment")
        arch_page.page.wait_for_timeout(1000)
        count = arch_page.get_force_graph_node_count()
        assert count >= 1, "No graph nodes in Technical Deployment"

    def test_has_legend(self, arch_page):
        """Technical view has an edge legend."""
        arch_page.switch_viewpoint("technical-deployment")
        arch_page.page.wait_for_timeout(500)
        page_text = arch_page.page.evaluate(
            "() => document.getElementById('root')?.textContent ?? ''"
        )
        assert "imports" in page_text or "implements" in page_text, (
            "Edge legend not found in Technical view"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Viewpoint 6: Requirements Decomposition
# ─────────────────────────────────────────────────────────────────────────────


class TestRequirements:
    """Requirements Decomposition view: hierarchical requirement cards."""

    def test_view_renders(self, arch_page):
        """Requirements view renders without error."""
        arch_page.switch_viewpoint("requirements-decomposition")
        arch_page.page.wait_for_timeout(500)
        assert not arch_page.has_error()

    def test_has_title(self, arch_page):
        """View displays 'Requirements Decomposition' heading."""
        arch_page.switch_viewpoint("requirements-decomposition")
        arch_page.page.wait_for_timeout(500)
        page_text = arch_page.page.evaluate(
            "() => document.getElementById('root')?.textContent ?? ''"
        )
        assert "Requirements Decomposition" in page_text

    def test_has_requirement_cards(self, arch_page):
        """View displays requirement cards with type badges."""
        arch_page.switch_viewpoint("requirements-decomposition")
        arch_page.page.wait_for_timeout(500)
        count = arch_page.get_requirement_count()
        assert count >= 3, f"Expected >=3 requirements, got {count}"

    def test_requirements_have_ids(self, arch_page):
        """Requirement cards show REQ-* identifiers."""
        arch_page.switch_viewpoint("requirements-decomposition")
        arch_page.page.wait_for_timeout(500)
        titles = arch_page.get_requirement_titles()
        assert len(titles) >= 3, f"Expected >=3 REQ IDs, got {len(titles)}: {titles}"
        assert any("REQ-N" in t for t in titles), (
            f"No Need requirements found. IDs: {titles}"
        )

    def test_requirements_have_allocation_badges(self, arch_page):
        """At least some requirements show allocation badges to arch nodes."""
        arch_page.switch_viewpoint("requirements-decomposition")
        arch_page.page.wait_for_timeout(500)
        page_text = arch_page.page.evaluate(
            "() => document.getElementById('root')?.textContent ?? ''"
        )
        # Allocation badges show arch node names like "Simulation Engine"
        has_alloc = "Engine" in page_text or "Orbit" in page_text or "Subsystems" in page_text
        assert has_alloc, "No allocation badges found on requirement cards"


# ─────────────────────────────────────────────────────────────────────────────
# Cross-Viewpoint Navigation
# ─────────────────────────────────────────────────────────────────────────────


class TestViewpointSwitching:
    """Test switching between all 6 viewpoints without errors."""

    def test_cycle_all_viewpoints(self, arch_page):
        """Cycle through all 6 viewpoints without JS errors or blank screens."""
        errors = []

        def on_console(msg):
            if msg.type == "error":
                text = msg.text
                if "TypeError" in text or "ReferenceError" in text:
                    errors.append(text)

        arch_page.page.on("console", on_console)

        for vp_id in arch_page.VIEWPOINTS:
            switched = arch_page.switch_viewpoint(vp_id)
            assert switched, f"Failed to switch to {vp_id}"
            arch_page.page.wait_for_timeout(500)
            assert not arch_page.has_error(), (
                f"Error after switching to {vp_id}: {arch_page.get_error_message()}"
            )

        assert len(errors) == 0, (
            f"JS errors during viewpoint cycling:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    def test_rapid_viewpoint_switching(self, arch_page):
        """Rapid switching doesn't crash the app."""
        for _ in range(3):
            for vp_id in arch_page.VIEWPOINTS:
                arch_page.switch_viewpoint(vp_id)
                arch_page.page.wait_for_timeout(100)

        # App should still be functional
        assert not arch_page.has_error()
        # Verify we can still read content
        arch_page.switch_viewpoint("requirements-decomposition")
        arch_page.page.wait_for_timeout(300)
        count = arch_page.get_requirement_count()
        assert count >= 1, "App non-functional after rapid switching"


# ─────────────────────────────────────────────────────────────────────────────
# Hierarchy Navigation Sidebar
# ─────────────────────────────────────────────────────────────────────────────


class TestHierarchyNav:
    """Test the left sidebar hierarchy navigation."""

    def test_sidebar_has_items(self, arch_page):
        """Hierarchy nav sidebar has clickable items."""
        items = arch_page.get_hierarchy_nav_items()
        assert len(items) >= 3, f"Expected >=3 nav items, got {len(items)}"

    def test_sidebar_shows_segments(self, arch_page):
        """Sidebar shows L1 segment names."""
        page_text = arch_page.page.evaluate("""() => {
            const sidebar = document.querySelector('div[style*="width: 280px"]') ||
                           document.querySelector('div[style*="width:280px"]');
            return sidebar ? sidebar.textContent : '';
        }""")
        # Should contain segment names
        assert "Simulation Engine" in page_text or "Physical Models" in page_text, (
            f"Sidebar doesn't show segment names. Content: {page_text[:200]}"
        )
