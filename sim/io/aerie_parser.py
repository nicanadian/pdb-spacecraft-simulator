"""Parser for NASA Aerie/PLANDEV JSON plan exports.

Converts Aerie-exported plans to the simulator's normalized PlanInput format.
Handles ISO 8601 duration parsing and anchor chain resolution.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sim.core.types import Activity, PlanInput


# Default activity durations when not specified
DEFAULT_DURATIONS: dict[str, timedelta] = {
    "orbit_lower": timedelta(hours=1),
    "eo_collect": timedelta(minutes=15),
    "downlink": timedelta(minutes=15),
    "momentum_desat": timedelta(minutes=30),
    "station_keeping": timedelta(minutes=30),
    "collision_avoidance": timedelta(hours=1),
    "safe_mode": timedelta(hours=2),
    "idle": timedelta(hours=1),
}

DEFAULT_DURATION = timedelta(minutes=30)


def parse_iso_duration(duration_str: str) -> timedelta:
    """Parse ISO 8601 duration string to timedelta.

    Supports formats like:
    - P1D (1 day)
    - PT1H (1 hour)
    - PT30M (30 minutes)
    - PT45S (45 seconds)
    - PT1H30M (1 hour 30 minutes)
    - P1DT2H30M (1 day, 2 hours, 30 minutes)

    Args:
        duration_str: ISO 8601 duration string

    Returns:
        timedelta object

    Raises:
        ValueError: If duration string is invalid
    """
    if not duration_str:
        raise ValueError("Duration string cannot be empty")

    pattern = r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$"
    match = re.match(pattern, duration_str)

    if not match:
        raise ValueError(f"Invalid ISO 8601 duration format: {duration_str}")

    days = int(match.group(1) or 0)
    hours = int(match.group(2) or 0)
    minutes = int(match.group(3) or 0)
    seconds = float(match.group(4) or 0)

    # Validate that at least some time component is present
    if days == 0 and hours == 0 and minutes == 0 and seconds == 0:
        # P0D or PT0S are valid zero durations
        pass

    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


def resolve_activity_times(
    activities: list[dict],
    plan_start: datetime,
) -> list[dict]:
    """Resolve anchored activities to absolute start times.

    Uses topological sort to handle anchor dependencies, then computes
    absolute times from plan start + offsets.

    Args:
        activities: List of Aerie activity dicts with anchor info
        plan_start: Plan start datetime

    Returns:
        List of activities with resolved 'resolved_start' and 'resolved_end' fields
    """
    # Build lookup by id
    by_id: dict[int | str, dict] = {act["id"]: act for act in activities}

    # Track resolved times
    resolved: dict[int | str, datetime] = {}

    def resolve(act_id: int | str) -> datetime:
        """Recursively resolve activity start time."""
        if act_id in resolved:
            return resolved[act_id]

        act = by_id[act_id]
        offset = parse_iso_duration(act.get("start_offset", "PT0S"))
        anchor_id = act.get("anchor_id")

        if anchor_id is None:
            # Anchored to plan start
            start = plan_start + offset
        else:
            # Anchored to another activity
            anchor_start = resolve(anchor_id)
            anchor_act = by_id[anchor_id]

            # Get anchor activity duration for end anchor
            anchor_duration = _get_activity_duration(anchor_act)

            if act.get("anchored_to_start", True):
                # Anchor to start of anchor activity
                start = anchor_start + offset
            else:
                # Anchor to end of anchor activity
                start = anchor_start + anchor_duration + offset

        resolved[act_id] = start
        return start

    # Resolve all activities
    result = []
    for act in activities:
        start_time = resolve(act["id"])
        duration = _get_activity_duration(act)
        end_time = start_time + duration

        act_copy = act.copy()
        act_copy["resolved_start"] = start_time
        act_copy["resolved_end"] = end_time
        result.append(act_copy)

    return result


def _get_activity_duration(act: dict) -> timedelta:
    """Get duration for an activity from arguments or defaults."""
    arguments = act.get("arguments", {})

    # Check for explicit duration in arguments
    if "duration" in arguments:
        duration_val = arguments["duration"]
        if isinstance(duration_val, str):
            return parse_iso_duration(duration_val)
        elif isinstance(duration_val, (int, float)):
            # Assume seconds
            return timedelta(seconds=duration_val)

    # Check for duration_s in arguments
    if "duration_s" in arguments:
        return timedelta(seconds=arguments["duration_s"])

    # Use activity type default
    act_type = act.get("type", "")
    return DEFAULT_DURATIONS.get(act_type, DEFAULT_DURATION)


def parse_aerie_plan(
    data: dict,
    plan_start: datetime | None = None,
    spacecraft_id: str | None = None,
) -> PlanInput:
    """Convert Aerie export JSON to normalized PlanInput.

    Args:
        data: Aerie plan export dict
        plan_start: Override plan start time (uses data["start_time"] if not provided)
        spacecraft_id: Override spacecraft ID (uses data["spacecraft_id"] or default)

    Returns:
        PlanInput with normalized activities
    """
    # Determine plan start time
    if plan_start is None:
        start_str = data.get("start_time")
        if start_str:
            plan_start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        else:
            raise ValueError("Plan start_time not found and not provided")

    # Ensure timezone-aware
    if plan_start.tzinfo is None:
        plan_start = plan_start.replace(tzinfo=timezone.utc)

    # Get plan metadata
    plan_id = str(data.get("plan_id", data.get("name", "aerie_plan")))
    sc_id = spacecraft_id or data.get("spacecraft_id", "SC001")

    # Get activities
    aerie_activities = data.get("activities", [])
    if not aerie_activities:
        raise ValueError("No activities found in Aerie plan")

    # Resolve anchor chains to absolute times
    resolved_activities = resolve_activity_times(aerie_activities, plan_start)

    # Convert to normalized Activity objects
    activities = []
    for act in resolved_activities:
        # Extract parameters from arguments, excluding duration
        params = dict(act.get("arguments", {}))
        params.pop("duration", None)
        params.pop("duration_s", None)

        # Preserve Aerie metadata
        if act.get("tags"):
            params["_aerie_tags"] = act["tags"]
        if act.get("metadata"):
            params["_aerie_metadata"] = act["metadata"]
        if act.get("name"):
            params["_aerie_name"] = act["name"]

        activity = Activity(
            activity_id=str(act["id"]),
            activity_type=act["type"],
            start_time=act["resolved_start"],
            end_time=act["resolved_end"],
            parameters=params,
        )
        activities.append(activity)

    return PlanInput(
        spacecraft_id=sc_id,
        plan_id=plan_id,
        activities=activities,
    )


def detect_plan_format(data: dict) -> str:
    """Detect whether plan data is Aerie or normalized format.

    Args:
        data: Plan data dict

    Returns:
        "aerie" or "normalized"
    """
    activities = data.get("activities", [])
    if not activities:
        return "normalized"  # Empty plan, default to normalized

    first_act = activities[0]

    # Aerie format indicators
    if "start_offset" in first_act:
        return "aerie"
    if "type" in first_act and "id" in first_act and "arguments" in first_act:
        return "aerie"

    # Normalized format indicators
    if "start_time" in first_act and "activity_id" in first_act:
        return "normalized"
    if "activity_type" in first_act:
        return "normalized"

    # Default to normalized for backwards compatibility
    return "normalized"


def load_plan_file(filepath: str, format_hint: str | None = None) -> PlanInput:
    """Load a plan file, auto-detecting format if needed.

    Args:
        filepath: Path to plan JSON file
        format_hint: Optional format hint ("aerie" or "normalized")

    Returns:
        PlanInput object
    """
    import json
    from pathlib import Path

    with open(filepath) as f:
        data = json.load(f)

    # Determine format
    fmt = format_hint or detect_plan_format(data)

    if fmt == "aerie":
        return parse_aerie_plan(data)
    else:
        # Parse normalized format
        activities = []
        for act in data.get("activities", []):
            activities.append(Activity(
                activity_id=act["activity_id"],
                activity_type=act["activity_type"],
                start_time=datetime.fromisoformat(act["start_time"]),
                end_time=datetime.fromisoformat(act["end_time"]),
                parameters=act.get("parameters", {}),
            ))

        return PlanInput(
            spacecraft_id=data.get("spacecraft_id", "SC001"),
            plan_id=data.get("plan_id", "plan_001"),
            activities=activities,
        )
