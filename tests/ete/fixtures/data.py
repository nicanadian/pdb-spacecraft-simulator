"""Test data fixtures for ETE tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional


# Import GMAT case registry for case IDs
try:
    from validation.gmat.case_registry import (
        TIER_A_CASES,
        TIER_B_CASES,
        CaseDefinition,
        get_case,
    )

    GMAT_AVAILABLE = True
except ImportError:
    GMAT_AVAILABLE = False
    TIER_A_CASES = []
    TIER_B_CASES = []


@dataclass
class ScenarioData:
    """Test scenario data."""

    case_id: str
    name: str
    duration_hours: float
    fidelity: str = "MEDIUM"
    start_time: Optional[datetime] = None
    tle: Optional[str] = None
    activities: List[Dict] = field(default_factory=list)

    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.now(timezone.utc) + timedelta(hours=1)


@dataclass
class CompletedRunData:
    """Data from a completed simulation run."""

    path: str
    case_id: str
    event_count: int
    constraint_violations: int
    manifest: Dict = field(default_factory=dict)

    @classmethod
    def from_run_dir(cls, run_dir: Path, case_id: str) -> "CompletedRunData":
        """
        Create from a completed run directory.

        Args:
            run_dir: Path to run output directory
            case_id: Case identifier

        Returns:
            CompletedRunData instance
        """
        import json

        # Load manifest
        manifest_path = run_dir / "viz" / "run_manifest.json"
        manifest = {}
        if manifest_path.exists():
            with open(manifest_path) as f:
                manifest = json.load(f)

        # Load events
        events_path = run_dir / "viz" / "events.json"
        event_count = 0
        constraint_violations = 0
        if events_path.exists():
            with open(events_path) as f:
                events = json.load(f)
                if isinstance(events, list):
                    event_count = len(events)
                    constraint_violations = sum(
                        1 for e in events if "violation" in e.get("type", "")
                    )
                elif isinstance(events, dict):
                    event_list = events.get("events", [])
                    event_count = len(event_list)
                    constraint_violations = sum(
                        1 for e in event_list if "violation" in e.get("type", "")
                    )

        return cls(
            path=str(run_dir),
            case_id=case_id,
            event_count=event_count,
            constraint_violations=constraint_violations,
            manifest=manifest,
        )


def get_tier_a_case_ids() -> List[str]:
    """Get list of Tier A case IDs for parametrized tests."""
    if GMAT_AVAILABLE:
        return [case.case_id for case in TIER_A_CASES]
    # Fallback default cases
    return ["R01", "R04", "R05", "R07", "R08", "R09", "R11"]


def get_tier_b_case_ids() -> List[str]:
    """Get list of Tier B case IDs for parametrized tests."""
    if GMAT_AVAILABLE:
        return [case.case_id for case in TIER_B_CASES]
    # Fallback default cases
    return ["N01", "N02", "N03", "N04", "N05", "N06"]


def create_test_plan(
    case_id: str,
    start_time: Optional[datetime] = None,
) -> Dict:
    """
    Create a test plan dictionary for a given case.

    Args:
        case_id: GMAT case ID
        start_time: Plan start time (defaults to now + 1 hour)

    Returns:
        Plan dictionary suitable for simulation
    """
    if start_time is None:
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)

    # Get case definition if available
    duration_hours = 24.0
    activities = []

    if GMAT_AVAILABLE:
        try:
            case_def = get_case(case_id)
            duration_hours = case_def.duration_hours

            # Create activities based on case type
            if case_def.propulsion.value in ["chemical_fb", "ep"]:
                # Add orbit maintenance activity
                activities.append(
                    {
                        "id": f"{case_id}_activity_1",
                        "type": "orbit_maintain",
                        "start_offset_hours": 0.5,
                        "duration_hours": min(2.0, duration_hours - 1),
                    }
                )

            if case_def.category == "eclipse":
                # Add power monitoring activity
                activities.append(
                    {
                        "id": f"{case_id}_activity_2",
                        "type": "power_monitor",
                        "start_offset_hours": 0.0,
                        "duration_hours": duration_hours,
                    }
                )

        except KeyError:
            pass

    end_time = start_time + timedelta(hours=duration_hours)

    return {
        "plan_id": f"ete_test_{case_id}",
        "case_id": case_id,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_hours": duration_hours,
        "activities": [
            {
                "id": act["id"],
                "activity_type": act["type"],
                "start_time": (
                    start_time + timedelta(hours=act["start_offset_hours"])
                ).isoformat(),
                "end_time": (
                    start_time
                    + timedelta(hours=act["start_offset_hours"] + act["duration_hours"])
                ).isoformat(),
                "parameters": {},
            }
            for act in activities
        ],
    }


# Sample TLEs for testing
SAMPLE_TLES = {
    "ISS": (
        "1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9992\n"
        "2 25544  51.6400 208.9163 0006703 274.9993  85.0352 15.50377559  1000"
    ),
    "STARLINK": (
        "1 44713U 19074A   24001.50000000  .00000578  00000-0  45632-4 0  9995\n"
        "2 44713  53.0539 284.2468 0001502  98.2419 261.8793 15.06388762  1000"
    ),
    "SSO": (
        "1 28654U 05007A   24001.50000000  .00000100  00000-0  18200-4 0  9998\n"
        "2 28654  98.1234  45.6789 0001234  90.1234 270.1234 14.57654321  1000"
    ),
}


def get_sample_tle(orbit_type: str = "ISS") -> str:
    """
    Get a sample TLE for testing.

    Args:
        orbit_type: Type of orbit ("ISS", "STARLINK", "SSO")

    Returns:
        TLE string
    """
    return SAMPLE_TLES.get(orbit_type.upper(), SAMPLE_TLES["ISS"])
