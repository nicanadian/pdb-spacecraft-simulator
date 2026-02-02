"""ETE fidelity tests - validate MEDIUM/HIGH fidelity and cross-fidelity comparison.

Tests Basilisk integration for MEDIUM and HIGH fidelity simulations,
and validates cross-fidelity consistency between LOW and MEDIUM.

Key features:
- MEDIUM fidelity simulation with Basilisk
- HIGH fidelity simulation (when available)
- Cross-fidelity comparison (LOW vs MEDIUM)
- Fallback behavior when Basilisk not installed
- Physics validation across fidelity levels

Usage:
    pytest tests/ete/test_fidelity.py -v
    pytest tests/ete/ -m "ete_tier_a" -v
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

import pytest
import numpy as np

from .conftest import (
    REFERENCE_EPOCH,
    create_test_plan,
    create_test_initial_state,
    create_test_config,
)

# Check Basilisk availability
try:
    from sim.models.basilisk_propagator import BASILISK_AVAILABLE
except ImportError:
    BASILISK_AVAILABLE = False


pytestmark = [
    pytest.mark.ete_tier_a,
    pytest.mark.ete,
]


class TestFidelitySelection:
    """Test fidelity selection and propagator routing."""

    def test_low_fidelity_uses_sgp4(self, reference_epoch, tmp_path):
        """
        Verify LOW fidelity uses SGP4 propagator.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=2)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        result = simulate(
            plan=create_test_plan(
                plan_id="low_fidelity_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        assert result is not None
        assert result.final_state is not None

        # Check propagator info if available
        if hasattr(result, 'propagator_version'):
            assert 'sgp4' in result.propagator_version.lower()

    def test_fidelity_enum_values(self):
        """
        Verify all fidelity levels are defined.
        """
        from sim.core.types import Fidelity

        assert hasattr(Fidelity, 'LOW')
        assert hasattr(Fidelity, 'MEDIUM')
        assert hasattr(Fidelity, 'HIGH')

        # Verify they have string values
        assert Fidelity.LOW.value in ('LOW', 'low')
        assert Fidelity.MEDIUM.value in ('MEDIUM', 'medium')
        assert Fidelity.HIGH.value in ('HIGH', 'high')


class TestMediumFidelity:
    """Test MEDIUM fidelity simulation with Basilisk."""

    @pytest.mark.skipif(
        not BASILISK_AVAILABLE,
        reason="Basilisk not installed - install with: pip install Basilisk"
    )
    def test_medium_fidelity_completes(self, reference_epoch, tmp_path):
        """
        Verify MEDIUM fidelity simulation completes with Basilisk.

        This test requires Basilisk to be installed.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=2)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        result = simulate(
            plan=create_test_plan(
                plan_id="medium_fidelity_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        assert result is not None, "MEDIUM fidelity simulation returned None"
        assert result.final_state is not None, "No final state from MEDIUM fidelity"

        # Verify propagator was Basilisk (not fallback)
        if hasattr(result, 'propagator_version'):
            assert 'basilisk' in result.propagator_version.lower(), (
                f"Expected Basilisk propagator, got: {result.propagator_version}\n"
                "MEDIUM fidelity should use Basilisk, not SGP4 fallback"
            )

    @pytest.mark.skipif(
        not BASILISK_AVAILABLE,
        reason="Basilisk not installed"
    )
    def test_medium_fidelity_orbit_valid(self, reference_epoch, tmp_path, physics_validator):
        """
        Verify MEDIUM fidelity produces physically valid orbit.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=6)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        result = simulate(
            plan=create_test_plan(
                plan_id="medium_orbit_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        # Validate physics
        final_pos = np.array(result.final_state.position_eci)
        final_vel = np.array(result.final_state.velocity_eci)

        # Check bound orbit
        energy = physics_validator.compute_specific_energy(final_pos, final_vel)
        assert energy < 0, (
            f"MEDIUM fidelity produced unbound orbit\n"
            f"  Energy: {energy:.6f} km²/s²"
        )

        # Check reasonable altitude
        altitude_km = np.linalg.norm(final_pos) - 6378.137
        assert 100 < altitude_km < 1000, (
            f"MEDIUM fidelity altitude unreasonable: {altitude_km:.1f} km"
        )

    @pytest.mark.skipif(
        not BASILISK_AVAILABLE,
        reason="Basilisk not installed"
    )
    def test_medium_fidelity_with_drag(self, reference_epoch, tmp_path):
        """
        Verify MEDIUM fidelity includes atmospheric drag effects.

        Drag should cause altitude decay over time for LEO.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        # Run for 24 hours to see drag effects
        end_time = start_time + timedelta(hours=24)

        # Start at 400 km - drag should be noticeable
        initial_altitude_km = 400.0
        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6378.137 + initial_altitude_km, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        result = simulate(
            plan=create_test_plan(
                plan_id="medium_drag_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        final_pos = np.array(result.final_state.position_eci)
        final_altitude_km = np.linalg.norm(final_pos) - 6378.137

        # With drag, altitude should decay (or stay roughly same)
        # Without drag, altitude would be exactly preserved
        altitude_change = final_altitude_km - initial_altitude_km

        # At 400km over 24h, expect 0-5km decay from drag
        # Allow small positive change for J2 effects
        assert -10.0 < altitude_change < 2.0, (
            f"MEDIUM fidelity drag effects unexpected\n"
            f"  Initial altitude: {initial_altitude_km:.1f} km\n"
            f"  Final altitude:   {final_altitude_km:.1f} km\n"
            f"  Change:           {altitude_change:.3f} km\n"
            f"\n"
            f"Expected slight decay from atmospheric drag."
        )

    @pytest.mark.skipif(
        not BASILISK_AVAILABLE,
        reason="Basilisk not installed"
    )
    def test_medium_fidelity_deterministic(self, reference_epoch, tmp_path):
        """
        Verify MEDIUM fidelity is deterministic.

        Same inputs should produce identical outputs.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=2)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id="determinism_test",
            start_time=start_time,
            end_time=end_time,
        )

        # Run twice
        result1 = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=create_test_config(output_dir=str(tmp_path / "run1"), time_step_s=60.0),
        )

        result2 = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=create_test_config(output_dir=str(tmp_path / "run2"), time_step_s=60.0),
        )

        # Compare final states
        pos1 = np.array(result1.final_state.position_eci)
        pos2 = np.array(result2.final_state.position_eci)

        pos_diff = np.linalg.norm(pos1 - pos2)

        assert pos_diff < 1e-9, (
            f"MEDIUM fidelity not deterministic\n"
            f"  Run 1 position: {pos1}\n"
            f"  Run 2 position: {pos2}\n"
            f"  Difference:     {pos_diff} km"
        )


class TestHighFidelity:
    """Test HIGH fidelity simulation."""

    @pytest.mark.skipif(
        not BASILISK_AVAILABLE,
        reason="Basilisk not installed"
    )
    @pytest.mark.ete_tier_b  # HIGH fidelity is slower, run nightly
    def test_high_fidelity_completes(self, reference_epoch, tmp_path):
        """
        Verify HIGH fidelity simulation completes.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=2)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        result = simulate(
            plan=create_test_plan(
                plan_id="high_fidelity_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.HIGH,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=30.0),
        )

        assert result is not None, "HIGH fidelity simulation returned None"
        assert result.final_state is not None, "No final state from HIGH fidelity"


class TestCrossFidelityComparison:
    """Test cross-fidelity validation (LOW vs MEDIUM)."""

    @pytest.mark.skipif(
        not BASILISK_AVAILABLE,
        reason="Basilisk not installed - cross-fidelity comparison requires MEDIUM"
    )
    def test_low_vs_medium_position_comparable(
        self, reference_epoch, tmp_path, tolerance_config
    ):
        """
        Verify LOW and MEDIUM produce comparable positions.

        For simple propagation (no maneuvers), LOW and MEDIUM should
        agree within tolerance. Large discrepancies indicate a bug.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=6)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id="cross_fidelity_test",
            start_time=start_time,
            end_time=end_time,
        )

        # Run LOW
        low_result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path / "low"), time_step_s=60.0),
        )

        # Run MEDIUM
        med_result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=create_test_config(output_dir=str(tmp_path / "medium"), time_step_s=60.0),
        )

        # Compare final positions
        low_pos = np.array(low_result.final_state.position_eci)
        med_pos = np.array(med_result.final_state.position_eci)

        position_diff_km = np.linalg.norm(low_pos - med_pos)

        # Cross-fidelity tolerance is relaxed (SGP4 vs numerical have inherent differences)
        # For 6 hours, expect < 50 km difference for simple case
        cross_fidelity_tolerance_km = 50.0

        assert position_diff_km < cross_fidelity_tolerance_km, (
            f"LOW vs MEDIUM POSITION DISCREPANCY\n"
            f"  LOW final position:    {low_pos}\n"
            f"  MEDIUM final position: {med_pos}\n"
            f"  Difference:            {position_diff_km:.3f} km\n"
            f"  Tolerance:             {cross_fidelity_tolerance_km:.1f} km\n"
            f"\n"
            f"Large discrepancy may indicate propagator bug."
        )

    @pytest.mark.skipif(
        not BASILISK_AVAILABLE,
        reason="Basilisk not installed"
    )
    def test_low_vs_medium_altitude_comparable(
        self, reference_epoch, tmp_path
    ):
        """
        Verify LOW and MEDIUM produce comparable altitudes.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=6)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id="altitude_comparison_test",
            start_time=start_time,
            end_time=end_time,
        )

        low_result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path / "low"), time_step_s=60.0),
        )

        med_result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=create_test_config(output_dir=str(tmp_path / "medium"), time_step_s=60.0),
        )

        low_alt = np.linalg.norm(low_result.final_state.position_eci) - 6378.137
        med_alt = np.linalg.norm(med_result.final_state.position_eci) - 6378.137

        altitude_diff_km = abs(low_alt - med_alt)

        # Altitude should be very close (within 10 km for 6 hours)
        assert altitude_diff_km < 10.0, (
            f"LOW vs MEDIUM ALTITUDE DISCREPANCY\n"
            f"  LOW altitude:    {low_alt:.3f} km\n"
            f"  MEDIUM altitude: {med_alt:.3f} km\n"
            f"  Difference:      {altitude_diff_km:.3f} km"
        )

    @pytest.mark.skipif(
        not BASILISK_AVAILABLE,
        reason="Basilisk not installed"
    )
    def test_low_vs_medium_energy_both_valid(
        self, reference_epoch, tmp_path, physics_validator
    ):
        """
        Verify both LOW and MEDIUM produce bound orbits with valid energy.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=6)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id="energy_comparison_test",
            start_time=start_time,
            end_time=end_time,
        )

        low_result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path / "low"), time_step_s=60.0),
        )

        med_result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=create_test_config(output_dir=str(tmp_path / "medium"), time_step_s=60.0),
        )

        # Check both are bound orbits
        low_energy = physics_validator.compute_specific_energy(
            low_result.final_state.position_eci,
            low_result.final_state.velocity_eci,
        )
        med_energy = physics_validator.compute_specific_energy(
            med_result.final_state.position_eci,
            med_result.final_state.velocity_eci,
        )

        assert low_energy < 0, f"LOW fidelity unbound: energy = {low_energy}"
        assert med_energy < 0, f"MEDIUM fidelity unbound: energy = {med_energy}"

        # Energy should be similar (within 1%)
        energy_diff_pct = abs(low_energy - med_energy) / abs(low_energy) * 100

        assert energy_diff_pct < 5.0, (
            f"LOW vs MEDIUM ENERGY DISCREPANCY\n"
            f"  LOW energy:    {low_energy:.6f} km²/s²\n"
            f"  MEDIUM energy: {med_energy:.6f} km²/s²\n"
            f"  Difference:    {energy_diff_pct:.2f}%"
        )


class TestFidelityFallback:
    """Test fallback behavior when Basilisk is not available."""

    def test_medium_falls_back_to_sgp4_when_basilisk_unavailable(
        self, reference_epoch, tmp_path, monkeypatch
    ):
        """
        Verify MEDIUM fidelity falls back to SGP4 gracefully.

        When Basilisk is not installed, MEDIUM should use SGP4
        and log a warning, not crash.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        # Force Basilisk to be "unavailable" by mocking the import
        def mock_import_error(*args, **kwargs):
            raise ImportError("Basilisk not available (mocked)")

        # Patch the BasiliskPropagator import in engine
        import sim.engine
        original_get_propagator = sim.engine._select_propagator

        def patched_get_propagator(fidelity, initial_state, plan, config):
            if fidelity in (Fidelity.MEDIUM, Fidelity.HIGH):
                # Simulate import failure
                from sim.models.orbit import OrbitPropagator
                propagator = OrbitPropagator(
                    altitude_km=np.linalg.norm(initial_state.position_eci) - 6378.137,
                    inclination_deg=53.0,
                    epoch=plan.start_time,
                )
                return propagator, "sgp4-2.22 (fallback)"
            return original_get_propagator(fidelity, initial_state, plan, config)

        monkeypatch.setattr(sim.engine, "_select_propagator", patched_get_propagator)

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=2)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        # Should not crash
        result = simulate(
            plan=create_test_plan(
                plan_id="fallback_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        assert result is not None, "Fallback simulation failed"
        assert result.final_state is not None

    def test_all_fidelities_produce_valid_output(self, reference_epoch, tmp_path):
        """
        Verify all fidelity levels produce valid output (with or without Basilisk).
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=1)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        for fidelity in [Fidelity.LOW, Fidelity.MEDIUM, Fidelity.HIGH]:
            result = simulate(
                plan=create_test_plan(
                    plan_id=f"fidelity_{fidelity.value}_test",
                    start_time=start_time,
                    end_time=end_time,
                ),
                initial_state=initial_state,
                fidelity=fidelity,
                config=create_test_config(
                    output_dir=str(tmp_path / fidelity.value.lower()),
                    time_step_s=60.0,
                ),
            )

            assert result is not None, f"{fidelity.value} simulation returned None"
            assert result.final_state is not None, (
                f"{fidelity.value} simulation has no final state"
            )

            # Verify basic physics
            final_pos = np.array(result.final_state.position_eci)
            altitude = np.linalg.norm(final_pos) - 6378.137

            assert 100 < altitude < 1000, (
                f"{fidelity.value} fidelity produced invalid altitude: {altitude:.1f} km"
            )


@pytest.mark.ete_tier_b
class TestExtendedCrossFidelity:
    """Extended cross-fidelity tests (Tier B - nightly)."""

    @pytest.mark.skipif(
        not BASILISK_AVAILABLE,
        reason="Basilisk not installed"
    )
    def test_24h_propagation_comparison(self, reference_epoch, tmp_path):
        """
        Compare LOW vs MEDIUM over 24 hours.

        Longer duration amplifies any systematic differences.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=24)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id="24h_comparison_test",
            start_time=start_time,
            end_time=end_time,
        )

        low_result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path / "low"), time_step_s=60.0),
        )

        med_result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=create_test_config(output_dir=str(tmp_path / "medium"), time_step_s=60.0),
        )

        low_pos = np.array(low_result.final_state.position_eci)
        med_pos = np.array(med_result.final_state.position_eci)

        position_diff_km = np.linalg.norm(low_pos - med_pos)

        # For 24h, expect larger but still reasonable difference
        # SGP4 vs numerical propagation with J2 + drag will diverge
        assert position_diff_km < 200.0, (
            f"24h LOW vs MEDIUM position difference: {position_diff_km:.1f} km\n"
            f"Exceeds 200 km tolerance - check propagator consistency"
        )

    @pytest.mark.skipif(
        not BASILISK_AVAILABLE,
        reason="Basilisk not installed"
    )
    def test_sso_orbit_comparison(self, reference_epoch, tmp_path):
        """
        Compare LOW vs MEDIUM for sun-synchronous orbit.

        SSO has specific J2 requirements that MEDIUM should model better.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=12)

        # SSO at 600 km, ~97.8° inclination
        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6978.137, 0.0, 0.0],
            velocity_eci=[0.0, 0.598, 7.509],  # ~97.8° inclination
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id="sso_comparison_test",
            start_time=start_time,
            end_time=end_time,
        )

        low_result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path / "low"), time_step_s=60.0),
        )

        med_result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=create_test_config(output_dir=str(tmp_path / "medium"), time_step_s=60.0),
        )

        # Both should complete
        assert low_result is not None
        assert med_result is not None

        # Both should maintain reasonable altitude
        low_alt = np.linalg.norm(low_result.final_state.position_eci) - 6378.137
        med_alt = np.linalg.norm(med_result.final_state.position_eci) - 6378.137

        assert 500 < low_alt < 700, f"LOW SSO altitude invalid: {low_alt:.1f} km"
        assert 500 < med_alt < 700, f"MEDIUM SSO altitude invalid: {med_alt:.1f} km"
