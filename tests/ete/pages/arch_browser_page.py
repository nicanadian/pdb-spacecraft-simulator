"""Page object model for the Architecture Browser (modelui) UI.

Provides methods for interacting with the UAF-lite architecture browser
for Playwright-based testing.
"""

from __future__ import annotations

from typing import Dict, List, Optional

try:
    from playwright.sync_api import Page, expect

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = None


class ArchBrowserPage:
    """
    Page object for the Architecture Browser UI.

    The browser has 6 viewpoints accessible via tab buttons in the header:
    Context, Capabilities, Logical, Interfaces, Technical, Requirements.
    """

    VIEWPOINTS = [
        "operational-context",
        "capability-map",
        "logical-architecture",
        "interface-contracts",
        "technical-deployment",
        "requirements-decomposition",
    ]

    VIEWPOINT_LABELS = {
        "operational-context": "Context",
        "capability-map": "Capabilities",
        "logical-architecture": "Logical",
        "interface-contracts": "Interfaces",
        "technical-deployment": "Technical",
        "requirements-decomposition": "Requirements",
    }

    def __init__(self, page: Page, base_url: str = "http://localhost:8099"):
        self.page = page
        self.base_url = base_url

    def goto(self) -> None:
        """Navigate to the architecture browser."""
        self.page.goto(self.base_url)
        self.page.wait_for_load_state("networkidle")

    def wait_for_ready(self, timeout_ms: int = 15000) -> None:
        """Wait for model data to load and app to render."""
        self.page.wait_for_load_state("networkidle", timeout=timeout_ms)
        # Wait until "Loading..." disappears
        self.page.wait_for_function(
            """() => {
                const root = document.getElementById('root');
                if (!root) return false;
                const text = root.textContent || '';
                return !text.includes('Loading...') && text.length > 50;
            }""",
            timeout=timeout_ms,
        )

    def get_header_title(self) -> str:
        """Get the app header title text."""
        header = self.page.query_selector("header")
        if header:
            return header.inner_text()
        return ""

    def get_node_count(self) -> Optional[int]:
        """Extract node count from the header stats badge."""
        header_text = self.get_header_title()
        import re
        match = re.search(r"(\d+)\s*nodes", header_text)
        if match:
            return int(match.group(1))
        return None

    def get_edge_count(self) -> Optional[int]:
        """Extract edge count from the header stats badge."""
        header_text = self.get_header_title()
        import re
        match = re.search(r"(\d+)\s*edges", header_text)
        if match:
            return int(match.group(1))
        return None

    def has_error(self) -> bool:
        """Check if an error message is displayed."""
        root_text = self.page.evaluate(
            "() => document.getElementById('root')?.textContent ?? ''"
        )
        return "Error:" in root_text

    def get_error_message(self) -> Optional[str]:
        """Get the error message if displayed."""
        root_text = self.page.evaluate(
            "() => document.getElementById('root')?.textContent ?? ''"
        )
        if "Error:" in root_text:
            import re
            match = re.search(r"Error:\s*(.+)", root_text)
            if match:
                return match.group(1).strip()
        return None

    # ── Viewpoint Navigation ──

    def get_viewpoint_buttons(self) -> List[str]:
        """Get labels of all viewpoint tab buttons."""
        buttons = self.page.query_selector_all("header button")
        labels = []
        for btn in buttons:
            text = btn.inner_text().strip()
            if text in self.VIEWPOINT_LABELS.values():
                labels.append(text)
        return labels

    def get_active_viewpoint_label(self) -> Optional[str]:
        """Get the label of the currently active viewpoint tab."""
        buttons = self.page.query_selector_all("header button")
        for btn in buttons:
            text = btn.inner_text().strip()
            if text not in self.VIEWPOINT_LABELS.values():
                continue
            # Active tab has brighter text and background
            bg = btn.evaluate("el => getComputedStyle(el).backgroundColor")
            if bg and "51, 65, 85" in bg:  # #334155 = active
                return text
        return None

    def switch_viewpoint(self, viewpoint_id: str) -> bool:
        """
        Switch to a viewpoint by its ID.

        Args:
            viewpoint_id: One of the VIEWPOINTS IDs

        Returns:
            True if the button was found and clicked
        """
        label = self.VIEWPOINT_LABELS.get(viewpoint_id)
        if not label:
            return False

        buttons = self.page.query_selector_all("header button")
        for btn in buttons:
            text = btn.inner_text().strip()
            if text == label:
                btn.click()
                self.page.wait_for_timeout(300)
                return True
        return False

    # ── SVG Canvas Queries ──

    def get_svg_node_count(self) -> int:
        """Count SVG <rect> or <g> nodes in the main canvas (tree/swimlane views)."""
        return self.page.evaluate("""() => {
            const main = document.querySelector('div[style*="flex: 1"] svg') ||
                         document.querySelector('div[style*="flex:1"] svg');
            if (!main) return 0;
            // Tree nodes: <g> elements with a <rect> child
            const groups = main.querySelectorAll('g > rect');
            return groups.length;
        }""")

    def get_svg_text_labels(self) -> List[str]:
        """Get all visible text labels in the main SVG canvas."""
        return self.page.evaluate("""() => {
            const main = document.querySelector('div[style*="flex: 1"] svg') ||
                         document.querySelector('div[style*="flex:1"] svg');
            if (!main) return [];
            const texts = main.querySelectorAll('text');
            return Array.from(texts)
                .map(t => t.textContent?.trim())
                .filter(t => t && t.length > 0 && t.length < 50);
        }""")

    def get_svg_viewbox_extent(self) -> Optional[Dict]:
        """Get the bounding box of all SVG content to assess readability."""
        return self.page.evaluate("""() => {
            const svg = document.querySelector('div[style*="flex: 1"] svg') ||
                        document.querySelector('div[style*="flex:1"] svg');
            if (!svg) return null;
            const g = svg.querySelector('g[transform]');
            if (!g) return null;
            const bbox = g.getBBox();
            return {
                x: bbox.x, y: bbox.y,
                width: bbox.width, height: bbox.height,
            };
        }""")

    # ── Operational Context View ──

    def get_context_external_actors(self) -> List[str]:
        """Get names of external actors in the operational context view."""
        return self.page.evaluate("""() => {
            const actors = [];
            const divs = document.querySelectorAll('div');
            for (const div of divs) {
                const badge = div.querySelector('div');
                if (badge && (badge.textContent === 'ACT' || badge.textContent === 'SYS')) {
                    // Next sibling or child has the name
                    const nameEl = badge.nextElementSibling || div.children[1];
                    if (nameEl) actors.push(nameEl.textContent?.trim() || '');
                }
            }
            return actors.filter(a => a.length > 0);
        }""")

    def get_context_enterprise_name(self) -> Optional[str]:
        """Get the enterprise name from the system boundary box."""
        return self.page.evaluate("""() => {
            // The enterprise box has "Click to explore capabilities" text
            const divs = document.querySelectorAll('div');
            for (const div of divs) {
                if (div.textContent?.includes('Click to explore capabilities')) {
                    const nameEl = div.querySelector('div');
                    if (nameEl) return nameEl.textContent?.trim() || null;
                }
            }
            return null;
        }""")

    # ── Capability Map (Swimlane) View ──

    def get_swimlane_column_count(self) -> int:
        """Count swimlane columns (segments) in capability map."""
        return self.page.evaluate("""() => {
            const svg = document.querySelector('div[style*="flex: 1"] svg') ||
                        document.querySelector('div[style*="flex:1"] svg');
            if (!svg) return 0;
            // Column headers are rect elements with specific styling
            const rects = svg.querySelectorAll('rect[fill]');
            let columns = 0;
            for (const r of rects) {
                const fill = r.getAttribute('fill') || '';
                // Column headers have segment colors
                if (fill && fill !== 'none' && !fill.includes('22') && r.getAttribute('height') === '36') {
                    columns++;
                }
            }
            return columns;
        }""")

    def get_swimlane_column_labels(self) -> List[str]:
        """Get column header labels from the swimlane view."""
        return self.page.evaluate("""() => {
            const svg = document.querySelector('div[style*="flex: 1"] svg') ||
                        document.querySelector('div[style*="flex:1"] svg');
            if (!svg) return [];
            // Column labels are white text at the top
            const texts = svg.querySelectorAll('text');
            const labels = [];
            for (const t of texts) {
                const fill = t.getAttribute('fill') || '';
                const fontSize = t.getAttribute('font-size') || '';
                if (fill === '#f1f5f9' && fontSize === '12') {
                    labels.push(t.textContent?.trim() || '');
                }
            }
            return labels.filter(l => l.length > 0);
        }""")

    # ── Interface Contracts View ──

    def get_interface_card_count(self) -> int:
        """Count interface/contract cards in the interface contracts view."""
        return self.page.evaluate("""() => {
            // Cards have INTERFACE or DATA labels
            const spans = document.querySelectorAll('span');
            let count = 0;
            for (const s of spans) {
                const text = s.textContent?.trim() || '';
                if (text === 'INTERFACE' || text === 'DATA') count++;
            }
            return count;
        }""")

    def get_interface_domain_groups(self) -> List[str]:
        """Get the domain group headings in interface contracts view."""
        return self.page.evaluate("""() => {
            // Domain headings are uppercase, cyan, 13px
            const divs = document.querySelectorAll('div');
            const groups = [];
            for (const div of divs) {
                const style = div.getAttribute('style') || '';
                if (style.includes('text-transform') && style.includes('uppercase')
                    && style.includes('#06b6d4')) {
                    const text = div.textContent?.trim();
                    if (text && text.length > 0) groups.push(text);
                }
            }
            return groups;
        }""")

    # ── Requirements View ──

    def get_requirement_count(self) -> int:
        """Count requirement cards in the requirements view."""
        return self.page.evaluate("""() => {
            // Requirement type badges (NEED, CAPABILITYREQUIREMENT, etc.)
            const spans = document.querySelectorAll('span');
            let count = 0;
            const reqTypes = ['NEED', 'CAPABILITYREQUIREMENT', 'ARCHITECTURECONSTRAINT',
                            'INTERFACECONTRACT', 'QUALITYATTRIBUTE', 'VERIFICATIONREQUIREMENT'];
            for (const s of spans) {
                const text = (s.textContent?.trim() || '').toUpperCase();
                if (reqTypes.includes(text)) count++;
            }
            return count;
        }""")

    def get_requirement_titles(self) -> List[str]:
        """Get requirement title texts."""
        return self.page.evaluate("""() => {
            // Requirements have IDs like REQ-N-001 as monospace text
            const monoSpans = document.querySelectorAll('span');
            const ids = [];
            for (const s of monoSpans) {
                const text = s.textContent?.trim() || '';
                if (text.match(/^REQ-/)) ids.push(text);
            }
            return ids;
        }""")

    # ── Hierarchy Nav Sidebar ──

    def get_hierarchy_nav_items(self) -> List[str]:
        """Get visible items in the hierarchy navigation sidebar."""
        return self.page.evaluate("""() => {
            // Sidebar is the first child div after header
            const sidebar = document.querySelector('div[style*="width: 280px"]') ||
                           document.querySelector('div[style*="width:280px"]');
            if (!sidebar) return [];
            const items = sidebar.querySelectorAll('button');
            return Array.from(items)
                .map(el => el.textContent?.trim() || '')
                .filter(t => t.length > 0 && t.length < 100);
        }""")

    # ── Logical Architecture View ──

    def get_tree_node_labels(self) -> List[str]:
        """Get visible node labels in the tree canvas."""
        return self.get_svg_text_labels()

    def get_tree_node_level_badges(self) -> List[str]:
        """Get level badges (L0, L1, L2, L3) visible in the tree."""
        return self.page.evaluate("""() => {
            const svg = document.querySelector('div[style*="flex: 1"] svg') ||
                        document.querySelector('div[style*="flex:1"] svg');
            if (!svg) return [];
            const texts = svg.querySelectorAll('text');
            const levels = [];
            for (const t of texts) {
                const text = t.textContent?.trim() || '';
                if (/^L[0-4]$/.test(text)) levels.push(text);
            }
            return levels;
        }""")

    # ── Technical Deployment View ──

    def get_force_graph_node_count(self) -> int:
        """Count nodes in the force-directed graph canvas."""
        return self.page.evaluate("""() => {
            const svg = document.querySelector('div[style*="flex: 1"] svg') ||
                        document.querySelector('div[style*="flex:1"] svg');
            if (!svg) return 0;
            return svg.querySelectorAll('circle, rect').length;
        }""")

    # ── General Interaction ──

    def click_node_by_text(self, text: str) -> bool:
        """Click a node containing the given text."""
        element = self.page.query_selector(f"text:has-text('{text}')")
        if element:
            element.click()
            self.page.wait_for_timeout(200)
            return True
        # Try div-based nodes
        element = self.page.query_selector(f"div:has-text('{text}')")
        if element:
            element.click()
            self.page.wait_for_timeout(200)
            return True
        return False

    def has_js_errors(self) -> List[str]:
        """Collect JS console errors. Must be called BEFORE navigating."""
        errors = []

        def handle(msg):
            if msg.type == "error":
                errors.append(msg.text)

        self.page.on("console", handle)
        return errors

    def capture_screenshot(self, path: str) -> None:
        """Capture a screenshot."""
        self.page.screenshot(path=path, full_page=True)
