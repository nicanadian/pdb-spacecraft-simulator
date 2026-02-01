"""Validation metrics for comparing simulator output with GMAT reference."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class EphemerisMetrics:
    """Metrics for ephemeris comparison."""

    # Position metrics (km)
    position_rms_km: float
    position_max_km: float
    position_mean_km: float

    # Velocity metrics (m/s)
    velocity_rms_m_s: float
    velocity_max_m_s: float
    velocity_mean_m_s: float

    # Altitude metrics (km)
    altitude_rms_km: float
    altitude_max_km: float
    altitude_bias_km: float  # mean(sim - ref)

    # Component-wise position metrics (km)
    x_rms_km: float
    y_rms_km: float
    z_rms_km: float

    # Time span
    start_time: datetime
    end_time: datetime
    duration_hours: float
    num_points: int

    # Thresholds for pass/fail
    position_threshold_km: float = 5.0
    velocity_threshold_m_s: float = 5.0
    altitude_threshold_km: float = 2.0

    @property
    def position_passed(self) -> bool:
        """Check if position RMS is within threshold."""
        return self.position_rms_km <= self.position_threshold_km

    @property
    def velocity_passed(self) -> bool:
        """Check if velocity RMS is within threshold."""
        return self.velocity_rms_m_s <= self.velocity_threshold_m_s

    @property
    def altitude_passed(self) -> bool:
        """Check if altitude RMS is within threshold."""
        return self.altitude_rms_km <= self.altitude_threshold_km

    @property
    def all_passed(self) -> bool:
        """Check if all metrics pass."""
        return self.position_passed and self.velocity_passed and self.altitude_passed

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "position_rms_km": self.position_rms_km,
            "position_max_km": self.position_max_km,
            "position_mean_km": self.position_mean_km,
            "velocity_rms_m_s": self.velocity_rms_m_s,
            "velocity_max_m_s": self.velocity_max_m_s,
            "velocity_mean_m_s": self.velocity_mean_m_s,
            "altitude_rms_km": self.altitude_rms_km,
            "altitude_max_km": self.altitude_max_km,
            "altitude_bias_km": self.altitude_bias_km,
            "x_rms_km": self.x_rms_km,
            "y_rms_km": self.y_rms_km,
            "z_rms_km": self.z_rms_km,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_hours": self.duration_hours,
            "num_points": self.num_points,
            "position_passed": self.position_passed,
            "velocity_passed": self.velocity_passed,
            "altitude_passed": self.altitude_passed,
            "all_passed": self.all_passed,
        }


@dataclass
class AccessMetrics:
    """Metrics for access window comparison."""

    # Timing errors (seconds)
    aos_rms_s: float  # AOS timing error RMS
    aos_max_s: float
    los_rms_s: float  # LOS timing error RMS
    los_max_s: float

    # Window matching
    num_reference_windows: int
    num_simulator_windows: int
    num_matched_windows: int
    num_missed_windows: int  # In reference but not simulator
    num_extra_windows: int  # In simulator but not reference

    # Duration errors
    duration_rms_s: float
    duration_max_s: float

    # Threshold
    timing_threshold_s: float = 60.0

    @property
    def timing_passed(self) -> bool:
        """Check if timing errors are within threshold."""
        return self.aos_rms_s <= self.timing_threshold_s and \
               self.los_rms_s <= self.timing_threshold_s

    @property
    def matching_passed(self) -> bool:
        """Check if window matching is acceptable (>90% match)."""
        if self.num_reference_windows == 0:
            return True
        match_rate = self.num_matched_windows / self.num_reference_windows
        return match_rate >= 0.9

    @property
    def all_passed(self) -> bool:
        """Check if all metrics pass."""
        return self.timing_passed and self.matching_passed

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "aos_rms_s": self.aos_rms_s,
            "aos_max_s": self.aos_max_s,
            "los_rms_s": self.los_rms_s,
            "los_max_s": self.los_max_s,
            "num_reference_windows": self.num_reference_windows,
            "num_simulator_windows": self.num_simulator_windows,
            "num_matched_windows": self.num_matched_windows,
            "num_missed_windows": self.num_missed_windows,
            "num_extra_windows": self.num_extra_windows,
            "duration_rms_s": self.duration_rms_s,
            "duration_max_s": self.duration_max_s,
            "timing_passed": self.timing_passed,
            "matching_passed": self.matching_passed,
            "all_passed": self.all_passed,
        }


def compute_ephemeris_metrics(
    sim_df: pd.DataFrame,
    ref_df: pd.DataFrame,
    position_threshold_km: float = 5.0,
    velocity_threshold_m_s: float = 5.0,
    altitude_threshold_km: float = 2.0,
) -> EphemerisMetrics:
    """
    Compute ephemeris comparison metrics.

    Args:
        sim_df: Simulator ephemeris DataFrame with columns:
            time, x_km, y_km, z_km, vx_km_s, vy_km_s, vz_km_s
        ref_df: Reference (GMAT) ephemeris DataFrame with same columns
        position_threshold_km: Pass/fail threshold for position RMS
        velocity_threshold_m_s: Pass/fail threshold for velocity RMS
        altitude_threshold_km: Pass/fail threshold for altitude RMS

    Returns:
        EphemerisMetrics with comparison results
    """
    # Time-align the data by interpolating reference to simulator times
    aligned_sim, aligned_ref = time_align_dataframes(sim_df, ref_df)

    if len(aligned_sim) == 0:
        raise ValueError("No overlapping time range between simulator and reference data")

    # Position differences (km)
    dx = aligned_sim["x_km"].values - aligned_ref["x_km"].values
    dy = aligned_sim["y_km"].values - aligned_ref["y_km"].values
    dz = aligned_sim["z_km"].values - aligned_ref["z_km"].values

    pos_errors = np.sqrt(dx**2 + dy**2 + dz**2)

    # Velocity differences (km/s -> m/s)
    dvx = (aligned_sim["vx_km_s"].values - aligned_ref["vx_km_s"].values) * 1000
    dvy = (aligned_sim["vy_km_s"].values - aligned_ref["vy_km_s"].values) * 1000
    dvz = (aligned_sim["vz_km_s"].values - aligned_ref["vz_km_s"].values) * 1000

    vel_errors = np.sqrt(dvx**2 + dvy**2 + dvz**2)

    # Altitude differences (km)
    EARTH_RADIUS = 6378.137
    sim_alt = np.sqrt(
        aligned_sim["x_km"]**2 + aligned_sim["y_km"]**2 + aligned_sim["z_km"]**2
    ) - EARTH_RADIUS
    ref_alt = np.sqrt(
        aligned_ref["x_km"]**2 + aligned_ref["y_km"]**2 + aligned_ref["z_km"]**2
    ) - EARTH_RADIUS

    alt_errors = sim_alt.values - ref_alt.values

    # Compute metrics
    start_time = aligned_sim["time"].iloc[0]
    end_time = aligned_sim["time"].iloc[-1]

    return EphemerisMetrics(
        # Position
        position_rms_km=float(np.sqrt(np.mean(pos_errors**2))),
        position_max_km=float(np.max(pos_errors)),
        position_mean_km=float(np.mean(pos_errors)),

        # Velocity
        velocity_rms_m_s=float(np.sqrt(np.mean(vel_errors**2))),
        velocity_max_m_s=float(np.max(vel_errors)),
        velocity_mean_m_s=float(np.mean(vel_errors)),

        # Altitude
        altitude_rms_km=float(np.sqrt(np.mean(alt_errors**2))),
        altitude_max_km=float(np.max(np.abs(alt_errors))),
        altitude_bias_km=float(np.mean(alt_errors)),

        # Component-wise
        x_rms_km=float(np.sqrt(np.mean(dx**2))),
        y_rms_km=float(np.sqrt(np.mean(dy**2))),
        z_rms_km=float(np.sqrt(np.mean(dz**2))),

        # Time span
        start_time=start_time,
        end_time=end_time,
        duration_hours=(end_time - start_time).total_seconds() / 3600,
        num_points=len(aligned_sim),

        # Thresholds
        position_threshold_km=position_threshold_km,
        velocity_threshold_m_s=velocity_threshold_m_s,
        altitude_threshold_km=altitude_threshold_km,
    )


def compute_access_metrics(
    sim_windows: List[Dict],
    ref_windows: List[Dict],
    timing_threshold_s: float = 60.0,
    match_threshold_s: float = 300.0,
) -> AccessMetrics:
    """
    Compute access window comparison metrics.

    Args:
        sim_windows: Simulator access windows as list of dicts with
            start_time, end_time keys
        ref_windows: Reference access windows
        timing_threshold_s: Pass/fail threshold for timing error RMS
        match_threshold_s: Maximum time difference to consider windows matched

    Returns:
        AccessMetrics with comparison results
    """
    # Convert to datetime if needed
    def to_datetime(val):
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(str(val))

    sim_windows = [
        {"start": to_datetime(w.get("start_time", w.get("start"))),
         "end": to_datetime(w.get("end_time", w.get("end")))}
        for w in sim_windows
    ]
    ref_windows = [
        {"start": to_datetime(w.get("start_time", w.get("start"))),
         "end": to_datetime(w.get("end_time", w.get("end")))}
        for w in ref_windows
    ]

    # Sort by start time
    sim_windows = sorted(sim_windows, key=lambda w: w["start"])
    ref_windows = sorted(ref_windows, key=lambda w: w["start"])

    # Match windows
    matched_pairs = []
    matched_ref_indices = set()
    matched_sim_indices = set()

    for i, sim_w in enumerate(sim_windows):
        best_match = None
        best_diff = float("inf")

        for j, ref_w in enumerate(ref_windows):
            if j in matched_ref_indices:
                continue

            # Check if windows overlap or are close
            start_diff = abs((sim_w["start"] - ref_w["start"]).total_seconds())
            end_diff = abs((sim_w["end"] - ref_w["end"]).total_seconds())

            if start_diff < match_threshold_s:
                if start_diff < best_diff:
                    best_diff = start_diff
                    best_match = j

        if best_match is not None:
            matched_pairs.append((i, best_match))
            matched_ref_indices.add(best_match)
            matched_sim_indices.add(i)

    # Calculate timing errors for matched windows
    aos_errors = []
    los_errors = []
    duration_errors = []

    for sim_idx, ref_idx in matched_pairs:
        sim_w = sim_windows[sim_idx]
        ref_w = ref_windows[ref_idx]

        aos_err = (sim_w["start"] - ref_w["start"]).total_seconds()
        los_err = (sim_w["end"] - ref_w["end"]).total_seconds()

        sim_dur = (sim_w["end"] - sim_w["start"]).total_seconds()
        ref_dur = (ref_w["end"] - ref_w["start"]).total_seconds()
        dur_err = sim_dur - ref_dur

        aos_errors.append(aos_err)
        los_errors.append(los_err)
        duration_errors.append(dur_err)

    # Handle case with no matches
    if not aos_errors:
        aos_errors = [0.0]
        los_errors = [0.0]
        duration_errors = [0.0]

    return AccessMetrics(
        aos_rms_s=float(np.sqrt(np.mean(np.array(aos_errors)**2))),
        aos_max_s=float(np.max(np.abs(aos_errors))),
        los_rms_s=float(np.sqrt(np.mean(np.array(los_errors)**2))),
        los_max_s=float(np.max(np.abs(los_errors))),
        num_reference_windows=len(ref_windows),
        num_simulator_windows=len(sim_windows),
        num_matched_windows=len(matched_pairs),
        num_missed_windows=len(ref_windows) - len(matched_pairs),
        num_extra_windows=len(sim_windows) - len(matched_pairs),
        duration_rms_s=float(np.sqrt(np.mean(np.array(duration_errors)**2))),
        duration_max_s=float(np.max(np.abs(duration_errors))),
        timing_threshold_s=timing_threshold_s,
    )


def time_align_dataframes(
    sim_df: pd.DataFrame,
    ref_df: pd.DataFrame,
    max_gap_s: float = 120.0,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Time-align two DataFrames by interpolating to common time points.

    Args:
        sim_df: Simulator DataFrame with 'time' column
        ref_df: Reference DataFrame with 'time' column
        max_gap_s: Maximum time gap to interpolate across

    Returns:
        Tuple of (aligned_sim_df, aligned_ref_df) with same time indices
    """
    # Ensure time columns are datetime
    sim_df = sim_df.copy()
    ref_df = ref_df.copy()

    # Convert to pandas datetime if needed and ensure timezone consistency
    if not pd.api.types.is_datetime64_any_dtype(sim_df["time"]):
        sim_df["time"] = pd.to_datetime(sim_df["time"], utc=True)
    if not pd.api.types.is_datetime64_any_dtype(ref_df["time"]):
        ref_df["time"] = pd.to_datetime(ref_df["time"], utc=True)

    # Find overlapping time range
    sim_start = sim_df["time"].min()
    sim_end = sim_df["time"].max()
    ref_start = ref_df["time"].min()
    ref_end = ref_df["time"].max()

    common_start = max(sim_start, ref_start)
    common_end = min(sim_end, ref_end)

    if common_end <= common_start:
        return pd.DataFrame(), pd.DataFrame()

    # Filter to common range
    sim_df = sim_df[(sim_df["time"] >= common_start) & (sim_df["time"] <= common_end)]
    ref_df = ref_df[(ref_df["time"] >= common_start) & (ref_df["time"] <= common_end)]

    # Use simulator times as the reference
    sim_times = sim_df["time"].values

    # Interpolate reference data to simulator times
    ref_numeric = ref_df.drop(columns=["time"])
    ref_times = ref_df["time"].values

    # Convert times to numeric (seconds since epoch) for interpolation
    # Use numpy datetime64 for consistent arithmetic
    common_start_np = np.datetime64(common_start)

    def to_seconds(dt_array):
        return np.array([(np.datetime64(t) - common_start_np) / np.timedelta64(1, 's') for t in dt_array])

    sim_seconds = to_seconds(sim_times)
    ref_seconds = to_seconds(ref_times)

    interpolated_ref = {}
    for col in ref_numeric.columns:
        interpolated_ref[col] = np.interp(sim_seconds, ref_seconds, ref_df[col].values)

    interpolated_ref["time"] = sim_df["time"].values

    ref_aligned = pd.DataFrame(interpolated_ref)

    return sim_df.reset_index(drop=True), ref_aligned.reset_index(drop=True)


def compute_error_growth_rate(
    sim_df: pd.DataFrame,
    ref_df: pd.DataFrame,
    window_hours: float = 1.0,
) -> pd.DataFrame:
    """
    Compute error growth rate over time.

    Args:
        sim_df: Simulator ephemeris
        ref_df: Reference ephemeris
        window_hours: Window size for computing RMS

    Returns:
        DataFrame with time-dependent error metrics
    """
    aligned_sim, aligned_ref = time_align_dataframes(sim_df, ref_df)

    if len(aligned_sim) == 0:
        return pd.DataFrame()

    # Position errors
    dx = aligned_sim["x_km"].values - aligned_ref["x_km"].values
    dy = aligned_sim["y_km"].values - aligned_ref["y_km"].values
    dz = aligned_sim["z_km"].values - aligned_ref["z_km"].values
    pos_errors = np.sqrt(dx**2 + dy**2 + dz**2)

    # Create time series
    times = aligned_sim["time"].values
    start_time = times[0]

    # Convert timedelta64 to hours
    elapsed_hours = np.array([
        (np.datetime64(t) - np.datetime64(start_time)) / np.timedelta64(1, 'h') for t in times
    ])

    # Compute rolling RMS
    window_size = int(window_hours * 60)  # Assuming 1-minute data
    window_size = max(1, min(window_size, len(pos_errors)))

    rms_values = []
    for i in range(len(pos_errors)):
        start_idx = max(0, i - window_size // 2)
        end_idx = min(len(pos_errors), i + window_size // 2)
        window = pos_errors[start_idx:end_idx]
        rms_values.append(np.sqrt(np.mean(window**2)))

    return pd.DataFrame({
        "time": times,
        "elapsed_hours": elapsed_hours,
        "position_error_km": pos_errors,
        "position_rms_km": rms_values,
    })
