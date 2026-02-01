"""
Cross-fidelity comparator for LOW vs MEDIUM/HIGH validation.

Compares simulation outputs across fidelity levels to validate
accuracy and identify significant differences.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from validation.cross_fidelity.metrics import (
    CrossFidelityMetrics,
    PositionDelta,
    TimingDelta,
    compute_position_delta,
    compute_contact_timing_delta,
    compute_eclipse_timing_delta,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class ValidationTolerances:
    """Tolerances for validation pass/fail criteria."""

    position_rms_km: float = 10.0  # Position RMS threshold
    position_max_km: float = 50.0  # Maximum position difference
    contact_timing_rms_s: float = 60.0  # Contact timing RMS
    contact_timing_max_s: float = 300.0  # Maximum contact timing diff
    eclipse_timing_rms_s: float = 30.0  # Eclipse timing RMS
    min_contact_match_ratio: float = 0.9  # Minimum fraction of matched contacts


@dataclass
class ValidationResult:
    """Result of cross-fidelity validation."""

    passed: bool
    metrics: CrossFidelityMetrics
    tolerances: ValidationTolerances
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "metrics": self.metrics.to_dict(),
            "tolerances": {
                "position_rms_km": self.tolerances.position_rms_km,
                "position_max_km": self.tolerances.position_max_km,
                "contact_timing_rms_s": self.tolerances.contact_timing_rms_s,
                "contact_timing_max_s": self.tolerances.contact_timing_max_s,
                "eclipse_timing_rms_s": self.tolerances.eclipse_timing_rms_s,
                "min_contact_match_ratio": self.tolerances.min_contact_match_ratio,
            },
            "failures": self.failures,
            "warnings": self.warnings,
        }


class CrossFidelityComparator:
    """
    Comparator for cross-fidelity validation.

    Compares LOW fidelity run against MEDIUM/HIGH and validates
    that differences are within acceptable tolerances.
    """

    def __init__(
        self,
        tolerances: Optional[ValidationTolerances] = None,
    ):
        self.tolerances = tolerances or ValidationTolerances()

    def compare_runs(
        self,
        run_a_path: Path,
        run_b_path: Path,
    ) -> ValidationResult:
        """
        Compare two simulation runs.

        Args:
            run_a_path: Path to first run directory (typically LOW)
            run_b_path: Path to second run directory (typically MEDIUM)

        Returns:
            ValidationResult with metrics and pass/fail status
        """
        logger.info(f"Comparing runs: {run_a_path.name} vs {run_b_path.name}")

        failures = []
        warnings = []

        # Load ephemeris
        eph_a = self._load_ephemeris(run_a_path)
        eph_b = self._load_ephemeris(run_b_path)

        # Compute position delta
        if eph_a is not None and eph_b is not None:
            position_delta = compute_position_delta(eph_a, eph_b)
        else:
            position_delta = PositionDelta(
                rms_km=float("nan"),
                max_km=float("nan"),
                mean_km=float("nan"),
                along_track_rms_km=float("nan"),
                cross_track_rms_km=float("nan"),
                radial_rms_km=float("nan"),
            )
            warnings.append("Could not load ephemeris for comparison")

        # Load and compare contacts
        contacts_a = self._load_access_windows(run_a_path)
        contacts_b = self._load_access_windows(run_b_path)

        contact_timing, contact_comparisons = compute_contact_timing_delta(
            contacts_a, contacts_b
        )

        # Load and compare eclipses
        eclipses_a = self._load_eclipse_windows(run_a_path)
        eclipses_b = self._load_eclipse_windows(run_b_path)

        if eclipses_a and eclipses_b:
            eclipse_timing = compute_eclipse_timing_delta(eclipses_a, eclipses_b)
        else:
            eclipse_timing = None

        # Build metrics
        metrics = CrossFidelityMetrics(
            position=position_delta,
            contact_timing=contact_timing,
            eclipse_timing=eclipse_timing,
            contacts=contact_comparisons,
        )

        # Validate against tolerances
        if not self._check_tolerances(metrics, failures, warnings):
            passed = False
        else:
            passed = True

        return ValidationResult(
            passed=passed,
            metrics=metrics,
            tolerances=self.tolerances,
            failures=failures,
            warnings=warnings,
        )

    def _check_tolerances(
        self,
        metrics: CrossFidelityMetrics,
        failures: List[str],
        warnings: List[str],
    ) -> bool:
        """Check if metrics are within tolerances."""
        passed = True

        # Position checks
        if not pd.isna(metrics.position.rms_km):
            if metrics.position.rms_km > self.tolerances.position_rms_km:
                failures.append(
                    f"Position RMS {metrics.position.rms_km:.2f} km exceeds "
                    f"tolerance {self.tolerances.position_rms_km:.2f} km"
                )
                passed = False

            if metrics.position.max_km > self.tolerances.position_max_km:
                failures.append(
                    f"Max position diff {metrics.position.max_km:.2f} km exceeds "
                    f"tolerance {self.tolerances.position_max_km:.2f} km"
                )
                passed = False

        # Contact timing checks
        if metrics.contact_timing.rms_s > self.tolerances.contact_timing_rms_s:
            failures.append(
                f"Contact timing RMS {metrics.contact_timing.rms_s:.1f}s exceeds "
                f"tolerance {self.tolerances.contact_timing_rms_s:.1f}s"
            )
            passed = False

        if metrics.contact_timing.max_s > self.tolerances.contact_timing_max_s:
            warnings.append(
                f"Max contact timing diff {metrics.contact_timing.max_s:.1f}s exceeds "
                f"tolerance {self.tolerances.contact_timing_max_s:.1f}s"
            )

        # Contact match ratio
        total_contacts = (
            metrics.contact_timing.count_matched +
            metrics.contact_timing.count_unmatched_a +
            metrics.contact_timing.count_unmatched_b
        )
        if total_contacts > 0:
            match_ratio = metrics.contact_timing.count_matched / total_contacts
            if match_ratio < self.tolerances.min_contact_match_ratio:
                failures.append(
                    f"Contact match ratio {match_ratio:.1%} below "
                    f"threshold {self.tolerances.min_contact_match_ratio:.1%}"
                )
                passed = False

        # Eclipse timing checks
        if metrics.eclipse_timing:
            if metrics.eclipse_timing.rms_s > self.tolerances.eclipse_timing_rms_s:
                warnings.append(
                    f"Eclipse timing RMS {metrics.eclipse_timing.rms_s:.1f}s exceeds "
                    f"tolerance {self.tolerances.eclipse_timing_rms_s:.1f}s"
                )

        return passed

    def _load_ephemeris(self, run_path: Path) -> Optional[pd.DataFrame]:
        """Load ephemeris from run directory."""
        eph_path = run_path / "ephemeris.parquet"
        if eph_path.exists():
            return pd.read_parquet(eph_path)

        eph_json = run_path / "ephemeris.json"
        if eph_json.exists():
            with open(eph_json) as f:
                data = json.load(f)
            return pd.DataFrame(data)

        return None

    def _load_access_windows(self, run_path: Path) -> Dict[str, List[Dict]]:
        """Load access windows from run directory."""
        access_path = run_path / "access_windows.json"
        if access_path.exists():
            with open(access_path) as f:
                return json.load(f)
        return {}

    def _load_eclipse_windows(self, run_path: Path) -> List[Dict]:
        """Load eclipse windows from run directory."""
        eclipse_path = run_path / "eclipse_windows.json"
        if eclipse_path.exists():
            with open(eclipse_path) as f:
                return json.load(f)
        return []

    def generate_report(
        self,
        result: ValidationResult,
        output_path: Optional[Path] = None,
    ) -> str:
        """
        Generate validation report.

        Args:
            result: Validation result
            output_path: Optional path to write report

        Returns:
            Report text
        """
        lines = [
            "=" * 60,
            "CROSS-FIDELITY VALIDATION REPORT",
            "=" * 60,
            "",
            f"Status: {'PASSED' if result.passed else 'FAILED'}",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
            "-" * 60,
            "POSITION COMPARISON",
            "-" * 60,
            f"  RMS:          {result.metrics.position.rms_km:.3f} km",
            f"  Maximum:      {result.metrics.position.max_km:.3f} km",
            f"  Mean:         {result.metrics.position.mean_km:.3f} km",
            f"  Along-track:  {result.metrics.position.along_track_rms_km:.3f} km (RMS)",
            f"  Cross-track:  {result.metrics.position.cross_track_rms_km:.3f} km (RMS)",
            f"  Radial:       {result.metrics.position.radial_rms_km:.3f} km (RMS)",
            "",
            "-" * 60,
            "CONTACT TIMING COMPARISON",
            "-" * 60,
            f"  RMS:          {result.metrics.contact_timing.rms_s:.1f} s",
            f"  Maximum:      {result.metrics.contact_timing.max_s:.1f} s",
            f"  Mean:         {result.metrics.contact_timing.mean_s:.1f} s",
            f"  Matched:      {result.metrics.contact_timing.count_matched}",
            f"  Unmatched A:  {result.metrics.contact_timing.count_unmatched_a}",
            f"  Unmatched B:  {result.metrics.contact_timing.count_unmatched_b}",
        ]

        if result.metrics.eclipse_timing:
            lines.extend([
                "",
                "-" * 60,
                "ECLIPSE TIMING COMPARISON",
                "-" * 60,
                f"  RMS:          {result.metrics.eclipse_timing.rms_s:.1f} s",
                f"  Maximum:      {result.metrics.eclipse_timing.max_s:.1f} s",
                f"  Mean:         {result.metrics.eclipse_timing.mean_s:.1f} s",
            ])

        if result.failures:
            lines.extend([
                "",
                "-" * 60,
                "FAILURES",
                "-" * 60,
            ])
            for failure in result.failures:
                lines.append(f"  [FAIL] {failure}")

        if result.warnings:
            lines.extend([
                "",
                "-" * 60,
                "WARNINGS",
                "-" * 60,
            ])
            for warning in result.warnings:
                lines.append(f"  [WARN] {warning}")

        lines.extend([
            "",
            "=" * 60,
        ])

        report = "\n".join(lines)

        if output_path:
            with open(output_path, "w") as f:
                f.write(report)
            # Also write JSON
            json_path = output_path.with_suffix(".json")
            with open(json_path, "w") as f:
                json.dump(result.to_dict(), f, indent=2)

        return report


def main():
    """CLI for cross-fidelity comparison."""
    parser = argparse.ArgumentParser(
        description="Compare simulation runs across fidelity levels"
    )
    parser.add_argument(
        "run_a",
        type=Path,
        help="Path to first run directory (LOW fidelity)",
    )
    parser.add_argument(
        "run_b",
        type=Path,
        help="Path to second run directory (MEDIUM/HIGH fidelity)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output report path",
    )
    parser.add_argument(
        "--position-tol",
        type=float,
        default=10.0,
        help="Position RMS tolerance (km)",
    )
    parser.add_argument(
        "--timing-tol",
        type=float,
        default=60.0,
        help="Contact timing RMS tolerance (s)",
    )

    args = parser.parse_args()

    tolerances = ValidationTolerances(
        position_rms_km=args.position_tol,
        contact_timing_rms_s=args.timing_tol,
    )

    comparator = CrossFidelityComparator(tolerances)
    result = comparator.compare_runs(args.run_a, args.run_b)

    report = comparator.generate_report(
        result,
        output_path=args.output,
    )
    print(report)

    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
