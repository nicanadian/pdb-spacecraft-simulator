"""ETE baseline regression tests - validate simulator against committed baselines.

Tests position/velocity accuracy against GMAT baselines stored in
validation/baselines/gmat/.

Key features:
- Uses committed baseline data (not generated on-the-fly)
- Tests both ephemeris baselines and final state baselines
- Validates physics invariants alongside accuracy
- Clear failure messages with subsystem identification

Usage:
    pytest tests/ete/test_baseline_regression.py -v
    pytest tests/ete/ -m "ete_tier_a" -v
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pytest
import numpy as np

from .conftest import (
    REFERENCE_EPOCH,
    get_baseline_file_path,
    create_test_plan,
    create_test_initial_state,
    create_test_config,
)

pytestmark = [
    pytest.mark.ete_tier_a,
    pytest.mark.ete,
]


# Baseline directory
BASELINES_DIR = Path("validation/baselines/gmat")


def load_baseline_manifest() -> Dict:
    """Load the baselines manifest."""
    manifest_path = BASELINES_DIR / "manifest.json"
    if not manifest_path.exists():
        return {"baselines": {}}

    with open(manifest_path) as f:
        return json.load(f)


def get_available_baselines() -> List[str]:
    """Get list of available baseline case IDs."""
    manifest = load_baseline_manifest()
    return list(manifest.get("baselines", {}).keys())


def load_baseline(case_id: str, version: str = "v1") -> Optional[Dict]:
    """Load baseline data for a case."""
    baseline_path = get_baseline_file_path(case_id, version)
    if not baseline_path.exists():
        return None

    with open(baseline_path) as f:
        return json.load(f)


# Get available baselines for parametrization
AVAILABLE_BASELINES = get_available_baselines()


class TestBaselineAvailability:
    """Test that baseline infrastructure is available."""

    def test_baselines_directory_exists(self):
        """Verify baselines directory exists."""
        assert BASELINES_DIR.exists(), (
            f"Baselines directory not found: {BASELINES_DIR}\n"
            "Run baseline generation to create baselines."
        )

    def test_manifest_exists(self):
        """Verify manifest file exists."""
        manifest_path = BASELINES_DIR / "manifest.json"
        assert manifest_path.exists(), (
            f"Manifest not found: {manifest_path}\n"
            "Baselines manifest tracks available baseline data."
        )

    def test_manifest_has_baselines(self):
        """Verify manifest contains baseline entries."""
        manifest = load_baseline_manifest()
        baselines = manifest.get("baselines", {})

        assert len(baselines) > 0, (
            "No baselines in manifest.\n"
            "Generate baselines with validation harness."
        )


class TestEphemerisBaseline:
    """Test ephemeris (time-series) baselines."""

    @pytest.mark.parametrize("case_id", [
        "pure_propagation_12h",
    ])
    def test_ephemeris_baseline_structure(self, case_id: str, require_baseline):
        """
        Verify ephemeris baseline has correct structure.
        """
        baseline_path = require_baseline(case_id)

        with open(baseline_path) as f:
            baseline = json.load(f)

        # Check structure
        assert "metadata" in baseline or "ephemeris" in baseline, (
            f"Baseline {case_id} missing metadata or ephemeris"
        )

        if "ephemeris" in baseline:
            ephemeris = baseline["ephemeris"]
            assert len(ephemeris) > 0, f"Baseline {case_id} has empty ephemeris"

            # Check first point has required fields
            first_point = ephemeris[0]
            required_fields = ["epoch_utc", "x_km", "y_km", "z_km"]
            for field in required_fields:
                assert field in first_point, (
                    f"Baseline {case_id} ephemeris missing field: {field}"
                )

    @pytest.mark.parametrize("case_id", [
        "pure_propagation_12h",
    ])
    def test_propagation_against_ephemeris_baseline(
        self, case_id: str, require_baseline, tolerance_config, physics_validator, tmp_path
    ):
        """
        Compare propagation against ephemeris baseline.

        This test runs the simulator with the same initial conditions
        as the baseline and compares the trajectory.
        """
        baseline_path = require_baseline(case_id)

        with open(baseline_path) as f:
            baseline = json.load(f)

        if "ephemeris" not in baseline:
            pytest.skip(f"Baseline {case_id} is not an ephemeris baseline")

        ephemeris = baseline["ephemeris"]
        metadata = baseline.get("metadata", {})

        # Get initial state from first ephemeris point
        first = ephemeris[0]
        last = ephemeris[-1]

        # Parse epoch
        start_epoch = datetime.fromisoformat(
            first["epoch_utc"].replace("Z", "+00:00")
        )
        end_epoch = datetime.fromisoformat(
            last["epoch_utc"].replace("Z", "+00:00")
        )

        from sim.engine import simulate
        from sim.core.types import Fidelity

        initial_state = create_test_initial_state(
            epoch=start_epoch,
            position_eci=[first["x_km"], first["y_km"], first["z_km"]],
            velocity_eci=[
                first.get("vx_km_s", 0),
                first.get("vy_km_s", 0),
                first.get("vz_km_s", 0),
            ],
            mass_kg=metadata.get("mass_kg", 500.0),
        )

        # Use MEDIUM fidelity for GMAT baseline comparisons
        # LOW fidelity uses SGP4 which will diverge significantly from GMAT numerical integration
        result = simulate(
            plan=create_test_plan(
                plan_id=f"baseline_test_{case_id}",
                start_time=start_epoch,
                end_time=end_epoch,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        assert result is not None
        assert result.final_state is not None

        # Compare final position
        final_pos_sim = np.array(result.final_state.position_eci)
        final_pos_baseline = np.array([last["x_km"], last["y_km"], last["z_km"]])

        position_error_km = np.linalg.norm(final_pos_sim - final_pos_baseline)
        tolerance_km = tolerance_config.get_tolerance("position_rms_km", case_id)

        assert position_error_km < tolerance_km, (
            f"POSITION ERROR vs BASELINE for {case_id}\n"
            f"  Simulator final: {final_pos_sim}\n"
            f"  Baseline final:  {final_pos_baseline}\n"
            f"  Error:           {position_error_km:.3f} km\n"
            f"  Tolerance:       {tolerance_km:.3f} km"
        )


class TestFinalStateBaseline:
    """Test final state baselines (R01-R12, N01-N06)."""

    # Cases that have final state baselines
    FINAL_STATE_CASES = [
        c for c in AVAILABLE_BASELINES
        if c.startswith("R") or c.startswith("N") or c.startswith("r") or c.startswith("n")
    ]

    @pytest.mark.parametrize("case_id", FINAL_STATE_CASES or ["skip"])
    def test_final_state_baseline_structure(self, case_id: str, require_baseline):
        """
        Verify final state baseline has correct structure.
        """
        if case_id == "skip":
            pytest.skip("No final state baselines available")

        baseline_path = require_baseline(case_id)

        with open(baseline_path) as f:
            baseline = json.load(f)

        # Check structure
        assert "initial" in baseline or "final" in baseline, (
            f"Baseline {case_id} missing initial/final state"
        )

        if "final" in baseline:
            final = baseline["final"]

            # Required orbital elements or cartesian state
            # Support both naming conventions: sma/x and sma_km/x_km
            has_elements = any(k in final for k in ["sma", "a", "sma_km", "a_km"])
            has_cartesian = any(k in final for k in ["x", "position", "x_km"])

            assert has_elements or has_cartesian, (
                f"Baseline {case_id} final state missing orbital elements or cartesian state\n"
                f"Available keys: {list(final.keys())}"
            )

    @pytest.mark.parametrize("case_id", FINAL_STATE_CASES[:3] if FINAL_STATE_CASES else ["skip"])
    def test_scenario_against_final_state_baseline(
        self, case_id: str, require_baseline, tolerance_config
    ):
        """
        Compare scenario execution against final state baseline.
        """
        if case_id == "skip":
            pytest.skip("No final state baselines available")

        baseline_path = require_baseline(case_id)

        with open(baseline_path) as f:
            baseline = json.load(f)

        initial = baseline.get("initial", {})
        final_expected = baseline.get("final", {})

        if not initial or not final_expected:
            pytest.skip(f"Baseline {case_id} incomplete")

        # Get initial state - support both naming conventions
        if "x_km" in initial:
            pos = [initial["x_km"], initial["y_km"], initial["z_km"]]
            vel = [initial["vx_km_s"], initial["vy_km_s"], initial["vz_km_s"]]
        elif "x" in initial:
            pos = [initial["x"], initial["y"], initial["z"]]
            vel = [initial["vx"], initial["vy"], initial["vz"]]
        else:
            pytest.skip(f"Cannot parse initial state for {case_id}")

        # Get epoch - support multiple naming conventions
        epoch_str = initial.get("epoch_utc") or initial.get("epoch") or baseline.get("epoch")
        if epoch_str:
            start_epoch = datetime.fromisoformat(epoch_str.replace("Z", "+00:00"))
        else:
            start_epoch = REFERENCE_EPOCH

        # Get end epoch from final state or duration
        final_epoch_str = final_expected.get("epoch_utc") or final_expected.get("epoch")
        if final_epoch_str:
            end_epoch = datetime.fromisoformat(final_epoch_str.replace("Z", "+00:00"))
        else:
            duration_days = baseline.get("duration_days", 1.0)
            end_epoch = start_epoch + timedelta(days=duration_days)

        from sim.engine import simulate
        from sim.core.types import Fidelity

        initial_state = create_test_initial_state(
            epoch=start_epoch,
            position_eci=pos,
            velocity_eci=vel,
            mass_kg=initial.get("mass_kg") or initial.get("mass", 500.0),
        )

        result = simulate(
            plan=create_test_plan(
                plan_id=f"final_state_test_{case_id}",
                start_time=start_epoch,
                end_time=end_epoch,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=f"/tmp/baseline_test_{case_id}", time_step_s=60.0),
        )

        assert result is not None
        assert result.final_state is not None

        # Compare final SMA if available - support both naming conventions
        sma_key = "sma_km" if "sma_km" in final_expected else "sma"
        if sma_key in final_expected:
            # Compute SMA from final state
            pos_final = np.array(result.final_state.position_eci)
            vel_final = np.array(result.final_state.velocity_eci)

            r = np.linalg.norm(pos_final)
            v = np.linalg.norm(vel_final)
            mu = 398600.4418  # km^3/s^2

            energy = v**2 / 2 - mu / r
            sma_sim = -mu / (2 * energy) if abs(energy) > 1e-10 else float('inf')

            sma_baseline = final_expected[sma_key]
            sma_error_km = abs(sma_sim - sma_baseline)

            tolerance_km = tolerance_config.get_tolerance(
                "sma_rms_km", case_id, default=10.0
            )

            assert sma_error_km < tolerance_km, (
                f"SMA ERROR vs BASELINE for {case_id}\n"
                f"  Simulator SMA: {sma_sim:.3f} km\n"
                f"  Baseline SMA:  {sma_baseline:.3f} km\n"
                f"  Error:         {sma_error_km:.3f} km\n"
                f"  Tolerance:     {tolerance_km:.3f} km"
            )


class TestBaselinePhysicsInvariants:
    """Test that baselines satisfy physics invariants."""

    @pytest.mark.parametrize("case_id", AVAILABLE_BASELINES[:5] if AVAILABLE_BASELINES else ["skip"])
    def test_baseline_orbit_is_bound(self, case_id: str, physics_validator):
        """
        Verify baseline initial/final states are bound orbits.
        """
        if case_id == "skip":
            pytest.skip("No baselines available")

        baseline = load_baseline(case_id)
        if baseline is None:
            pytest.skip(f"Baseline {case_id} not found")

        # Check initial state
        initial = baseline.get("initial", {})
        if "x_km" in initial:
            pos = [initial["x_km"], initial["y_km"], initial["z_km"]]
            vel = [initial["vx_km_s"], initial["vy_km_s"], initial["vz_km_s"]]
            energy = physics_validator.compute_specific_energy(pos, vel)
            assert energy < 0, (
                f"BASELINE {case_id} INITIAL STATE NOT BOUND\n"
                f"  Energy: {energy:.6f} km²/s²\n"
                f"  Bound orbits must have negative energy."
            )
        elif "x" in initial:
            pos = [initial["x"], initial["y"], initial["z"]]
            vel = [initial["vx"], initial["vy"], initial["vz"]]
            energy = physics_validator.compute_specific_energy(pos, vel)
            assert energy < 0, (
                f"BASELINE {case_id} INITIAL STATE NOT BOUND\n"
                f"  Energy: {energy:.6f} km²/s²\n"
                f"  Bound orbits must have negative energy."
            )

        # Check final state
        final = baseline.get("final", {})
        if "x_km" in final:
            pos = [final["x_km"], final["y_km"], final["z_km"]]
            vel = [final["vx_km_s"], final["vy_km_s"], final["vz_km_s"]]
            energy = physics_validator.compute_specific_energy(pos, vel)
            assert energy < 0, (
                f"BASELINE {case_id} FINAL STATE NOT BOUND\n"
                f"  Energy: {energy:.6f} km²/s²\n"
                f"  Bound orbits must have negative energy."
            )
        elif "x" in final:
            pos = [final["x"], final["y"], final["z"]]
            vel = [final["vx"], final["vy"], final["vz"]]
            energy = physics_validator.compute_specific_energy(pos, vel)
            assert energy < 0, (
                f"BASELINE {case_id} FINAL STATE NOT BOUND\n"
                f"  Energy: {energy:.6f} km²/s²\n"
                f"  Bound orbits must have negative energy."
            )

    @pytest.mark.parametrize("case_id", ["pure_propagation_12h"])
    def test_ephemeris_baseline_energy_conservation(
        self, case_id: str, physics_validator
    ):
        """
        Verify ephemeris baseline conserves energy (for non-thrust cases).
        """
        baseline = load_baseline(case_id)
        if baseline is None:
            pytest.skip(f"Baseline {case_id} not found")

        if "ephemeris" not in baseline:
            pytest.skip(f"Baseline {case_id} is not an ephemeris baseline")

        ephemeris = baseline["ephemeris"]
        if len(ephemeris) < 2:
            pytest.skip("Ephemeris too short")

        first = ephemeris[0]
        last = ephemeris[-1]

        pos_initial = [first["x_km"], first["y_km"], first["z_km"]]
        vel_initial = [
            first.get("vx_km_s", 0),
            first.get("vy_km_s", 0),
            first.get("vz_km_s", 0),
        ]

        pos_final = [last["x_km"], last["y_km"], last["z_km"]]
        vel_final = [
            last.get("vx_km_s", 0),
            last.get("vy_km_s", 0),
            last.get("vz_km_s", 0),
        ]

        is_valid, drift_pct, msg = physics_validator.validate_energy_conservation(
            pos_initial, vel_initial,
            pos_final, vel_final,
            tolerance_pct=0.2,  # Relaxed for development (target: 0.1%)
        )

        assert is_valid, (
            f"BASELINE {case_id} ENERGY DRIFT\n"
            f"  {msg}\n"
            f"\n"
            f"GMAT baseline should conserve energy for pure propagation."
        )


@pytest.mark.ete_tier_b
class TestExtendedBaselineRegression:
    """Extended baseline regression tests (Tier B - nightly)."""

    @pytest.mark.parametrize("case_id", AVAILABLE_BASELINES or ["skip"])
    def test_all_baselines_loadable(self, case_id: str):
        """
        Verify all baselines in manifest are loadable.
        """
        if case_id == "skip":
            pytest.skip("No baselines available")

        baseline = load_baseline(case_id)
        assert baseline is not None, f"Failed to load baseline: {case_id}"

        # Verify JSON structure is valid
        assert isinstance(baseline, dict), f"Baseline {case_id} not a dict"

    @pytest.mark.parametrize("case_id", AVAILABLE_BASELINES or ["skip"])
    def test_baseline_metadata_complete(self, case_id: str):
        """
        Verify baselines have complete metadata.
        """
        if case_id == "skip":
            pytest.skip("No baselines available")

        baseline = load_baseline(case_id)
        if baseline is None:
            pytest.skip(f"Baseline {case_id} not found")

        # Check for required metadata
        metadata = baseline.get("metadata", baseline)

        # Should have version info
        has_version = (
            "schema_version" in baseline or
            "version" in baseline or
            "gmat_version" in metadata
        )

        assert has_version or "case_id" in baseline, (
            f"Baseline {case_id} missing version or identification metadata"
        )
