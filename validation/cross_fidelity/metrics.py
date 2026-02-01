"""
Metrics for cross-fidelity validation.

Computes comparison metrics between LOW and MEDIUM/HIGH fidelity runs
to validate simulation accuracy and identify significant differences.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class PositionDelta:
    """Position difference metrics."""

    rms_km: float  # RMS position difference
    max_km: float  # Maximum position difference
    mean_km: float  # Mean position difference
    along_track_rms_km: float  # Along-track component
    cross_track_rms_km: float  # Cross-track component
    radial_rms_km: float  # Radial component


@dataclass
class TimingDelta:
    """Timing difference metrics for events."""

    rms_s: float  # RMS timing difference
    max_s: float  # Maximum timing difference
    mean_s: float  # Mean timing difference
    count_matched: int  # Number of matched events
    count_unmatched_a: int  # Events only in run A
    count_unmatched_b: int  # Events only in run B


@dataclass
class ContactComparison:
    """Comparison of ground station contacts."""

    station_id: str
    aos_delta_s: float  # AOS time difference
    los_delta_s: float  # LOS time difference
    duration_delta_s: float  # Duration difference
    matched: bool


@dataclass
class CrossFidelityMetrics:
    """Complete set of cross-fidelity comparison metrics."""

    position: PositionDelta
    contact_timing: TimingDelta
    eclipse_timing: Optional[TimingDelta] = None
    altitude_delta: Optional[PositionDelta] = None
    contacts: List[ContactComparison] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "position": {
                "rms_km": self.position.rms_km,
                "max_km": self.position.max_km,
                "mean_km": self.position.mean_km,
                "along_track_rms_km": self.position.along_track_rms_km,
                "cross_track_rms_km": self.position.cross_track_rms_km,
                "radial_rms_km": self.position.radial_rms_km,
            },
            "contact_timing": {
                "rms_s": self.contact_timing.rms_s,
                "max_s": self.contact_timing.max_s,
                "mean_s": self.contact_timing.mean_s,
                "matched": self.contact_timing.count_matched,
                "unmatched_low": self.contact_timing.count_unmatched_a,
                "unmatched_medium": self.contact_timing.count_unmatched_b,
            },
            "eclipse_timing": {
                "rms_s": self.eclipse_timing.rms_s,
                "max_s": self.eclipse_timing.max_s,
                "mean_s": self.eclipse_timing.mean_s,
            } if self.eclipse_timing else None,
            "contacts": [
                {
                    "station_id": c.station_id,
                    "aos_delta_s": c.aos_delta_s,
                    "los_delta_s": c.los_delta_s,
                    "duration_delta_s": c.duration_delta_s,
                    "matched": c.matched,
                }
                for c in self.contacts
            ],
        }


def compute_position_delta(
    ephemeris_a: pd.DataFrame,
    ephemeris_b: pd.DataFrame,
    time_tolerance_s: float = 60.0,
) -> PositionDelta:
    """
    Compute position difference between two ephemeris datasets.

    Args:
        ephemeris_a: First ephemeris DataFrame with x_km, y_km, z_km columns
        ephemeris_b: Second ephemeris DataFrame
        time_tolerance_s: Time tolerance for matching points

    Returns:
        PositionDelta with RMS, max, and component metrics
    """
    # Ensure time index
    if "time" in ephemeris_a.columns:
        ephemeris_a = ephemeris_a.set_index("time")
    if "time" in ephemeris_b.columns:
        ephemeris_b = ephemeris_b.set_index("time")

    # Find common time points (interpolate if needed)
    common_times = ephemeris_a.index.intersection(ephemeris_b.index)

    if len(common_times) == 0:
        # Try to resample to common grid
        combined = pd.concat([
            ephemeris_a[["x_km", "y_km", "z_km"]].add_suffix("_a"),
            ephemeris_b[["x_km", "y_km", "z_km"]].add_suffix("_b"),
        ], axis=1).interpolate(method="time")
        combined = combined.dropna()
    else:
        combined = pd.DataFrame({
            "x_a": ephemeris_a.loc[common_times, "x_km"],
            "y_a": ephemeris_a.loc[common_times, "y_km"],
            "z_a": ephemeris_a.loc[common_times, "z_km"],
            "x_b": ephemeris_b.loc[common_times, "x_km"],
            "y_b": ephemeris_b.loc[common_times, "y_km"],
            "z_b": ephemeris_b.loc[common_times, "z_km"],
        })

    if len(combined) == 0:
        return PositionDelta(
            rms_km=float("nan"),
            max_km=float("nan"),
            mean_km=float("nan"),
            along_track_rms_km=float("nan"),
            cross_track_rms_km=float("nan"),
            radial_rms_km=float("nan"),
        )

    # Compute position differences
    if "x_km_a" in combined.columns:
        dx = combined["x_km_a"] - combined["x_km_b"]
        dy = combined["y_km_a"] - combined["y_km_b"]
        dz = combined["z_km_a"] - combined["z_km_b"]
    else:
        dx = combined["x_a"] - combined["x_b"]
        dy = combined["y_a"] - combined["y_b"]
        dz = combined["z_a"] - combined["z_b"]

    dr = np.sqrt(dx**2 + dy**2 + dz**2)

    # Compute RSW components (simplified - assumes circular orbit)
    # R: radial, S: along-track, W: cross-track
    # For accurate RSW, need velocity vector
    radial = np.abs(dz)  # Approximate
    along_track = np.abs(dx)  # Approximate
    cross_track = np.abs(dy)  # Approximate

    return PositionDelta(
        rms_km=float(np.sqrt(np.mean(dr**2))),
        max_km=float(np.max(dr)),
        mean_km=float(np.mean(dr)),
        along_track_rms_km=float(np.sqrt(np.mean(along_track**2))),
        cross_track_rms_km=float(np.sqrt(np.mean(cross_track**2))),
        radial_rms_km=float(np.sqrt(np.mean(radial**2))),
    )


def compute_contact_timing_delta(
    contacts_a: Dict[str, List[Dict]],
    contacts_b: Dict[str, List[Dict]],
    time_tolerance_s: float = 300.0,
) -> Tuple[TimingDelta, List[ContactComparison]]:
    """
    Compare contact timing between two runs.

    Args:
        contacts_a: Access windows from run A (station_id -> list of windows)
        contacts_b: Access windows from run B
        time_tolerance_s: Maximum time difference to consider a match

    Returns:
        Tuple of (TimingDelta summary, list of ContactComparisons)
    """
    aos_deltas = []
    los_deltas = []
    comparisons = []
    unmatched_a = 0
    unmatched_b = 0

    all_stations = set(contacts_a.keys()) | set(contacts_b.keys())

    for station_id in all_stations:
        windows_a = contacts_a.get(station_id, [])
        windows_b = contacts_b.get(station_id, [])

        # Match windows by AOS time
        matched_b = set()

        for wa in windows_a:
            aos_a = _parse_time(wa.get("start_time", wa.get("aos")))
            los_a = _parse_time(wa.get("end_time", wa.get("los")))

            best_match = None
            best_delta = float("inf")

            for i, wb in enumerate(windows_b):
                if i in matched_b:
                    continue

                aos_b = _parse_time(wb.get("start_time", wb.get("aos")))
                delta = abs((aos_a - aos_b).total_seconds())

                if delta < best_delta and delta < time_tolerance_s:
                    best_delta = delta
                    best_match = (i, wb)

            if best_match:
                i, wb = best_match
                matched_b.add(i)

                aos_b = _parse_time(wb.get("start_time", wb.get("aos")))
                los_b = _parse_time(wb.get("end_time", wb.get("los")))

                aos_delta = (aos_a - aos_b).total_seconds()
                los_delta = (los_a - los_b).total_seconds()
                duration_a = (los_a - aos_a).total_seconds()
                duration_b = (los_b - aos_b).total_seconds()

                aos_deltas.append(aos_delta)
                los_deltas.append(los_delta)

                comparisons.append(ContactComparison(
                    station_id=station_id,
                    aos_delta_s=aos_delta,
                    los_delta_s=los_delta,
                    duration_delta_s=duration_a - duration_b,
                    matched=True,
                ))
            else:
                unmatched_a += 1
                comparisons.append(ContactComparison(
                    station_id=station_id,
                    aos_delta_s=float("nan"),
                    los_delta_s=float("nan"),
                    duration_delta_s=float("nan"),
                    matched=False,
                ))

        unmatched_b += len(windows_b) - len(matched_b)

    # Compute summary statistics
    all_deltas = aos_deltas + los_deltas

    if all_deltas:
        timing = TimingDelta(
            rms_s=float(np.sqrt(np.mean(np.array(all_deltas)**2))),
            max_s=float(np.max(np.abs(all_deltas))),
            mean_s=float(np.mean(all_deltas)),
            count_matched=len(aos_deltas),
            count_unmatched_a=unmatched_a,
            count_unmatched_b=unmatched_b,
        )
    else:
        timing = TimingDelta(
            rms_s=0.0,
            max_s=0.0,
            mean_s=0.0,
            count_matched=0,
            count_unmatched_a=unmatched_a,
            count_unmatched_b=unmatched_b,
        )

    return timing, comparisons


def compute_eclipse_timing_delta(
    eclipses_a: List[Dict],
    eclipses_b: List[Dict],
    time_tolerance_s: float = 120.0,
) -> TimingDelta:
    """
    Compare eclipse timing between two runs.

    Args:
        eclipses_a: Eclipse windows from run A
        eclipses_b: Eclipse windows from run B
        time_tolerance_s: Maximum time difference to consider a match

    Returns:
        TimingDelta with eclipse timing comparison
    """
    entry_deltas = []
    exit_deltas = []
    matched_b = set()
    unmatched_a = 0

    for ea in eclipses_a:
        entry_a = _parse_time(ea.get("start_time", ea.get("entry")))
        exit_a = _parse_time(ea.get("end_time", ea.get("exit")))

        best_match = None
        best_delta = float("inf")

        for i, eb in enumerate(eclipses_b):
            if i in matched_b:
                continue

            entry_b = _parse_time(eb.get("start_time", eb.get("entry")))
            delta = abs((entry_a - entry_b).total_seconds())

            if delta < best_delta and delta < time_tolerance_s:
                best_delta = delta
                best_match = (i, eb)

        if best_match:
            i, eb = best_match
            matched_b.add(i)

            entry_b = _parse_time(eb.get("start_time", eb.get("entry")))
            exit_b = _parse_time(eb.get("end_time", eb.get("exit")))

            entry_deltas.append((entry_a - entry_b).total_seconds())
            exit_deltas.append((exit_a - exit_b).total_seconds())
        else:
            unmatched_a += 1

    unmatched_b = len(eclipses_b) - len(matched_b)
    all_deltas = entry_deltas + exit_deltas

    if all_deltas:
        return TimingDelta(
            rms_s=float(np.sqrt(np.mean(np.array(all_deltas)**2))),
            max_s=float(np.max(np.abs(all_deltas))),
            mean_s=float(np.mean(all_deltas)),
            count_matched=len(entry_deltas),
            count_unmatched_a=unmatched_a,
            count_unmatched_b=unmatched_b,
        )
    else:
        return TimingDelta(
            rms_s=0.0, max_s=0.0, mean_s=0.0,
            count_matched=0,
            count_unmatched_a=unmatched_a,
            count_unmatched_b=unmatched_b,
        )


def _parse_time(time_val: Any) -> datetime:
    """Parse time value to datetime."""
    if isinstance(time_val, datetime):
        return time_val
    if isinstance(time_val, str):
        return datetime.fromisoformat(time_val.replace("Z", "+00:00"))
    raise ValueError(f"Cannot parse time: {time_val}")
