"""CLI entrypoint for spacecraft simulator."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
import numpy as np
import yaml

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


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx, verbose):
    """Spacecraft mission simulator CLI."""
    ctx.ensure_object(dict)
    level = logging.DEBUG if verbose else logging.INFO
    setup_logging(level)


@cli.command()
@click.option("--plan", "-p", required=True, type=click.Path(exists=True), help="Plan file (JSON)")
@click.option("--config", "-c", type=click.Path(exists=True), help="Config file (YAML)")
@click.option("--tle", "-t", type=click.Path(exists=True), help="TLE file")
@click.option("--altitude", "-a", type=float, default=500.0, help="Initial altitude (km)")
@click.option("--inclination", "-i", type=float, default=53.0, help="Inclination (deg)")
@click.option("--fidelity", "-f", type=click.Choice(["LOW", "MEDIUM", "HIGH"]), default="LOW")
@click.option("--output", "-o", type=click.Path(), default="runs", help="Output directory")
def run(plan, config, tle, altitude, inclination, fidelity, output):
    """Run a simulation with given plan."""
    logger = logging.getLogger(__name__)

    # Load plan
    logger.info(f"Loading plan: {plan}")
    with open(plan) as f:
        plan_data = json.load(f)

    # Parse activities
    activities = []
    for act in plan_data.get("activities", []):
        activities.append(Activity(
            activity_id=act["activity_id"],
            activity_type=act["activity_type"],
            start_time=datetime.fromisoformat(act["start_time"]),
            end_time=datetime.fromisoformat(act["end_time"]),
            parameters=act.get("parameters", {}),
        ))

    plan_input = PlanInput(
        spacecraft_id=plan_data.get("spacecraft_id", "SC001"),
        plan_id=plan_data.get("plan_id", "plan_001"),
        activities=activities,
    )

    # Load or create config
    if config:
        with open(config) as f:
            config_data = yaml.safe_load(f)
        spacecraft_config = SpacecraftConfig(**config_data.get("spacecraft", {}))
    else:
        spacecraft_config = SpacecraftConfig(spacecraft_id=plan_input.spacecraft_id)

    sim_config = create_sim_config(
        spacecraft_config=spacecraft_config,
        fidelity=fidelity,
        output_dir=output,
    )

    # Create initial state
    epoch = plan_input.start_time
    if tle:
        # Load TLE and propagate to epoch
        with open(tle) as f:
            lines = f.readlines()
        tle_line1 = lines[0].strip() if len(lines) > 0 else ""
        tle_line2 = lines[1].strip() if len(lines) > 1 else ""

        from sim.models.orbit import tle_to_state
        position, velocity = tle_to_state(tle_line1, tle_line2, epoch)
    else:
        # Generate synthetic state from altitude/inclination
        from sim.models.orbit import OrbitPropagator
        prop = OrbitPropagator(
            altitude_km=altitude,
            inclination_deg=inclination,
            epoch=epoch,
        )
        point = prop.propagate(epoch)
        position = point.position_eci
        velocity = point.velocity_eci

    initial_state = InitialState(
        epoch=epoch,
        position_eci=position,
        velocity_eci=velocity,
        mass_kg=spacecraft_config.dry_mass_kg + spacecraft_config.initial_propellant_kg,
        propellant_kg=spacecraft_config.initial_propellant_kg,
    )

    # Run simulation
    logger.info("Starting simulation...")
    results = simulate(
        plan=plan_input,
        initial_state=initial_state,
        fidelity=Fidelity(fidelity),
        config=sim_config,
    )

    # Print summary
    click.echo("\n=== Simulation Complete ===")
    click.echo(f"Run directory: {results.artifacts.get('run_dir', 'N/A')}")
    click.echo(f"Activities: {results.summary['activities']['successful']}/{results.summary['activities']['total']} successful")
    click.echo(f"Violations: {results.summary['events']['violations']}")
    click.echo(f"Warnings: {results.summary['events']['warnings']}")

    if "orbit" in results.summary:
        click.echo(f"Altitude change: {results.summary['orbit']['altitude_change_km']:.2f} km")

    click.echo(f"Propellant used: {results.summary['state_changes']['propellant_used_kg']:.2f} kg")
    click.echo(f"Final SOC: {results.summary['state_changes']['final_soc']:.1%}")


@cli.command()
@click.option("--altitude", "-a", type=float, required=True, help="Orbital altitude (km)")
@click.option("--inclination", "-i", type=float, required=True, help="Inclination (deg)")
@click.option("--epoch", "-e", type=str, help="Epoch (ISO format)")
@click.option("--output", "-o", type=click.Path(), help="Output file")
def generate_tle(altitude, inclination, epoch, output):
    """Generate a synthetic TLE."""
    from sim.models.orbit import generate_synthetic_tle

    if epoch:
        dt = datetime.fromisoformat(epoch)
    else:
        dt = datetime.now(timezone.utc)

    line1, line2 = generate_synthetic_tle(
        altitude_km=altitude,
        inclination_deg=inclination,
        epoch=dt,
    )

    if output:
        with open(output, "w") as f:
            f.write(line1 + "\n")
            f.write(line2 + "\n")
        click.echo(f"TLE written to: {output}")
    else:
        click.echo(line1)
        click.echo(line2)


@cli.command()
@click.option("--altitude-start", "-as", type=float, default=500.0, help="Start altitude (km)")
@click.option("--altitude-end", "-ae", type=float, default=400.0, help="End altitude (km)")
def delta_v(altitude_start, altitude_end):
    """Calculate delta-V for orbit change."""
    from sim.models.orbit import compute_lowering_delta_v, orbital_period

    dv = compute_lowering_delta_v(altitude_start, altitude_end)
    period_start = orbital_period(altitude_start)
    period_end = orbital_period(altitude_end)

    click.echo(f"Altitude: {altitude_start:.1f} km -> {altitude_end:.1f} km")
    click.echo(f"Delta-V: {dv*1000:.1f} m/s")
    click.echo(f"Period: {period_start/60:.1f} min -> {period_end/60:.1f} min")


@cli.command()
@click.option("--altitude", "-a", type=float, default=500.0, help="Altitude (km)")
@click.option("--focal-length", "-f", type=float, default=1000.0, help="Focal length (mm)")
@click.option("--pixel-size", "-p", type=float, default=10.0, help="Pixel size (um)")
def sensor_geometry(altitude, focal_length, pixel_size):
    """Calculate EO sensor geometry."""
    from sim.models.imaging import EOSensorConfig, FrameSensor

    config = EOSensorConfig(
        focal_length_mm=focal_length,
        pixel_size_um=pixel_size,
    )
    sensor = FrameSensor(config)

    gsd = sensor.compute_gsd(altitude)
    swath = sensor.compute_swath(altitude)
    footprint = sensor.compute_frame_footprint(altitude)
    frame_mb = sensor.compute_frame_data_mb()

    click.echo(f"Altitude: {altitude:.1f} km")
    click.echo(f"GSD: {gsd:.2f} m")
    click.echo(f"Swath: {swath:.2f} km")
    click.echo(f"Footprint: {footprint[0]:.2f} x {footprint[1]:.2f} km")
    click.echo(f"Frame size: {frame_mb:.1f} MB")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
