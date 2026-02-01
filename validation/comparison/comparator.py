"""Validation comparator for running comparisons between simulator and reference data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from sim.core.types import InitialState
from sim.models.orbit import OrbitPropagator, EphemerisPoint, EARTH_RADIUS_KM
from sim.models.access import AccessModel, GroundStation, get_default_stations

from .metrics import (
    EphemerisMetrics,
    AccessMetrics,
    compute_ephemeris_metrics,
    compute_access_metrics,
    compute_error_growth_rate,
)


@dataclass
class ValidationResult:
    """Result of a validation comparison."""

    scenario_id: str
    scenario_type: str  # "propagation", "orbit_lowering", "access"
    timestamp: datetime
    passed: bool
    metrics: Dict
    details: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "scenario_id": self.scenario_id,
            "scenario_type": self.scenario_type,
            "timestamp": self.timestamp.isoformat(),
            "passed": self.passed,
            "metrics": self.metrics,
            "details": self.details,
        }


class ValidationComparator:
    """
    Comparator for validating simulator output against reference data.

    Supports comparison of:
    - Ephemeris (position/velocity)
    - Orbital elements
    - Ground station access windows
    """

    def __init__(
        self,
        reference_dir: Optional[Path] = None,
        thresholds: Optional[Dict] = None,
    ):
        """
        Initialize comparator.

        Args:
            reference_dir: Path to reference data directory
            thresholds: Custom pass/fail thresholds
        """
        if reference_dir is None:
            reference_dir = Path(__file__).parent.parent / "reference"
        self.reference_dir = Path(reference_dir)

        self.thresholds = {
            "position_rms_km": 5.0,
            "velocity_rms_m_s": 5.0,
            "altitude_rms_km": 2.0,
            "access_timing_s": 60.0,
        }
        if thresholds:
            self.thresholds.update(thresholds)

    def validate_propagation(
        self,
        scenario_id: str,
        initial_state: InitialState,
        duration_hours: float = 12.0,
        step_s: float = 60.0,
    ) -> ValidationResult:
        """
        Validate SGP4 propagation against reference data.

        Args:
            scenario_id: Scenario identifier
            initial_state: Initial state for propagation
            duration_hours: Duration to propagate
            step_s: Time step in seconds

        Returns:
            ValidationResult with comparison metrics
        """
        from datetime import timedelta

        # Run simulator propagation
        propagator = OrbitPropagator(
            altitude_km=initial_state.position_eci[0] - EARTH_RADIUS_KM
            if initial_state.position_eci is not None else 500.0,
            inclination_deg=53.0,
            epoch=initial_state.epoch,
        )

        # If we have position/velocity, use them directly
        # For now, use the propagator initialized above
        end_time = initial_state.epoch + timedelta(hours=duration_hours)
        ephemeris = propagator.propagate_range(
            initial_state.epoch,
            end_time,
            step_s,
        )

        # Convert to DataFrame
        sim_df = self._ephemeris_to_dataframe(ephemeris)

        # Load reference data
        ref_df = self._load_reference_ephemeris(scenario_id)

        if ref_df is None or len(ref_df) == 0:
            return ValidationResult(
                scenario_id=scenario_id,
                scenario_type="propagation",
                timestamp=datetime.now(timezone.utc),
                passed=False,
                metrics={},
                details={"error": "Reference data not found"},
            )

        # Compute metrics
        metrics = compute_ephemeris_metrics(
            sim_df,
            ref_df,
            position_threshold_km=self.thresholds["position_rms_km"],
            velocity_threshold_m_s=self.thresholds["velocity_rms_m_s"],
            altitude_threshold_km=self.thresholds["altitude_rms_km"],
        )

        # Compute error growth
        error_growth = compute_error_growth_rate(sim_df, ref_df)

        return ValidationResult(
            scenario_id=scenario_id,
            scenario_type="propagation",
            timestamp=datetime.now(timezone.utc),
            passed=metrics.all_passed,
            metrics=metrics.to_dict(),
            details={
                "num_sim_points": len(sim_df),
                "num_ref_points": len(ref_df),
                "final_position_error_km": float(error_growth["position_error_km"].iloc[-1])
                if len(error_growth) > 0 else None,
            },
        )

    def validate_access(
        self,
        scenario_id: str,
        initial_state: InitialState,
        stations: Optional[List[GroundStation]] = None,
        duration_hours: float = 24.0,
        step_s: float = 60.0,
    ) -> ValidationResult:
        """
        Validate ground station access computation against reference data.

        Args:
            scenario_id: Scenario identifier
            initial_state: Initial state for propagation
            stations: Ground stations to check (defaults to standard set)
            duration_hours: Duration to check access
            step_s: Time step for ephemeris

        Returns:
            ValidationResult with comparison metrics
        """
        from datetime import timedelta

        if stations is None:
            stations = get_default_stations()

        # Run simulator propagation
        propagator = OrbitPropagator(
            altitude_km=500.0,
            inclination_deg=53.0,
            epoch=initial_state.epoch,
        )

        end_time = initial_state.epoch + timedelta(hours=duration_hours)
        ephemeris = propagator.propagate_range(
            initial_state.epoch,
            end_time,
            step_s,
        )

        # Compute access windows
        access_model = AccessModel(stations)
        all_windows = access_model.compute_all_access_windows(ephemeris)

        # Compare against reference for each station
        all_metrics = {}
        overall_passed = True

        for station in stations:
            sim_windows = all_windows.get(station.station_id, [])

            # Convert to dict format
            sim_windows_dict = [
                {
                    "start_time": w.start_time,
                    "end_time": w.end_time,
                }
                for w in sim_windows
            ]

            # Load reference
            ref_windows = self._load_reference_access(scenario_id, station.station_id)

            if ref_windows is None:
                continue

            # Compute metrics
            station_metrics = compute_access_metrics(
                sim_windows_dict,
                ref_windows,
                timing_threshold_s=self.thresholds["access_timing_s"],
            )

            all_metrics[station.station_id] = station_metrics.to_dict()
            if not station_metrics.all_passed:
                overall_passed = False

        return ValidationResult(
            scenario_id=scenario_id,
            scenario_type="access",
            timestamp=datetime.now(timezone.utc),
            passed=overall_passed,
            metrics=all_metrics,
            details={
                "num_stations": len(stations),
                "duration_hours": duration_hours,
            },
        )

    def validate_from_reference(
        self,
        scenario_id: str,
        sim_ephemeris: pd.DataFrame,
    ) -> ValidationResult:
        """
        Validate simulator ephemeris against stored reference data.

        Args:
            scenario_id: Scenario identifier
            sim_ephemeris: Simulator ephemeris DataFrame

        Returns:
            ValidationResult
        """
        ref_df = self._load_reference_ephemeris(scenario_id)

        if ref_df is None or len(ref_df) == 0:
            return ValidationResult(
                scenario_id=scenario_id,
                scenario_type="propagation",
                timestamp=datetime.now(timezone.utc),
                passed=False,
                metrics={},
                details={"error": "Reference data not found"},
            )

        metrics = compute_ephemeris_metrics(
            sim_ephemeris,
            ref_df,
            position_threshold_km=self.thresholds["position_rms_km"],
            velocity_threshold_m_s=self.thresholds["velocity_rms_m_s"],
            altitude_threshold_km=self.thresholds["altitude_rms_km"],
        )

        return ValidationResult(
            scenario_id=scenario_id,
            scenario_type="propagation",
            timestamp=datetime.now(timezone.utc),
            passed=metrics.all_passed,
            metrics=metrics.to_dict(),
        )

    def _ephemeris_to_dataframe(self, ephemeris: List[EphemerisPoint]) -> pd.DataFrame:
        """Convert ephemeris points to DataFrame."""
        records = []
        for point in ephemeris:
            records.append({
                "time": point.time,
                "x_km": point.position_eci[0],
                "y_km": point.position_eci[1],
                "z_km": point.position_eci[2],
                "vx_km_s": point.velocity_eci[0],
                "vy_km_s": point.velocity_eci[1],
                "vz_km_s": point.velocity_eci[2],
            })
        return pd.DataFrame(records)

    def _load_reference_ephemeris(self, scenario_id: str) -> Optional[pd.DataFrame]:
        """Load reference ephemeris for a scenario."""
        from validation.gmat.parser import GMATOutputParser

        parser = GMATOutputParser()

        # Try different locations
        possible_paths = [
            self.reference_dir / "pure_propagation" / f"ephemeris_{scenario_id}.csv",
            self.reference_dir / "pure_propagation" / f"ephemeris_{scenario_id}.txt",
            self.reference_dir / "orbit_lowering" / f"ephemeris_{scenario_id}.csv",
            self.reference_dir / "orbit_lowering" / f"ephemeris_{scenario_id}.txt",
            self.reference_dir / f"ephemeris_{scenario_id}.csv",
        ]

        for path in possible_paths:
            if path.exists():
                if path.suffix == ".csv":
                    df = pd.read_csv(path)
                    if "time" in df.columns:
                        df["time"] = pd.to_datetime(df["time"], utc=True)
                    return df
                else:
                    return parser.parse_ephemeris_report(path)

        return None

    def _load_reference_access(
        self,
        scenario_id: str,
        station_id: str
    ) -> Optional[List[Dict]]:
        """Load reference access windows for a scenario and station."""
        import json

        possible_paths = [
            self.reference_dir / "access_windows" / f"access_{station_id}_{scenario_id}.json",
            self.reference_dir / "access_windows" / f"{station_id}_{scenario_id}.json",
            self.reference_dir / f"access_{station_id}.json",
        ]

        for path in possible_paths:
            if path.exists():
                with open(path) as f:
                    return json.load(f)

        return None


def run_all_validations(
    reference_dir: Optional[Path] = None,
    thresholds: Optional[Dict] = None,
) -> List[ValidationResult]:
    """
    Run all validation scenarios.

    Args:
        reference_dir: Path to reference data
        thresholds: Custom thresholds

    Returns:
        List of validation results
    """
    comparator = ValidationComparator(reference_dir, thresholds)
    results = []

    # Standard epoch for validation scenarios
    epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

    # Create standard initial state
    initial_state = InitialState(
        epoch=epoch,
        position_eci=np.array([6878.137, 0.0, 0.0]),
        velocity_eci=np.array([0.0, 7.612, 0.0]),
    )

    # Propagation validation
    results.append(comparator.validate_propagation(
        "pure_prop_12h",
        initial_state,
        duration_hours=12.0,
    ))

    # Access validation
    results.append(comparator.validate_access(
        "access_24h",
        initial_state,
        duration_hours=24.0,
    ))

    return results
