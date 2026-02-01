"""
Events formatter for web viewer.

Converts simulation events to a format suitable for
timeline display with click-to-jump functionality.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sim.core.types import Event, EventType


logger = logging.getLogger(__name__)


@dataclass
class ViewerEvent:
    """Event formatted for viewer display."""

    id: str
    timestamp: str
    timestamp_ms: int  # Milliseconds since epoch for timeline
    type: str  # "info", "warning", "violation", "error"
    category: str
    title: str
    description: str
    details: Dict[str, Any]
    icon: str  # Icon identifier

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "timestamp_ms": self.timestamp_ms,
            "type": self.type,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "details": self.details,
            "icon": self.icon,
        }


# Icon mapping for event types and categories
ICONS = {
    # By type
    "info": "info-circle",
    "warning": "exclamation-triangle",
    "violation": "times-circle",
    "error": "exclamation-circle",
    # By category
    "contact": "satellite-dish",
    "imaging": "camera",
    "downlink": "download",
    "power": "bolt",
    "storage": "database",
    "propulsion": "rocket",
    "eclipse": "moon",
    "mode": "toggle-on",
}


def format_events_for_viewer(
    events: List[Dict[str, Any]],
    plan_start: Optional[datetime] = None,
) -> List[ViewerEvent]:
    """
    Format simulation events for web viewer.

    Args:
        events: List of event dictionaries
        plan_start: Plan start time for relative offsets

    Returns:
        List of ViewerEvents
    """
    viewer_events = []

    for i, event in enumerate(events):
        # Parse timestamp
        ts = event.get("timestamp", "")
        if isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                dt = datetime.now(timezone.utc)
        elif isinstance(ts, datetime):
            dt = ts
        else:
            dt = datetime.now(timezone.utc)

        # Compute milliseconds
        timestamp_ms = int(dt.timestamp() * 1000)

        # Determine type
        event_type = event.get("type", "info").lower()
        if event_type not in ["info", "warning", "violation", "error"]:
            event_type = "info"

        # Get category
        category = event.get("category", "general")

        # Determine icon
        icon = ICONS.get(category, ICONS.get(event_type, "info-circle"))

        # Build title and description
        message = event.get("message", "")
        title = _create_title(category, event_type, message)
        description = message

        viewer_events.append(ViewerEvent(
            id=f"event_{i}",
            timestamp=dt.isoformat(),
            timestamp_ms=timestamp_ms,
            type=event_type,
            category=category,
            title=title,
            description=description,
            details=event.get("details", {}),
            icon=icon,
        ))

    # Sort by timestamp
    viewer_events.sort(key=lambda e: e.timestamp_ms)

    return viewer_events


def _create_title(category: str, event_type: str, message: str) -> str:
    """Create concise title for event."""
    # Extract first sentence or key phrase
    if ":" in message:
        title = message.split(":")[0].strip()
    elif "." in message:
        title = message.split(".")[0].strip()
    else:
        title = message[:50] + "..." if len(message) > 50 else message

    # Add type prefix for important events
    if event_type == "violation":
        title = f"VIOLATION: {title}"
    elif event_type == "error":
        title = f"ERROR: {title}"

    return title


def save_viewer_events(
    events: List[Dict[str, Any]],
    output_path: Path,
    plan_start: Optional[datetime] = None,
) -> None:
    """
    Format and save events for viewer.

    Args:
        events: List of event dictionaries
        output_path: Path to save formatted events
        plan_start: Plan start time
    """
    viewer_events = format_events_for_viewer(events, plan_start)

    with open(output_path, "w") as f:
        json.dump([e.to_dict() for e in viewer_events], f, indent=2)

    logger.info(f"Saved {len(viewer_events)} events to {output_path}")


def generate_timeline_data(
    run_dir: Path,
) -> Dict[str, Any]:
    """
    Generate timeline data for viewer.

    Combines events, activities, and contacts into unified timeline.

    Args:
        run_dir: Path to run directory

    Returns:
        Timeline data dictionary
    """
    timeline = {
        "events": [],
        "activities": [],
        "contacts": [],
        "eclipses": [],
    }

    # Load events
    events_path = run_dir / "events.json"
    if events_path.exists():
        with open(events_path) as f:
            events = json.load(f)
        viewer_events = format_events_for_viewer(events)
        timeline["events"] = [e.to_dict() for e in viewer_events]

    # Load access windows as contacts
    access_path = run_dir / "access_windows.json"
    if access_path.exists():
        with open(access_path) as f:
            access = json.load(f)

        contact_id = 0
        for station_id, windows in access.items():
            for window in windows:
                start = datetime.fromisoformat(window["start_time"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(window["end_time"].replace("Z", "+00:00"))

                timeline["contacts"].append({
                    "id": f"contact_{contact_id}",
                    "station_id": station_id,
                    "start_ms": int(start.timestamp() * 1000),
                    "end_ms": int(end.timestamp() * 1000),
                    "duration_s": window.get("duration_s", (end - start).total_seconds()),
                    "max_elevation_deg": window.get("max_elevation_deg", 0),
                })
                contact_id += 1

    # Load eclipse windows
    eclipse_path = run_dir / "eclipse_windows.json"
    if eclipse_path.exists():
        with open(eclipse_path) as f:
            eclipses = json.load(f)

        for i, eclipse in enumerate(eclipses):
            start = datetime.fromisoformat(eclipse["start_time"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(eclipse["end_time"].replace("Z", "+00:00"))

            timeline["eclipses"].append({
                "id": f"eclipse_{i}",
                "start_ms": int(start.timestamp() * 1000),
                "end_ms": int(end.timestamp() * 1000),
                "duration_s": eclipse.get("duration_s", (end - start).total_seconds()),
            })

    return timeline


def generate_viz_events(run_dir: Path) -> Path:
    """
    Generate visualization events file.

    Args:
        run_dir: Path to run directory

    Returns:
        Path to generated events file
    """
    viz_dir = run_dir / "viz"
    viz_dir.mkdir(exist_ok=True)

    # Load events
    events_path = run_dir / "events.json"
    if events_path.exists():
        with open(events_path) as f:
            events = json.load(f)
    else:
        events = []

    # Format and save
    output_path = viz_dir / "events.json"
    save_viewer_events(events, output_path)

    return output_path
