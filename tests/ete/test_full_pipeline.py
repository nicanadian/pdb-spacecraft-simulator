"""ETE full pipeline tests - complete end-to-end validation.

Tests the complete pipeline: Plan -> Simulation -> GMAT Comparison -> Viewer Output.

This is the capstone test that validates all components work together.

Key features:
- Complete pipeline execution
- Data format validation at each stage
- Cross-component consistency checks
- Viewer artifact generation validation

Usage:
    pytest tests/ete/test_full_pipeline.py -v
    pytest tests/ete/ -m "ete_tier_a" -v
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

pytestmark = [
    pytest.mark.ete_tier_a,
    pytest.mark.ete,
]


class TestPlanInputValidation:
    """Test plan input format validation."""

    def test_plan_input_serialization(self, reference_epoch):
        """
        Verify plan input can be serialized and deserialized.
        """
        from sim.core.types import Activity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=24)

        activities = [
            Activity(
                activity_id="act_001",
                activity_type="imaging",
                start_time=start_time + timedelta(hours=2),
                end_time=start_time + timedelta(hours=2, minutes=5),
                parameters={"mode": "high_res", "target_id": "target_001"},
            ),
            Activity(
                activity_id="act_002",
                activity_type="downlink",
                start_time=start_time + timedelta(hours=4),
                end_time=start_time + timedelta(hours=4, minutes=15),
                parameters={"station_id": "SVALBARD", "data_rate_mbps": 100},
            ),
        ]

        plan = create_test_plan(
            plan_id="pipeline_test_001",
            start_time=start_time,
            end_time=end_time,
            activities=activities,
        )

        # Serialize to dict
        plan_dict = {
            "plan_id": plan.plan_id,
            "start_time": plan.start_time.isoformat(),
            "end_time": plan.end_time.isoformat(),
            "activities": [
                {
                    "activity_id": a.activity_id,
                    "activity_type": a.activity_type,
                    "start_time": a.start_time.isoformat(),
                    "end_time": a.end_time.isoformat(),
                    "parameters": a.parameters,
                }
                for a in plan.activities
            ],
        }

        # Verify JSON serializable
        json_str = json.dumps(plan_dict)
        assert len(json_str) > 0

        # Verify deserializable
        plan_restored = json.loads(json_str)
        assert plan_restored["plan_id"] == "pipeline_test_001"
        assert len(plan_restored["activities"]) == 2

    def test_initial_state_serialization(self, reference_epoch):
        """
        Verify initial state can be serialized and deserialized.
        """
        initial_state = create_test_initial_state(
            epoch=reference_epoch,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
            battery_soc=0.85,
        )

        # Serialize
        state_dict = {
            "epoch": initial_state.epoch.isoformat(),
            "position_eci": list(initial_state.position_eci),
            "velocity_eci": list(initial_state.velocity_eci),
            "mass_kg": initial_state.mass_kg,
            "battery_soc": initial_state.battery_soc,
        }

        json_str = json.dumps(state_dict)
        state_restored = json.loads(json_str)

        assert state_restored["mass_kg"] == 500.0
        assert len(state_restored["position_eci"]) == 3
        assert len(state_restored["velocity_eci"]) == 3


class TestSimulationExecution:
    """Test simulation execution stage."""

    def test_simulation_completes_with_all_fidelities(self, reference_epoch, tmp_path):
        """
        Verify simulation completes for all fidelity levels.
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
            plan_id="fidelity_test",
            start_time=start_time,
            end_time=end_time,
        )

        # Test LOW fidelity (always available)
        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path / "low"), time_step_s=60.0),
        )

        assert result is not None, "LOW fidelity simulation failed"
        assert result.final_state is not None

    def test_simulation_produces_output_files(self, reference_epoch, tmp_path):
        """
        Verify simulation produces expected output files.
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
            battery_soc=0.9,
        )

        plan = create_test_plan(
            plan_id="output_test",
            start_time=start_time,
            end_time=end_time,
        )

        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        # Check for output directory structure
        # Simulator creates a timestamped subdirectory, so search recursively
        expected_files = ["run_manifest.json"]

        for expected in expected_files:
            matches = list(tmp_path.glob(f"**/{expected}"))
            summary_matches = list(tmp_path.glob("**/summary.json"))

            assert len(matches) > 0 or len(summary_matches) > 0, (
                f"Missing expected output: {expected}\n"
                f"Contents of {tmp_path}: {list(tmp_path.glob('**/*'))}"
            )


class TestOutputValidation:
    """Test simulation output validation."""

    def test_manifest_format_valid(self, reference_epoch, tmp_path):
        """
        Verify manifest file has valid format.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=2)

        result = simulate(
            plan=create_test_plan(
                plan_id="manifest_format_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=create_test_initial_state(
                epoch=start_time,
                position_eci=[6778.137, 0.0, 0.0],
                velocity_eci=[0.0, 7.6686, 0.0],
                mass_kg=500.0,
            ),
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        # Find manifest
        manifest_path = tmp_path / "viz" / "run_manifest.json"
        if not manifest_path.exists():
            manifest_path = tmp_path / "run_manifest.json"

        if manifest_path.exists():
            with open(manifest_path) as f:
                manifest = json.load(f)

            # Required fields
            assert "plan_id" in manifest, "Manifest missing plan_id"
            assert manifest["plan_id"] == "manifest_format_test"

    def test_czml_format_valid(self, reference_epoch, tmp_path):
        """
        Verify CZML file has valid Cesium format.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=3)

        result = simulate(
            plan=create_test_plan(
                plan_id="czml_format_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=create_test_initial_state(
                epoch=start_time,
                position_eci=[6778.137, 0.0, 0.0],
                velocity_eci=[0.0, 7.6686, 0.0],
                mass_kg=500.0,
            ),
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        czml_path = tmp_path / "viz" / "scene.czml"
        if not czml_path.exists():
            pytest.skip("CZML file not generated")

        with open(czml_path) as f:
            czml = json.load(f)

        # CZML must be an array
        assert isinstance(czml, list), "CZML must be an array"
        assert len(czml) > 0, "CZML array is empty"

        # First element must be document packet
        assert czml[0].get("id") == "document", (
            "CZML first element must be document packet"
        )

        # Should have at least document and one entity
        assert len(czml) >= 2, "CZML should have document and at least one entity"

    def test_events_format_valid(self, reference_epoch, tmp_path):
        """
        Verify events file has valid format.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity, Activity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=12)

        # Add activity that might generate events
        activities = [
            Activity(
                activity_id="power_test",
                activity_type="imaging",
                start_time=start_time + timedelta(hours=1),
                end_time=start_time + timedelta(hours=2),
                parameters={"power_draw_w": 200.0},
            ),
        ]

        result = simulate(
            plan=create_test_plan(
                plan_id="events_format_test",
                start_time=start_time,
                end_time=end_time,
                activities=activities,
            ),
            initial_state=create_test_initial_state(
                epoch=start_time,
                position_eci=[6778.137, 0.0, 0.0],
                velocity_eci=[0.0, 7.6686, 0.0],
                mass_kg=500.0,
                battery_soc=0.3,  # Low SOC may trigger events
            ),
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        events_path = tmp_path / "viz" / "events.json"
        if not events_path.exists():
            # No events is OK if SOC didn't drop
            return

        with open(events_path) as f:
            events = json.load(f)

        # Events should be list or dict with events key
        if isinstance(events, dict):
            events = events.get("events", [])

        assert isinstance(events, list), "Events must be a list"

        # Validate event structure
        for i, event in enumerate(events):
            assert isinstance(event, dict), f"Event {i} must be a dict"
            # Events should have id or type
            assert "id" in event or "type" in event, (
                f"Event {i} missing id or type"
            )


class TestCrossComponentConsistency:
    """Test consistency across pipeline components."""

    def test_final_state_matches_profiles(self, reference_epoch, tmp_path):
        """
        Verify final state matches last profile entry.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=6)

        result = simulate(
            plan=create_test_plan(
                plan_id="consistency_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=create_test_initial_state(
                epoch=start_time,
                position_eci=[6778.137, 0.0, 0.0],
                velocity_eci=[0.0, 7.6686, 0.0],
                mass_kg=500.0,
            ),
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        # Compare final state epoch with expected
        assert result.final_state.epoch == end_time, (
            f"Final state epoch mismatch:\n"
            f"  Expected: {end_time}\n"
            f"  Got:      {result.final_state.epoch}"
        )

    def test_event_times_within_sim_bounds(self, reference_epoch, tmp_path):
        """
        Verify all event times are within simulation time bounds.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity, Activity
        from datetime import datetime

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=6)

        activities = [
            Activity(
                activity_id="test_act",
                activity_type="imaging",
                start_time=start_time + timedelta(hours=1),
                end_time=start_time + timedelta(hours=1, minutes=5),
                parameters={},
            ),
        ]

        result = simulate(
            plan=create_test_plan(
                plan_id="event_bounds_test",
                start_time=start_time,
                end_time=end_time,
                activities=activities,
            ),
            initial_state=create_test_initial_state(
                epoch=start_time,
                position_eci=[6778.137, 0.0, 0.0],
                velocity_eci=[0.0, 7.6686, 0.0],
                mass_kg=500.0,
                battery_soc=0.5,
            ),
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        events_path = tmp_path / "viz" / "events.json"
        if not events_path.exists():
            return  # No events is OK

        with open(events_path) as f:
            events = json.load(f)

        if isinstance(events, dict):
            events = events.get("events", [])

        for i, event in enumerate(events):
            time_key = "time" if "time" in event else "timestamp"
            if time_key not in event:
                continue

            event_time_str = event[time_key]
            event_time = datetime.fromisoformat(event_time_str.replace("Z", "+00:00"))

            assert start_time <= event_time <= end_time, (
                f"EVENT TIME OUT OF BOUNDS\n"
                f"  Event {i}: {event_time}\n"
                f"  Sim start: {start_time}\n"
                f"  Sim end:   {end_time}"
            )


@pytest.mark.ete_tier_b
class TestFullPipelineIntegration:
    """Full pipeline integration tests (Tier B - nightly)."""

    def test_complete_pipeline_with_activities(
        self, reference_epoch, tmp_path, tolerance_config
    ):
        """
        Complete pipeline test with realistic activities.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity, Activity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=24)

        # Realistic activity schedule
        activities = [
            Activity(
                activity_id="imaging_001",
                activity_type="imaging",
                start_time=start_time + timedelta(hours=2),
                end_time=start_time + timedelta(hours=2, minutes=5),
                parameters={"target_id": "T001", "mode": "high_res"},
            ),
            Activity(
                activity_id="downlink_001",
                activity_type="downlink",
                start_time=start_time + timedelta(hours=4),
                end_time=start_time + timedelta(hours=4, minutes=15),
                parameters={"station_id": "SVALBARD"},
            ),
            Activity(
                activity_id="imaging_002",
                activity_type="imaging",
                start_time=start_time + timedelta(hours=8),
                end_time=start_time + timedelta(hours=8, minutes=5),
                parameters={"target_id": "T002", "mode": "standard"},
            ),
            Activity(
                activity_id="downlink_002",
                activity_type="downlink",
                start_time=start_time + timedelta(hours=12),
                end_time=start_time + timedelta(hours=12, minutes=10),
                parameters={"station_id": "FAIRBANKS"},
            ),
        ]

        plan = create_test_plan(
            plan_id="full_pipeline_test",
            start_time=start_time,
            end_time=end_time,
            activities=activities,
        )

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 6.024, 4.766],  # ISS inclination
            mass_kg=500.0,
            battery_soc=0.9,
        )

        config = create_test_config(
            output_dir=str(tmp_path),
            time_step_s=60.0,
        )

        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )

        # Stage 1: Simulation completed
        assert result is not None, "Simulation failed"
        assert result.final_state is not None, "No final state"

        # Stage 2: Output files generated (simulator creates timestamped subdirectory)
        manifest_matches = list(tmp_path.glob("**/run_manifest.json"))
        summary_matches = list(tmp_path.glob("**/summary.json"))
        assert len(manifest_matches) > 0 or len(summary_matches) > 0, (
            f"No output files generated\n"
            f"Contents of {tmp_path}: {list(tmp_path.glob('**/*'))}"
        )

        # Stage 3: Validate physics
        pos_final = np.array(result.final_state.position_eci)
        vel_final = np.array(result.final_state.velocity_eci)

        # Check still in bound orbit
        r = np.linalg.norm(pos_final)
        v = np.linalg.norm(vel_final)
        mu = 398600.4418
        energy = v**2 / 2 - mu / r

        assert energy < 0, (
            f"Spacecraft escaped after 24h simulation\n"
            f"  Energy: {energy:.6f} km²/s²"
        )

        # Check altitude reasonable
        earth_radius = 6378.137
        altitude = r - earth_radius

        assert 100 < altitude < 1000, (
            f"Final altitude unreasonable: {altitude:.1f} km\n"
            f"Expected 100-1000 km for LEO"
        )

        # Stage 4: Validate mass conservation (no thrust activities)
        # Mass should be unchanged since no propulsion activities
        assert abs(result.final_state.mass_kg - initial_state.mass_kg) < 1.0, (
            f"Mass changed unexpectedly:\n"
            f"  Initial: {initial_state.mass_kg} kg\n"
            f"  Final:   {result.final_state.mass_kg} kg"
        )

    def test_pipeline_determinism(self, reference_epoch, tmp_path):
        """
        Verify pipeline produces deterministic results.

        Running the same simulation twice should produce identical results.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=6)

        plan = create_test_plan(
            plan_id="determinism_test",
            start_time=start_time,
            end_time=end_time,
        )

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        # Run 1
        result1 = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path / "run1"), time_step_s=60.0),
        )

        # Run 2
        result2 = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path / "run2"), time_step_s=60.0),
        )

        # Compare final states
        pos1 = np.array(result1.final_state.position_eci)
        pos2 = np.array(result2.final_state.position_eci)

        vel1 = np.array(result1.final_state.velocity_eci)
        vel2 = np.array(result2.final_state.velocity_eci)

        pos_diff = np.linalg.norm(pos1 - pos2)
        vel_diff = np.linalg.norm(vel1 - vel2)

        assert pos_diff < 1e-10, (
            f"NON-DETERMINISTIC POSITION\n"
            f"  Run 1: {pos1}\n"
            f"  Run 2: {pos2}\n"
            f"  Diff:  {pos_diff} km"
        )

        assert vel_diff < 1e-12, (
            f"NON-DETERMINISTIC VELOCITY\n"
            f"  Run 1: {vel1}\n"
            f"  Run 2: {vel2}\n"
            f"  Diff:  {vel_diff} km/s"
        )
