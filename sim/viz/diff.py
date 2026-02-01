"""
Run comparison and diff generation for compare mode visualization.

Computes differences between two simulation runs for
overlay visualization in the web viewer.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)


@dataclass
class RunDiff:
    """Computed differences between two runs."""

    run_a_id: str
    run_b_id: str
    run_a_fidelity: str
    run_b_fidelity: str

    # Position differences
    position_rmse_km: float
    max_position_diff_km: float
    altitude_rmse_km: float

    # Contact differences
    contact_diffs: List[Dict[str, Any]] = field(default_factory=list)
    contact_timing_rmse_s: float = 0.0

    # State differences
    soc_rmse: float = 0.0
    storage_rmse_gb: float = 0.0

    # Summary
    comparable: bool = True
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runs": {
                "a": {"id": self.run_a_id, "fidelity": self.run_a_fidelity},
                "b": {"id": self.run_b_id, "fidelity": self.run_b_fidelity},
            },
            "position": {
                "rmse_km": self.position_rmse_km,
                "max_diff_km": self.max_position_diff_km,
                "altitude_rmse_km": self.altitude_rmse_km,
            },
            "contacts": {
                "diffs": self.contact_diffs,
                "timing_rmse_s": self.contact_timing_rmse_s,
            },
            "state": {
                "soc_rmse": self.soc_rmse,
                "storage_rmse_gb": self.storage_rmse_gb,
            },
            "comparable": self.comparable,
            "warnings": self.warnings,
        }


def compute_run_diff(
    run_a_dir: Path,
    run_b_dir: Path,
) -> RunDiff:
    """
    Compute differences between two simulation runs.

    Args:
        run_a_dir: Path to first run
        run_b_dir: Path to second run

    Returns:
        RunDiff with computed differences
    """
    warnings = []

    # Load manifests
    manifest_a = _load_manifest(run_a_dir)
    manifest_b = _load_manifest(run_b_dir)

    run_a_id = manifest_a.get("run_id", run_a_dir.name)
    run_b_id = manifest_b.get("run_id", run_b_dir.name)
    fidelity_a = manifest_a.get("fidelity", "UNKNOWN")
    fidelity_b = manifest_b.get("fidelity", "UNKNOWN")

    # Load ephemeris
    eph_a = _load_ephemeris(run_a_dir)
    eph_b = _load_ephemeris(run_b_dir)

    # Compute position differences
    if eph_a is not None and eph_b is not None:
        pos_rmse, max_diff, alt_rmse = _compute_position_diff(eph_a, eph_b)
    else:
        pos_rmse, max_diff, alt_rmse = float("nan"), float("nan"), float("nan")
        warnings.append("Could not compare ephemeris")

    # Load and compare contacts
    contacts_a = _load_access_windows(run_a_dir)
    contacts_b = _load_access_windows(run_b_dir)
    contact_diffs, timing_rmse = _compute_contact_diff(contacts_a, contacts_b)

    # Load and compare profiles
    profiles_a = _load_profiles(run_a_dir)
    profiles_b = _load_profiles(run_b_dir)
    soc_rmse, storage_rmse = _compute_profile_diff(profiles_a, profiles_b)

    return RunDiff(
        run_a_id=run_a_id,
        run_b_id=run_b_id,
        run_a_fidelity=fidelity_a,
        run_b_fidelity=fidelity_b,
        position_rmse_km=pos_rmse,
        max_position_diff_km=max_diff,
        altitude_rmse_km=alt_rmse,
        contact_diffs=contact_diffs,
        contact_timing_rmse_s=timing_rmse,
        soc_rmse=soc_rmse,
        storage_rmse_gb=storage_rmse,
        comparable=len(warnings) == 0,
        warnings=warnings,
    )


def _load_manifest(run_dir: Path) -> Dict[str, Any]:
    """Load run manifest."""
    path = run_dir / "run_manifest.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _load_ephemeris(run_dir: Path) -> Optional[pd.DataFrame]:
    """Load ephemeris."""
    path = run_dir / "ephemeris.parquet"
    if path.exists():
        return pd.read_parquet(path)
    return None


def _load_access_windows(run_dir: Path) -> Dict[str, List[Dict]]:
    """Load access windows."""
    path = run_dir / "access_windows.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _load_profiles(run_dir: Path) -> Optional[pd.DataFrame]:
    """Load profiles."""
    path = run_dir / "profiles.parquet"
    if path.exists():
        return pd.read_parquet(path)
    return None


def _compute_position_diff(
    eph_a: pd.DataFrame,
    eph_b: pd.DataFrame,
) -> Tuple[float, float, float]:
    """Compute position differences."""
    # Align by time
    if "time" in eph_a.columns:
        eph_a = eph_a.set_index("time")
    if "time" in eph_b.columns:
        eph_b = eph_b.set_index("time")

    common = eph_a.index.intersection(eph_b.index)
    if len(common) == 0:
        return float("nan"), float("nan"), float("nan")

    # Position difference
    dx = eph_a.loc[common, "x_km"] - eph_b.loc[common, "x_km"]
    dy = eph_a.loc[common, "y_km"] - eph_b.loc[common, "y_km"]
    dz = eph_a.loc[common, "z_km"] - eph_b.loc[common, "z_km"]
    dr = np.sqrt(dx**2 + dy**2 + dz**2)

    # Altitude difference
    alt_a = eph_a.loc[common, "altitude_km"]
    alt_b = eph_b.loc[common, "altitude_km"]
    dalt = alt_a - alt_b

    return (
        float(np.sqrt(np.mean(dr**2))),
        float(np.max(dr)),
        float(np.sqrt(np.mean(dalt**2))),
    )


def _compute_contact_diff(
    contacts_a: Dict[str, List[Dict]],
    contacts_b: Dict[str, List[Dict]],
) -> Tuple[List[Dict], float]:
    """Compute contact timing differences."""
    diffs = []
    timing_deltas = []

    all_stations = set(contacts_a.keys()) | set(contacts_b.keys())

    for station in all_stations:
        windows_a = contacts_a.get(station, [])
        windows_b = contacts_b.get(station, [])

        # Match by AOS time
        for wa in windows_a:
            aos_a = datetime.fromisoformat(wa["start_time"].replace("Z", "+00:00"))

            # Find closest in B
            best_match = None
            best_delta = float("inf")

            for wb in windows_b:
                aos_b = datetime.fromisoformat(wb["start_time"].replace("Z", "+00:00"))
                delta = abs((aos_a - aos_b).total_seconds())
                if delta < best_delta and delta < 600:  # 10 min tolerance
                    best_delta = delta
                    best_match = wb

            if best_match:
                los_a = datetime.fromisoformat(wa["end_time"].replace("Z", "+00:00"))
                los_b = datetime.fromisoformat(best_match["end_time"].replace("Z", "+00:00"))

                aos_diff = (aos_a - datetime.fromisoformat(
                    best_match["start_time"].replace("Z", "+00:00")
                )).total_seconds()
                los_diff = (los_a - los_b).total_seconds()

                timing_deltas.extend([aos_diff, los_diff])

                diffs.append({
                    "station_id": station,
                    "aos_diff_s": aos_diff,
                    "los_diff_s": los_diff,
                    "duration_diff_s": wa.get("duration_s", 0) - best_match.get("duration_s", 0),
                })

    timing_rmse = float(np.sqrt(np.mean(np.array(timing_deltas)**2))) if timing_deltas else 0.0

    return diffs, timing_rmse


def _compute_profile_diff(
    profiles_a: Optional[pd.DataFrame],
    profiles_b: Optional[pd.DataFrame],
) -> Tuple[float, float]:
    """Compute profile differences."""
    if profiles_a is None or profiles_b is None:
        return float("nan"), float("nan")

    # Align by time
    if "time" in profiles_a.columns:
        profiles_a = profiles_a.set_index("time")
    if "time" in profiles_b.columns:
        profiles_b = profiles_b.set_index("time")

    common = profiles_a.index.intersection(profiles_b.index)
    if len(common) == 0:
        return float("nan"), float("nan")

    # SOC difference
    if "battery_soc" in profiles_a.columns and "battery_soc" in profiles_b.columns:
        dsoc = profiles_a.loc[common, "battery_soc"] - profiles_b.loc[common, "battery_soc"]
        soc_rmse = float(np.sqrt(np.mean(dsoc**2)))
    else:
        soc_rmse = float("nan")

    # Storage difference
    if "storage_gb" in profiles_a.columns and "storage_gb" in profiles_b.columns:
        dstorage = profiles_a.loc[common, "storage_gb"] - profiles_b.loc[common, "storage_gb"]
        storage_rmse = float(np.sqrt(np.mean(dstorage**2)))
    else:
        storage_rmse = float("nan")

    return soc_rmse, storage_rmse


def generate_compare_czml(
    run_a_dir: Path,
    run_b_dir: Path,
    output_dir: Path,
) -> Path:
    """
    Generate CZML for compare mode with dual tracks.

    Args:
        run_a_dir: First run directory
        run_b_dir: Second run directory
        output_dir: Output directory

    Returns:
        Path to generated CZML
    """
    from sim.viz.czml_generator import CZMLGenerator, CZMLStyle

    # Load ephemeris
    eph_a = _load_ephemeris(run_a_dir)
    eph_b = _load_ephemeris(run_b_dir)

    if eph_a is None or eph_b is None:
        raise ValueError("Both runs must have ephemeris")

    # Create generator with distinct styles
    style_a = CZMLStyle(
        satellite_color=(0, 255, 255, 255),  # Cyan
        orbit_trail_color=(0, 200, 255, 180),
    )
    style_b = CZMLStyle(
        satellite_color=(255, 0, 255, 255),  # Magenta
        orbit_trail_color=(255, 100, 255, 180),
    )

    generator = CZMLGenerator(style_a)

    # Get time bounds
    if "time" in eph_a.columns:
        times = eph_a["time"]
    else:
        times = eph_a.index
    start_time = times.iloc[0]
    end_time = times.iloc[-1]

    # Add document
    generator.add_document(
        name="Comparison View",
        start_time=start_time,
        end_time=end_time,
        description="Dual-track comparison",
    )

    # Add satellite A
    generator.add_satellite(
        satellite_id="satellite_a",
        name=f"Run A ({run_a_dir.name})",
        ephemeris=eph_a,
    )

    # Switch style and add satellite B
    generator._packets.append({
        "id": "satellite_b",
        "name": f"Run B ({run_b_dir.name})",
        "availability": f"{start_time.isoformat()}/{end_time.isoformat()}",
        "position": _build_position_array(eph_b),
        "point": {
            "color": {"rgba": list(style_b.satellite_color)},
            "pixelSize": 10,
            "outlineColor": {"rgba": [255, 255, 255, 255]},
            "outlineWidth": 2,
        },
        "path": {
            "material": {
                "polylineDash": {
                    "color": {"rgba": list(style_b.orbit_trail_color)},
                    "dashLength": 16,
                }
            },
            "width": 2,
            "leadTime": 3600,
            "trailTime": 3600,
        },
    })

    # Save
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "compare.czml"
    generator.save(output_path)

    # Also save diff data
    diff = compute_run_diff(run_a_dir, run_b_dir)
    diff_path = output_dir / "diff.json"
    with open(diff_path, "w") as f:
        json.dump(diff.to_dict(), f, indent=2)

    logger.info(f"Generated compare CZML: {output_path}")
    return output_path


def _build_position_array(eph: pd.DataFrame) -> Dict[str, Any]:
    """Build CZML position array from ephemeris."""
    if "time" in eph.columns:
        times = eph["time"]
    else:
        times = eph.index

    start_time = times.iloc[0]
    positions = []

    for i, (_, row) in enumerate(eph.iterrows()):
        t = times.iloc[i]
        if isinstance(t, datetime):
            offset = (t - start_time).total_seconds()
        else:
            offset = float(t)

        positions.extend([
            offset,
            row["x_km"] * 1000,
            row["y_km"] * 1000,
            row["z_km"] * 1000,
        ])

    return {
        "epoch": start_time.isoformat() if isinstance(start_time, datetime) else str(start_time),
        "cartesian": positions,
        "interpolationAlgorithm": "LAGRANGE",
        "interpolationDegree": 5,
    }
