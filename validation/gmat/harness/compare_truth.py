"""Truth comparison for GMAT regression tests.

Compares simulator results against GMAT truth files to verify
orbital mechanics fidelity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..case_registry import (
    CaseDefinition,
    CaseTruth,
    TruthCheckpoint,
    get_case,
)
from ..tolerance_config import GMATToleranceConfig, load_default_tolerance_config
from .generate_truth import TruthGenerator


@dataclass
class ComparisonResult:
    """Result of comparing simulator output against GMAT truth."""

    passed: bool
    case_id: str

    # Checkpoint comparisons
    initial_errors: Dict[str, float] = field(default_factory=dict)
    final_errors: Dict[str, float] = field(default_factory=dict)

    # Derived metric comparisons
    derived_errors: Dict[str, float] = field(default_factory=dict)

    # Tolerance violations
    failures: List[str] = field(default_factory=list)

    # Applied tolerances
    tolerances: Dict[str, float] = field(default_factory=dict)

    # Metadata
    truth_version: str = ""
    comparison_timestamp: str = ""

    @property
    def summary(self) -> str:
        """Generate human-readable summary."""
        status = "PASS" if self.passed else "FAIL"
        lines = [f"Case {self.case_id}: {status}"]

        if self.final_errors:
            lines.append("  Final state errors:")
            for key, value in sorted(self.final_errors.items()):
                tol = self.tolerances.get(key, float("inf"))
                marker = "!" if abs(value) > tol else " "
                lines.append(f"   {marker} {key}: {value:.6f} (tol: {tol:.6f})")

        if self.derived_errors:
            lines.append("  Derived metric errors:")
            for key, value in sorted(self.derived_errors.items()):
                tol = self.tolerances.get(key, float("inf"))
                marker = "!" if abs(value) > tol else " "
                lines.append(f"   {marker} {key}: {value:.6f} (tol: {tol:.6f})")

        if self.failures:
            lines.append("  Failures:")
            for failure in self.failures:
                lines.append(f"    - {failure}")

        return "\n".join(lines)

    @property
    def metrics(self) -> Dict[str, float]:
        """
        Get combined metrics dict for easy access.

        Returns a dict combining final_errors and derived_errors with
        standardized metric names for test compatibility.
        """
        metrics = {}

        # Add final errors with standardized names
        if self.final_errors:
            metrics.update(self.final_errors)
            # Map specific error keys to expected metric names
            if "position_error_km" in self.final_errors:
                metrics["position_rms_km"] = self.final_errors["position_error_km"]
                metrics["position_max_km"] = self.final_errors["position_error_km"]
            if "velocity_error_m_s" in self.final_errors:
                metrics["velocity_rms_m_s"] = self.final_errors["velocity_error_m_s"]
                metrics["velocity_max_m_s"] = self.final_errors["velocity_error_m_s"]
            if "altitude_km" in self.final_errors:
                metrics["altitude_rms_km"] = abs(self.final_errors["altitude_km"])
            if "sma_km" in self.final_errors:
                metrics["sma_error_km"] = abs(self.final_errors["sma_km"])

        # Add derived errors
        if self.derived_errors:
            metrics.update(self.derived_errors)

        # Add initial errors with prefixed names
        if self.initial_errors:
            if "position_error_km" in self.initial_errors:
                metrics["initial_position_error_m"] = self.initial_errors["position_error_km"] * 1000
            if "velocity_error_m_s" in self.initial_errors:
                metrics["initial_velocity_error_mm_s"] = self.initial_errors["velocity_error_m_s"]

        return metrics

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "case_id": self.case_id,
            "initial_errors": self.initial_errors,
            "final_errors": self.final_errors,
            "derived_errors": self.derived_errors,
            "failures": self.failures,
            "tolerances": self.tolerances,
            "truth_version": self.truth_version,
            "comparison_timestamp": self.comparison_timestamp,
        }


@dataclass
class SimulatorState:
    """Simulator output state for comparison."""

    epoch_utc: str
    sma_km: float
    ecc: float
    inc_deg: float
    raan_deg: float
    aop_deg: float
    ta_deg: float
    mass_kg: float
    altitude_km: Optional[float] = None
    x_km: Optional[float] = None
    y_km: Optional[float] = None
    z_km: Optional[float] = None
    vx_km_s: Optional[float] = None
    vy_km_s: Optional[float] = None
    vz_km_s: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict) -> "SimulatorState":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class TruthComparator:
    """Comparator for simulator results against GMAT truth."""

    def __init__(
        self,
        tolerance_config: Optional[GMATToleranceConfig] = None,
        baselines_dir: Optional[Path] = None,
    ):
        """
        Initialize comparator.

        Args:
            tolerance_config: Tolerance configuration (loads default if None)
            baselines_dir: Directory containing truth files
        """
        self.tolerance_config = tolerance_config or load_default_tolerance_config()
        self.truth_generator = TruthGenerator(baselines_dir)

    def compare_truth(
        self,
        case_id: str,
        sim_initial: Optional[SimulatorState] = None,
        sim_final: Optional[SimulatorState] = None,
        sim_derived: Optional[Dict[str, float]] = None,
        truth_version: str = "v1",
    ) -> ComparisonResult:
        """
        Compare simulator results against GMAT truth.

        Args:
            case_id: Case identifier
            sim_initial: Simulator initial state
            sim_final: Simulator final state
            sim_derived: Simulator derived metrics
            truth_version: Version of truth file to compare against

        Returns:
            ComparisonResult with detailed comparison
        """
        from datetime import datetime, timezone

        # Load truth file
        try:
            truth = self.truth_generator.load_truth(case_id, truth_version)
        except FileNotFoundError:
            return ComparisonResult(
                passed=False,
                case_id=case_id,
                failures=[f"Truth file not found for {case_id} version {truth_version}"],
                truth_version=truth_version,
                comparison_timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # Get tolerances for this case
        tolerances = self.tolerance_config.get_tolerances_for_scenario(case_id)

        result = ComparisonResult(
            passed=True,
            case_id=case_id,
            truth_version=truth_version,
            comparison_timestamp=datetime.now(timezone.utc).isoformat(),
            tolerances=tolerances,
        )

        # Compare initial state
        if sim_initial and truth.initial:
            result.initial_errors = self._compare_checkpoint(
                sim_initial, truth.initial
            )
            self._check_tolerances(
                result, result.initial_errors, tolerances, "initial"
            )

        # Compare final state
        if sim_final and truth.final:
            result.final_errors = self._compare_checkpoint(
                sim_final, truth.final
            )
            self._check_tolerances(
                result, result.final_errors, tolerances, "final"
            )

        # Compare derived metrics
        if sim_derived and truth.derived:
            result.derived_errors = self._compare_derived(
                sim_derived, truth.derived
            )
            self._check_derived_tolerances(
                result, result.derived_errors, tolerances
            )

        return result

    def _compare_checkpoint(
        self,
        sim_state: SimulatorState,
        truth_checkpoint: TruthCheckpoint,
    ) -> Dict[str, float]:
        """Compare a single checkpoint."""
        errors = {}

        # Keplerian elements
        errors["sma_km"] = sim_state.sma_km - truth_checkpoint.sma_km
        errors["ecc"] = sim_state.ecc - truth_checkpoint.ecc
        errors["inc_deg"] = self._angle_diff(sim_state.inc_deg, truth_checkpoint.inc_deg)
        errors["raan_deg"] = self._angle_diff(sim_state.raan_deg, truth_checkpoint.raan_deg)
        errors["aop_deg"] = self._angle_diff(sim_state.aop_deg, truth_checkpoint.aop_deg)
        errors["ta_deg"] = self._angle_diff(sim_state.ta_deg, truth_checkpoint.ta_deg)

        # Mass
        if truth_checkpoint.mass_kg > 0:
            errors["mass_kg"] = sim_state.mass_kg - truth_checkpoint.mass_kg

        # Altitude
        if sim_state.altitude_km is not None and truth_checkpoint.altitude_km is not None:
            errors["altitude_km"] = sim_state.altitude_km - truth_checkpoint.altitude_km

        # ECI position/velocity if available
        if all(v is not None for v in [sim_state.x_km, sim_state.y_km, sim_state.z_km,
                                         truth_checkpoint.x_km, truth_checkpoint.y_km, truth_checkpoint.z_km]):
            sim_pos = np.array([sim_state.x_km, sim_state.y_km, sim_state.z_km])
            truth_pos = np.array([truth_checkpoint.x_km, truth_checkpoint.y_km, truth_checkpoint.z_km])
            errors["position_error_km"] = float(np.linalg.norm(sim_pos - truth_pos))

        if all(v is not None for v in [sim_state.vx_km_s, sim_state.vy_km_s, sim_state.vz_km_s,
                                         truth_checkpoint.vx_km_s, truth_checkpoint.vy_km_s, truth_checkpoint.vz_km_s]):
            sim_vel = np.array([sim_state.vx_km_s, sim_state.vy_km_s, sim_state.vz_km_s])
            truth_vel = np.array([truth_checkpoint.vx_km_s, truth_checkpoint.vy_km_s, truth_checkpoint.vz_km_s])
            errors["velocity_error_m_s"] = float(np.linalg.norm(sim_vel - truth_vel) * 1000)  # km/s to m/s

        return errors

    def _compare_derived(
        self,
        sim_derived: Dict[str, float],
        truth_derived: Dict[str, float],
    ) -> Dict[str, float]:
        """Compare derived metrics."""
        errors = {}

        for key in truth_derived:
            if key in sim_derived:
                errors[key] = sim_derived[key] - truth_derived[key]

        return errors

    def _angle_diff(self, a: float, b: float) -> float:
        """Compute angle difference handling wraparound."""
        diff = a - b
        while diff > 180:
            diff -= 360
        while diff < -180:
            diff += 360
        return diff

    def _check_tolerances(
        self,
        result: ComparisonResult,
        errors: Dict[str, float],
        tolerances: Dict[str, float],
        checkpoint_name: str,
    ) -> None:
        """Check errors against tolerances and record failures."""
        # Mapping from error keys to tolerance keys
        tolerance_map = {
            "sma_km": "sma_km",
            "ecc": "ecc",
            "inc_deg": "inc_deg",
            "raan_deg": "raan_deg",
            "aop_deg": "aop_deg",
            "ta_deg": "ta_deg",
            "mass_kg": "mass_kg",
            "altitude_km": "altitude_rms_km",
            "position_error_km": "position_rms_km",
            "velocity_error_m_s": "velocity_rms_m_s",
        }

        for error_key, error_value in errors.items():
            tol_key = tolerance_map.get(error_key, error_key)
            if tol_key in tolerances:
                tolerance = tolerances[tol_key]
                if abs(error_value) > tolerance:
                    result.passed = False
                    result.failures.append(
                        f"{checkpoint_name}.{error_key}: {error_value:.6f} exceeds tolerance {tolerance:.6f}"
                    )

    def _check_derived_tolerances(
        self,
        result: ComparisonResult,
        errors: Dict[str, float],
        tolerances: Dict[str, float],
    ) -> None:
        """Check derived metric errors against tolerances."""
        for key, error_value in errors.items():
            if key in tolerances:
                tolerance = tolerances[key]
                if abs(error_value) > tolerance:
                    result.passed = False
                    result.failures.append(
                        f"derived.{key}: {error_value:.6f} exceeds tolerance {tolerance:.6f}"
                    )


def compare_truth(
    case_id: str,
    sim_initial: Optional[SimulatorState] = None,
    sim_final: Optional[SimulatorState] = None,
    sim_derived: Optional[Dict[str, float]] = None,
    truth_version: str = "v1",
) -> ComparisonResult:
    """
    Compare simulator results against GMAT truth.

    Convenience function that creates a TruthComparator and runs comparison.

    Args:
        case_id: Case identifier (e.g., "R01", "N01")
        sim_initial: Simulator initial state
        sim_final: Simulator final state
        sim_derived: Simulator derived metrics
        truth_version: Version of truth file to compare against

    Returns:
        ComparisonResult with detailed comparison
    """
    comparator = TruthComparator()
    return comparator.compare_truth(
        case_id, sim_initial, sim_final, sim_derived, truth_version
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compare simulator results against GMAT truth")
    parser.add_argument("--case", "-c", required=True, help="Case ID (e.g., R01)")
    parser.add_argument("--version", "-v", default="v1", help="Truth version")
    parser.add_argument("--sim-file", help="Path to simulator output JSON")

    args = parser.parse_args()

    # Load simulator results if provided
    sim_initial = None
    sim_final = None
    sim_derived = None

    if args.sim_file:
        import json
        with open(args.sim_file) as f:
            sim_data = json.load(f)
        if "initial" in sim_data:
            sim_initial = SimulatorState.from_dict(sim_data["initial"])
        if "final" in sim_data:
            sim_final = SimulatorState.from_dict(sim_data["final"])
        sim_derived = sim_data.get("derived")

    result = compare_truth(
        args.case,
        sim_initial=sim_initial,
        sim_final=sim_final,
        sim_derived=sim_derived,
        truth_version=args.version,
    )

    print(result.summary)
