"""Integration tests for spacecraft simulator."""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from sim.core.types import (
    Activity,
    Fidelity,
    InitialState,
    PlanInput,
    SimConfig,
    SpacecraftConfig,
)
from sim.core.config import create_sim_config
from sim.engine import simulate
from sim.models.orbit import OrbitPropagator


class TestOrbitLoweringIntegration:
    """Integration tests for orbit lowering scenario."""

    @pytest.fixture
    def orbit_lowering_setup(self):
        """Set up orbit lowering scenario."""
        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

        # Create propagator
        propagator = OrbitPropagator(
            altitude_km=500.0,
            inclination_deg=53.0,
            epoch=epoch,
        )
        point = propagator.propagate(epoch)

        # Initial state
        initial_state = InitialState(
            epoch=epoch,
            position_eci=point.position_eci,
            velocity_eci=point.velocity_eci,
            mass_kg=500.0,
            propellant_kg=50.0,
            battery_soc=1.0,
        )

        # Plan with orbit lowering activity
        activities = [
            Activity(
                activity_id="ol_001",
                activity_type="orbit_lower",
                start_time=epoch,
                end_time=epoch + timedelta(hours=6),
                parameters={
                    "target_altitude_km": 400.0,
                    "thrust_n": 0.1,
                    "isp_s": 1500.0,
                    "power_w": 1500.0,
                    "thrusts_per_orbit": 2,
                    "thrust_arc_deg": 30.0,
                },
            )
        ]

        plan = PlanInput(
            spacecraft_id="TEST-001",
            plan_id="test_orbit_lower",
            activities=activities,
        )

        # Config
        spacecraft_config = SpacecraftConfig(
            spacecraft_id="TEST-001",
            dry_mass_kg=450.0,
            initial_propellant_kg=50.0,
            battery_capacity_wh=5000.0,
        )

        sim_config = create_sim_config(
            spacecraft_config=spacecraft_config,
            fidelity="LOW",
            time_step_s=60.0,
            output_dir="runs",
        )

        return {
            "initial_state": initial_state,
            "plan": plan,
            "config": sim_config,
        }

    def test_orbit_lowering_runs(self, orbit_lowering_setup):
        """Test that orbit lowering simulation runs without error."""
        results = simulate(
            plan=orbit_lowering_setup["plan"],
            initial_state=orbit_lowering_setup["initial_state"],
            fidelity=Fidelity.LOW,
            config=orbit_lowering_setup["config"],
        )

        assert results is not None
        assert "run_id" in results.artifacts

    def test_orbit_lowering_uses_propellant(self, orbit_lowering_setup):
        """Test that propellant is consumed."""
        results = simulate(
            plan=orbit_lowering_setup["plan"],
            initial_state=orbit_lowering_setup["initial_state"],
            fidelity=Fidelity.LOW,
            config=orbit_lowering_setup["config"],
        )

        initial_propellant = orbit_lowering_setup["initial_state"].propellant_kg
        final_propellant = results.final_state.propellant_kg

        # Should have used some propellant
        assert final_propellant < initial_propellant
        # But not all of it
        assert final_propellant > 0

    def test_orbit_lowering_soc_constraint(self, orbit_lowering_setup):
        """Test that SOC stays in valid range."""
        results = simulate(
            plan=orbit_lowering_setup["plan"],
            initial_state=orbit_lowering_setup["initial_state"],
            fidelity=Fidelity.LOW,
            config=orbit_lowering_setup["config"],
        )

        # Final SOC should be in [0, 1]
        assert 0 <= results.final_state.battery_soc <= 1


class TestEOImagingIntegration:
    """Integration tests for EO imaging scenario."""

    @pytest.fixture
    def eo_imaging_setup(self):
        """Set up EO imaging scenario."""
        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

        # Create propagator
        propagator = OrbitPropagator(
            altitude_km=500.0,
            inclination_deg=53.0,
            epoch=epoch,
        )
        point = propagator.propagate(epoch)

        # Initial state
        initial_state = InitialState(
            epoch=epoch,
            position_eci=point.position_eci,
            velocity_eci=point.velocity_eci,
            mass_kg=500.0,
            propellant_kg=50.0,
            battery_soc=1.0,
            storage_used_gb=0.0,
        )

        # Plan with EO collect activity
        activities = [
            Activity(
                activity_id="eo_001",
                activity_type="eo_collect",
                start_time=epoch,
                end_time=epoch + timedelta(minutes=30),
                parameters={
                    "target_id": "target_1",
                    "target_lat_deg": 40.0,
                    "target_lon_deg": -74.0,
                    "max_cross_track_deg": 30.0,
                    "max_along_track_deg": 5.0,
                    "num_frames": 2,
                    "sensor_power_w": 100.0,
                },
            )
        ]

        plan = PlanInput(
            spacecraft_id="TEST-001",
            plan_id="test_eo_imaging",
            activities=activities,
        )

        # Config
        spacecraft_config = SpacecraftConfig(
            spacecraft_id="TEST-001",
            dry_mass_kg=450.0,
            initial_propellant_kg=50.0,
            battery_capacity_wh=5000.0,
            storage_capacity_gb=500.0,
        )

        sim_config = create_sim_config(
            spacecraft_config=spacecraft_config,
            fidelity="LOW",
            time_step_s=60.0,
            output_dir="runs",
        )

        return {
            "initial_state": initial_state,
            "plan": plan,
            "config": sim_config,
        }

    def test_eo_imaging_runs(self, eo_imaging_setup):
        """Test that EO imaging simulation runs without error."""
        results = simulate(
            plan=eo_imaging_setup["plan"],
            initial_state=eo_imaging_setup["initial_state"],
            fidelity=Fidelity.LOW,
            config=eo_imaging_setup["config"],
        )

        assert results is not None
        assert "run_id" in results.artifacts

    def test_storage_constraint(self, eo_imaging_setup):
        """Test that storage stays in valid range."""
        results = simulate(
            plan=eo_imaging_setup["plan"],
            initial_state=eo_imaging_setup["initial_state"],
            fidelity=Fidelity.LOW,
            config=eo_imaging_setup["config"],
        )

        # Storage should be >= 0 and <= capacity
        assert results.final_state.storage_used_gb >= 0
        assert results.final_state.storage_used_gb <= 500.0


class TestConstraintValidation:
    """Test constraint validation during simulation."""

    def test_soc_never_negative(self):
        """Test that SOC is never negative."""
        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

        propagator = OrbitPropagator(altitude_km=500.0, inclination_deg=53.0, epoch=epoch)
        point = propagator.propagate(epoch)

        # Start with low SOC
        initial_state = InitialState(
            epoch=epoch,
            position_eci=point.position_eci,
            velocity_eci=point.velocity_eci,
            mass_kg=500.0,
            propellant_kg=50.0,
            battery_soc=0.2,  # Low starting SOC
        )

        activities = [
            Activity(
                activity_id="ol_001",
                activity_type="orbit_lower",
                start_time=epoch,
                end_time=epoch + timedelta(hours=12),  # Long duration
                parameters={
                    "target_altitude_km": 400.0,
                    "thrust_n": 0.1,
                    "power_w": 1500.0,
                },
            )
        ]

        plan = PlanInput(
            spacecraft_id="TEST-001",
            plan_id="test_low_soc",
            activities=activities,
        )

        spacecraft_config = SpacecraftConfig(spacecraft_id="TEST-001")
        sim_config = create_sim_config(
            spacecraft_config=spacecraft_config,
            fidelity="LOW",
        )

        results = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=sim_config,
        )

        # SOC should never go below 0
        assert results.final_state.battery_soc >= 0

    def test_propellant_never_negative(self):
        """Test that propellant is never negative."""
        epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

        propagator = OrbitPropagator(altitude_km=500.0, inclination_deg=53.0, epoch=epoch)
        point = propagator.propagate(epoch)

        # Start with minimal propellant
        initial_state = InitialState(
            epoch=epoch,
            position_eci=point.position_eci,
            velocity_eci=point.velocity_eci,
            mass_kg=500.0,
            propellant_kg=0.5,  # Very little propellant
            battery_soc=1.0,
        )

        activities = [
            Activity(
                activity_id="ol_001",
                activity_type="orbit_lower",
                start_time=epoch,
                end_time=epoch + timedelta(hours=6),
                parameters={
                    "target_altitude_km": 300.0,  # Large altitude change
                },
            )
        ]

        plan = PlanInput(
            spacecraft_id="TEST-001",
            plan_id="test_low_propellant",
            activities=activities,
        )

        spacecraft_config = SpacecraftConfig(spacecraft_id="TEST-001")
        sim_config = create_sim_config(
            spacecraft_config=spacecraft_config,
            fidelity="LOW",
        )

        results = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=sim_config,
        )

        # Propellant should never go below 0
        assert results.final_state.propellant_kg >= 0
