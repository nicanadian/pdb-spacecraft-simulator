#!/usr/bin/env python
"""Run example simulations demonstrating spacecraft simulator capabilities."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from sim.core.types import (
    Activity,
    Fidelity,
    InitialState,
    PlanInput,
    SimConfig,
    SpacecraftConfig,
)
from sim.core.config import create_sim_config, setup_logging
from sim.engine import simulate
from sim.models.orbit import OrbitPropagator, compute_lowering_delta_v, orbital_period
from sim.models.imaging import EOSensorConfig, FrameSensor


def run_orbit_lowering_example():
    """Run orbit lowering scenario: 500 km to 400 km."""
    print("\n" + "=" * 60)
    print("ORBIT LOWERING EXAMPLE")
    print("500 km -> 400 km using electric propulsion")
    print("=" * 60)

    # Calculate expected delta-V
    dv = compute_lowering_delta_v(500.0, 400.0)
    print(f"\nExpected delta-V: {dv*1000:.1f} m/s")
    print(f"Orbital period at 500 km: {orbital_period(500.0)/60:.1f} min")
    print(f"Orbital period at 400 km: {orbital_period(400.0)/60:.1f} min")

    # Set up simulation
    epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

    # Create initial state
    propagator = OrbitPropagator(
        altitude_km=500.0,
        inclination_deg=53.0,
        epoch=epoch,
    )
    point = propagator.propagate(epoch)

    initial_state = InitialState(
        epoch=epoch,
        position_eci=point.position_eci,
        velocity_eci=point.velocity_eci,
        mass_kg=500.0,
        propellant_kg=50.0,
        battery_soc=1.0,
    )

    # Create plan
    activities = [
        Activity(
            activity_id="ol_001",
            activity_type="orbit_lower",
            start_time=epoch,
            end_time=datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
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
        spacecraft_id="LEO-SAT-001",
        plan_id="orbit_lowering_demo",
        activities=activities,
    )

    # Create config
    spacecraft_config = SpacecraftConfig(
        spacecraft_id="LEO-SAT-001",
        dry_mass_kg=450.0,
        initial_propellant_kg=50.0,
        battery_capacity_wh=5000.0,
        solar_panel_area_m2=10.0,
        solar_efficiency=0.30,
        base_power_w=200.0,
    )

    sim_config = create_sim_config(
        spacecraft_config=spacecraft_config,
        fidelity="LOW",
        time_step_s=60.0,
        output_dir="runs",
    )

    # Run simulation
    print("\nRunning simulation...")
    results = simulate(
        plan=plan,
        initial_state=initial_state,
        fidelity=Fidelity.LOW,
        config=sim_config,
    )

    # Print results
    print("\n--- Results ---")
    print(f"Run directory: {results.artifacts.get('run_dir', 'N/A')}")
    print(f"Activities successful: {results.summary['activities']['successful']}/{results.summary['activities']['total']}")
    print(f"Violations: {results.summary['events']['violations']}")
    print(f"Propellant used: {results.summary['state_changes']['propellant_used_kg']:.2f} kg")
    print(f"Final SOC: {results.summary['state_changes']['final_soc']:.1%}")

    if "orbit" in results.summary:
        print(f"Altitude change: {results.summary['orbit']['altitude_change_km']:.2f} km")

    return results


def run_eo_imaging_example():
    """Run EO imaging scenario with point targets."""
    print("\n" + "=" * 60)
    print("EO IMAGING EXAMPLE")
    print("Cross-track imaging of point targets")
    print("=" * 60)

    # Compute sensor geometry
    sensor_config = EOSensorConfig(
        focal_length_mm=1000.0,
        pixel_size_um=10.0,
        detector_rows=4096,
        detector_cols=4096,
    )
    sensor = FrameSensor(sensor_config)

    print(f"\nSensor at 500 km:")
    print(f"  GSD: {sensor.compute_gsd(500.0):.2f} m")
    print(f"  Swath: {sensor.compute_swath(500.0):.2f} km")
    print(f"  Frame size: {sensor.compute_frame_data_mb():.1f} MB")

    # Set up simulation
    epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

    # Create initial state
    propagator = OrbitPropagator(
        altitude_km=500.0,
        inclination_deg=53.0,
        epoch=epoch,
    )
    point = propagator.propagate(epoch)

    initial_state = InitialState(
        epoch=epoch,
        position_eci=point.position_eci,
        velocity_eci=point.velocity_eci,
        mass_kg=500.0,
        propellant_kg=50.0,
        battery_soc=1.0,
        storage_used_gb=0.0,
    )

    # Define targets
    targets = [
        ("target_1", 40.7128, -74.0060, "New York"),
        ("target_2", 51.5074, -0.1278, "London"),
        ("target_3", 35.6762, 139.6503, "Tokyo"),
        ("target_4", -33.8688, 151.2093, "Sydney"),
        ("target_5", 48.8566, 2.3522, "Paris"),
    ]

    print("\nTargets:")
    for tid, lat, lon, name in targets:
        print(f"  {name}: ({lat:.2f}, {lon:.2f})")

    # Create activities
    activities = []
    for i, (tid, lat, lon, name) in enumerate(targets):
        start = datetime(2025, 1, 15, i, 0, 0, tzinfo=timezone.utc)
        end = datetime(2025, 1, 15, i, 30, 0, tzinfo=timezone.utc)
        activities.append(Activity(
            activity_id=f"eo_{i+1:03d}",
            activity_type="eo_collect",
            start_time=start,
            end_time=end,
            parameters={
                "target_id": tid,
                "target_lat_deg": lat,
                "target_lon_deg": lon,
                "priority": 1,
                "max_cross_track_deg": 30.0,
                "max_along_track_deg": 5.0,
                "num_frames": 2,
                "sensor_power_w": 100.0,
            },
        ))

    plan = PlanInput(
        spacecraft_id="LEO-SAT-001",
        plan_id="eo_imaging_demo",
        activities=activities,
    )

    # Create config
    spacecraft_config = SpacecraftConfig(
        spacecraft_id="LEO-SAT-001",
        dry_mass_kg=450.0,
        initial_propellant_kg=50.0,
        battery_capacity_wh=5000.0,
        storage_capacity_gb=500.0,
        solar_panel_area_m2=10.0,
        solar_efficiency=0.30,
        base_power_w=200.0,
    )

    sim_config = create_sim_config(
        spacecraft_config=spacecraft_config,
        fidelity="LOW",
        time_step_s=60.0,
        output_dir="runs",
    )

    # Run simulation
    print("\nRunning simulation...")
    results = simulate(
        plan=plan,
        initial_state=initial_state,
        fidelity=Fidelity.LOW,
        config=sim_config,
    )

    # Print results
    print("\n--- Results ---")
    print(f"Run directory: {results.artifacts.get('run_dir', 'N/A')}")
    print(f"Activities successful: {results.summary['activities']['successful']}/{results.summary['activities']['total']}")
    print(f"Violations: {results.summary['events']['violations']}")
    print(f"Final SOC: {results.summary['state_changes']['final_soc']:.1%}")
    print(f"Storage used: {results.summary['state_changes']['final_storage_gb']:.2f} GB")

    # Count collected frames
    frame_count = sum(
        len(artifacts.get("frames", []))
        for aid, artifacts in results.artifacts.items()
        if isinstance(artifacts, dict) and "frames" in artifacts
    )
    print(f"Total frames collected: {frame_count}")

    return results


def main():
    """Run all examples."""
    setup_logging(logging.INFO)

    print("\n" + "=" * 60)
    print("SPACECRAFT SIMULATOR EXAMPLES")
    print("=" * 60)

    # Run orbit lowering example
    orbit_results = run_orbit_lowering_example()

    # Run EO imaging example
    imaging_results = run_eo_imaging_example()

    print("\n" + "=" * 60)
    print("ALL EXAMPLES COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
