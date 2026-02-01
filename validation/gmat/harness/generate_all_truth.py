"""Batch truth file generation for all GMAT regression cases.

Runs GMAT cases and generates truth files for regression testing.

Usage:
    # Generate truth for all Tier A cases (CI-critical, faster)
    python -m validation.gmat.harness.generate_all_truth --tier A

    # Generate truth for all Tier B cases (nightly, longer-running)
    python -m validation.gmat.harness.generate_all_truth --tier B

    # Generate truth for all cases
    python -m validation.gmat.harness.generate_all_truth --all

    # Generate truth for specific cases
    python -m validation.gmat.harness.generate_all_truth --cases R01,R05,N01

    # Dry run (show what would be generated)
    python -m validation.gmat.harness.generate_all_truth --tier A --dry-run

    # Skip existing truth files
    python -m validation.gmat.harness.generate_all_truth --all --skip-existing
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ..case_registry import (
    CaseDefinition,
    CaseTier,
    CaseTruth,
    CASE_REGISTRY,
    get_all_cases,
    get_case,
    get_tier_cases,
    list_case_ids,
)
from .generate_truth import TruthGenerator
from .run_case import CaseRunner


@dataclass
class CaseGenerationResult:
    """Result of generating truth for a single case."""

    case_id: str
    success: bool
    execution_time_s: float
    truth_path: Optional[Path] = None
    error_message: Optional[str] = None
    initial_sma_km: Optional[float] = None
    final_sma_km: Optional[float] = None
    derived_metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "case_id": self.case_id,
            "success": self.success,
            "execution_time_s": self.execution_time_s,
            "truth_path": str(self.truth_path) if self.truth_path else None,
            "error_message": self.error_message,
            "initial_sma_km": self.initial_sma_km,
            "final_sma_km": self.final_sma_km,
            "derived_metrics": self.derived_metrics,
        }


@dataclass
class BatchGenerationResult:
    """Result of batch truth generation."""

    total_cases: int
    successful: int
    failed: int
    skipped: int
    total_time_s: float
    results: List[CaseGenerationResult]
    started_at: str
    completed_at: str

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "total_cases": self.total_cases,
            "successful": self.successful,
            "failed": self.failed,
            "skipped": self.skipped,
            "total_time_s": self.total_time_s,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "results": [r.to_dict() for r in self.results],
        }

    def summary(self) -> str:
        """Generate summary string."""
        lines = [
            f"Batch Truth Generation Summary",
            f"=" * 40,
            f"Total cases: {self.total_cases}",
            f"Successful:  {self.successful}",
            f"Failed:      {self.failed}",
            f"Skipped:     {self.skipped}",
            f"Total time:  {self.total_time_s:.1f}s",
            f"",
        ]

        if self.results:
            lines.append("Results by case:")
            for r in self.results:
                status = "PASS" if r.success else "FAIL"
                if r.error_message and "skipped" in r.error_message.lower():
                    status = "SKIP"
                time_str = f"{r.execution_time_s:.1f}s" if r.execution_time_s > 0 else "-"
                lines.append(f"  {r.case_id}: {status} ({time_str})")
                if r.initial_sma_km and r.final_sma_km:
                    lines.append(f"    SMA: {r.initial_sma_km:.3f} -> {r.final_sma_km:.3f} km")

        if self.failed > 0:
            lines.append("")
            lines.append("Failed cases:")
            for r in self.results:
                if not r.success and r.error_message and "skipped" not in r.error_message.lower():
                    lines.append(f"  {r.case_id}: {r.error_message[:80]}")

        return "\n".join(lines)


class BatchTruthGenerator:
    """Batch generator for GMAT truth files."""

    def __init__(
        self,
        baselines_dir: Optional[Path] = None,
        verbose: bool = True,
    ):
        """
        Initialize batch generator.

        Args:
            baselines_dir: Directory for storing truth files
            verbose: Whether to print progress
        """
        base_dir = Path(__file__).parent.parent.parent
        self.baselines_dir = baselines_dir or base_dir / "baselines" / "gmat"
        self.verbose = verbose
        self.truth_generator = TruthGenerator(baselines_dir=self.baselines_dir)
        self.case_runner = CaseRunner()

    def _log(self, message: str) -> None:
        """Print message if verbose."""
        if self.verbose:
            print(message)

    def _truth_exists(self, case_id: str, version: str = "v1") -> bool:
        """Check if truth file already exists."""
        truth_path = self.baselines_dir / case_id / f"truth_{version}.json"
        return truth_path.exists()

    def generate_truth_for_case(
        self,
        case_id: str,
        version: str = "v1",
        skip_existing: bool = False,
    ) -> CaseGenerationResult:
        """
        Generate truth file for a single case.

        Args:
            case_id: Case identifier
            version: Version string for truth file
            skip_existing: Skip if truth file already exists

        Returns:
            CaseGenerationResult with status and metrics
        """
        import time

        case_def = get_case(case_id)

        # Check if should skip
        if skip_existing and self._truth_exists(case_id, version):
            self._log(f"  {case_id}: Skipped (truth already exists)")
            return CaseGenerationResult(
                case_id=case_id,
                success=True,
                execution_time_s=0.0,
                error_message="Skipped - truth file already exists",
            )

        self._log(f"  {case_id}: Running GMAT ({case_def.name})...")

        start_time = time.time()

        try:
            # Run case
            result = self.case_runner.run_case(case_id, generate_truth=True)

            if not result.success:
                error_msg = result.stderr[:200] if result.stderr else result.error_message
                self._log(f"  {case_id}: FAIL - GMAT execution failed")
                return CaseGenerationResult(
                    case_id=case_id,
                    success=False,
                    execution_time_s=time.time() - start_time,
                    error_message=f"GMAT execution failed: {error_msg}",
                )

            # Generate truth
            truth = self.truth_generator.generate_truth(case_id, result=result, version=version)

            # Save truth
            truth_path = self.truth_generator.save_truth(truth, version)

            execution_time = time.time() - start_time

            self._log(f"  {case_id}: PASS ({execution_time:.1f}s)")

            return CaseGenerationResult(
                case_id=case_id,
                success=True,
                execution_time_s=execution_time,
                truth_path=truth_path,
                initial_sma_km=truth.initial.sma_km if truth.initial else None,
                final_sma_km=truth.final.sma_km if truth.final else None,
                derived_metrics=truth.derived,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            self._log(f"  {case_id}: FAIL - {str(e)[:80]}")
            return CaseGenerationResult(
                case_id=case_id,
                success=False,
                execution_time_s=execution_time,
                error_message=str(e),
            )

    def generate_for_tier(
        self,
        tier: CaseTier,
        version: str = "v1",
        skip_existing: bool = False,
    ) -> BatchGenerationResult:
        """
        Generate truth files for all cases in a tier.

        Args:
            tier: Tier (A or B)
            version: Version string for truth files
            skip_existing: Skip cases with existing truth files

        Returns:
            BatchGenerationResult with all results
        """
        cases = get_tier_cases(tier)
        return self._generate_for_cases(cases, version, skip_existing)

    def generate_for_all(
        self,
        version: str = "v1",
        skip_existing: bool = False,
    ) -> BatchGenerationResult:
        """
        Generate truth files for all cases.

        Args:
            version: Version string for truth files
            skip_existing: Skip cases with existing truth files

        Returns:
            BatchGenerationResult with all results
        """
        cases = get_all_cases()
        return self._generate_for_cases(cases, version, skip_existing)

    def generate_for_case_ids(
        self,
        case_ids: List[str],
        version: str = "v1",
        skip_existing: bool = False,
    ) -> BatchGenerationResult:
        """
        Generate truth files for specific case IDs.

        Args:
            case_ids: List of case IDs
            version: Version string for truth files
            skip_existing: Skip cases with existing truth files

        Returns:
            BatchGenerationResult with all results
        """
        cases = [get_case(cid) for cid in case_ids]
        return self._generate_for_cases(cases, version, skip_existing)

    def _generate_for_cases(
        self,
        cases: List[CaseDefinition],
        version: str,
        skip_existing: bool,
    ) -> BatchGenerationResult:
        """Internal method to generate truth for a list of cases."""
        import time

        started_at = datetime.now(timezone.utc).isoformat()
        total_start = time.time()

        self._log(f"\nGenerating truth files for {len(cases)} cases...")
        self._log(f"Output directory: {self.baselines_dir}")
        self._log("")

        results = []
        for case_def in cases:
            result = self.generate_truth_for_case(
                case_def.case_id,
                version=version,
                skip_existing=skip_existing,
            )
            results.append(result)

        total_time = time.time() - total_start
        completed_at = datetime.now(timezone.utc).isoformat()

        successful = sum(1 for r in results if r.success and "skipped" not in (r.error_message or "").lower())
        skipped = sum(1 for r in results if r.success and "skipped" in (r.error_message or "").lower())
        failed = sum(1 for r in results if not r.success)

        return BatchGenerationResult(
            total_cases=len(cases),
            successful=successful,
            failed=failed,
            skipped=skipped,
            total_time_s=total_time,
            results=results,
            started_at=started_at,
            completed_at=completed_at,
        )


def generate_all_truth(
    tier: Optional[str] = None,
    case_ids: Optional[List[str]] = None,
    all_cases: bool = False,
    version: str = "v1",
    skip_existing: bool = False,
    dry_run: bool = False,
    verbose: bool = True,
) -> BatchGenerationResult:
    """
    Generate truth files for GMAT cases.

    Convenience function for batch truth generation.

    Args:
        tier: Tier to generate ("A" or "B")
        case_ids: Specific case IDs to generate
        all_cases: Generate for all cases
        version: Version string for truth files
        skip_existing: Skip cases with existing truth files
        dry_run: Only show what would be generated
        verbose: Print progress

    Returns:
        BatchGenerationResult with all results
    """
    generator = BatchTruthGenerator(verbose=verbose)

    # Determine cases to process
    if case_ids:
        cases = [get_case(cid) for cid in case_ids]
    elif tier:
        tier_enum = CaseTier.A if tier.upper() == "A" else CaseTier.B
        cases = get_tier_cases(tier_enum)
    elif all_cases:
        cases = get_all_cases()
    else:
        raise ValueError("Must specify --tier, --cases, or --all")

    if dry_run:
        print(f"\nDry run - would generate truth for {len(cases)} cases:")
        for case in cases:
            exists = generator._truth_exists(case.case_id, version)
            status = " (exists)" if exists else ""
            skip = " [SKIP]" if skip_existing and exists else ""
            print(f"  {case.case_id}: {case.name}{status}{skip}")
        return BatchGenerationResult(
            total_cases=len(cases),
            successful=0,
            failed=0,
            skipped=0,
            total_time_s=0.0,
            results=[],
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    if case_ids:
        return generator.generate_for_case_ids(case_ids, version, skip_existing)
    elif tier:
        tier_enum = CaseTier.A if tier.upper() == "A" else CaseTier.B
        return generator.generate_for_tier(tier_enum, version, skip_existing)
    else:
        return generator.generate_for_all(version, skip_existing)


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Generate GMAT truth files for regression testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate truth for Tier A (CI fast)
  python -m validation.gmat.harness.generate_all_truth --tier A

  # Generate truth for Tier B (nightly)
  python -m validation.gmat.harness.generate_all_truth --tier B

  # Generate truth for all cases
  python -m validation.gmat.harness.generate_all_truth --all

  # Generate truth for specific cases
  python -m validation.gmat.harness.generate_all_truth --cases R01,R05,N01

  # Skip existing truth files
  python -m validation.gmat.harness.generate_all_truth --all --skip-existing

  # Preview what would be generated
  python -m validation.gmat.harness.generate_all_truth --tier A --dry-run
""",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--tier", "-t",
        choices=["A", "B"],
        help="Generate truth for all cases in tier (A=CI fast, B=nightly)",
    )
    group.add_argument(
        "--cases", "-c",
        help="Comma-separated list of case IDs (e.g., R01,R05,N01)",
    )
    group.add_argument(
        "--all", "-a",
        action="store_true",
        help="Generate truth for all cases (Tier A + Tier B)",
    )
    group.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all available cases",
    )

    parser.add_argument(
        "--version", "-v",
        default="v1",
        help="Version string for truth files (default: v1)",
    )
    parser.add_argument(
        "--skip-existing", "-s",
        action="store_true",
        help="Skip cases that already have truth files",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be generated without running",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output",
    )
    parser.add_argument(
        "--output-json", "-o",
        type=Path,
        help="Write results to JSON file",
    )

    args = parser.parse_args()

    # Handle --list
    if args.list:
        print("\nAvailable GMAT regression cases:")
        print("\nTier A (CI fast):")
        for case in get_tier_cases(CaseTier.A):
            print(f"  {case.case_id}: {case.name} ({case.duration_hours}h, ~{case.expected_runtime_s}s)")
        print("\nTier B (nightly):")
        for case in get_tier_cases(CaseTier.B):
            print(f"  {case.case_id}: {case.name} ({case.duration_hours}h, ~{case.expected_runtime_s}s)")
        return 0

    # Parse case IDs if provided
    case_ids = None
    if args.cases:
        case_ids = [c.strip() for c in args.cases.split(",")]
        # Validate case IDs
        for cid in case_ids:
            if cid not in CASE_REGISTRY:
                print(f"Error: Unknown case ID '{cid}'")
                print(f"Valid IDs: {', '.join(sorted(CASE_REGISTRY.keys()))}")
                return 1

    # Run generation
    try:
        result = generate_all_truth(
            tier=args.tier,
            case_ids=case_ids,
            all_cases=args.all,
            version=args.version,
            skip_existing=args.skip_existing,
            dry_run=args.dry_run,
            verbose=not args.quiet,
        )

        # Print summary
        if not args.quiet:
            print("\n" + result.summary())

        # Write JSON output if requested
        if args.output_json:
            with open(args.output_json, "w") as f:
                json.dump(result.to_dict(), f, indent=2)
            print(f"\nResults written to: {args.output_json}")

        # Return exit code based on failures
        return 1 if result.failed > 0 else 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
