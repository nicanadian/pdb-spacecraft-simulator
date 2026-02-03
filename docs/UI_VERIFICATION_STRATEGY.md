# Web UI Verification Strategy for ETE Test Suite

## Executive Summary

This document provides a comprehensive strategy for refining Web UI verification in the ETE test suite. The current tests verify basic element presence but lack scenario-specific validation that builds confidence in the correctness of the UI-to-backend data flow.

**Current State:**
- 186 tests pass, with 9 intentional skips
- ViewerPage has 20+ methods, but ~50% are underutilized
- No `data-testid` attributes in viewer; relies on CSS class selectors
- Event counts verified, but not event content structure
- Timeline scrubbing tested, but not timeline content accuracy

**Recommended Improvements:**
- Add 47 new scenario-specific UI verification assertions
- Introduce 12 reusable verification primitives
- Add data-testid attributes to 23 key UI elements
- Create deterministic checkpoints for 6 visualization types

---

## UI Verification Strategy

### 1. Verification Philosophy

#### Principle: Verify Outcomes, Not Presence

**Do This:**
```python
# Verify KPI card shows correct event count from simulation
kpi_events = viewer_page.get_kpi_value("Events")
assert kpi_events == completed_run.event_count, (
    f"KPI Events mismatch: UI shows {kpi_events}, simulation produced {completed_run.event_count}"
)
```

**Not This:**
```python
# Just checking element exists
assert viewer_page.page.locator(".kpi-card").count() == 4
```

#### Principle: Scenario-Specific Assertions

Different scenarios require different verification focus:

| Scenario Type | Primary UI Verification Focus |
|---------------|-------------------------------|
| R-series (Maneuvers) | Maneuver Planning workspace, sequence panel, timeline events |
| N-series (LEO Drag) | VLEO Drag workspace, altitude visualization, atmospheric effects |
| Pure Propagation | Mission Overview, trajectory accuracy, contact windows |
| Anomaly Scenarios | Anomaly Response workspace, alert threads, consequence chains |

#### Principle: Semantic Over Structural

```python
# Semantic (robust to UI changes)
alerts = viewer_page.get_alerts_by_severity("failure")
assert len(alerts) == expected_failures

# Structural (brittle to UI changes)
failure_cards = page.locator(".alert-card.failure")
assert failure_cards.count() == expected_failures
```

### 2. Selector Strategy

#### Priority Order for Selectors

1. **data-testid** (most stable, not yet in codebase)
2. **ARIA roles and labels** (accessible, semantic)
3. **CSS classes with semantic meaning** (current approach)
4. **Element structure** (least stable, avoid)

#### Recommended Test IDs to Add

```typescript
// viewer/src/components/shell/HeaderBar.tsx
<div class="context-chips" data-testid="context-chips">
  <span class="chip" data-testid="chip-plan-id">{planId}</span>
  <span class="chip" data-testid="chip-fidelity">{fidelity}</span>
  <span class="chip" data-testid="chip-duration">{duration}</span>
</div>
<button class="alert-button" data-testid="alert-counter">
  {alertCount}
</button>

// viewer/src/components/alerts/AlertsSummary.tsx
<div class="alerts-summary" data-testid="alerts-summary">
  <div class="alert-summary-item" data-testid={`alert-${alert.id}`}>

// viewer/src/workspaces/MissionOverview.tsx
<div class="kpi-grid" data-testid="kpi-grid">
  <div class="kpi-card" data-testid="kpi-elapsed-time">
  <div class="kpi-card" data-testid="kpi-events">
  <div class="kpi-card" data-testid="kpi-contacts">
  <div class="kpi-card" data-testid="kpi-fidelity">

// viewer/src/components/timeline/TimelinePanel.tsx
<div class="contact-block" data-testid={`contact-${contact.id}`}>
<div class="event-marker" data-testid={`event-${event.id}`}>
<div class="time-cursor" data-testid="timeline-cursor">
```

### 3. Reusable Verification Primitives

Add these methods to `tests/ete/pages/viewer_page.py`:

```python
class ViewerPage:
    # === Existing Methods (Enhanced) ===

    def get_kpi_values(self) -> Dict[str, str]:
        """Get all KPI card values from Mission Overview."""
        kpis = {}
        cards = self.page.query_selector_all(".kpi-card")
        for card in cards:
            label = card.query_selector(".kpi-label").inner_text()
            value = card.query_selector(".kpi-value").inner_text()
            kpis[label.lower()] = value
        return kpis

    def get_context_chips(self) -> Dict[str, str]:
        """Get header context chips (plan, fidelity, duration)."""
        chips = {}
        elements = self.page.query_selector_all(".context-chips .chip")
        # Order: Plan ID, Fidelity, Duration
        keys = ["plan_id", "fidelity", "duration"]
        for key, el in zip(keys, elements):
            chips[key] = el.inner_text()
        return chips

    def get_timeline_contacts(self) -> List[Dict]:
        """Get contact blocks from timeline visualization."""
        contacts = []
        blocks = self.page.query_selector_all(".contact-block")
        for block in blocks:
            contact = {
                "station": block.get_attribute("title") or "",
                "left_pct": float(block.evaluate("el => el.style.left").replace("%", "")),
                "width_pct": float(block.evaluate("el => el.style.width").replace("%", "")),
            }
            contacts.append(contact)
        return contacts

    def get_timeline_events(self) -> List[Dict]:
        """Get event markers from timeline visualization."""
        events = []
        markers = self.page.query_selector_all(".event-marker")
        for marker in markers:
            severity_classes = marker.get_attribute("class").split()
            severity = next((c for c in ["failure", "warning", "info"] if c in severity_classes), "info")
            events.append({
                "severity": severity,
                "left_pct": float(marker.evaluate("el => el.style.left").replace("%", "")),
            })
        return events

    def get_alerts_by_severity(self, severity: str) -> List[Dict]:
        """Get alerts filtered by severity level."""
        alerts = []
        items = self.page.query_selector_all(f".alert-summary-item.{severity}, .alert-card.{severity}")
        for item in items:
            alerts.append({
                "title": item.query_selector(".alert-title, .item-title").inner_text(),
                "severity": severity,
            })
        return alerts

    def get_alert_thread_structure(self) -> List[Dict]:
        """Get alert thread structure with root causes and consequences."""
        threads = []
        thread_els = self.page.query_selector_all(".alert-thread")
        for thread in thread_els:
            root = thread.query_selector(".thread-root .alert-card")
            consequences = thread.query_selector_all(".thread-consequences .alert-card")
            threads.append({
                "root_title": root.query_selector(".alert-title").inner_text() if root else None,
                "consequence_count": len(consequences),
            })
        return threads

    # === Playback Control Methods ===

    def get_playback_state(self) -> Dict:
        """Get current playback state."""
        play_btn = self.page.query_selector(".play-button")
        is_playing = "playing" in (play_btn.get_attribute("class") or "")

        time_display = self.page.query_selector(".time-display")
        current_time = time_display.inner_text() if time_display else "0:00 / 0:00"

        speed_select = self.page.query_selector(".speed-control select")
        speed = speed_select.input_value() if speed_select else "1"

        return {
            "is_playing": is_playing,
            "current_time": current_time,
            "speed": speed,
        }

    def click_playback_control(self, control: str) -> None:
        """Click a playback control button."""
        index_map = {"start": 0, "back": 1, "play": 2, "forward": 3, "end": 4}
        if control == "play":
            self.page.click(".play-button")
        else:
            btns = self.page.query_selector_all(".playback-controls button")
            btns[index_map[control]].click()

    def set_playback_speed(self, speed: str) -> None:
        """Set playback speed (1, 10, 60, 300, 1000)."""
        self.page.select_option(".speed-control select", speed)

    # === Cesium 3D Verification Methods ===

    def get_cesium_entities(self) -> List[str]:
        """Get list of entity IDs in Cesium viewer."""
        return self.page.evaluate("""() => {
            if (!window.cesiumViewer) return [];
            return window.cesiumViewer.entities.values.map(e => e.id);
        }""")

    def select_cesium_entity(self, entity_id: str) -> bool:
        """Select an entity in the 3D viewer by ID."""
        return self.page.evaluate(f"""() => {{
            if (!window.cesiumViewer) return false;
            const entity = window.cesiumViewer.entities.getById('{entity_id}');
            if (!entity) return false;
            window.cesiumViewer.selectedEntity = entity;
            return true;
        }}""")

    def get_telemetry_inspector_data(self) -> Optional[Dict]:
        """Get data from the telemetry inspector panel (when entity selected)."""
        inspector = self.page.query_selector(".inspector-wrapper")
        if not inspector or not inspector.is_visible():
            return None
        # Parse inspector fields
        return {
            "visible": True,
            "content": inspector.inner_text(),
        }

    # === State Transition Helpers ===

    def wait_for_data_loaded(self, timeout_ms: int = 10000) -> bool:
        """Wait for simulation data to be fully loaded."""
        try:
            # Wait for KPI cards to have non-empty values
            self.page.wait_for_function("""() => {
                const values = document.querySelectorAll('.kpi-value');
                return values.length >= 4 && Array.from(values).every(v => v.textContent.trim() !== '');
            }""", timeout=timeout_ms)
            return True
        except:
            return False

    def wait_for_alerts_loaded(self, timeout_ms: int = 5000) -> bool:
        """Wait for alerts to be loaded and rendered."""
        try:
            self.page.wait_for_function("""() => {
                // Either we have alerts rendered, or the no-alerts indicator
                return document.querySelector('.alert-summary-item') !== null ||
                       document.querySelector('.no-alerts') !== null;
            }""", timeout=timeout_ms)
            return True
        except:
            return False

    def wait_for_timeline_populated(self, timeout_ms: int = 5000) -> bool:
        """Wait for timeline lanes to have content."""
        try:
            self.page.wait_for_function("""() => {
                return document.querySelectorAll('.contact-block, .event-marker').length > 0;
            }""", timeout=timeout_ms)
            return True
        except:
            return False

    # === Artifact Export Helpers ===

    def capture_failure_artifacts(self, test_name: str, output_dir: Path) -> Dict[str, Path]:
        """Capture diagnostic artifacts on test failure."""
        artifacts = {}

        # Screenshot
        screenshot_path = output_dir / f"{test_name}_screenshot.png"
        self.page.screenshot(path=str(screenshot_path), full_page=True)
        artifacts["screenshot"] = screenshot_path

        # Console logs
        logs_path = output_dir / f"{test_name}_console.json"
        logs = self.page.evaluate("() => window.__consoleLogs || []")
        with open(logs_path, "w") as f:
            json.dump(logs, f, indent=2)
        artifacts["console_logs"] = logs_path

        # DOM snapshot (key elements only)
        dom_path = output_dir / f"{test_name}_dom.html"
        dom_content = self.page.evaluate("""() => {
            return {
                kpis: document.querySelector('.kpi-grid')?.outerHTML,
                alerts: document.querySelector('.alerts-summary')?.outerHTML,
                timeline: document.querySelector('.timeline-panel')?.outerHTML,
            };
        }""")
        with open(dom_path, "w") as f:
            json.dump(dom_content, f, indent=2)
        artifacts["dom_snapshot"] = dom_path

        return artifacts
```

### 4. Async State Transition Handling

```python
# Pattern for waiting on state transitions

def wait_for_workspace_transition(viewer_page: ViewerPage, target_workspace: str, timeout_ms: int = 3000) -> bool:
    """Wait for workspace transition to complete."""
    try:
        viewer_page.page.wait_for_function(f"""() => {{
            const active = document.querySelector('.workspace-item.active');
            if (!active) return false;
            const items = Array.from(document.querySelectorAll('.workspace-item'));
            const targetIndex = {{'mission-overview': 0, 'maneuver-planning': 1, 'vleo-drag': 2, 'anomaly-response': 3, 'payload-ops': 4}}['{target_workspace}'];
            return items.indexOf(active) === targetIndex;
        }}""", timeout=timeout_ms)

        # Additional wait for workspace content to render
        viewer_page.page.wait_for_load_state("networkidle", timeout=timeout_ms)
        return True
    except:
        return False


def wait_for_playback_state(viewer_page: ViewerPage, expected_playing: bool, timeout_ms: int = 2000) -> bool:
    """Wait for playback to reach expected state."""
    try:
        viewer_page.page.wait_for_function(f"""() => {{
            const btn = document.querySelector('.play-button');
            const isPlaying = btn?.classList.contains('playing') || false;
            return isPlaying === {str(expected_playing).lower()};
        }}""", timeout=timeout_ms)
        return True
    except:
        return False
```

---

## Scenario Refinements

### Scenario: R01 - Finite Burn Maneuver

**Scenario Intent:** Validate that a finite burn maneuver is correctly displayed in the UI, with proper event markers and state transitions.

**UI Pages Involved:**
- Mission Overview (initial load)
- Maneuver Planning (primary workspace for this scenario)
- Anomaly Response (if constraints violated)

**Key User Actions:**
1. Load simulation run with R01 case data
2. Navigate to Maneuver Planning workspace
3. View sequence panel for maneuver activities
4. Verify timeline shows maneuver event markers
5. Scrub to maneuver start time
6. Verify 3D view shows thrust vector (if visualized)

**High-Value Assertions:**

| Checkpoint | Before | After | Expected Result |
|------------|--------|-------|-----------------|
| Load run | Empty viewer | Data loaded | KPI Events = simulation event count |
| KPI Fidelity | - | After load | Shows "MEDIUM" or "HIGH" (not "LOW" for R-series) |
| Timeline events | Empty | After load | Contains ≥1 event marker at maneuver time |
| Maneuver workspace | Overview active | Click maneuver-planning | Sequence panel visible |
| Sequence panel | - | In maneuver workspace | Shows finite burn activity with parameters |
| Timeline scrub | t=0 | t=maneuver_start | Time cursor at ~50% (if maneuver at midpoint) |

**Visualization Verification:**
```python
def test_r01_maneuver_ui_validation(self, viewer_page, completed_run):
    """R01: Finite burn maneuver UI validation."""
    viewer_page.load_run(completed_run.path)
    viewer_page.wait_for_data_loaded()

    # 1. Verify context chips show correct fidelity
    chips = viewer_page.get_context_chips()
    assert chips["fidelity"] in ["MEDIUM", "HIGH"], (
        f"R-series scenarios should use MEDIUM/HIGH fidelity, got {chips['fidelity']}"
    )

    # 2. Verify KPI event count matches simulation
    kpis = viewer_page.get_kpi_values()
    expected_events = len(completed_run.events)
    assert kpis.get("events") == str(expected_events), (
        f"KPI Events mismatch: UI shows {kpis.get('events')}, expected {expected_events}"
    )

    # 3. Switch to Maneuver Planning workspace
    viewer_page.switch_workspace("maneuver-planning")
    wait_for_workspace_transition(viewer_page, "maneuver-planning")

    # 4. Verify sequence panel has maneuver activity
    sequence = viewer_page.page.query_selector(".sequence-panel")
    assert sequence and sequence.is_visible(), "Sequence panel should be visible in Maneuver Planning"

    activities = viewer_page.page.query_selector_all(".activity-item, .sequence-item")
    maneuver_activities = [a for a in activities if "burn" in a.inner_text().lower() or "maneuver" in a.inner_text().lower()]
    assert len(maneuver_activities) >= 1, "Should have at least one maneuver/burn activity in sequence"

    # 5. Verify timeline has event markers at correct positions
    timeline_events = viewer_page.get_timeline_events()
    assert len(timeline_events) >= 1, "Timeline should have event markers"

    # 6. Scrub to maneuver time and verify cursor position
    # Maneuver typically at ~50% of timeline for R01
    viewer_page.scrub_to_time(0.5)
    time.sleep(0.5)  # Wait for UI update

    cursor = viewer_page.page.query_selector(".time-cursor")
    cursor_left = float(cursor.evaluate("el => el.style.left").replace("%", ""))
    assert 45 <= cursor_left <= 55, f"Cursor should be near 50%, got {cursor_left}%"
```

**Missing Edge Cases:**
- Maneuver that spans eclipse transition
- Multi-segment maneuver (start, coast, end)
- Maneuver with constraint violation (e.g., propellant exhaustion)

**Missing/Weak UI/UX Elements:**
- **P1**: No visual indicator of thrust magnitude on timeline
- **P1**: Sequence panel doesn't show maneuver parameters (delta-V, duration)
- **P2**: No delta-V progress indicator during maneuver

---

### Scenario: N01 - LEO Drag (10-Day)

**Scenario Intent:** Validate long-duration drag compensation scenario with altitude decay visualization.

**UI Pages Involved:**
- Mission Overview (quick status check)
- VLEO Drag workspace (primary for this scenario)

**Key User Actions:**
1. Load N01 simulation run
2. Navigate to VLEO Drag workspace
3. Verify altitude trend visualization
4. Check for drag-related constraint events
5. Verify contact windows affected by orbit decay

**High-Value Assertions:**

| Checkpoint | Expected Result |
|------------|-----------------|
| Duration chip | Shows ~10 days ("240 hours" or similar) |
| KPI contacts | Multiple contacts (10-day span) |
| VLEO workspace | Altitude visualization present |
| Altitude trend | Shows decay over time (not constant) |
| Timeline contacts | Many contact blocks (10+ days of passes) |

**Visualization Verification:**
```python
def test_n01_vleo_drag_ui_validation(self, viewer_page, completed_run):
    """N01: LEO drag 10-day scenario UI validation."""
    viewer_page.load_run(completed_run.path)
    viewer_page.wait_for_data_loaded()

    # 1. Verify duration is ~10 days
    chips = viewer_page.get_context_chips()
    duration_text = chips.get("duration", "")
    # Duration could be "240h", "10d", "10 days", etc.
    assert any(x in duration_text.lower() for x in ["240", "10d", "10 day"]), (
        f"N01 should show ~10-day duration, got {duration_text}"
    )

    # 2. Verify many contacts for multi-day mission
    kpis = viewer_page.get_kpi_values()
    contacts_count = int(kpis.get("contacts", "0").split()[0])  # May include unit
    assert contacts_count >= 50, (
        f"10-day LEO mission should have 50+ contacts, got {contacts_count}"
    )

    # 3. Navigate to VLEO Drag workspace
    viewer_page.switch_workspace("vleo-drag")
    wait_for_workspace_transition(viewer_page, "vleo-drag")

    # 4. Verify altitude visualization exists
    # (Implementation depends on actual VLEO workspace content)
    workspace_content = viewer_page.page.query_selector(".workspace-content")
    assert workspace_content and workspace_content.is_visible()

    # 5. Verify timeline has many contact blocks
    timeline_contacts = viewer_page.get_timeline_contacts()
    assert len(timeline_contacts) >= 10, (
        f"Long-duration mission should show many contacts on timeline, got {len(timeline_contacts)}"
    )
```

**Missing Edge Cases:**
- Orbit decay causing missed contact windows
- Atmospheric density spike event
- Decay rate exceeding predictions

**Missing/Weak UI/UX Elements:**
- **P0**: VLEO workspace may not show altitude decay graph
- **P1**: No perigee altitude trend line
- **P2**: No atmospheric density overlay

---

### Scenario: Anomaly Response (Alert Threads)

**Scenario Intent:** Validate that constraint violations create proper alert threads with root causes and consequences.

**UI Pages Involved:**
- Anomaly Response (primary)
- Mission Overview (alert counter verification)

**Key User Actions:**
1. Load simulation run with constraint violations
2. Verify alert counter in header shows correct count
3. Navigate to Anomaly Response workspace
4. Verify alert threads show root causes and consequences
5. Click on an alert to jump to timestamp
6. Verify suggested actions are present

**High-Value Assertions:**

| Checkpoint | Expected Result |
|------------|-----------------|
| Header alert counter | Shows total alert count |
| Anomaly workspace | Alert Center fully visible |
| Alert threads | Threaded structure with connectors |
| Alert severity colors | Correct color for failure/warning/info |
| Click alert | Jumps to alert timestamp on timeline |
| Suggested actions | Buttons present for actionable alerts |

**Visualization Verification:**
```python
def test_anomaly_response_ui_validation(self, viewer_page, completed_run):
    """Anomaly Response: Alert thread and consequence UI validation."""
    # Use a run known to have constraint violations
    viewer_page.load_run(completed_run.path)
    viewer_page.wait_for_data_loaded()
    viewer_page.wait_for_alerts_loaded()

    # 1. Verify alert counter in header
    alert_btn = viewer_page.page.query_selector(".alert-button")
    if alert_btn:
        alert_count_text = alert_btn.inner_text()
        expected_count = len([e for e in completed_run.events if e.get("severity") in ["warning", "failure"]])
        # Parse count from button text (may be just number or "5 alerts")
        actual_count = int(''.join(c for c in alert_count_text if c.isdigit()) or "0")
        assert actual_count == expected_count, (
            f"Alert counter mismatch: header shows {actual_count}, expected {expected_count}"
        )

    # 2. Navigate to Anomaly Response workspace
    viewer_page.switch_workspace("anomaly-response")
    wait_for_workspace_transition(viewer_page, "anomaly-response")

    # 3. Verify Alert Center is visible
    alert_center = viewer_page.page.query_selector(".alert-center")
    assert alert_center and alert_center.is_visible(), "Alert Center should be visible"

    # 4. Verify alert threads structure
    threads = viewer_page.get_alert_thread_structure()
    if len(threads) > 0:
        # At least one thread should have a root cause
        assert any(t["root_title"] is not None for t in threads), (
            "Alert threads should have identifiable root causes"
        )

    # 5. Verify severity colors are correct
    failure_alerts = viewer_page.get_alerts_by_severity("failure")
    warning_alerts = viewer_page.get_alerts_by_severity("warning")
    info_alerts = viewer_page.get_alerts_by_severity("info")

    total_categorized = len(failure_alerts) + len(warning_alerts) + len(info_alerts)
    total_in_sim = len(completed_run.events)

    # All events should be categorized
    assert total_categorized >= total_in_sim * 0.9, (
        f"Most events should be categorized by severity: {total_categorized} of {total_in_sim}"
    )

    # 6. Click an alert and verify navigation
    first_alert = viewer_page.page.query_selector(".alert-card, .alert-summary-item")
    if first_alert:
        first_alert.click()
        time.sleep(0.5)
        # Verify timeline cursor moved (rough check)
        cursor = viewer_page.page.query_selector(".time-cursor")
        assert cursor, "Time cursor should exist after clicking alert"
```

**Missing Edge Cases:**
- Alert with no suggested actions
- Long consequence chain (3+ levels deep)
- Alert acknowledgment workflow
- Filtering alerts by severity

**Missing/Weak UI/UX Elements:**
- **P1**: No alert acknowledgment button
- **P1**: No filter controls for severity
- **P2**: Consequence connector lines may be hard to follow

---

### Scenario: Pure Propagation (Baseline)

**Scenario Intent:** Validate basic propagation with no activities - verify contact windows and eclipse computation are displayed correctly.

**UI Pages Involved:**
- Mission Overview (primary)
- Timeline (contacts and eclipses)

**High-Value Assertions:**

| Checkpoint | Expected Result |
|------------|-----------------|
| Fidelity chip | Shows configured fidelity |
| KPI contacts | Matches access_windows.json count |
| Timeline contacts | Blue blocks at correct positions |
| Contact tooltips | Show station names |
| No events (or minimal) | No constraint violations expected |

**Visualization Verification:**
```python
def test_pure_propagation_ui_validation(self, viewer_page, completed_run):
    """Pure propagation: Contact window and baseline UI validation."""
    viewer_page.load_run(completed_run.path)
    viewer_page.wait_for_data_loaded()
    viewer_page.wait_for_timeline_populated()

    # 1. Verify contacts match simulation output
    kpis = viewer_page.get_kpi_values()
    expected_contacts = completed_run.contact_count
    actual_contacts = int(kpis.get("contacts", "0").split()[0])
    assert actual_contacts == expected_contacts, (
        f"Contacts mismatch: UI shows {actual_contacts}, simulation has {expected_contacts}"
    )

    # 2. Verify timeline has contact blocks
    timeline_contacts = viewer_page.get_timeline_contacts()
    assert len(timeline_contacts) >= 1, "Pure propagation should have contact windows"

    # 3. Verify contact blocks have station info (via title attribute)
    contacts_with_station = [c for c in timeline_contacts if c["station"]]
    assert len(contacts_with_station) >= 1, "Contact blocks should have station names in title"

    # 4. Verify no/minimal constraint violations (pure propagation is safe)
    events_count = int(kpis.get("events", "0").split()[0])
    assert events_count <= 5, (
        f"Pure propagation should have minimal events, got {events_count}"
    )

    # 5. Verify 3D view has spacecraft entity
    entities = viewer_page.get_cesium_entities()
    assert "spacecraft" in [e.lower() for e in entities], (
        "Cesium viewer should have spacecraft entity"
    )
```

---

### Scenario: Cross-Fidelity Comparison

**Scenario Intent:** Validate that different fidelity runs are distinguishable in the UI.

**High-Value Assertions:**
```python
def test_fidelity_display_accuracy(self, viewer_page, low_run, medium_run, high_run):
    """Verify fidelity is correctly displayed for each run."""

    for run, expected_fidelity in [(low_run, "LOW"), (medium_run, "MEDIUM"), (high_run, "HIGH")]:
        viewer_page.load_run(run.path)
        viewer_page.wait_for_data_loaded()

        chips = viewer_page.get_context_chips()
        assert chips["fidelity"] == expected_fidelity, (
            f"Fidelity chip should show {expected_fidelity}, got {chips['fidelity']}"
        )

        kpis = viewer_page.get_kpi_values()
        assert kpis.get("fidelity") == expected_fidelity, (
            f"KPI fidelity should show {expected_fidelity}, got {kpis.get('fidelity')}"
        )
```

---

## Edge Case Coverage Map

| Edge Case Category | Coverage Status | Test File | Priority |
|--------------------|-----------------|-----------|----------|
| Empty events list | Partial | test_viewer_validation.py | P1 |
| No contacts (polar orbit?) | Missing | - | P2 |
| Very long duration (30+ days) | Missing | - | P2 |
| Very short duration (<1 orbit) | Missing | - | P1 |
| Malformed manifest.json | Missing | - | P0 |
| Missing CZML file | Covered | test_viewer_validation.py | - |
| Invalid run path | Covered | test_viewer_validation.py | - |
| Unicode in activity names | Missing | - | P2 |
| Extremely long alert messages | Missing | - | P2 |
| Rapid workspace switching | Partial | test_viewer_validation.py | P1 |
| Playback at max speed | Missing | - | P1 |
| Seek to exact edge times | Missing | - | P1 |
| Browser back/forward | Missing | - | P0 |
| Page refresh mid-playback | Missing | - | P0 |
| Multiple browser tabs | Missing | - | P2 |
| Network failure during load | Missing | - | P1 |
| Slow network simulation | Missing | - | P2 |
| Memory leak during long playback | Missing | - | P2 |
| Touch device interactions | Missing | - | P2 |

---

## Prioritized Backlog

### P0 - Breaks Correctness or Trust

| ID | Issue | Impact | Recommendation |
|----|-------|--------|----------------|
| P0-1 | No verification that KPI values match simulation output | Users may see stale/wrong data | Add `test_kpi_values_match_simulation()` |
| P0-2 | No verification of browser navigation (back/forward) | State corruption possible | Add `test_browser_navigation_preserves_state()` |
| P0-3 | No verification of page refresh handling | Data loss or corruption | Add `test_page_refresh_reloads_data()` |
| P0-4 | No verification of malformed data handling | Silent failures | Add `test_malformed_manifest_shows_error()` |
| P0-5 | VLEO workspace may be empty/non-functional | Core feature untested | Add `test_vleo_workspace_has_content()` |

### P1 - Major Workflow Reliability or Usability Issues

| ID | Issue | Impact | Recommendation |
|----|-------|--------|----------------|
| P1-1 | Timeline contact blocks not verified against source data | Visual may not match data | Add `test_timeline_contacts_match_access_windows()` |
| P1-2 | Playback controls not tested | Core UX untested | Add `test_playback_controls_work()` |
| P1-3 | Entity selection in 3D view not tested | Inspector may be broken | Add `test_cesium_entity_selection()` |
| P1-4 | Rapid workspace switching stability | May cause race conditions | Add `test_rapid_workspace_switching()` |
| P1-5 | Alert-to-timeline navigation not verified | Click handlers may be broken | Add `test_alert_click_navigates_to_time()` |
| P1-6 | No verification of sequence panel content | Maneuver planning UX broken | Add `test_sequence_panel_shows_activities()` |
| P1-7 | Network failure during load not handled | Users see blank screen | Add `test_network_failure_shows_error()` |

### P2 - Polish, Clarity, Debuggability

| ID | Issue | Impact | Recommendation |
|----|-------|--------|----------------|
| P2-1 | No screenshot capture on test failure | Debugging harder | Add failure artifact capture |
| P2-2 | Objects panel tree not tested | Minor UX | Add `test_objects_panel_tree_structure()` |
| P2-3 | Speed control dropdown not tested | Minor UX | Add `test_speed_control_changes_playback()` |
| P2-4 | Tooltip content not verified | Minor UX | Add tooltip content checks |
| P2-5 | Very long/short durations untested | Edge UX | Add duration edge case tests |
| P2-6 | Unicode handling in UI | Edge UX | Add unicode edge case tests |
| P2-7 | Console error filtering may miss issues | Debugging harder | Refine error filtering |

---

## MCP Implementation Notes

### 1. Recommended data-testid Additions

Add the following test IDs to the viewer codebase for stable selectors:

```typescript
// Priority additions (enables key verifications)
data-testid="context-chip-fidelity"
data-testid="context-chip-duration"
data-testid="context-chip-plan-id"
data-testid="kpi-events-value"
data-testid="kpi-contacts-value"
data-testid="kpi-fidelity-value"
data-testid="kpi-elapsed-time-value"
data-testid="alert-counter"
data-testid="alert-counter-value"
data-testid="timeline-cursor"
data-testid="timeline-contact-{id}"
data-testid="timeline-event-{id}"
data-testid="workspace-switcher"
data-testid="workspace-{id}"
data-testid="play-button"
data-testid="speed-selector"
data-testid="cesium-container"
data-testid="objects-panel"
data-testid="telemetry-inspector"
data-testid="alert-thread-{id}"
data-testid="alert-card-{id}"
data-testid="sequence-panel"
data-testid="activity-item-{id}"
```

### 2. Async State Transition Patterns

```python
# Pattern: Wait for workspace content to render
def wait_for_workspace_content(page, workspace_id, timeout_ms=5000):
    """Wait for workspace-specific content to appear."""
    content_selectors = {
        "mission-overview": ".kpi-grid, .geometry-view",
        "maneuver-planning": ".sequence-panel, .geometry-view",
        "vleo-drag": ".vleo-content, .altitude-chart",
        "anomaly-response": ".alert-center",
        "payload-ops": ".payload-content",
    }
    selector = content_selectors.get(workspace_id, ".workspace-content")
    page.wait_for_selector(selector, state="visible", timeout=timeout_ms)

# Pattern: Wait for data update after action
def wait_for_data_update(page, before_state, check_fn, timeout_ms=5000):
    """Wait for data to change from before_state."""
    start = time.time()
    while time.time() - start < timeout_ms / 1000:
        current = check_fn()
        if current != before_state:
            return current
        time.sleep(0.1)
    raise TimeoutError(f"Data did not update within {timeout_ms}ms")
```

### 3. Failure Artifact Capture

```python
# On test failure, capture:
@pytest.fixture
def capture_on_failure(request, viewer_page, tmp_path):
    """Capture artifacts on test failure."""
    yield
    if request.node.rep_call.failed:
        test_name = request.node.name
        output_dir = tmp_path / "failure_artifacts"
        output_dir.mkdir(exist_ok=True)

        artifacts = viewer_page.capture_failure_artifacts(test_name, output_dir)

        # Attach to pytest report
        for name, path in artifacts.items():
            request.node.add_report_section("call", name, str(path))
```

### 4. Console Log Capture

Add to viewer's main.tsx for test builds:
```typescript
// Capture console logs for testing
if (import.meta.env.MODE === 'test') {
  window.__consoleLogs = [];
  const originalConsole = { ...console };
  ['log', 'warn', 'error'].forEach(method => {
    console[method] = (...args) => {
      window.__consoleLogs.push({ method, args: args.map(String), timestamp: Date.now() });
      originalConsole[method](...args);
    };
  });
}
```

### 5. Network Event Capture (Optional)

```python
# Capture network events for debugging
def setup_network_logging(page):
    """Set up network event capture."""
    network_events = []

    def on_request(request):
        network_events.append({
            "type": "request",
            "url": request.url,
            "method": request.method,
            "timestamp": time.time(),
        })

    def on_response(response):
        network_events.append({
            "type": "response",
            "url": response.url,
            "status": response.status,
            "timestamp": time.time(),
        })

    page.on("request", on_request)
    page.on("response", on_response)

    return network_events
```

---

## Next Steps

1. **Immediate (Sprint 1):**
   - Add P0 tests for KPI validation and browser navigation
   - Add data-testid attributes to key UI elements
   - Implement failure artifact capture

2. **Short-term (Sprint 2):**
   - Add P1 tests for playback, timeline, and entity selection
   - Add ViewerPage helper methods from this document
   - Implement async state transition helpers

3. **Medium-term (Sprint 3):**
   - Add scenario-specific tests for R01, N01, and Anomaly scenarios
   - Add edge case tests from coverage map
   - Implement network failure simulation

4. **Long-term:**
   - Visual regression testing with Percy or similar
   - Performance profiling for long-duration playback
   - Accessibility (a11y) audit and testing
