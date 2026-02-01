"""Scenario runner for simulator validation against GMAT.

Executes GMAT-defined scenarios through the simulator and compares
results against GMAT truth data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

from ..case_registry import CaseDefinition, get_case, get_all_cases
from .sim_adapter import GmatToSimAdapter, SimScenario
from .compare_truth import (
    TruthComparator,
    SimulatorState,
    ComparisonResult,
)


logger = logging.getLogger(__name__)


@dataclass
class ScenarioResult:
    """Result of running a scenario through the simulator."""

    case_id: str
    success: bool
    error_message: Optional[str] = None

    # Simulator outputs
    initial_state: Optional[SimulatorState] = None
    final_state: Optional[SimulatorState] = None
    derived_metrics: Dict[str, float] = field(default_factory=dict)

    # Comparison with GMAT (if available)
    comparison: Optional[ComparisonResult] = None

    # Runtime metadata
    sim_duration_s: float = 0.0
    output_dir: Optional[str] = None

    @property
    def summary(self) -> str:
        """Generate human-readable summary."""
        status = "SUCCESS" if self.success else "FAILED"
        lines = [f"Scenario {self.case_id}: {status}"]

        if self.error_message:
            lines.append(f"  Error: {self.error_message}")

        if self.final_state:
            lines.append("  Final state:")
            lines.append(f"    SMA: {self.final_state.sma_km:.3f} km")
            lines.append(f"    Alt: {self.final_state.altitude_km:.3f} km")
            lines.append(f"    Mass: {self.final_state.mass_kg:.3f} kg")

        if self.derived_metrics:
            lines.append("  Derived metrics:")
            for key, value in sorted(self.derived_metrics.items()):
                lines.append(f"    {key}: {value:.6f}")

        if self.comparison:
            if self.comparison.passed:
                lines.append("  Comparison: PASS")
            else:
                lines.append("  Comparison: FAIL")
                for failure in self.comparison.failures[:3]:
                    lines.append(f"    - {failure}")

        lines.append(f"  Runtime: {self.sim_duration_s:.2f}s")

        return "\n".join(lines)


class ScenarioRunner:
    """Runs GMAT-defined scenarios through the simulator."""

    # Earth parameters
    EARTH_RADIUS_KM = 6378.137
    MU_EARTH = 398600.4418  # km^3/s^2

    def __init__(
        self,
        adapter: Optional[GmatToSimAdapter] = None,
        comparator: Optional[TruthComparator] = None,
        output_base_dir: Optional[Path] = None,
    ):
        """
        Initialize scenario runner.

        Args:
            adapter: GMAT to simulator adapter (creates default if None)
            comparator: Truth comparator (creates default if None)
            output_base_dir: Base directory for simulation outputs
        """
        self.adapter = adapter or GmatToSimAdapter()
        self.comparator = comparator or TruthComparator()
        self.output_base_dir = output_base_dir or Path("validation/output/scenarios")

    def run_scenario(
        self,
        case_id: str,
        overrides: Optional[Dict] = None,
        compare_truth: bool = True,
        truth_version: str = "v1",
        fallback_to_low_fidelity: bool = True,
    ) -> ScenarioResult:
        """
        Run a single scenario through the simulator.

        Args:
            case_id: GMAT case identifier (e.g., "R01", "N01")
            overrides: Optional parameter overrides
            compare_truth: Whether to compare against GMAT truth
            truth_version: Version of truth file to compare against
            fallback_to_low_fidelity: If True, retry with LOW fidelity on failure

        Returns:
            ScenarioResult with simulation outputs and comparison
        """
        import time

        logger.info(f"Running scenario: {case_id}")

        start_time = time.time()

        try:
            # Create scenario from GMAT case definition
            scenario = self.adapter.create_scenario(case_id, overrides)
        except ValueError as e:
            return ScenarioResult(
                case_id=case_id,
                success=False,
                error_message=f"Failed to create scenario: {e}",
            )

        try:
            # Run through simulator
            sim_result = self._execute_simulation(scenario)
        except Exception as e:
            logger.warning(f"Simulation failed for {case_id}: {e}")

            # Try with LOW fidelity as fallback (uses SGP4 instead of Basilisk)
            if fallback_to_low_fidelity and scenario.config.fidelity.value != "LOW":
                logger.info(f"Retrying {case_id} with LOW fidelity")
                from sim.core.types import Fidelity
                scenario.config.fidelity = Fidelity.LOW
                scenario.config.time_step_s = 60.0
                try:
                    sim_result = self._execute_simulation(scenario)
                except Exception as e2:
                    logger.exception(f"Simulation failed for {case_id} (LOW fidelity)")
                    return ScenarioResult(
                        case_id=case_id,
                        success=False,
                        error_message=f"Simulation failed: {e2}",
                        sim_duration_s=time.time() - start_time,
                    )
            else:
                return ScenarioResult(
                    case_id=case_id,
                    success=False,
                    error_message=f"Simulation failed: {e}",
                    sim_duration_s=time.time() - start_time,
                )

        # Extract initial and final states
        initial_state = self._extract_initial_state(scenario)
        final_state = self._extract_final_state(sim_result, scenario)

        # Compute derived metrics
        derived_metrics = self._compute_derived_metrics(
            scenario, initial_state, final_state, sim_result
        )

        result = ScenarioResult(
            case_id=case_id,
            success=True,
            initial_state=initial_state,
            final_state=final_state,
            derived_metrics=derived_metrics,
            sim_duration_s=time.time() - start_time,
            output_dir=sim_result.artifacts.get("run_dir"),
        )

        # Compare against GMAT truth if requested
        if compare_truth:
            try:
                result.comparison = self.comparator.compare_truth(
                    case_id=case_id,
                    sim_initial=initial_state,
                    sim_final=final_state,
                    sim_derived=derived_metrics,
                    truth_version=truth_version,
                )
                # Update success based on comparison
                if result.comparison and not result.comparison.passed:
                    result.success = False
                    result.error_message = "Failed GMAT truth comparison"
            except Exception as e:
                logger.warning(f"Truth comparison failed for {case_id}: {e}")
                # Don't fail the run, just note the comparison issue

        logger.info(f"Scenario {case_id} complete: {result.success}")
        return result

    def run_tier(
        self,
        tier: str,
        compare_truth: bool = True,
    ) -> List[ScenarioResult]:
        """
        Run all scenarios in a tier.

        Args:
            tier: Tier identifier ("A" or "B")
            compare_truth: Whether to compare against GMAT truth

        Returns:
            List of ScenarioResults for all cases in tier
        """
        cases = get_all_cases()
        tier_cases = [c for c in cases if c.tier.upper() == tier.upper()]

        logger.info(f"Running {len(tier_cases)} cases in tier {tier}")

        results = []
        for case_def in tier_cases:
            result = self.run_scenario(
                case_id=case_def.case_id,
                compare_truth=compare_truth,
            )
            results.append(result)

        # Summary
        passed = sum(1 for r in results if r.success)
        logger.info(f"Tier {tier}: {passed}/{len(results)} passed")

        return results

    def _execute_simulation(self, scenario: SimScenario) -> "SimResults":
        """Execute simulation and return results."""
        from sim.engine import simulate

        # Ensure output directory exists
        output_dir = self.output_base_dir / scenario.case_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Update config output directory
        scenario.config.output_dir = str(output_dir)

        # Run simulation
        results = simulate(
            plan=scenario.plan,
            initial_state=scenario.initial_state,
            fidelity=scenario.config.fidelity,
            config=scenario.config,
        )

        return results

    def _extract_initial_state(self, scenario: SimScenario) -> SimulatorState:
        """Extract initial state as SimulatorState."""
        initial = scenario.initial_state

        # Convert position to Keplerian elements
        sma_km, ecc, inc_deg, raan_deg, aop_deg, ta_deg = self._cartesian_to_keplerian(
            position_km=initial.position_eci,
            velocity_km_s=initial.velocity_eci,
        )

        altitude_km = np.linalg.norm(initial.position_eci) - self.EARTH_RADIUS_KM

        return SimulatorState(
            epoch_utc=initial.epoch.isoformat(),
            sma_km=sma_km,
            ecc=ecc,
            inc_deg=inc_deg,
            raan_deg=raan_deg,
            aop_deg=aop_deg,
            ta_deg=ta_deg,
            mass_kg=initial.mass_kg,
            altitude_km=altitude_km,
            x_km=initial.position_eci[0],
            y_km=initial.position_eci[1],
            z_km=initial.position_eci[2],
            vx_km_s=initial.velocity_eci[0],
            vy_km_s=initial.velocity_eci[1],
            vz_km_s=initial.velocity_eci[2],
        )

    def _extract_final_state(
        self,
        sim_result: "SimResults",
        scenario: SimScenario,
    ) -> SimulatorState:
        """Extract final state as SimulatorState."""
        final = sim_result.final_state

        # Convert position to Keplerian elements
        sma_km, ecc, inc_deg, raan_deg, aop_deg, ta_deg = self._cartesian_to_keplerian(
            position_km=final.position_eci,
            velocity_km_s=final.velocity_eci,
        )

        altitude_km = np.linalg.norm(final.position_eci) - self.EARTH_RADIUS_KM

        return SimulatorState(
            epoch_utc=final.epoch.isoformat(),
            sma_km=sma_km,
            ecc=ecc,
            inc_deg=inc_deg,
            raan_deg=raan_deg,
            aop_deg=aop_deg,
            ta_deg=ta_deg,
            mass_kg=final.mass_kg,
            altitude_km=altitude_km,
            x_km=final.position_eci[0],
            y_km=final.position_eci[1],
            z_km=final.position_eci[2],
            vx_km_s=final.velocity_eci[0],
            vy_km_s=final.velocity_eci[1],
            vz_km_s=final.velocity_eci[2],
        )

    def _compute_derived_metrics(
        self,
        scenario: SimScenario,
        initial_state: SimulatorState,
        final_state: SimulatorState,
        sim_result: "SimResults",
    ) -> Dict[str, float]:
        """Compute derived metrics for comparison."""
        metrics = {}

        # SMA drift
        sma_drift_km = final_state.sma_km - initial_state.sma_km
        metrics["sma_drift_km"] = sma_drift_km

        # SMA drift rate (per day)
        duration_days = scenario.duration_s / 86400.0
        if duration_days > 0:
            metrics["sma_drift_km_per_day"] = sma_drift_km / duration_days

        # Propellant used
        propellant_used_kg = initial_state.mass_kg - final_state.mass_kg
        metrics["propellant_used_kg"] = propellant_used_kg

        # Altitude change
        metrics["altitude_change_km"] = final_state.altitude_km - initial_state.altitude_km

        # Duty cycle (for EP cases)
        if scenario.case_def.propulsion.value in ["EP", "EP_THF"]:
            # Estimate based on activity types
            total_thrust_time = 0.0
            for activity in scenario.plan.activities:
                if activity.activity_type in ["orbit_lower", "drag_makeup"]:
                    duration = (activity.end_time - activity.start_time).total_seconds()
                    total_thrust_time += duration

            if scenario.duration_s > 0:
                metrics["duty_cycle"] = total_thrust_time / scenario.duration_s

        return metrics

    def _cartesian_to_keplerian(
        self,
        position_km: np.ndarray,
        velocity_km_s: np.ndarray,
    ) -> Tuple[float, float, float, float, float, float]:
        """
        Convert Cartesian state to Keplerian elements.

        Returns:
            Tuple of (sma_km, ecc, inc_deg, raan_deg, aop_deg, ta_deg)
        """
        r = np.array(position_km)
        v = np.array(velocity_km_s)

        # Magnitudes
        r_mag = np.linalg.norm(r)
        v_mag = np.linalg.norm(v)

        # Angular momentum
        h = np.cross(r, v)
        h_mag = np.linalg.norm(h)

        # Node vector
        n = np.cross([0, 0, 1], h)
        n_mag = np.linalg.norm(n)

        # Eccentricity vector
        e_vec = ((v_mag**2 - self.MU_EARTH / r_mag) * r - np.dot(r, v) * v) / self.MU_EARTH
        ecc = np.linalg.norm(e_vec)

        # Specific energy
        energy = v_mag**2 / 2 - self.MU_EARTH / r_mag

        # Semi-major axis
        if abs(1 - ecc) > 1e-10:  # Not parabolic
            sma_km = -self.MU_EARTH / (2 * energy)
        else:
            sma_km = float("inf")

        # Inclination
        inc_rad = np.arccos(np.clip(h[2] / h_mag, -1, 1))
        inc_deg = np.degrees(inc_rad)

        # RAAN
        if n_mag > 1e-10:
            raan_rad = np.arccos(np.clip(n[0] / n_mag, -1, 1))
            if n[1] < 0:
                raan_rad = 2 * np.pi - raan_rad
        else:
            raan_rad = 0.0
        raan_deg = np.degrees(raan_rad)

        # Argument of periapsis
        if n_mag > 1e-10 and ecc > 1e-10:
            aop_rad = np.arccos(np.clip(np.dot(n, e_vec) / (n_mag * ecc), -1, 1))
            if e_vec[2] < 0:
                aop_rad = 2 * np.pi - aop_rad
        else:
            aop_rad = 0.0
        aop_deg = np.degrees(aop_rad)

        # True anomaly
        if ecc > 1e-10:
            ta_rad = np.arccos(np.clip(np.dot(e_vec, r) / (ecc * r_mag), -1, 1))
            if np.dot(r, v) < 0:
                ta_rad = 2 * np.pi - ta_rad
        else:
            # Circular orbit - use argument of latitude
            if n_mag > 1e-10:
                ta_rad = np.arccos(np.clip(np.dot(n, r) / (n_mag * r_mag), -1, 1))
                if r[2] < 0:
                    ta_rad = 2 * np.pi - ta_rad
            else:
                ta_rad = 0.0
        ta_deg = np.degrees(ta_rad)

        return sma_km, ecc, inc_deg, raan_deg, aop_deg, ta_deg


def run_scenario(
    case_id: str,
    overrides: Optional[Dict] = None,
    compare_truth: bool = True,
) -> ScenarioResult:
    """
    Convenience function to run a single scenario.

    Args:
        case_id: GMAT case identifier
        overrides: Optional parameter overrides
        compare_truth: Whether to compare against GMAT truth

    Returns:
        ScenarioResult
    """
    runner = ScenarioRunner()
    return runner.run_scenario(case_id, overrides, compare_truth)


def run_all_scenarios(
    tier: Optional[str] = None,
    compare_truth: bool = True,
) -> Dict[str, ScenarioResult]:
    """
    Run all scenarios (or tier subset).

    Args:
        tier: Optional tier filter ("A" or "B")
        compare_truth: Whether to compare against GMAT truth

    Returns:
        Dict mapping case_id to ScenarioResult
    """
    runner = ScenarioRunner()

    if tier:
        results = runner.run_tier(tier, compare_truth)
    else:
        # Run all cases
        cases = get_all_cases()
        results = []
        for case_def in cases:
            result = runner.run_scenario(
                case_id=case_def.case_id,
                compare_truth=compare_truth,
            )
            results.append(result)

    return {r.case_id: r for r in results}


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Run GMAT validation scenarios")
    parser.add_argument("--case", "-c", help="Case ID to run (e.g., R01)")
    parser.add_argument("--tier", "-t", choices=["A", "B"], help="Run all cases in tier")
    parser.add_argument("--no-compare", action="store_true", help="Skip truth comparison")
    parser.add_argument("--output", "-o", help="Output directory")

    args = parser.parse_args()

    if args.case:
        result = run_scenario(
            case_id=args.case,
            compare_truth=not args.no_compare,
        )
        print(result.summary)
    elif args.tier:
        runner = ScenarioRunner()
        if args.output:
            runner.output_base_dir = Path(args.output)
        results = runner.run_tier(args.tier, compare_truth=not args.no_compare)
        print(f"\n{'='*60}")
        print(f"Tier {args.tier} Results")
        print(f"{'='*60}")
        for result in results:
            print(result.summary)
            print("-" * 40)
    else:
        parser.print_help()
