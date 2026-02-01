"""Case execution harness for GMAT regression tests.

Provides functionality to:
- Execute a single GMAT regression case
- Execute all cases in a tier
- Generate scripts from templates for each case
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from ..case_registry import (
    CaseDefinition,
    CaseResult,
    CaseTier,
    CASE_REGISTRY,
    get_case,
    get_tier_cases,
)
from ..executor import GMATExecutor, GMATExecutionResult


@dataclass
class CaseConfig:
    """Configuration for a case execution."""

    case_id: str
    output_dir: Path
    template_dir: Path
    cases_dir: Path
    timeout_s: int = 300
    isolated: bool = True
    generate_script: bool = True


class CaseRunner:
    """Runner for GMAT regression test cases."""

    # Default epoch for all cases
    DEFAULT_EPOCH = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

    def __init__(
        self,
        gmat_executor: Optional[GMATExecutor] = None,
        template_dir: Optional[Path] = None,
        cases_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        """
        Initialize case runner.

        Args:
            gmat_executor: GMAT executor instance (auto-created if None)
            template_dir: Directory containing case templates
            cases_dir: Directory containing case definitions
            output_dir: Directory for case outputs
        """
        self.executor = gmat_executor or GMATExecutor()

        base_dir = Path(__file__).parent.parent
        self.template_dir = template_dir or base_dir / "templates"
        self.cases_dir = cases_dir or base_dir / "cases"
        self.output_dir = output_dir or base_dir / "output"

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader([
                str(self.template_dir),
                str(self.template_dir / "cases"),
                str(self.template_dir / "includes"),
            ]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        self.env.filters["gmat_epoch"] = self._format_gmat_epoch

    def _format_gmat_epoch(self, dt: datetime) -> str:
        """Format datetime as GMAT epoch string."""
        return dt.strftime("%d %b %Y %H:%M:%S.000")

    def run_case(
        self,
        case_id: str,
        generate_truth: bool = False,
        timeout_s: Optional[int] = None,
    ) -> CaseResult:
        """
        Execute a single GMAT regression case.

        Args:
            case_id: Case identifier (e.g., "R01", "N01")
            generate_truth: Whether to run in truth generation mode
            timeout_s: Override timeout in seconds

        Returns:
            CaseResult with execution details and artifact paths
        """
        # Get case definition
        case_def = get_case(case_id)

        # Determine timeout
        if timeout_s is None:
            timeout_s = int(case_def.expected_runtime_s * 3)  # 3x expected for safety

        # Prepare output directory
        case_output_dir = self.output_dir / case_id
        case_output_dir.mkdir(parents=True, exist_ok=True)

        # Generate script from template
        script_path = self._generate_case_script(case_def, case_output_dir)

        if script_path is None:
            return CaseResult(
                case_id=case_id,
                success=False,
                execution_time_s=0.0,
                return_code=-1,
                stdout="",
                stderr=f"Failed to generate script for case {case_id}",
                error_message=f"Template not found: {case_def.template_name}",
            )

        # Execute script
        result = self.executor.execute_script(
            script_path,
            timeout_s=timeout_s,
            isolated=True,
        )

        # Find output artifacts
        ephemeris_path = self._find_output_file(result.working_dir, "ephemeris")
        keplerian_path = self._find_output_file(result.working_dir, "keplerian")
        mass_path = self._find_output_file(result.working_dir, "mass")
        truth_path = self._find_output_file(result.working_dir, "truth")

        return CaseResult(
            case_id=case_id,
            success=result.success,
            execution_time_s=result.execution_time_s,
            return_code=result.return_code,
            stdout=result.stdout,
            stderr=result.stderr,
            output_files=result.output_files,
            ephemeris_path=ephemeris_path,
            keplerian_path=keplerian_path,
            mass_path=mass_path,
            truth_path=truth_path,
            working_dir=result.working_dir,
        )

    def _generate_case_script(
        self,
        case_def: CaseDefinition,
        output_dir: Path,
    ) -> Optional[Path]:
        """
        Generate GMAT script from case template.

        Args:
            case_def: Case definition
            output_dir: Directory for output files

        Returns:
            Path to generated script, or None if template not found
        """
        if not case_def.template_name:
            return None

        # Check if template exists
        template_path = self.template_dir / "cases" / case_def.template_name
        if not template_path.exists():
            # Try alternative locations
            alt_paths = [
                self.template_dir / case_def.template_name,
                self.cases_dir / case_def.case_id / "case.script",
            ]
            for alt_path in alt_paths:
                if alt_path.exists():
                    # Copy existing script
                    script_path = output_dir / f"{case_def.case_id}.script"
                    shutil.copy2(alt_path, script_path)
                    return script_path
            return None

        # Load and render template
        try:
            template = self.env.get_template(f"cases/{case_def.template_name}")
        except Exception:
            return None

        # Build context for template
        context = self._build_case_context(case_def, output_dir)

        # Render script
        script_content = template.render(**context)

        # Write to output directory
        script_path = output_dir / f"{case_def.case_id}.script"
        script_path.write_text(script_content)

        return script_path

    def _build_case_context(
        self,
        case_def: CaseDefinition,
        output_dir: Path,
    ) -> Dict:
        """
        Build template context for a case.

        Args:
            case_def: Case definition
            output_dir: Output directory

        Returns:
            Dictionary of template variables
        """
        # Default spacecraft parameters
        from ..generator import ScenarioConfig

        # Create base scenario config
        config = ScenarioConfig(
            scenario_id=case_def.case_id,
            scenario_name=case_def.name,
            epoch=self.DEFAULT_EPOCH,
            duration_hours=case_def.duration_hours,
            output_dir=str(output_dir),
        )

        # Load case-specific overrides from meta file
        meta_path = self.cases_dir / case_def.case_id / "case.meta.json"
        overrides = {}
        if meta_path.exists():
            with open(meta_path) as f:
                overrides = json.load(f)

        # Build base context
        context = {
            # Case metadata
            "case_id": case_def.case_id,
            "case_name": case_def.name,
            "category": case_def.category,

            # Scenario
            "scenario_id": case_def.case_id,
            "scenario_name": case_def.name,
            "epoch": self._format_gmat_epoch(config.epoch),
            "duration_hours": case_def.duration_hours,
            "duration_s": case_def.duration_hours * 3600.0,
            "report_step_s": overrides.get("report_step_s", 60.0),

            # Spacecraft
            "sc_name": overrides.get("spacecraft_name", "ValidationSC"),
            "spacecraft_name": overrides.get("spacecraft_name", "ValidationSC"),
            "sma_km": overrides.get("sma_km", 6878.137),
            "ecc": overrides.get("ecc", 0.0001),
            "inc_deg": overrides.get("inc_deg", 53.0),
            "raan_deg": overrides.get("raan_deg", 0.0),
            "aop_deg": overrides.get("aop_deg", 0.0),
            "ta_deg": overrides.get("ta_deg", 0.0),
            "dry_mass_kg": overrides.get("dry_mass_kg", 450.0),
            "propellant_kg": overrides.get("propellant_kg", 50.0),
            "drag_area_m2": overrides.get("drag_area_m2", 5.0),
            "srp_area_m2": overrides.get("srp_area_m2", 10.0),

            # Propulsion
            "has_ep_thruster": case_def.propulsion.value == "ep",
            "has_chemical_thruster": case_def.propulsion.value == "chemical_fb",
            "thrust_mN": overrides.get("thrust_mN", 100.0),
            "isp_s": overrides.get("isp_s", 1500.0),
            "max_power_kw": overrides.get("max_power_kw", 1.5),

            # Force models
            "include_gravity": "gravity" in case_def.force_models,
            "include_drag": "drag" in case_def.force_models,
            "include_srp": "srp" in case_def.force_models,
            "include_third_bodies": "third_bodies" in case_def.force_models,
            "f107": overrides.get("f107", 150.0),
            "f107a": overrides.get("f107a", 150.0),
            "kp": overrides.get("kp", 3.0),

            # Propagator
            "force_model_name": "FM_Validation",
            "propagator_name": "Prop_Validation",
            "high_fidelity": overrides.get("high_fidelity", False),
            "integrator_type": overrides.get("integrator_type", "RungeKutta89"),
            "initial_step_s": overrides.get("initial_step_s", 60.0),
            "accuracy": overrides.get("accuracy", 1e-12),
            "min_step_s": overrides.get("min_step_s", 0.001),
            "max_step_s": overrides.get("max_step_s", 2700.0),

            # Output
            "output_dir": str(output_dir),

            # Flags
            "has_targeting": case_def.has_targeting,
            "has_events": case_def.category in ["finite_burn", "station_keeping", "eclipse"],
            "capture_initial": True,
        }

        # Add case-specific overrides
        context.update(overrides.get("template_vars", {}))

        return context

    def _find_output_file(
        self,
        working_dir: Optional[Path],
        prefix: str,
    ) -> Optional[Path]:
        """Find an output file by prefix in working directory."""
        if not working_dir or not working_dir.exists():
            return None

        for ext in [".txt", ".csv", ".report"]:
            for path in working_dir.glob(f"{prefix}*{ext}"):
                return path
            for path in working_dir.glob(f"**/{prefix}*{ext}"):
                return path

        return None

    def run_tier(
        self,
        tier: CaseTier,
        timeout_per_case_s: Optional[int] = None,
    ) -> Dict[str, CaseResult]:
        """
        Execute all cases in a tier.

        Args:
            tier: Tier to execute (A or B)
            timeout_per_case_s: Override timeout per case

        Returns:
            Dictionary mapping case_id to CaseResult
        """
        results = {}
        cases = get_tier_cases(tier)

        for case_def in cases:
            print(f"Running case {case_def.case_id}: {case_def.name}")
            result = self.run_case(
                case_def.case_id,
                timeout_s=timeout_per_case_s,
            )
            results[case_def.case_id] = result

            if result.success:
                print(f"  PASS ({result.execution_time_s:.1f}s)")
            else:
                print(f"  FAIL: {result.stderr[:100] if result.stderr else result.error_message}")

        return results


def run_case(
    case_id: str,
    generate_truth: bool = False,
    timeout_s: Optional[int] = None,
) -> CaseResult:
    """
    Execute a single GMAT regression case.

    Convenience function that creates a CaseRunner and runs the case.

    Args:
        case_id: Case identifier (e.g., "R01", "N01")
        generate_truth: Whether to run in truth generation mode
        timeout_s: Override timeout in seconds

    Returns:
        CaseResult with execution details
    """
    runner = CaseRunner()
    return runner.run_case(case_id, generate_truth, timeout_s)


def run_tier(
    tier: CaseTier,
    timeout_per_case_s: Optional[int] = None,
) -> Dict[str, CaseResult]:
    """
    Execute all cases in a tier.

    Convenience function that creates a CaseRunner and runs all tier cases.

    Args:
        tier: Tier to execute (A or B)
        timeout_per_case_s: Override timeout per case

    Returns:
        Dictionary mapping case_id to CaseResult
    """
    runner = CaseRunner()
    return runner.run_tier(tier, timeout_per_case_s)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run GMAT regression test cases")
    parser.add_argument("--case", "-c", help="Case ID to run (e.g., R01)")
    parser.add_argument("--tier", "-t", choices=["A", "B"], help="Run all cases in tier")
    parser.add_argument("--timeout", type=int, help="Timeout in seconds")

    args = parser.parse_args()

    if args.case:
        result = run_case(args.case, timeout_s=args.timeout)
        print(f"\nCase {args.case}:")
        print(f"  Success: {result.success}")
        print(f"  Time: {result.execution_time_s:.1f}s")
        if result.working_dir:
            print(f"  Output: {result.working_dir}")
        if not result.success:
            print(f"  Error: {result.stderr[:200] if result.stderr else result.error_message}")
    elif args.tier:
        tier = CaseTier.A if args.tier == "A" else CaseTier.B
        results = run_tier(tier, args.timeout)
        passed = sum(1 for r in results.values() if r.success)
        print(f"\nTier {args.tier}: {passed}/{len(results)} passed")
    else:
        parser.print_help()
