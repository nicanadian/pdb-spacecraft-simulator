"""Simulation tools for MCP server.

Provides tools for running simulations and retrieving results.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def run_simulation(
    plan_path: Path,
    fidelity: str = "LOW",
    config_overrides: Optional[Dict[str, Any]] = None,
    runs_dir: Path = Path("runs"),
) -> Dict[str, Any]:
    """
    Run a spacecraft simulation.

    Args:
        plan_path: Path to the plan file (JSON or YAML)
        fidelity: Simulation fidelity level (LOW, MEDIUM, HIGH)
        config_overrides: Optional configuration overrides
        runs_dir: Directory for simulation outputs

    Returns:
        Dictionary with run_id and initial status
    """
    from sim.io.aerie_parser import load_plan_file
    from sim.engine import simulate
    from sim.core.types import Fidelity, SimConfig, SpacecraftConfig, InitialState

    logger.info(f"Starting simulation with plan: {plan_path}, fidelity: {fidelity}")

    # Validate plan exists
    if not plan_path.exists():
        return {
            "success": False,
            "error": f"Plan file not found: {plan_path}",
        }

    # Load plan
    try:
        plan_input = load_plan_file(plan_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load plan: {e}",
        }

    # Generate run ID
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{fidelity.lower()}"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Build config
    spacecraft_config = SpacecraftConfig(
        spacecraft_id=plan_input.spacecraft_id,
        **(config_overrides or {}),
    )

    sim_config = SimConfig(
        fidelity=Fidelity(fidelity),
        spacecraft=spacecraft_config,
        output_dir=str(run_dir),
    )

    # Run simulation
    try:
        # Note: In a real implementation, this would be run in a background task
        # For now, we run synchronously
        results = simulate(plan_input, sim_config)

        # Write run manifest
        manifest = {
            "run_id": run_id,
            "plan_path": str(plan_path),
            "fidelity": fidelity,
            "status": "complete",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "has_violations": results.has_violations(),
            "violation_count": results.violation_count(),
        }

        with open(run_dir / "run_manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

        return {
            "success": True,
            "run_id": run_id,
            "status": "complete",
            "has_violations": results.has_violations(),
            "violation_count": results.violation_count(),
            "output_dir": str(run_dir),
        }

    except Exception as e:
        logger.exception(f"Simulation failed: {e}")
        return {
            "success": False,
            "run_id": run_id,
            "error": str(e),
        }


async def get_run_status(
    run_id: str,
    runs_dir: Path = Path("runs"),
) -> Dict[str, Any]:
    """
    Get the status of a simulation run.

    Args:
        run_id: The run ID to check
        runs_dir: Directory containing runs

    Returns:
        Dictionary with run status information
    """
    run_dir = runs_dir / run_id

    if not run_dir.exists():
        return {
            "found": False,
            "error": f"Run not found: {run_id}",
        }

    manifest_path = run_dir / "run_manifest.json"

    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)

        return {
            "found": True,
            "run_id": run_id,
            "status": manifest.get("status", "unknown"),
            "fidelity": manifest.get("fidelity"),
            "created_at": manifest.get("created_at"),
            "has_violations": manifest.get("has_violations"),
        }
    else:
        return {
            "found": True,
            "run_id": run_id,
            "status": "incomplete",
            "message": "Run directory exists but no manifest found",
        }


async def get_run_results(
    run_id: str,
    runs_dir: Path = Path("runs"),
) -> Dict[str, Any]:
    """
    Get the results of a completed simulation run.

    Args:
        run_id: The run ID to retrieve
        runs_dir: Directory containing runs

    Returns:
        Dictionary with run results and artifacts
    """
    run_dir = runs_dir / run_id

    if not run_dir.exists():
        return {
            "found": False,
            "error": f"Run not found: {run_id}",
        }

    results = {
        "found": True,
        "run_id": run_id,
        "artifacts": {},
    }

    # Load manifest
    manifest_path = run_dir / "run_manifest.json"
    if manifest_path.exists():
        with open(manifest_path) as f:
            results["manifest"] = json.load(f)

    # Load summary
    summary_path = run_dir / "summary.json"
    if summary_path.exists():
        with open(summary_path) as f:
            results["summary"] = json.load(f)

    # Load events
    events_path = run_dir / "events.json"
    if events_path.exists():
        with open(events_path) as f:
            results["events"] = json.load(f)

    # List available artifacts
    for artifact_name in ["ephemeris.parquet", "profiles.parquet", "access_windows.json"]:
        artifact_path = run_dir / artifact_name
        if artifact_path.exists():
            results["artifacts"][artifact_name] = str(artifact_path)

    # Check for viz artifacts
    viz_dir = run_dir / "viz"
    if viz_dir.exists():
        for viz_file in viz_dir.iterdir():
            results["artifacts"][f"viz/{viz_file.name}"] = str(viz_file)

    return results


async def list_runs(
    runs_dir: Path = Path("runs"),
    limit: int = 10,
) -> Dict[str, Any]:
    """
    List available simulation runs.

    Args:
        runs_dir: Directory containing runs
        limit: Maximum number of runs to return

    Returns:
        Dictionary with list of runs
    """
    if not runs_dir.exists():
        return {
            "runs": [],
            "total": 0,
        }

    runs = []
    run_dirs = sorted(runs_dir.iterdir(), reverse=True)[:limit]

    for run_dir in run_dirs:
        if not run_dir.is_dir():
            continue

        run_info = {
            "run_id": run_dir.name,
            "path": str(run_dir),
        }

        manifest_path = run_dir / "run_manifest.json"
        if manifest_path.exists():
            with open(manifest_path) as f:
                manifest = json.load(f)
            run_info.update({
                "status": manifest.get("status"),
                "fidelity": manifest.get("fidelity"),
                "created_at": manifest.get("created_at"),
            })

        runs.append(run_info)

    return {
        "runs": runs,
        "total": len(runs),
        "limit": limit,
    }
