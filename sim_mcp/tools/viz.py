"""Visualization tools for MCP server.

Provides tools for generating visualization artifacts and comparing runs.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def generate_viz(
    run_id: str,
    runs_dir: Path = Path("runs"),
) -> Dict[str, Any]:
    """
    Generate visualization artifacts for a simulation run.

    Args:
        run_id: Run ID to generate visualization for
        runs_dir: Directory containing runs

    Returns:
        Dictionary with generated artifact paths
    """
    from sim.viz.czml_generator import generate_czml
    from sim.viz.manifest_generator import generate_viz_manifest

    run_dir = runs_dir / run_id

    if not run_dir.exists():
        return {
            "success": False,
            "error": f"Run not found: {run_id}",
        }

    artifacts = {}
    errors = []

    # Generate CZML
    try:
        czml_path = generate_czml(run_dir)
        artifacts["czml"] = str(czml_path)
    except Exception as e:
        logger.exception(f"CZML generation failed: {e}")
        errors.append(f"CZML generation failed: {e}")

    # Generate manifest
    try:
        manifest = generate_viz_manifest(
            run_dir,
            czml_path=Path(artifacts["czml"]) if "czml" in artifacts else None,
        )
        artifacts["manifest"] = str(run_dir / "viz" / "run_manifest.json")
        artifacts["artifact_count"] = len(manifest.artifacts)
    except Exception as e:
        logger.exception(f"Manifest generation failed: {e}")
        errors.append(f"Manifest generation failed: {e}")

    # Format events for viewer
    try:
        events_path = run_dir / "events.json"
        if events_path.exists():
            with open(events_path) as f:
                events = json.load(f)

            viewer_events = _format_events_for_viewer(events)

            viz_dir = run_dir / "viz"
            viz_dir.mkdir(exist_ok=True)

            viewer_events_path = viz_dir / "events.json"
            with open(viewer_events_path, "w") as f:
                json.dump(viewer_events, f, indent=2)

            artifacts["viewer_events"] = str(viewer_events_path)

    except Exception as e:
        logger.exception(f"Events formatting failed: {e}")
        errors.append(f"Events formatting failed: {e}")

    return {
        "success": len(errors) == 0,
        "run_id": run_id,
        "artifacts": artifacts,
        "errors": errors if errors else None,
    }


async def compare_runs(
    run_a_id: str,
    run_b_id: str,
    runs_dir: Path = Path("runs"),
) -> Dict[str, Any]:
    """
    Compare two simulation runs and generate diff summary.

    Args:
        run_a_id: First run ID
        run_b_id: Second run ID
        runs_dir: Directory containing runs

    Returns:
        Dictionary with comparison results
    """
    from sim.viz.diff import compute_run_diff, generate_compare_czml

    run_a_dir = runs_dir / run_a_id
    run_b_dir = runs_dir / run_b_id

    # Validate both runs exist
    if not run_a_dir.exists():
        return {
            "success": False,
            "error": f"Run A not found: {run_a_id}",
        }

    if not run_b_dir.exists():
        return {
            "success": False,
            "error": f"Run B not found: {run_b_id}",
        }

    try:
        # Compute diff
        diff = compute_run_diff(run_a_dir, run_b_dir)

        # Generate comparison CZML
        compare_dir = runs_dir / f"compare_{run_a_id}_vs_{run_b_id}"
        compare_dir.mkdir(exist_ok=True)

        try:
            compare_czml_path = generate_compare_czml(run_a_dir, run_b_dir, compare_dir)
            compare_czml = str(compare_czml_path)
        except Exception as e:
            logger.warning(f"Compare CZML generation failed: {e}")
            compare_czml = None

        # Save diff to file
        diff_path = compare_dir / "diff.json"
        with open(diff_path, "w") as f:
            json.dump(diff.to_dict(), f, indent=2)

        return {
            "success": True,
            "run_a": {
                "id": run_a_id,
                "fidelity": diff.run_a_fidelity,
            },
            "run_b": {
                "id": run_b_id,
                "fidelity": diff.run_b_fidelity,
            },
            "position_rmse_km": diff.position_rmse_km,
            "max_position_diff_km": diff.max_position_diff_km,
            "altitude_rmse_km": diff.altitude_rmse_km,
            "contact_timing_rmse_s": diff.contact_timing_rmse_s,
            "soc_rmse": diff.soc_rmse,
            "storage_rmse_gb": diff.storage_rmse_gb,
            "comparable": diff.comparable,
            "warnings": diff.warnings,
            "artifacts": {
                "diff_file": str(diff_path),
                "compare_czml": compare_czml,
            },
        }

    except Exception as e:
        logger.exception(f"Comparison failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


def _format_events_for_viewer(events: list) -> dict:
    """
    Format simulation events for the web viewer.

    Args:
        events: List of event dictionaries

    Returns:
        Formatted events for viewer
    """
    formatted = {
        "violations": [],
        "warnings": [],
        "info": [],
        "timeline": [],
    }

    for event in events:
        event_type = event.get("event_type", "INFO")

        formatted_event = {
            "timestamp": event.get("timestamp"),
            "category": event.get("category"),
            "message": event.get("message"),
            "details": event.get("details", {}),
        }

        # Add to category list
        if event_type == "VIOLATION":
            formatted["violations"].append(formatted_event)
        elif event_type == "WARNING":
            formatted["warnings"].append(formatted_event)
        else:
            formatted["info"].append(formatted_event)

        # Add to timeline
        formatted["timeline"].append({
            "type": event_type.lower(),
            **formatted_event,
        })

    # Sort timeline by timestamp
    formatted["timeline"].sort(key=lambda e: e.get("timestamp", ""))

    return formatted
