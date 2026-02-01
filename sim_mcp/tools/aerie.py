"""Aerie integration tools for MCP server.

Provides tools for interacting with the Aerie mission planning system.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def aerie_status(
    host: str = "localhost",
    port: int = 9000,
) -> Dict[str, Any]:
    """
    Check Aerie service health and availability.

    Args:
        host: Aerie host
        port: Aerie port

    Returns:
        Dictionary with health status
    """
    from sim.io.aerie_client import AerieClient, AerieConfig, AerieConnectionError

    config = AerieConfig(host=host, port=port)
    client = AerieClient(config)

    try:
        # Try to list mission models as a health check
        models = client.list_mission_models()

        return {
            "healthy": True,
            "host": host,
            "port": port,
            "graphql_url": config.graphql_url,
            "mission_models": len(models),
        }

    except AerieConnectionError as e:
        return {
            "healthy": False,
            "host": host,
            "port": port,
            "error": str(e),
        }

    except Exception as e:
        return {
            "healthy": False,
            "host": host,
            "port": port,
            "error": f"Unexpected error: {e}",
        }


async def create_plan(
    scenario_path: Path,
    plan_name: str,
    model_id: int,
    host: str = "localhost",
    port: int = 9000,
) -> Dict[str, Any]:
    """
    Create a new plan in Aerie from a scenario file.

    Args:
        scenario_path: Path to scenario definition file
        plan_name: Name for the new plan
        model_id: Mission model ID to use
        host: Aerie host
        port: Aerie port

    Returns:
        Dictionary with plan creation result
    """
    from sim.io.aerie_client import (
        AerieClient,
        AerieConfig,
        ActivityInput,
        AerieClientError,
    )

    # Validate scenario file exists
    if not scenario_path.exists():
        return {
            "success": False,
            "error": f"Scenario file not found: {scenario_path}",
        }

    # Load scenario
    try:
        with open(scenario_path) as f:
            if scenario_path.suffix == ".yaml" or scenario_path.suffix == ".yml":
                import yaml
                scenario = yaml.safe_load(f)
            else:
                scenario = json.load(f)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load scenario: {e}",
        }

    # Connect to Aerie
    config = AerieConfig(host=host, port=port)
    client = AerieClient(config)

    try:
        # Check if plan already exists
        existing = client.find_plan_by_name(plan_name)
        if existing:
            return {
                "success": False,
                "error": f"Plan '{plan_name}' already exists with ID {existing['id']}",
                "existing_plan_id": existing["id"],
            }

        # Parse scenario duration and start time
        start_time_str = scenario.get("start_time")
        if start_time_str:
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        else:
            start_time = datetime.now(timezone.utc)

        duration_hours = scenario.get("duration_hours", 24)
        duration = timedelta(hours=duration_hours)

        # Create plan
        plan_id = client.create_plan(
            name=plan_name,
            model_id=model_id,
            start_time=start_time,
            duration=duration,
        )

        # Insert activities if present in scenario
        activities = scenario.get("activities", [])
        activity_ids = []

        if activities:
            activity_inputs = []
            for activity in activities:
                activity_input = ActivityInput(
                    activity_type=activity["type"],
                    start_offset=timedelta(seconds=activity.get("start_offset_s", 0)),
                    arguments=activity.get("arguments", {}),
                )
                activity_inputs.append(activity_input)

            activity_ids = client.insert_activities_batch(plan_id, activity_inputs)

        return {
            "success": True,
            "plan_id": plan_id,
            "plan_name": plan_name,
            "model_id": model_id,
            "start_time": start_time.isoformat(),
            "duration_hours": duration_hours,
            "activities_created": len(activity_ids),
        }

    except AerieClientError as e:
        return {
            "success": False,
            "error": str(e),
        }


async def run_scheduler(
    plan_id: int,
    host: str = "localhost",
    port: int = 9000,
) -> Dict[str, Any]:
    """
    Trigger the Aerie scheduler for a plan.

    Args:
        plan_id: Plan ID to schedule
        host: Aerie host
        port: Aerie port

    Returns:
        Dictionary with scheduling status
    """
    from sim.io.aerie_client import AerieClient, AerieConfig, AerieClientError

    config = AerieConfig(host=host, port=port)
    client = AerieClient(config)

    try:
        # Get plan to find spec or create one
        plan = client.get_plan(plan_id)
        if not plan:
            return {
                "success": False,
                "error": f"Plan {plan_id} not found",
            }

        # Check for existing scheduling spec
        spec = client.get_scheduling_specification(plan_id)

        if not spec:
            # Create scheduling specification
            # We need to determine the horizon from the plan
            plan_start = datetime.fromisoformat(
                plan.get("start_time", "").replace("Z", "+00:00")
            )
            plan_duration_str = plan.get("duration", "24:00:00")

            # Parse duration
            parts = plan_duration_str.split(":")
            hours = int(parts[0])
            minutes = int(parts[1]) if len(parts) > 1 else 0
            seconds = int(parts[2]) if len(parts) > 2 else 0
            duration = timedelta(hours=hours, minutes=minutes, seconds=seconds)

            plan_end = plan_start + duration

            spec_id = client.create_scheduling_specification(
                plan_id=plan_id,
                plan_revision=plan.get("revision", 1),
                horizon_start=plan_start,
                horizon_end=plan_end,
            )
        else:
            spec_id = spec["id"]

        # Run scheduler
        analysis_id, reason = client.run_scheduler(spec_id)

        return {
            "success": True,
            "plan_id": plan_id,
            "specification_id": spec_id,
            "analysis_id": analysis_id,
            "reason": reason,
            "status": "started",
        }

    except AerieClientError as e:
        return {
            "success": False,
            "error": str(e),
        }


async def export_plan(
    plan_id: int,
    output_dir: Path = Path("."),
    host: str = "localhost",
    port: int = 9000,
) -> Dict[str, Any]:
    """
    Export a plan from Aerie.

    Args:
        plan_id: Plan ID to export
        output_dir: Directory for exported files
        host: Aerie host
        port: Aerie port

    Returns:
        Dictionary with export paths
    """
    from sim.io.aerie_client import AerieClient, AerieConfig, AerieClientError

    config = AerieConfig(host=host, port=port)
    client = AerieClient(config)

    try:
        # Export plan
        plan_data = client.export_plan(plan_id)

        if not plan_data:
            return {
                "success": False,
                "error": f"Plan {plan_id} not found",
            }

        # Ensure output directory exists
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write plan file
        plan_name = plan_data.get("name", f"plan_{plan_id}")
        plan_file = output_dir / f"{plan_name}.json"

        with open(plan_file, "w") as f:
            json.dump(plan_data, f, indent=2)

        # Extract activities summary
        activities = plan_data.get("activity_directives", [])
        activity_types = {}
        for activity in activities:
            act_type = activity.get("type", "unknown")
            activity_types[act_type] = activity_types.get(act_type, 0) + 1

        return {
            "success": True,
            "plan_id": plan_id,
            "plan_name": plan_name,
            "plan_file": str(plan_file),
            "activity_count": len(activities),
            "activity_types": activity_types,
        }

    except AerieClientError as e:
        return {
            "success": False,
            "error": str(e),
        }
