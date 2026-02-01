"""Regression comparison between simulator and GMAT baselines."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .baseline import GMATBaseline
from .baseline_manager import GMATBaselineManager
from .tolerance_config import GMATToleranceConfig, load_default_tolerance_config


@dataclass
class RegressionResult:
    """Result of regression comparison against GMAT baseline."""

    passed: bool
    scenario_id: str
    metrics: Dict[str, float]        # Computed metrics
    tolerances: Dict[str, float]     # Applied tolerances
    failures: List[str]              # Which checks failed
    absolute_errors: Dict[str, float]
    relative_errors: Dict[str, float]
    num_points_compared: int
    baseline_version: str
    baseline_hash: str

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "passed": self.passed,
            "scenario_id": self.scenario_id,
            "metrics": self.metrics,
            "tolerances": self.tolerances,
            "failures": self.failures,
            "absolute_errors": self.absolute_errors,
            "relative_errors": self.relative_errors,
            "num_points_compared": self.num_points_compared,
            "baseline_version": self.baseline_version,
            "baseline_hash": self.baseline_hash,
        }

    @property
    def summary(self) -> str:
        """Generate human-readable summary."""
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"Regression Result: {status}",
            f"  Scenario: {self.scenario_id}",
            f"  Baseline: {self.baseline_version} (hash: {self.baseline_hash[:8]})",
            f"  Points compared: {self.num_points_compared}",
            "",
            "  Metrics:",
        ]

        for metric, value in self.metrics.items():
            tolerance = self.tolerances.get(metric, "N/A")
            status_icon = "✓" if metric not in self.failures else "✗"
            lines.append(f"    {status_icon} {metric}: {value:.4f} (tolerance: {tolerance})")

        if self.failures:
            lines.append("")
            lines.append("  Failures:")
            for failure in self.failures:
                lines.append(f"    - {failure}")

        return "\n".join(lines)


class GMATRegressionComparator:
    """
    Comparator for regression testing against GMAT baselines.

    Loads stored baselines and compares simulator output against them,
    applying configurable tolerances.
    """

    def __init__(
        self,
        baseline_manager: Optional[GMATBaselineManager] = None,
        tolerance_config: Optional[GMATToleranceConfig] = None,
    ):
        """
        Initialize regression comparator.

        Args:
            baseline_manager: Manager for baseline storage/retrieval.
                Defaults to standard location.
            tolerance_config: Tolerance configuration.
                Defaults to values from validation_config.yaml.
        """
        self.baseline_manager = baseline_manager or GMATBaselineManager()
        self.tolerance_config = tolerance_config or load_default_tolerance_config()

    def compare_ephemeris(
        self,
        scenario_id: str,
        sim_ephemeris: pd.DataFrame,
        baseline_version: str = "latest",
    ) -> RegressionResult:
        """
        Compare simulator ephemeris against GMAT baseline.

        Args:
            scenario_id: Scenario identifier
            sim_ephemeris: Simulator output DataFrame with columns:
                time, x_km, y_km, z_km, vx_km_s, vy_km_s, vz_km_s
            baseline_version: Baseline version to compare against

        Returns:
            RegressionResult with detailed comparison

        Raises:
            FileNotFoundError: If baseline not found
        """
        # Load baseline
        baseline = self.baseline_manager.load_baseline(scenario_id, baseline_version)
        baseline_df = baseline.to_dataframe()

        # Get tolerances for this scenario
        tolerances = self.tolerance_config.get_tolerances_for_scenario(scenario_id)

        # Time-align the data
        aligned_sim, aligned_ref = self._time_align(sim_ephemeris, baseline_df)

        if len(aligned_sim) == 0:
            return RegressionResult(
                passed=False,
                scenario_id=scenario_id,
                metrics={},
                tolerances=tolerances,
                failures=["No overlapping time range between simulator and baseline"],
                absolute_errors={},
                relative_errors={},
                num_points_compared=0,
                baseline_version=baseline_version,
                baseline_hash=baseline.metadata.scenario_hash,
            )

        # Compute position errors
        dx = aligned_sim["x_km"].values - aligned_ref["x_km"].values
        dy = aligned_sim["y_km"].values - aligned_ref["y_km"].values
        dz = aligned_sim["z_km"].values - aligned_ref["z_km"].values
        pos_errors = np.sqrt(dx**2 + dy**2 + dz**2)

        # Compute velocity errors (km/s -> m/s)
        dvx = (aligned_sim["vx_km_s"].values - aligned_ref["vx_km_s"].values) * 1000
        dvy = (aligned_sim["vy_km_s"].values - aligned_ref["vy_km_s"].values) * 1000
        dvz = (aligned_sim["vz_km_s"].values - aligned_ref["vz_km_s"].values) * 1000
        vel_errors = np.sqrt(dvx**2 + dvy**2 + dvz**2)

        # Compute metrics
        metrics = {
            "position_rms_km": float(np.sqrt(np.mean(pos_errors**2))),
            "position_max_km": float(np.max(pos_errors)),
            "position_mean_km": float(np.mean(pos_errors)),
            "velocity_rms_m_s": float(np.sqrt(np.mean(vel_errors**2))),
            "velocity_max_m_s": float(np.max(vel_errors)),
            "velocity_mean_m_s": float(np.mean(vel_errors)),
        }

        # Compute altitude errors
        ref_alt = np.sqrt(
            aligned_ref["x_km"]**2 + aligned_ref["y_km"]**2 + aligned_ref["z_km"]**2
        ) - 6378.137
        sim_alt = np.sqrt(
            aligned_sim["x_km"]**2 + aligned_sim["y_km"]**2 + aligned_sim["z_km"]**2
        ) - 6378.137
        alt_errors = np.abs(sim_alt.values - ref_alt.values)
        metrics["altitude_rms_km"] = float(np.sqrt(np.mean(alt_errors**2)))

        # Compute absolute errors
        absolute_errors = {
            "position_km": metrics["position_rms_km"],
            "velocity_m_s": metrics["velocity_rms_m_s"],
            "altitude_km": metrics["altitude_rms_km"],
        }

        # Compute relative errors (percentage of typical values)
        ref_pos_mag = np.sqrt(
            aligned_ref["x_km"]**2 + aligned_ref["y_km"]**2 + aligned_ref["z_km"]**2
        )
        ref_vel_mag = np.sqrt(
            aligned_ref["vx_km_s"]**2 + aligned_ref["vy_km_s"]**2 + aligned_ref["vz_km_s"]**2
        ) * 1000  # m/s

        relative_errors = {
            "position_pct": metrics["position_rms_km"] / float(ref_pos_mag.mean()) * 100,
            "velocity_pct": metrics["velocity_rms_m_s"] / float(ref_vel_mag.mean()) * 100,
        }

        # Check against tolerances
        failures = []
        if metrics["position_rms_km"] > tolerances["position_rms_km"]:
            failures.append(
                f"position_rms_km: {metrics['position_rms_km']:.4f} > {tolerances['position_rms_km']}"
            )
        if metrics["velocity_rms_m_s"] > tolerances["velocity_rms_m_s"]:
            failures.append(
                f"velocity_rms_m_s: {metrics['velocity_rms_m_s']:.4f} > {tolerances['velocity_rms_m_s']}"
            )
        if metrics["position_max_km"] > tolerances["position_max_km"]:
            failures.append(
                f"position_max_km: {metrics['position_max_km']:.4f} > {tolerances['position_max_km']}"
            )
        if metrics.get("velocity_max_m_s", 0) > tolerances.get("velocity_max_m_s", float("inf")):
            failures.append(
                f"velocity_max_m_s: {metrics['velocity_max_m_s']:.4f} > {tolerances['velocity_max_m_s']}"
            )
        if metrics["altitude_rms_km"] > tolerances["altitude_rms_km"]:
            failures.append(
                f"altitude_rms_km: {metrics['altitude_rms_km']:.4f} > {tolerances['altitude_rms_km']}"
            )

        return RegressionResult(
            passed=len(failures) == 0,
            scenario_id=scenario_id,
            metrics=metrics,
            tolerances=tolerances,
            failures=failures,
            absolute_errors=absolute_errors,
            relative_errors=relative_errors,
            num_points_compared=len(aligned_sim),
            baseline_version=baseline_version,
            baseline_hash=baseline.metadata.scenario_hash,
        )

    def _time_align(
        self,
        sim_df: pd.DataFrame,
        ref_df: pd.DataFrame,
    ) -> tuple:
        """
        Time-align two DataFrames by interpolating reference to simulator times.

        Args:
            sim_df: Simulator DataFrame with 'time' column
            ref_df: Reference DataFrame with 'time' column

        Returns:
            Tuple of (aligned_sim_df, aligned_ref_df)
        """
        sim_df = sim_df.copy()
        ref_df = ref_df.copy()

        # Ensure time columns are datetime
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

        # Use simulator times as reference
        sim_times = sim_df["time"].values
        ref_times = ref_df["time"].values

        # Convert to seconds from start for interpolation
        common_start_np = np.datetime64(common_start)

        def to_seconds(dt_array):
            return np.array([
                (np.datetime64(t) - common_start_np) / np.timedelta64(1, 's')
                for t in dt_array
            ])

        sim_seconds = to_seconds(sim_times)
        ref_seconds = to_seconds(ref_times)

        # Interpolate reference columns
        interpolated_ref = {"time": sim_df["time"].values}
        for col in ["x_km", "y_km", "z_km", "vx_km_s", "vy_km_s", "vz_km_s"]:
            if col in ref_df.columns:
                interpolated_ref[col] = np.interp(
                    sim_seconds, ref_seconds, ref_df[col].values
                )

        ref_aligned = pd.DataFrame(interpolated_ref)

        return sim_df.reset_index(drop=True), ref_aligned.reset_index(drop=True)

    def run_all_regressions(
        self,
        sim_results: Dict[str, pd.DataFrame],
    ) -> Dict[str, RegressionResult]:
        """
        Run regression tests for multiple scenarios.

        Args:
            sim_results: Dict mapping scenario_id to simulator ephemeris DataFrame

        Returns:
            Dict mapping scenario_id to RegressionResult
        """
        results = {}

        for scenario_id, sim_ephemeris in sim_results.items():
            if self.baseline_manager.has_baseline(scenario_id):
                results[scenario_id] = self.compare_ephemeris(scenario_id, sim_ephemeris)
            else:
                results[scenario_id] = RegressionResult(
                    passed=False,
                    scenario_id=scenario_id,
                    metrics={},
                    tolerances=self.tolerance_config.get_tolerances_for_scenario(scenario_id),
                    failures=[f"No baseline found for scenario: {scenario_id}"],
                    absolute_errors={},
                    relative_errors={},
                    num_points_compared=0,
                    baseline_version="N/A",
                    baseline_hash="N/A",
                )

        return results

    def generate_report(self, results: Dict[str, RegressionResult]) -> str:
        """
        Generate a summary report for multiple regression results.

        Args:
            results: Dict mapping scenario_id to RegressionResult

        Returns:
            Formatted report string
        """
        lines = [
            "=" * 60,
            "GMAT REGRESSION TEST REPORT",
            "=" * 60,
            "",
        ]

        passed = sum(1 for r in results.values() if r.passed)
        total = len(results)
        lines.append(f"Summary: {passed}/{total} scenarios passed")
        lines.append("")

        for scenario_id, result in results.items():
            lines.append("-" * 40)
            lines.append(result.summary)
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)
