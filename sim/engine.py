"""Main simulation engine."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from sim.core.types import (
    Activity,
    Event,
    EventType,
    Fidelity,
    InitialState,
    PlanInput,
    SimConfig,
    SimResults,
)
from sim.core.config import generate_run_id, setup_run_directory
from sim.models.orbit import OrbitPropagator, EphemerisPoint
from sim.models.power import PowerModel, PowerConfig
from sim.models.access import AccessModel, get_default_stations
from sim.activities.base import (
    ActivityHandler,
    ActivityResult,
    IdleHandler,
    register_handler,
    get_handler,
)
from sim.activities.orbit_lower import OrbitLoweringHandler
from sim.activities.eo_collect import EOCollectHandler


logger = logging.getLogger(__name__)


# Register activity handlers
register_handler(IdleHandler())
register_handler(OrbitLoweringHandler())
register_handler(EOCollectHandler())


def simulate(
    plan: PlanInput,
    initial_state: InitialState,
    fidelity: Fidelity | str,
    config: SimConfig,
) -> SimResults:
    """
    Run spacecraft simulation.

    Args:
        plan: Mission plan with activities
        initial_state: Initial spacecraft state
        fidelity: Simulation fidelity level
        config: Simulation configuration

    Returns:
        SimResults with profiles, events, and artifacts
    """
    if isinstance(fidelity, str):
        fidelity = Fidelity(fidelity.upper())

    logger.info(f"Starting simulation: {plan.plan_id}")
    logger.info(f"Fidelity: {fidelity.value}")
    logger.info(f"Activities: {len(plan.activities)}")

    # Set up output directory
    run_id = generate_run_id(plan.plan_id)
    run_dir = setup_run_directory(config.output_dir, run_id)

    # Initialize random seed for reproducibility
    if config.random_seed is not None:
        np.random.seed(config.random_seed)

    # Generate ephemeris for plan duration
    logger.info("Generating ephemeris...")
    propagator = OrbitPropagator(
        altitude_km=initial_state.position_eci[0] if len(initial_state.position_eci) == 1
        else np.linalg.norm(initial_state.position_eci) - 6378.137,
        inclination_deg=53.0,  # Default inclination
        epoch=plan.start_time,
    )

    # Try to use TLE from initial state if position/velocity are provided
    try:
        ephemeris = propagator.propagate_range(
            start=plan.start_time,
            end=plan.end_time,
            step_s=config.time_step_s,
        )
    except Exception as e:
        logger.warning(f"Ephemeris generation failed: {e}")
        ephemeris = []

    # Compute eclipse intervals
    logger.info("Computing eclipse intervals...")
    power_config = PowerConfig(
        battery_capacity_wh=config.spacecraft.battery_capacity_wh,
        solar_panel_area_m2=config.spacecraft.solar_panel_area_m2,
        solar_efficiency=config.spacecraft.solar_efficiency,
        base_power_w=config.spacecraft.base_power_w,
    )
    power_model = PowerModel(power_config)
    eclipse_windows = power_model.compute_eclipse_intervals(ephemeris)

    # Compute ground station access windows
    logger.info("Computing ground station access...")
    access_model = AccessModel(get_default_stations())
    access_windows = access_model.compute_all_access_windows(ephemeris)

    # Process activities
    logger.info("Processing activities...")
    all_events: List[Event] = []
    all_artifacts: Dict[str, Any] = {
        "run_id": run_id,
        "run_dir": str(run_dir),
    }
    activity_results: List[ActivityResult] = []

    # Track state over time
    current_state = initial_state.copy()
    profile_data = {
        "time": [],
        "altitude_km": [],
        "battery_soc": [],
        "propellant_kg": [],
        "storage_gb": [],
        "in_eclipse": [],
    }

    for activity in plan.activities:
        logger.info(f"Processing activity: {activity.activity_id} ({activity.activity_type})")

        # Get handler for activity type
        handler = get_handler(activity.activity_type)
        if handler is None:
            all_events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.WARNING,
                category="activity",
                message=f"No handler for activity type: {activity.activity_type}",
                details={"activity_id": activity.activity_id},
            ))
            continue

        # Validate activity
        validation_events = handler.validate(activity)
        all_events.extend(validation_events)

        if any(e.event_type == EventType.ERROR for e in validation_events):
            continue

        # Get ephemeris for activity duration
        activity_ephemeris = [
            p for p in ephemeris
            if activity.start_time <= p.time <= activity.end_time
        ]

        # Process activity
        result = handler.process(
            activity=activity,
            state=current_state,
            ephemeris=activity_ephemeris,
            config=config,
        )
        activity_results.append(result)
        all_events.extend(result.events)

        # Update state
        for key, value in result.state_updates.items():
            if hasattr(current_state, key):
                setattr(current_state, key, value)

        # Store artifacts
        if result.artifacts:
            all_artifacts[activity.activity_id] = result.artifacts

        logger.info(f"  Result: {result.message}")

        # Record profile data
        for point in activity_ephemeris:
            profile_data["time"].append(point.time)
            profile_data["altitude_km"].append(point.altitude_km)
            profile_data["battery_soc"].append(current_state.battery_soc)
            profile_data["propellant_kg"].append(current_state.propellant_kg)
            profile_data["storage_gb"].append(current_state.storage_used_gb)
            profile_data["in_eclipse"].append(power_model.is_in_eclipse(point.position_eci))

    # Create profiles DataFrame
    profiles = pd.DataFrame(profile_data)
    if not profiles.empty:
        profiles.set_index("time", inplace=True)

    # Update final state epoch
    current_state.epoch = plan.end_time
    if ephemeris:
        current_state.position_eci = ephemeris[-1].position_eci
        current_state.velocity_eci = ephemeris[-1].velocity_eci

    # Generate summary
    summary = _generate_summary(
        plan=plan,
        activity_results=activity_results,
        events=all_events,
        initial_state=initial_state,
        final_state=current_state,
        ephemeris=ephemeris,
    )

    # Write outputs
    _write_outputs(
        run_dir=run_dir,
        profiles=profiles,
        ephemeris=ephemeris,
        events=all_events,
        access_windows=access_windows,
        eclipse_windows=eclipse_windows,
        summary=summary,
        artifacts=all_artifacts,
    )

    all_artifacts["summary"] = str(run_dir / "summary.json")
    all_artifacts["profiles"] = str(run_dir / "profiles.parquet")
    all_artifacts["ephemeris"] = str(run_dir / "ephemeris.parquet")
    all_artifacts["events"] = str(run_dir / "events.json")

    logger.info(f"Simulation complete: {run_dir}")

    return SimResults(
        profiles=profiles,
        events=all_events,
        artifacts=all_artifacts,
        final_state=current_state,
        summary=summary,
    )


def _generate_summary(
    plan: PlanInput,
    activity_results: List[ActivityResult],
    events: List[Event],
    initial_state: InitialState,
    final_state: InitialState,
    ephemeris: List[EphemerisPoint],
) -> Dict[str, Any]:
    """Generate simulation summary."""
    violations = [e for e in events if e.event_type == EventType.VIOLATION]
    warnings = [e for e in events if e.event_type == EventType.WARNING]

    successful_activities = sum(1 for r in activity_results if r.success)

    summary = {
        "plan_id": plan.plan_id,
        "spacecraft_id": plan.spacecraft_id,
        "start_time": plan.start_time.isoformat(),
        "end_time": plan.end_time.isoformat(),
        "duration_hours": (plan.end_time - plan.start_time).total_seconds() / 3600,
        "activities": {
            "total": len(plan.activities),
            "successful": successful_activities,
            "failed": len(activity_results) - successful_activities,
        },
        "events": {
            "violations": len(violations),
            "warnings": len(warnings),
            "total": len(events),
        },
        "state_changes": {
            "propellant_used_kg": initial_state.propellant_kg - final_state.propellant_kg,
            "final_soc": final_state.battery_soc,
            "final_storage_gb": final_state.storage_used_gb,
        },
    }

    if ephemeris:
        summary["orbit"] = {
            "initial_altitude_km": ephemeris[0].altitude_km,
            "final_altitude_km": ephemeris[-1].altitude_km,
            "altitude_change_km": ephemeris[-1].altitude_km - ephemeris[0].altitude_km,
        }

    return summary


def _write_outputs(
    run_dir: Path,
    profiles: pd.DataFrame,
    ephemeris: List[EphemerisPoint],
    events: List[Event],
    access_windows: Dict[str, list],
    eclipse_windows: list,
    summary: Dict[str, Any],
    artifacts: Dict[str, Any],
):
    """Write simulation outputs to disk."""
    # Write summary
    with open(run_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    # Write profiles
    if not profiles.empty:
        profiles.to_parquet(run_dir / "profiles.parquet")

    # Write ephemeris
    if ephemeris:
        eph_data = {
            "time": [p.time for p in ephemeris],
            "x_km": [p.position_eci[0] for p in ephemeris],
            "y_km": [p.position_eci[1] for p in ephemeris],
            "z_km": [p.position_eci[2] for p in ephemeris],
            "vx_km_s": [p.velocity_eci[0] for p in ephemeris],
            "vy_km_s": [p.velocity_eci[1] for p in ephemeris],
            "vz_km_s": [p.velocity_eci[2] for p in ephemeris],
            "altitude_km": [p.altitude_km for p in ephemeris],
        }
        pd.DataFrame(eph_data).to_parquet(run_dir / "ephemeris.parquet")

    # Write events
    events_data = [
        {
            "timestamp": e.timestamp.isoformat(),
            "type": e.event_type.value,
            "category": e.category,
            "message": e.message,
            "details": e.details,
        }
        for e in events
    ]
    with open(run_dir / "events.json", "w") as f:
        json.dump(events_data, f, indent=2)

    # Write access windows
    access_data = {
        station_id: [
            {
                "start_time": w.start_time.isoformat(),
                "end_time": w.end_time.isoformat(),
                "duration_s": w.duration_s,
                "max_elevation_deg": w.max_elevation_deg,
            }
            for w in windows
        ]
        for station_id, windows in access_windows.items()
    }
    with open(run_dir / "access_windows.json", "w") as f:
        json.dump(access_data, f, indent=2)

    # Write eclipse windows
    eclipse_data = [
        {
            "start_time": w.start_time.isoformat(),
            "end_time": w.end_time.isoformat(),
            "duration_s": w.duration_s,
        }
        for w in eclipse_windows
    ]
    with open(run_dir / "eclipse_windows.json", "w") as f:
        json.dump(eclipse_data, f, indent=2)
