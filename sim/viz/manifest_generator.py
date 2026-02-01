"""
Visualization manifest generator.

Creates run_manifest.json for the web viewer with metadata
and artifact locations.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


logger = logging.getLogger(__name__)


@dataclass
class VizArtifact:
    """Visualization artifact metadata."""

    name: str
    path: str
    type: str  # "czml", "json", "parquet", "image"
    description: str = ""
    size_bytes: int = 0


@dataclass
class VizManifest:
    """Complete visualization manifest."""

    run_id: str
    plan_id: str
    fidelity: str
    created_at: str
    start_time: str
    end_time: str
    duration_hours: float

    artifacts: List[VizArtifact] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "run_id": self.run_id,
            "plan_id": self.plan_id,
            "fidelity": self.fidelity,
            "created_at": self.created_at,
            "time_range": {
                "start": self.start_time,
                "end": self.end_time,
                "duration_hours": self.duration_hours,
            },
            "artifacts": [
                {
                    "name": a.name,
                    "path": a.path,
                    "type": a.type,
                    "description": a.description,
                    "size_bytes": a.size_bytes,
                }
                for a in self.artifacts
            ],
            "summary": self.summary,
            "metadata": self.metadata,
        }

    def save(self, path: Path) -> None:
        """Save manifest to JSON."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


def generate_viz_manifest(
    run_dir: Path,
    czml_path: Optional[Path] = None,
) -> VizManifest:
    """
    Generate visualization manifest for a run.

    Args:
        run_dir: Path to run directory
        czml_path: Path to CZML file (if already generated)

    Returns:
        VizManifest with artifact metadata
    """
    # Load run manifest if available
    manifest_path = run_dir / "run_manifest.json"
    if manifest_path.exists():
        with open(manifest_path) as f:
            run_manifest = json.load(f)
    else:
        run_manifest = {}

    # Load summary
    summary_path = run_dir / "summary.json"
    if summary_path.exists():
        with open(summary_path) as f:
            summary = json.load(f)
    else:
        summary = {}

    # Extract info
    run_id = run_manifest.get("run_id", run_dir.name)
    plan_id = summary.get("plan_id", run_manifest.get("plan_id", "unknown"))
    fidelity = run_manifest.get("fidelity", "LOW")
    start_time = summary.get("start_time", "")
    end_time = summary.get("end_time", "")
    duration_hours = summary.get("duration_hours", 0)

    # Build artifact list
    artifacts = []

    # CZML
    viz_dir = run_dir / "viz"
    if czml_path and czml_path.exists():
        artifacts.append(VizArtifact(
            name="scene.czml",
            path=str(czml_path.relative_to(run_dir)),
            type="czml",
            description="3D scene for CesiumJS",
            size_bytes=czml_path.stat().st_size,
        ))
    elif (viz_dir / "scene.czml").exists():
        czml = viz_dir / "scene.czml"
        artifacts.append(VizArtifact(
            name="scene.czml",
            path="viz/scene.czml",
            type="czml",
            description="3D scene for CesiumJS",
            size_bytes=czml.stat().st_size,
        ))

    # Events
    events_path = run_dir / "events.json"
    if events_path.exists():
        artifacts.append(VizArtifact(
            name="events.json",
            path="events.json",
            type="json",
            description="Simulation events for timeline",
            size_bytes=events_path.stat().st_size,
        ))

    # Viewer events
    viewer_events = viz_dir / "events.json" if viz_dir.exists() else None
    if viewer_events and viewer_events.exists():
        artifacts.append(VizArtifact(
            name="viewer_events.json",
            path="viz/events.json",
            type="json",
            description="Events formatted for viewer",
            size_bytes=viewer_events.stat().st_size,
        ))

    # Ephemeris
    eph_path = run_dir / "ephemeris.parquet"
    if eph_path.exists():
        artifacts.append(VizArtifact(
            name="ephemeris.parquet",
            path="ephemeris.parquet",
            type="parquet",
            description="Position/velocity timeseries",
            size_bytes=eph_path.stat().st_size,
        ))

    # Profiles
    profiles_path = run_dir / "profiles.parquet"
    if profiles_path.exists():
        artifacts.append(VizArtifact(
            name="profiles.parquet",
            path="profiles.parquet",
            type="parquet",
            description="Resource profiles (SOC, storage)",
            size_bytes=profiles_path.stat().st_size,
        ))

    # Access windows
    access_path = run_dir / "access_windows.json"
    if access_path.exists():
        artifacts.append(VizArtifact(
            name="access_windows.json",
            path="access_windows.json",
            type="json",
            description="Ground station contact windows",
            size_bytes=access_path.stat().st_size,
        ))

    # Create manifest
    manifest = VizManifest(
        run_id=run_id,
        plan_id=plan_id,
        fidelity=fidelity,
        created_at=datetime.now(timezone.utc).isoformat(),
        start_time=start_time,
        end_time=end_time,
        duration_hours=duration_hours,
        artifacts=artifacts,
        summary=_extract_summary(summary),
        metadata=run_manifest.get("metadata", {}),
    )

    # Save to viz directory
    viz_dir.mkdir(exist_ok=True)
    manifest.save(viz_dir / "run_manifest.json")

    logger.info(f"Generated viz manifest: {len(artifacts)} artifacts")
    return manifest


def _extract_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key summary info for viewer."""
    return {
        "activities": summary.get("activities", {}),
        "events": summary.get("events", {}),
        "state_changes": summary.get("state_changes", {}),
        "orbit": summary.get("orbit", {}),
    }
