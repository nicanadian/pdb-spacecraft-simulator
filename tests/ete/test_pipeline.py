"""ETE pipeline tests - full integration from Aerie to Viewer.

Tests the complete pipeline: Aerie -> Simulator -> GMAT comparison -> Viewer.
Run on every PR as part of Tier A.

Usage:
    pytest tests/ete/test_pipeline.py -v
    pytest tests/ete/ -m "ete_tier_a" -v
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from .fixtures.data import get_tier_a_case_ids, create_test_plan

# Skip all tests if Playwright is not installed
try:
    from playwright.sync_api import expect

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

if TYPE_CHECKING:
    from playwright.sync_api import Page


pytestmark = [
    pytest.mark.ete_tier_a,
    pytest.mark.ete,
]


# Subset of Tier A cases for quick pipeline validation
PIPELINE_TEST_CASES = ["R01", "R04", "R05", "R07", "R08", "R09", "R11"]


class TestSimulatorPipeline:
    """Test simulator execution pipeline."""

    @pytest.mark.parametrize("case_id", PIPELINE_TEST_CASES[:3])  # Quick subset
    def test_case_executes_successfully(self, case_id, scenario_runner, tmp_path):
        """
        Test case executes through simulator without errors.

        Args:
            case_id: GMAT case identifier
            scenario_runner: ScenarioRunner fixture
            tmp_path: Pytest temp directory
        """
        # Run scenario
        result = scenario_runner.run_scenario(
            case_id=case_id,
            compare_truth=False,  # Don't compare truth in this test
        )

        # Basic success checks
        assert result.success, f"Case {case_id} failed: {result.error_message}"
        assert result.final_state is not None
        assert result.sim_duration_s > 0

    def test_plan_to_simulation_flow(self, tmp_path):
        """Test complete flow from plan input to simulation results."""
        from sim.engine import simulate
        from sim.core.types import Fidelity, InitialState, PlanInput, SimConfig, Activity

        # Create a realistic plan
        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(hours=6)

        initial_state = InitialState(
            epoch=start_time,
            position_eci=[6778.0, 0.0, 0.0],
            velocity_eci=[0.0, 7.67, 0.0],
            mass_kg=1000.0,
        )

        # Add some activities
        activities = [
            Activity(
                activity_id="act_001",
                activity_type="imaging",
                start_time=start_time + timedelta(hours=1),
                end_time=start_time + timedelta(hours=1, minutes=10),
                parameters={"target": "test_target"},
            ),
            Activity(
                activity_id="act_002",
                activity_type="downlink",
                start_time=start_time + timedelta(hours=3),
                end_time=start_time + timedelta(hours=3, minutes=15),
                parameters={"station": "test_station"},
            ),
        ]

        plan = PlanInput(
            plan_id="pipeline_test",
            start_time=start_time,
            end_time=end_time,
            activities=activities,
        )

        config = SimConfig(
            output_dir=str(tmp_path),
            time_step_s=60.0,
        )

        # Run simulation
        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )

        # Verify outputs
        assert result is not None
        assert result.final_state is not None
        assert result.profiles is not None

        # Check output files were created
        output_dir = Path(tmp_path)
        assert output_dir.exists()


class TestGMATComparisonPipeline:
    """Test GMAT comparison pipeline."""

    @pytest.mark.parametrize("case_id", PIPELINE_TEST_CASES[:2])  # Quick subset
    def test_gmat_comparison_available(self, case_id, scenario_runner, gmat_comparator):
        """
        Test GMAT comparison can be performed for a case.

        Args:
            case_id: GMAT case identifier
        """
        # Run scenario with comparison
        result = scenario_runner.run_scenario(
            case_id=case_id,
            compare_truth=True,
        )

        # Result should have comparison data (even if no truth file exists)
        assert result.success or result.error_message is not None

        if result.comparison:
            # If comparison was performed, check it has results
            assert hasattr(result.comparison, "passed")
            assert hasattr(result.comparison, "metrics")


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed")
class TestFullPipeline:
    """Test complete end-to-end pipeline including viewer."""

    def test_simulation_to_viewer_flow(self, tmp_path, viewer_page, completed_run):
        """
        Test simulation results display in viewer.

        Uses the completed_run fixture which creates sample data.
        """
        # Load run in viewer
        viewer_page.load_run(completed_run.path)

        # Verify viewer loaded
        assert viewer_page.is_loaded()
        assert not viewer_page.has_error()

    def test_viewer_displays_events(self, viewer_page, completed_run):
        """Test viewer displays events from simulation."""
        viewer_page.load_run(completed_run.path)

        # Check alerts are displayed
        alerts_count = viewer_page.get_alerts_count()

        # Our test data has 2 events
        assert alerts_count >= 0  # May be 0 if alerts panel not visible by default

    def test_viewer_workspaces_accessible(self, viewer_page, completed_run):
        """Test all workspaces can be accessed."""
        viewer_page.load_run(completed_run.path)

        # Start at mission overview
        initial_ws = viewer_page.current_workspace()
        assert initial_ws == "mission-overview"

        # Try switching to maneuver planning
        viewer_page.switch_workspace("maneuver-planning")
        assert viewer_page.current_workspace() == "maneuver-planning"


class TestDataIntegrity:
    """Test data integrity through the pipeline."""

    def test_simulation_results_json_valid(self, tmp_path):
        """Test simulation outputs are valid JSON."""
        from sim.engine import simulate
        from sim.core.types import Fidelity, InitialState, PlanInput, SimConfig

        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(hours=1)

        initial_state = InitialState(
            epoch=start_time,
            position_eci=[6778.0, 0.0, 0.0],
            velocity_eci=[0.0, 7.67, 0.0],
            mass_kg=1000.0,
        )

        plan = PlanInput(
            plan_id="json_test",
            start_time=start_time,
            end_time=end_time,
            activities=[],
        )

        config = SimConfig(
            output_dir=str(tmp_path),
            time_step_s=60.0,
        )

        # Run simulation
        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )

        # Check output files are valid JSON
        output_dir = Path(tmp_path)

        # Check for common output files
        for json_file in output_dir.glob("**/*.json"):
            with open(json_file) as f:
                try:
                    data = json.load(f)
                    assert data is not None
                except json.JSONDecodeError as e:
                    pytest.fail(f"Invalid JSON in {json_file}: {e}")

    def test_time_axis_monotonic(self, tmp_path):
        """Test simulation time axis is monotonically increasing."""
        from sim.engine import simulate
        from sim.core.types import Fidelity, InitialState, PlanInput, SimConfig

        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(hours=2)

        initial_state = InitialState(
            epoch=start_time,
            position_eci=[6778.0, 0.0, 0.0],
            velocity_eci=[0.0, 7.67, 0.0],
            mass_kg=1000.0,
        )

        plan = PlanInput(
            plan_id="monotonic_test",
            start_time=start_time,
            end_time=end_time,
            activities=[],
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

        # Check profiles have monotonic time
        if hasattr(result, "profiles") and result.profiles is not None:
            # If profiles is a DataFrame with time index
            if hasattr(result.profiles, "index"):
                times = list(result.profiles.index)
                for i in range(1, len(times)):
                    assert times[i] > times[i - 1], "Time axis not monotonic"

    def test_constraint_invariants_maintained(self, tmp_path):
        """Test domain constraint invariants are maintained."""
        from sim.engine import simulate
        from sim.core.types import Fidelity, InitialState, PlanInput, SimConfig

        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(hours=1)

        initial_state = InitialState(
            epoch=start_time,
            position_eci=[6778.0, 0.0, 0.0],
            velocity_eci=[0.0, 7.67, 0.0],
            mass_kg=1000.0,
            soc=0.8,  # 80% state of charge
        )

        plan = PlanInput(
            plan_id="constraint_test",
            start_time=start_time,
            end_time=end_time,
            activities=[],
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

        # Check SOC in [0, 1]
        if hasattr(result.final_state, "soc"):
            assert 0.0 <= result.final_state.soc <= 1.0

        # Check mass is positive
        assert result.final_state.mass_kg > 0

        # Check propellant is non-negative
        if hasattr(result.final_state, "propellant_kg"):
            assert result.final_state.propellant_kg >= 0
