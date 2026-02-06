"""ETE numerical stability tests for long-duration simulations.

Tests numerical stability and error accumulation over extended time periods:
- Week-long propagations
- Month-long propagations (Tier B)
- Energy drift validation
- Angular momentum conservation
- Altitude corridor maintenance

Usage:
    pytest tests/ete/test_numerical_stability.py -v
    pytest tests/ete/ -m "ete_tier_b" -v
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional

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
    pytest.mark.ete_tier_b,
    pytest.mark.ete,
]


# Earth gravitational parameter
MU_EARTH = 398600.4418  # km^3/s^2
EARTH_RADIUS = 6378.137  # km


def compute_orbital_energy(position_km, velocity_km_s) -> float:
    """Compute specific orbital energy (km^2/s^2)."""
    r = np.linalg.norm(position_km)
    v = np.linalg.norm(velocity_km_s)
    return v**2 / 2 - MU_EARTH / r


def compute_angular_momentum(position_km, velocity_km_s) -> np.ndarray:
    """Compute specific angular momentum vector (km^2/s)."""
    return np.cross(position_km, velocity_km_s)


def compute_sma(position_km, velocity_km_s) -> float:
    """Compute semi-major axis (km)."""
    energy = compute_orbital_energy(position_km, velocity_km_s)
    if abs(energy) < 1e-10:
        return float('inf')
    return -MU_EARTH / (2 * energy)


class TestWeekLongPropagation:
    """Test numerical stability over 1-week propagation."""

    def test_week_propagation_completes(self, reference_epoch, tmp_path):
        """
        Verify 1-week propagation completes successfully.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(days=7)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id="week_propagation",
            start_time=start_time,
            end_time=end_time,
        )

        # Use larger timestep for long-duration
        config = create_test_config(
            output_dir=str(tmp_path),
            time_step_s=120.0,  # 2 minute steps
        )

        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )

        assert result is not None, "Week propagation failed"
        assert result.final_state is not None, "No final state from week propagation"

    def test_week_energy_conservation(self, reference_epoch, tmp_path):
        """
        Verify energy conservation over 1-week propagation.

        For a pure propagation (no maneuvers), energy should be conserved
        within tolerance accounting for numerical drift.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(days=7)

        initial_pos = np.array([6778.137, 0.0, 0.0])
        initial_vel = np.array([0.0, 7.6686, 0.0])

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=initial_pos.tolist(),
            velocity_eci=initial_vel.tolist(),
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id="week_energy",
            start_time=start_time,
            end_time=end_time,
        )

        config = create_test_config(
            output_dir=str(tmp_path),
            time_step_s=120.0,
        )

        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )

        assert result is not None

        # Compute energy drift
        initial_energy = compute_orbital_energy(initial_pos, initial_vel)
        final_pos = np.array(result.final_state.position_eci)
        final_vel = np.array(result.final_state.velocity_eci)
        final_energy = compute_orbital_energy(final_pos, final_vel)

        energy_drift_pct = abs(final_energy - initial_energy) / abs(initial_energy) * 100

        # Allow 1% energy drift over a week (SGP4 uses mean elements)
        assert energy_drift_pct < 1.0, (
            f"Energy drift too large over 1 week: {energy_drift_pct:.3f}%\n"
            f"  Initial energy: {initial_energy:.6f} km²/s²\n"
            f"  Final energy:   {final_energy:.6f} km²/s²"
        )

    def test_week_orbit_remains_bound(self, reference_epoch, tmp_path):
        """
        Verify orbit remains bound after 1 week.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(days=7)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id="week_bound",
            start_time=start_time,
            end_time=end_time,
        )

        config = create_test_config(
            output_dir=str(tmp_path),
            time_step_s=120.0,
        )

        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )

        assert result is not None

        final_pos = np.array(result.final_state.position_eci)
        final_vel = np.array(result.final_state.velocity_eci)
        final_energy = compute_orbital_energy(final_pos, final_vel)

        assert final_energy < 0, (
            f"Orbit became unbound after 1 week: energy = {final_energy:.6f} km²/s²"
        )

    def test_week_altitude_reasonable(self, reference_epoch, tmp_path):
        """
        Verify altitude remains in reasonable range after 1 week.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(days=7)

        initial_altitude_km = 400.0
        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[EARTH_RADIUS + initial_altitude_km, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id="week_altitude",
            start_time=start_time,
            end_time=end_time,
        )

        config = create_test_config(
            output_dir=str(tmp_path),
            time_step_s=120.0,
        )

        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )

        assert result is not None

        final_pos = np.array(result.final_state.position_eci)
        final_altitude_km = np.linalg.norm(final_pos) - EARTH_RADIUS

        # Altitude should stay within 100km of initial for pure propagation
        # (without drag, should be nearly constant; with drag, slight decay)
        altitude_change = abs(final_altitude_km - initial_altitude_km)
        assert altitude_change < 100.0, (
            f"Altitude change too large over 1 week: {altitude_change:.1f} km\n"
            f"  Initial: {initial_altitude_km:.1f} km\n"
            f"  Final:   {final_altitude_km:.1f} km"
        )


class TestMonthLongPropagation:
    """Test numerical stability over 1-month propagation."""

    @pytest.mark.slow
    def test_month_propagation_completes(self, reference_epoch, tmp_path):
        """
        Verify 1-month propagation completes successfully.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(days=30)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id="month_propagation",
            start_time=start_time,
            end_time=end_time,
        )

        # Use larger timestep for very long duration
        config = create_test_config(
            output_dir=str(tmp_path),
            time_step_s=300.0,  # 5 minute steps
        )

        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )

        assert result is not None, "Month propagation failed"
        assert result.final_state is not None

    @pytest.mark.slow
    def test_month_energy_conservation(self, reference_epoch, tmp_path):
        """
        Verify energy conservation over 1-month propagation.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(days=30)

        initial_pos = np.array([6778.137, 0.0, 0.0])
        initial_vel = np.array([0.0, 7.6686, 0.0])

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=initial_pos.tolist(),
            velocity_eci=initial_vel.tolist(),
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id="month_energy",
            start_time=start_time,
            end_time=end_time,
        )

        config = create_test_config(
            output_dir=str(tmp_path),
            time_step_s=300.0,
        )

        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )

        assert result is not None

        initial_energy = compute_orbital_energy(initial_pos, initial_vel)
        final_pos = np.array(result.final_state.position_eci)
        final_vel = np.array(result.final_state.velocity_eci)
        final_energy = compute_orbital_energy(final_pos, final_vel)

        energy_drift_pct = abs(final_energy - initial_energy) / abs(initial_energy) * 100

        # Allow 5% energy drift over a month (longer duration = more drift)
        assert energy_drift_pct < 5.0, (
            f"Energy drift too large over 1 month: {energy_drift_pct:.3f}%"
        )


class TestAngularMomentumConservation:
    """Test angular momentum conservation."""

    def test_angular_momentum_week(self, reference_epoch, tmp_path):
        """
        Verify angular momentum magnitude conservation over 1 week.

        Note: The angular momentum VECTOR may change direction due to orbital
        precession (J2 effect), but the MAGNITUDE should be conserved.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(days=7)

        initial_pos = np.array([6778.137, 0.0, 0.0])
        initial_vel = np.array([0.0, 7.6686, 0.0])

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=initial_pos.tolist(),
            velocity_eci=initial_vel.tolist(),
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id="momentum_test",
            start_time=start_time,
            end_time=end_time,
        )

        config = create_test_config(
            output_dir=str(tmp_path),
            time_step_s=120.0,
        )

        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )

        assert result is not None

        initial_h = compute_angular_momentum(initial_pos, initial_vel)
        final_pos = np.array(result.final_state.position_eci)
        final_vel = np.array(result.final_state.velocity_eci)
        final_h = compute_angular_momentum(final_pos, final_vel)

        # Compare MAGNITUDES (direction can precess due to J2)
        initial_h_mag = np.linalg.norm(initial_h)
        final_h_mag = np.linalg.norm(final_h)
        h_drift_pct = abs(final_h_mag - initial_h_mag) / initial_h_mag * 100

        # Allow 1% angular momentum magnitude drift
        assert h_drift_pct < 1.0, (
            f"Angular momentum magnitude drift too large: {h_drift_pct:.3f}%\n"
            f"  Initial |h|: {initial_h_mag:.3f} km²/s\n"
            f"  Final |h|:   {final_h_mag:.3f} km²/s"
        )


class TestSMAStability:
    """Test semi-major axis stability over time."""

    def test_sma_week_stability(self, reference_epoch, tmp_path):
        """
        Verify semi-major axis stability over 1 week.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(days=7)

        initial_pos = np.array([6778.137, 0.0, 0.0])
        initial_vel = np.array([0.0, 7.6686, 0.0])

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=initial_pos.tolist(),
            velocity_eci=initial_vel.tolist(),
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id="sma_stability",
            start_time=start_time,
            end_time=end_time,
        )

        config = create_test_config(
            output_dir=str(tmp_path),
            time_step_s=120.0,
        )

        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )

        assert result is not None

        initial_sma = compute_sma(initial_pos, initial_vel)
        final_pos = np.array(result.final_state.position_eci)
        final_vel = np.array(result.final_state.velocity_eci)
        final_sma = compute_sma(final_pos, final_vel)

        sma_drift_km = abs(final_sma - initial_sma)

        # SMA should be stable within 10 km
        assert sma_drift_km < 10.0, (
            f"SMA drift too large: {sma_drift_km:.3f} km\n"
            f"  Initial SMA: {initial_sma:.3f} km\n"
            f"  Final SMA:   {final_sma:.3f} km"
        )


class TestOrbitRegimeStability:
    """Test stability for different orbit regimes."""

    @pytest.mark.parametrize("altitude_km,inclination_deg,name", [
        (400.0, 53.0, "LEO_ISS"),
        (300.0, 53.0, "VLEO"),
        (600.0, 97.8, "SSO"),
        (500.0, 45.0, "LEO_45deg"),
    ])
    def test_orbit_regime_week_stability(
        self, reference_epoch, tmp_path, altitude_km, inclination_deg, name
    ):
        """
        Verify various orbit regimes remain stable over 1 week.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(days=7)

        # Compute velocity for circular orbit
        r = EARTH_RADIUS + altitude_km
        v_circ = np.sqrt(MU_EARTH / r)

        # Apply inclination (simplified - velocity in y-z plane)
        inc_rad = np.radians(inclination_deg)
        vy = v_circ * np.cos(inc_rad)
        vz = v_circ * np.sin(inc_rad)

        initial_pos = [r, 0.0, 0.0]
        initial_vel = [0.0, vy, vz]

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=initial_pos,
            velocity_eci=initial_vel,
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id=f"regime_{name}",
            start_time=start_time,
            end_time=end_time,
        )

        config = create_test_config(
            output_dir=str(tmp_path / name),
            time_step_s=120.0,
        )

        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )

        assert result is not None, f"{name} propagation failed"

        # Verify orbit remains bound
        final_pos = np.array(result.final_state.position_eci)
        final_vel = np.array(result.final_state.velocity_eci)
        final_energy = compute_orbital_energy(final_pos, final_vel)

        assert final_energy < 0, (
            f"{name} orbit became unbound: energy = {final_energy:.6f}"
        )

        # Verify altitude reasonable
        final_alt = np.linalg.norm(final_pos) - EARTH_RADIUS
        alt_change = abs(final_alt - altitude_km)

        # Allow 100km altitude change (accounts for eccentricity oscillation)
        assert alt_change < 100.0, (
            f"{name} altitude change too large: {alt_change:.1f} km"
        )


class TestTimestepSensitivity:
    """Test numerical stability across different timesteps."""

    @pytest.mark.parametrize("timestep_s", [30.0, 60.0, 120.0, 300.0])
    def test_timestep_energy_stability(self, reference_epoch, tmp_path, timestep_s):
        """
        Verify energy conservation is maintained across timesteps.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(days=1)  # 1 day

        initial_pos = np.array([6778.137, 0.0, 0.0])
        initial_vel = np.array([0.0, 7.6686, 0.0])

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=initial_pos.tolist(),
            velocity_eci=initial_vel.tolist(),
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id=f"timestep_{int(timestep_s)}s",
            start_time=start_time,
            end_time=end_time,
        )

        config = create_test_config(
            output_dir=str(tmp_path / f"{int(timestep_s)}s"),
            time_step_s=timestep_s,
        )

        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )

        assert result is not None

        initial_energy = compute_orbital_energy(initial_pos, initial_vel)
        final_pos = np.array(result.final_state.position_eci)
        final_vel = np.array(result.final_state.velocity_eci)
        final_energy = compute_orbital_energy(final_pos, final_vel)

        energy_drift_pct = abs(final_energy - initial_energy) / abs(initial_energy) * 100

        # All timesteps should maintain energy within 0.5% for 1 day
        assert energy_drift_pct < 0.5, (
            f"Energy drift at {timestep_s}s timestep: {energy_drift_pct:.4f}%"
        )


class TestMEDIUMFidelityStability:
    """Test numerical stability for MEDIUM fidelity (J2 or Basilisk)."""

    def test_medium_week_stability(self, reference_epoch, tmp_path):
        """
        Verify MEDIUM fidelity week-long propagation is stable.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(days=7)

        initial_pos = np.array([6778.137, 0.0, 0.0])
        initial_vel = np.array([0.0, 7.6686, 0.0])

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=initial_pos.tolist(),
            velocity_eci=initial_vel.tolist(),
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id="medium_week",
            start_time=start_time,
            end_time=end_time,
        )

        config = create_test_config(
            output_dir=str(tmp_path),
            time_step_s=120.0,
        )

        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=config,
        )

        assert result is not None

        # Verify bound orbit
        final_pos = np.array(result.final_state.position_eci)
        final_vel = np.array(result.final_state.velocity_eci)
        final_energy = compute_orbital_energy(final_pos, final_vel)

        assert final_energy < 0, "MEDIUM fidelity orbit became unbound"

        # Verify energy conservation
        initial_energy = compute_orbital_energy(initial_pos, initial_vel)
        energy_drift_pct = abs(final_energy - initial_energy) / abs(initial_energy) * 100

        # MEDIUM (with J2) may have slightly more drift due to J2 effects
        assert energy_drift_pct < 2.0, (
            f"MEDIUM energy drift: {energy_drift_pct:.3f}%"
        )
