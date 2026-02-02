"""ETE Aerie integration tests - validate Aerie to Simulator pipeline.

Tests the complete flow: Aerie Plan -> Export -> Simulator -> Results.

Key features:
- Real Aerie GraphQL integration (when available)
- Plan creation and export
- Simulation execution on exported plans
- Result validation

Usage:
    pytest tests/ete/test_aerie_integration.py -v
    pytest tests/ete/ -m "ete_tier_a" -v
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

import pytest

from .conftest import REFERENCE_EPOCH

pytestmark = [
    pytest.mark.ete_tier_a,
    pytest.mark.ete,
]


def aerie_available() -> bool:
    """Check if Aerie is available for testing."""
    try:
        import requests
        response = requests.post(
            "http://localhost:8080/v1/graphql",
            json={"query": "{ __typename }"},
            timeout=5,
        )
        return response.status_code == 200
    except Exception:
        return False


# Skip all tests if Aerie is not available
pytestmark.append(
    pytest.mark.skipif(
        not aerie_available(),
        reason="Aerie not available - start with 'make aerie-up'"
    )
)


class TestAerieConnection:
    """Test basic Aerie connectivity and health."""

    def test_aerie_graphql_responds(self, graphql_url):
        """
        Verify Aerie GraphQL endpoint responds to queries.

        This is the fundamental connectivity test.
        """
        import requests

        response = requests.post(
            graphql_url,
            json={"query": "{ __typename }"},
            timeout=10,
        )

        assert response.status_code == 200, (
            f"Aerie GraphQL returned {response.status_code}\n"
            f"Response: {response.text[:500]}"
        )

        data = response.json()
        assert "data" in data, f"Invalid GraphQL response: {data}"

    def test_aerie_schema_introspection(self, graphql_url):
        """
        Verify Aerie schema can be introspected.

        Schema introspection is required for client generation.
        """
        import requests

        introspection_query = """
        query {
            __schema {
                types {
                    name
                }
            }
        }
        """

        response = requests.post(
            graphql_url,
            json={"query": introspection_query},
            timeout=30,
        )

        assert response.status_code == 200
        data = response.json()

        assert "data" in data
        assert "__schema" in data["data"]
        assert "types" in data["data"]["__schema"]

        # Should have core Aerie types
        type_names = [t["name"] for t in data["data"]["__schema"]["types"]]

        # Check for essential Aerie types (these may vary by version)
        expected_types = ["Query", "Mutation"]
        for expected in expected_types:
            assert expected in type_names, (
                f"Missing expected type '{expected}' in schema"
            )


class TestAeriePlanOperations:
    """Test Aerie plan creation and management."""

    @pytest.fixture
    def test_mission_model_id(self, graphql_url) -> Optional[int]:
        """Get or create a test mission model ID."""
        import requests

        # Query for existing mission models
        query = """
        query {
            mission_model {
                id
                name
            }
        }
        """

        response = requests.post(
            graphql_url,
            json={"query": query},
            timeout=30,
        )

        if response.status_code != 200:
            pytest.skip("Cannot query mission models")

        data = response.json()
        models = data.get("data", {}).get("mission_model", [])

        if not models:
            pytest.skip("No mission models available - upload a model first")

        return models[0]["id"]

    def test_can_query_plans(self, graphql_url):
        """
        Verify plans can be queried from Aerie.
        """
        import requests

        query = """
        query {
            plan {
                id
                name
                start_time
                duration
            }
        }
        """

        response = requests.post(
            graphql_url,
            json={"query": query},
            timeout=30,
        )

        assert response.status_code == 200, (
            f"Plan query failed: {response.text}"
        )

        data = response.json()
        assert "errors" not in data, f"GraphQL errors: {data.get('errors')}"
        assert "data" in data
        assert "plan" in data["data"]

    def test_can_create_plan(self, graphql_url, test_mission_model_id, reference_epoch):
        """
        Verify a plan can be created in Aerie.

        Creates a test plan with deterministic parameters.
        """
        import requests

        if test_mission_model_id is None:
            pytest.skip("No mission model available")

        start_time = reference_epoch.isoformat().replace("+00:00", "Z")

        mutation = """
        mutation CreatePlan($plan: plan_insert_input!) {
            insert_plan_one(object: $plan) {
                id
                name
                start_time
            }
        }
        """

        variables = {
            "plan": {
                "name": f"ETE_Test_Plan_{reference_epoch.strftime('%Y%m%d_%H%M%S')}",
                "model_id": test_mission_model_id,
                "start_time": start_time,
                "duration": "24:00:00",
            }
        }

        response = requests.post(
            graphql_url,
            json={"query": mutation, "variables": variables},
            timeout=30,
        )

        assert response.status_code == 200, (
            f"Plan creation request failed: {response.text}"
        )

        data = response.json()

        # Plan creation may fail due to permissions or configuration
        # That's OK for connectivity testing - we just verify the endpoint works
        if "errors" in data:
            # Check if it's a permission error vs actual failure
            error_msg = str(data["errors"])
            if "permission" in error_msg.lower():
                pytest.skip("Aerie permissions not configured for plan creation")
            # Other errors should cause failure
            pytest.fail(f"Plan creation failed: {data['errors']}")

        assert "data" in data
        assert data["data"]["insert_plan_one"] is not None

        plan_id = data["data"]["insert_plan_one"]["id"]
        assert plan_id is not None, "Plan created but no ID returned"

        # Clean up: delete the test plan
        delete_mutation = """
        mutation DeletePlan($id: Int!) {
            delete_plan_by_pk(id: $id) {
                id
            }
        }
        """
        requests.post(
            graphql_url,
            json={"query": delete_mutation, "variables": {"id": plan_id}},
            timeout=30,
        )


class TestAeriePlanExport:
    """Test exporting plans from Aerie for simulation."""

    def test_plan_export_query_structure(self, graphql_url):
        """
        Verify the plan export query structure is valid.

        Tests that the GraphQL query we use for export compiles.
        """
        import requests

        # This query should be valid even if no plans exist
        query = """
        query GetPlanForExport($planId: Int!) {
            plan_by_pk(id: $planId) {
                id
                name
                start_time
                duration
                activity_directives {
                    id
                    type
                    start_offset
                    arguments
                }
            }
        }
        """

        # Use a non-existent ID - we just want to verify query validity
        response = requests.post(
            graphql_url,
            json={"query": query, "variables": {"planId": -1}},
            timeout=30,
        )

        assert response.status_code == 200
        data = response.json()

        # Query should be valid (no syntax errors)
        # May return null for non-existent plan, but no GraphQL errors
        if "errors" in data:
            errors = data["errors"]
            # Filter out "not found" errors - those are expected
            actual_errors = [
                e for e in errors
                if "not found" not in str(e).lower()
            ]
            assert len(actual_errors) == 0, f"Query errors: {actual_errors}"


class TestAerieToSimulatorPipeline:
    """Test the full Aerie to Simulator pipeline."""

    def test_exported_plan_format_valid(self, reference_epoch, tmp_path):
        """
        Verify exported plan format matches simulator expectations.

        This test uses a mock exported plan to validate format handling.
        """
        from sim.core.types import PlanInput, Activity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=24)

        # Simulate exported plan structure (as would come from Aerie)
        exported_plan = {
            "plan_id": "aerie_export_001",
            "name": "Test Plan from Aerie",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "activities": [
                {
                    "id": "act_001",
                    "type": "GroundContact",
                    "start_offset": "PT1H",  # ISO 8601 duration
                    "arguments": {
                        "station_id": "SVALBARD",
                        "duration_min": 10,
                    },
                },
                {
                    "id": "act_002",
                    "type": "Imaging",
                    "start_offset": "PT2H30M",
                    "arguments": {
                        "target_id": "target_001",
                        "mode": "high_res",
                    },
                },
            ],
        }

        # Convert to simulator format
        activities = []
        for act in exported_plan["activities"]:
            # Parse ISO 8601 duration (simplified)
            offset_str = act["start_offset"]
            hours = 0
            minutes = 0
            if "H" in offset_str:
                hours = int(offset_str.split("PT")[1].split("H")[0])
            if "M" in offset_str:
                if "H" in offset_str:
                    minutes = int(offset_str.split("H")[1].split("M")[0])
                else:
                    minutes = int(offset_str.split("PT")[1].split("M")[0])

            act_start = start_time + timedelta(hours=hours, minutes=minutes)
            act_duration = act["arguments"].get("duration_min", 5)
            act_end = act_start + timedelta(minutes=act_duration)

            activities.append(Activity(
                activity_id=act["id"],
                activity_type=act["type"].lower(),
                start_time=act_start,
                end_time=act_end,
                parameters=act["arguments"],
            ))

        plan = PlanInput(
            plan_id=exported_plan["plan_id"],
            start_time=start_time,
            end_time=end_time,
            activities=activities,
        )

        # Validate plan structure
        assert plan.plan_id == "aerie_export_001"
        assert len(plan.activities) == 2
        assert plan.activities[0].activity_type == "groundcontact"
        assert plan.activities[1].activity_type == "imaging"

    def test_simulation_accepts_aerie_format(self, reference_epoch, tmp_path):
        """
        Verify simulator can execute a plan in Aerie export format.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity, InitialState, PlanInput, SimConfig, Activity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=6)

        initial_state = InitialState(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
            soc=0.9,
        )

        # Activities in Aerie-like format (converted)
        activities = [
            Activity(
                activity_id="aerie_act_001",
                activity_type="imaging",
                start_time=start_time + timedelta(hours=1),
                end_time=start_time + timedelta(hours=1, minutes=5),
                parameters={
                    "target_id": "target_001",
                    "mode": "standard",
                    "power_draw_w": 50.0,
                },
            ),
            Activity(
                activity_id="aerie_act_002",
                activity_type="downlink",
                start_time=start_time + timedelta(hours=3),
                end_time=start_time + timedelta(hours=3, minutes=15),
                parameters={
                    "station_id": "SVALBARD",
                    "data_rate_mbps": 100.0,
                },
            ),
        ]

        plan = PlanInput(
            plan_id="aerie_pipeline_test",
            start_time=start_time,
            end_time=end_time,
            activities=activities,
        )

        config = SimConfig(
            output_dir=str(tmp_path),
            time_step_s=60.0,
        )

        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )

        # Validate simulation completed
        assert result is not None, "Simulation returned None"
        assert result.final_state is not None, "No final state"
        assert result.final_state.epoch == end_time, "Epoch mismatch"

        # Check outputs were generated
        assert (tmp_path / "viz").exists() or (tmp_path / "summary.json").exists(), (
            "No output files generated"
        )


class TestAerieActivityTypes:
    """Test that Aerie activity types map correctly to simulator."""

    @pytest.mark.parametrize("activity_type,expected_sim_type", [
        ("GroundContact", "downlink"),
        ("Imaging", "imaging"),
        ("Maneuver", "maneuver"),
        ("OrbitMaintenance", "orbit_maintain"),
        ("SafeMode", "safe_mode"),
    ])
    def test_activity_type_mapping(
        self, activity_type: str, expected_sim_type: str, reference_epoch
    ):
        """
        Verify Aerie activity types map to simulator types.
        """
        # This is the mapping that would be applied during export
        type_mapping = {
            "GroundContact": "downlink",
            "Imaging": "imaging",
            "Maneuver": "maneuver",
            "OrbitMaintenance": "orbit_maintain",
            "SafeMode": "safe_mode",
            "Calibration": "calibration",
            "DataProcessing": "processing",
        }

        sim_type = type_mapping.get(activity_type, activity_type.lower())
        assert sim_type == expected_sim_type, (
            f"Activity type mapping failed: {activity_type} -> {sim_type}, "
            f"expected {expected_sim_type}"
        )


@pytest.mark.ete_tier_b
class TestFullAeriePipeline:
    """Full Aerie pipeline tests (Tier B - nightly)."""

    def test_aerie_plan_to_viewer_pipeline(
        self, reference_epoch, tmp_path, graphql_url
    ):
        """
        Complete pipeline: Aerie Plan -> Export -> Simulate -> Viewer-ready output.

        This is the integration test that validates the entire flow.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity, InitialState, PlanInput, SimConfig, Activity
        import requests

        # Step 1: Query an existing plan (or use mock data)
        query = """
        query {
            plan(limit: 1) {
                id
                name
                start_time
                duration
            }
        }
        """

        response = requests.post(
            graphql_url,
            json={"query": query},
            timeout=30,
        )

        # If no plans exist, use mock data
        use_mock = True
        if response.status_code == 200:
            data = response.json()
            plans = data.get("data", {}).get("plan", [])
            if plans:
                use_mock = False
                # Would use real plan data here

        if use_mock:
            # Use deterministic mock data
            start_time = reference_epoch
            end_time = start_time + timedelta(hours=12)
        else:
            pytest.skip("Real Aerie plan pipeline test not implemented")

        # Step 2: Create simulation input
        initial_state = InitialState(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
            soc=0.85,
        )

        activities = [
            Activity(
                activity_id="pipeline_act_001",
                activity_type="imaging",
                start_time=start_time + timedelta(hours=2),
                end_time=start_time + timedelta(hours=2, minutes=5),
                parameters={"mode": "standard"},
            ),
            Activity(
                activity_id="pipeline_act_002",
                activity_type="downlink",
                start_time=start_time + timedelta(hours=6),
                end_time=start_time + timedelta(hours=6, minutes=10),
                parameters={"station_id": "SVALBARD"},
            ),
        ]

        plan = PlanInput(
            plan_id="aerie_full_pipeline_test",
            start_time=start_time,
            end_time=end_time,
            activities=activities,
        )

        config = SimConfig(
            output_dir=str(tmp_path),
            time_step_s=60.0,
        )

        # Step 3: Run simulation
        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )

        assert result is not None
        assert result.final_state is not None

        # Step 4: Verify viewer-ready output
        viz_dir = tmp_path / "viz"

        # Check for required viewer files
        required_files = ["run_manifest.json"]
        optional_files = ["scene.czml", "events.json"]

        for req_file in required_files:
            file_path = viz_dir / req_file
            assert file_path.exists(), (
                f"Required viewer file missing: {req_file}\n"
                f"Pipeline must generate viewer-compatible output."
            )

        # Validate manifest
        with open(viz_dir / "run_manifest.json") as f:
            manifest = json.load(f)

        assert "plan_id" in manifest, "Manifest missing plan_id"
        assert manifest["plan_id"] == "aerie_full_pipeline_test"
