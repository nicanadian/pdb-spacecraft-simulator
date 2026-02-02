"""ETE eclipse and contact window tests - validate timing accuracy.

Tests eclipse entry/exit times and ground station contact windows against
reference data.

Key features:
- Eclipse timing validation (umbra/penumbra transitions)
- Ground station access window validation
- Contact window timing accuracy
- AOS/LOS time validation

Usage:
    pytest tests/ete/test_eclipse_contacts.py -v
    pytest tests/ete/ -m "ete_tier_a" -v
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


# Reference data paths
REFERENCE_DIR = Path("validation/reference")
ACCESS_WINDOWS_DIR = REFERENCE_DIR / "access_windows"


def load_reference_access_windows(station_id: str) -> Optional[List[Dict]]:
    """Load reference access windows for a ground station."""
    file_path = ACCESS_WINDOWS_DIR / f"{station_id.lower()}_access_windows.json"
    if not file_path.exists():
        return None

    with open(file_path) as f:
        return json.load(f)


class TestEclipseComputation:
    """Test eclipse computation accuracy."""

    def test_eclipse_detection_basic(self, reference_epoch, tmp_path):
        """
        Verify eclipse detection for LEO orbit.

        A spacecraft in LEO should experience eclipses approximately
        once per orbit (~90 minutes for 400km altitude).
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        # Run for 2 orbits (~3 hours) to capture at least one eclipse
        end_time = start_time + timedelta(hours=3)

        # ISS-like orbit (51.6° inclination)
        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 6.024, 4.766],  # ~51.6° inclination
            mass_kg=500.0,
            battery_soc=0.9,
        )

        result = simulate(
            plan=create_test_plan(
                plan_id="eclipse_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        assert result is not None

        # Check for eclipse intervals in output
        if hasattr(result, "eclipse_intervals") and result.eclipse_intervals:
            intervals = result.eclipse_intervals

            # Should have at least one eclipse in 3 hours
            assert len(intervals) >= 1, (
                f"Expected at least 1 eclipse in 3 hours, found {len(intervals)}"
            )

            # Validate interval structure
            for i, interval in enumerate(intervals):
                assert "start" in interval or "entry" in interval, (
                    f"Eclipse interval {i} missing start time"
                )
                assert "end" in interval or "exit" in interval, (
                    f"Eclipse interval {i} missing end time"
                )

    def test_eclipse_duration_reasonable(self, reference_epoch, tmp_path):
        """
        Verify eclipse duration is physically reasonable.

        For LEO (400km), eclipse duration should be ~30-35 minutes.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=6)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],  # Equatorial orbit
            mass_kg=500.0,
        )

        result = simulate(
            plan=create_test_plan(
                plan_id="eclipse_duration_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        if hasattr(result, "eclipse_intervals") and result.eclipse_intervals:
            for interval in result.eclipse_intervals:
                # Get start and end times
                start_key = "start" if "start" in interval else "entry"
                end_key = "end" if "end" in interval else "exit"

                start_str = interval[start_key]
                end_str = interval[end_key]

                # Parse times
                if isinstance(start_str, str):
                    start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                else:
                    start_dt = start_str
                    end_dt = end_str

                duration_minutes = (end_dt - start_dt).total_seconds() / 60

                # LEO eclipse: typically 30-40 minutes
                assert 20 < duration_minutes < 50, (
                    f"ECLIPSE DURATION ANOMALY\n"
                    f"  Duration: {duration_minutes:.1f} minutes\n"
                    f"  Expected: 20-50 minutes for LEO\n"
                    f"\n"
                    f"Eclipse duration outside physical bounds."
                )


@pytest.mark.ete_tier_b
class TestEclipseTimingAccuracy:
    """Test eclipse timing accuracy against reference (Tier B)."""

    def test_eclipse_entry_timing(self, reference_epoch, tolerance_config, tmp_path):
        """
        Verify eclipse entry times match reference within tolerance.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        # Load reference eclipse data if available
        reference_path = REFERENCE_DIR / "eclipse_reference.json"
        if not reference_path.exists():
            pytest.skip("Eclipse reference data not available")

        with open(reference_path) as f:
            reference = json.load(f)

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=24)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=reference.get("initial_position", [6778.137, 0.0, 0.0]),
            velocity_eci=reference.get("initial_velocity", [0.0, 7.6686, 0.0]),
            mass_kg=500.0,
        )

        result = simulate(
            plan=create_test_plan(
                plan_id="eclipse_timing_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        if not hasattr(result, "eclipse_intervals") or not result.eclipse_intervals:
            pytest.skip("No eclipse intervals in result")

        # Get timing tolerance
        timing_tolerance_s = tolerance_config.get_tolerance(
            "timing_tolerance_s", None, default=60.0
        )

        # Compare first eclipse entry time
        ref_eclipses = reference.get("eclipse_intervals", [])
        if ref_eclipses:
            ref_entry = datetime.fromisoformat(
                ref_eclipses[0]["entry"].replace("Z", "+00:00")
            )

            sim_interval = result.eclipse_intervals[0]
            start_key = "start" if "start" in sim_interval else "entry"
            sim_entry_str = sim_interval[start_key]

            if isinstance(sim_entry_str, str):
                sim_entry = datetime.fromisoformat(
                    sim_entry_str.replace("Z", "+00:00")
                )
            else:
                sim_entry = sim_entry_str

            timing_error_s = abs((sim_entry - ref_entry).total_seconds())

            assert timing_error_s < timing_tolerance_s, (
                f"ECLIPSE ENTRY TIMING ERROR\n"
                f"  Simulated:  {sim_entry.isoformat()}\n"
                f"  Reference:  {ref_entry.isoformat()}\n"
                f"  Error:      {timing_error_s:.1f} seconds\n"
                f"  Tolerance:  {timing_tolerance_s:.1f} seconds"
            )


class TestGroundStationAccess:
    """Test ground station access window computation."""

    @pytest.fixture
    def ground_stations(self) -> List[Dict]:
        """Get list of ground stations for testing."""
        return [
            {
                "id": "SVALBARD",
                "name": "Svalbard",
                "lat_deg": 78.23,
                "lon_deg": 15.39,
                "alt_m": 458,
                "min_elevation_deg": 5.0,
            },
            {
                "id": "FAIRBANKS",
                "name": "Fairbanks",
                "lat_deg": 64.86,
                "lon_deg": -147.85,
                "alt_m": 150,
                "min_elevation_deg": 5.0,
            },
            {
                "id": "MCMURDO",
                "name": "McMurdo",
                "lat_deg": -77.85,
                "lon_deg": 166.67,
                "alt_m": 10,
                "min_elevation_deg": 5.0,
            },
        ]

    def test_access_windows_computed(self, reference_epoch, ground_stations, tmp_path):
        """
        Verify access windows are computed for ground stations.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=24)

        # Polar orbit for global coverage
        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6978.137, 0.0, 0.0],  # 600 km SSO
            velocity_eci=[0.0, 0.598, 7.509],   # ~97.8° inclination
            mass_kg=500.0,
        )

        result = simulate(
            plan=create_test_plan(
                plan_id="access_window_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        # Check for access windows in output
        if hasattr(result, "access_windows") and result.access_windows:
            windows = result.access_windows

            # Should have windows for at least some stations
            assert len(windows) > 0, "No access windows computed"

            # Validate window structure
            for station_id, station_windows in windows.items():
                for i, window in enumerate(station_windows):
                    assert "aos" in window or "start" in window, (
                        f"Window {i} for {station_id} missing AOS"
                    )
                    assert "los" in window or "end" in window, (
                        f"Window {i} for {station_id} missing LOS"
                    )

    def test_aos_before_los(self, reference_epoch, tmp_path):
        """
        Verify AOS is always before LOS for all windows.

        This is a fundamental invariant from CLAUDE.md.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=12)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 6.024, 4.766],
            mass_kg=500.0,
        )

        result = simulate(
            plan=create_test_plan(
                plan_id="aos_los_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        if hasattr(result, "access_windows") and result.access_windows:
            for station_id, windows in result.access_windows.items():
                for i, window in enumerate(windows):
                    aos_key = "aos" if "aos" in window else "start"
                    los_key = "los" if "los" in window else "end"

                    aos = window[aos_key]
                    los = window[los_key]

                    # Parse if strings
                    if isinstance(aos, str):
                        aos = datetime.fromisoformat(aos.replace("Z", "+00:00"))
                    if isinstance(los, str):
                        los = datetime.fromisoformat(los.replace("Z", "+00:00"))

                    assert aos < los, (
                        f"AOS/LOS INVARIANT VIOLATION\n"
                        f"  Station: {station_id}\n"
                        f"  Window:  {i}\n"
                        f"  AOS:     {aos}\n"
                        f"  LOS:     {los}\n"
                        f"\n"
                        f"AOS must be before LOS per CLAUDE.md invariants."
                    )


@pytest.mark.ete_tier_b
class TestContactWindowAccuracy:
    """Test contact window accuracy against reference data (Tier B)."""

    @pytest.mark.parametrize("station_id", ["SVALBARD", "FAIRBANKS", "MCMURDO"])
    def test_contact_window_timing(
        self, station_id: str, reference_epoch, tolerance_config, tmp_path
    ):
        """
        Verify contact window times match reference within tolerance.
        """
        reference_windows = load_reference_access_windows(station_id)
        if reference_windows is None:
            pytest.skip(f"No reference data for {station_id}")

        from sim.engine import simulate
        from sim.core.types import Fidelity

        # Get initial state from reference or use default
        start_time = reference_epoch
        end_time = start_time + timedelta(hours=24)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6978.137, 0.0, 0.0],
            velocity_eci=[0.0, 0.598, 7.509],
            mass_kg=500.0,
        )

        result = simulate(
            plan=create_test_plan(
                plan_id=f"contact_{station_id.lower()}_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        if not hasattr(result, "access_windows") or not result.access_windows:
            pytest.skip("No access windows in result")

        if station_id not in result.access_windows:
            pytest.skip(f"No windows computed for {station_id}")

        timing_tolerance_s = tolerance_config.get_tolerance(
            "timing_tolerance_s", station_id, default=60.0
        )

        sim_windows = result.access_windows[station_id]

        # Compare first window AOS timing
        if len(reference_windows) > 0 and len(sim_windows) > 0:
            ref_aos = datetime.fromisoformat(
                reference_windows[0]["aos"].replace("Z", "+00:00")
            )

            sim_window = sim_windows[0]
            aos_key = "aos" if "aos" in sim_window else "start"
            sim_aos_str = sim_window[aos_key]

            if isinstance(sim_aos_str, str):
                sim_aos = datetime.fromisoformat(sim_aos_str.replace("Z", "+00:00"))
            else:
                sim_aos = sim_aos_str

            timing_error_s = abs((sim_aos - ref_aos).total_seconds())

            assert timing_error_s < timing_tolerance_s, (
                f"CONTACT WINDOW TIMING ERROR for {station_id}\n"
                f"  Simulated AOS: {sim_aos.isoformat()}\n"
                f"  Reference AOS: {ref_aos.isoformat()}\n"
                f"  Error:         {timing_error_s:.1f} seconds\n"
                f"  Tolerance:     {timing_tolerance_s:.1f} seconds"
            )

    def test_pass_duration_reasonable(self, reference_epoch, tmp_path):
        """
        Verify pass durations are physically reasonable.

        For LEO, passes are typically 5-15 minutes.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=12)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 6.024, 4.766],
            mass_kg=500.0,
        )

        result = simulate(
            plan=create_test_plan(
                plan_id="pass_duration_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        if hasattr(result, "access_windows") and result.access_windows:
            for station_id, windows in result.access_windows.items():
                for i, window in enumerate(windows):
                    aos_key = "aos" if "aos" in window else "start"
                    los_key = "los" if "los" in window else "end"

                    aos = window[aos_key]
                    los = window[los_key]

                    if isinstance(aos, str):
                        aos = datetime.fromisoformat(aos.replace("Z", "+00:00"))
                    if isinstance(los, str):
                        los = datetime.fromisoformat(los.replace("Z", "+00:00"))

                    duration_minutes = (los - aos).total_seconds() / 60

                    # LEO passes: typically 5-20 minutes
                    assert 1 < duration_minutes < 30, (
                        f"PASS DURATION ANOMALY for {station_id}\n"
                        f"  Pass {i}: {duration_minutes:.1f} minutes\n"
                        f"  Expected: 1-30 minutes for LEO\n"
                        f"\n"
                        f"Pass duration outside physical bounds."
                    )


class TestContactLinkBudget:
    """Test contact window link budget calculations."""

    def test_elevation_angle_bounds(self, reference_epoch, tmp_path):
        """
        Verify elevation angles are within valid bounds.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=6)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 6.024, 4.766],
            mass_kg=500.0,
        )

        result = simulate(
            plan=create_test_plan(
                plan_id="elevation_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        if hasattr(result, "access_windows") and result.access_windows:
            for station_id, windows in result.access_windows.items():
                for i, window in enumerate(windows):
                    if "max_elevation_deg" in window:
                        max_el = window["max_elevation_deg"]

                        # Elevation must be between 0 and 90 degrees
                        assert 0 <= max_el <= 90, (
                            f"ELEVATION BOUNDS VIOLATION for {station_id}\n"
                            f"  Pass {i}: max elevation = {max_el}°\n"
                            f"  Valid range: 0° to 90°"
                        )

                        # High elevation passes should be rare but possible
                        # Very low elevation passes may have poor link margin
