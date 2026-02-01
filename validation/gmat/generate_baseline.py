#!/usr/bin/env python3
"""Generate GMAT baselines for validation scenarios.

Usage:
    python -m validation.gmat.generate_baseline --scenario pure_propagation_12h
    python -m validation.gmat.generate_baseline --all

This script generates GMAT reference data and stores it as baselines
for regression testing.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from .executor import GMATExecutor, check_gmat_installation
from .generator import GMATScriptGenerator, ScenarioConfig
from .parser import GMATOutputParser
from .baseline_manager import GMATBaselineManager, create_baseline_from_ephemeris


# Base output directory (absolute path)
BASE_OUTPUT_DIR = str((Path(__file__).parent / "output").resolve())

# Predefined scenarios matching validation_config.yaml
SCENARIOS = {
    "pure_propagation_12h": ScenarioConfig(
        scenario_id="pure_propagation_12h",
        scenario_name="Pure Propagation 12-hour",
        epoch=datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
        duration_hours=12.0,
        sma_km=6878.137,  # 500 km altitude
        inc_deg=53.0,
        report_step_s=60.0,
        output_dir=BASE_OUTPUT_DIR,
    ),
    "orbit_lowering_24h": ScenarioConfig(
        scenario_id="orbit_lowering_24h",
        scenario_name="Orbit Lowering 24-hour",
        epoch=datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
        duration_hours=24.0,
        sma_km=6878.137,
        inc_deg=53.0,
        has_ep_thruster=True,
        thrust_mN=100.0,
        isp_s=1500.0,
        report_step_s=60.0,
        output_dir=BASE_OUTPUT_DIR,
    ),
    "ground_access_24h": ScenarioConfig(
        scenario_id="ground_access_24h",
        scenario_name="Ground Station Access 24-hour",
        epoch=datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
        duration_hours=24.0,
        sma_km=6878.137,
        inc_deg=53.0,
        report_step_s=60.0,
        output_dir=BASE_OUTPUT_DIR,
    ),
}


def generate_baseline(
    scenario_id: str,
    executor: GMATExecutor,
    output_dir: Path,
) -> bool:
    """
    Generate a single baseline.

    Args:
        scenario_id: Scenario identifier
        executor: GMAT executor
        output_dir: Directory for script and output files

    Returns:
        True if successful
    """
    if scenario_id not in SCENARIOS:
        print(f"Error: Unknown scenario '{scenario_id}'")
        print(f"Available scenarios: {', '.join(SCENARIOS.keys())}")
        return False

    config = SCENARIOS[scenario_id]
    print(f"\nGenerating baseline for: {scenario_id}")
    print(f"  Duration: {config.duration_hours} hours")
    print(f"  Step: {config.report_step_s} seconds")

    # Generate script
    generator = GMATScriptGenerator()
    script_path = output_dir / f"{scenario_id}.script"

    if config.has_ep_thruster:
        generator.generate_orbit_lowering_script(config, script_path)
    else:
        generator.generate_pure_propagation_script(config, script_path)

    print(f"  Script: {script_path}")

    # Execute GMAT
    print("  Executing GMAT...")
    result = executor.execute_script(script_path, timeout_s=3600)

    if not result.success:
        print(f"  Error: GMAT execution failed")
        print(f"    Return code: {result.return_code}")
        print(f"    stderr: {result.stderr[:500]}")
        return False

    print(f"  Execution time: {result.execution_time_s:.1f}s")

    # Look for output files in the configured output directory (not the isolated run dir)
    gmat_output_dir = Path(config.output_dir)
    ephemeris_file = gmat_output_dir / f"ephemeris_{scenario_id}.txt"

    if not ephemeris_file.exists():
        # Fall back to checking the result output files
        ephemeris_files = [f for f in result.output_files if "ephemeris" in f.name.lower()]
        if ephemeris_files:
            ephemeris_file = ephemeris_files[0]
        else:
            print(f"  Error: No ephemeris output found")
            print(f"    Expected: {ephemeris_file}")
            return False

    print(f"  Ephemeris file: {ephemeris_file}")

    # Parse ephemeris
    parser = GMATOutputParser()
    ephemeris_df = parser.parse_ephemeris_report(ephemeris_file)
    print(f"  Ephemeris points: {len(ephemeris_df)}")

    # Create and store baseline
    gmat_info = check_gmat_installation()
    baseline = create_baseline_from_ephemeris(
        scenario_id=scenario_id,
        scenario_config=config,
        ephemeris_df=ephemeris_df,
        gmat_version=gmat_info.get("version"),
    )

    manager = GMATBaselineManager()
    baseline_path = manager.store_baseline(scenario_id, baseline)
    print(f"  Baseline stored: {baseline_path}")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Generate GMAT baselines for validation"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        help="Scenario ID to generate (e.g., pure_propagation_12h)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate all predefined scenarios",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent / "scripts",
        help="Directory for script and output files",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available scenarios",
    )

    args = parser.parse_args()

    if args.list:
        print("Available scenarios:")
        for name, config in SCENARIOS.items():
            print(f"  {name}: {config.scenario_name}")
        return 0

    # Check GMAT
    gmat_info = check_gmat_installation()
    if not gmat_info["available"]:
        print("Error: GMAT not installed")
        print("  Set GMAT_ROOT environment variable or install GMAT")
        return 1

    print(f"GMAT found: {gmat_info['path']}")
    print(f"Version: {gmat_info.get('version', 'unknown')}")

    executor = GMATExecutor()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.all:
        successes = 0
        for scenario_id in SCENARIOS:
            if generate_baseline(scenario_id, executor, args.output_dir):
                successes += 1
        print(f"\nGenerated {successes}/{len(SCENARIOS)} baselines")
        return 0 if successes == len(SCENARIOS) else 1

    if args.scenario:
        success = generate_baseline(args.scenario, executor, args.output_dir)
        return 0 if success else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
