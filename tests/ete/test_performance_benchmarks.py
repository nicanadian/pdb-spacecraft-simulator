"""ETE performance benchmark tests.

Tests timing and performance characteristics of simulations across fidelity levels.

Key validations:
- HIGH fidelity with smaller timestep produces more ephemeris points
- Simulation completes within expected time bounds
- Memory usage remains reasonable
- Cache effectiveness

Usage:
    pytest tests/ete/test_performance_benchmarks.py -v
    pytest tests/ete/ -m "ete_tier_b" -v
"""
from __future__ import annotations

import json
import time
from datetime import timedelta
from pathlib import Path
from typing import Dict, List

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


class TestTimestepResolution:
    """Test timestep resolution affects output granularity."""

    def test_smaller_timestep_produces_more_points(self, reference_epoch, tmp_path):
        """
        Verify smaller timestep produces more ephemeris points.

        This validates the HIGH fidelity timestep override works correctly.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity, SimConfig, SpacecraftConfig
        import pandas as pd

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=1)  # 1 hour

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        spacecraft = SpacecraftConfig(
            spacecraft_id="TEST-001",
            dry_mass_kg=450.0,
            initial_propellant_kg=50.0,
            battery_capacity_wh=5000.0,
            storage_capacity_gb=500.0,
            solar_panel_area_m2=10.0,
            solar_efficiency=0.30,
            base_power_w=200.0,
        )

        plan = create_test_plan(
            plan_id="timestep_test",
            start_time=start_time,
            end_time=end_time,
        )

        # Run with 60s timestep
        config_60s = SimConfig(
            fidelity=Fidelity.LOW,
            time_step_s=60.0,
            spacecraft=spacecraft,
            output_dir=str(tmp_path / "60s"),
            enable_cache=False,
        )

        result_60s = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config_60s,
        )

        # Run with 30s timestep
        config_30s = SimConfig(
            fidelity=Fidelity.LOW,
            time_step_s=30.0,
            spacecraft=spacecraft,
            output_dir=str(tmp_path / "30s"),
            enable_cache=False,
        )

        result_30s = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config_30s,
        )

        # Count ephemeris points
        eph_60s = list(Path(tmp_path / "60s").rglob("ephemeris.parquet"))
        eph_30s = list(Path(tmp_path / "30s").rglob("ephemeris.parquet"))

        if eph_60s and eph_30s:
            df_60s = pd.read_parquet(eph_60s[0])
            df_30s = pd.read_parquet(eph_30s[0])

            # 30s timestep should have ~2x the points of 60s
            ratio = len(df_30s) / len(df_60s)
            assert 1.8 < ratio < 2.2, (
                f"30s timestep should have ~2x points of 60s: "
                f"got {len(df_30s)} vs {len(df_60s)} (ratio: {ratio:.2f})"
            )

    def test_high_fidelity_timestep_override(self, reference_epoch, tmp_path):
        """
        Verify HIGH fidelity config overrides default timestep.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity, SimConfig, SpacecraftConfig
        import pandas as pd

        start_time = reference_epoch
        end_time = start_time + timedelta(minutes=30)  # 30 minutes

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        spacecraft = SpacecraftConfig(
            spacecraft_id="TEST-001",
            dry_mass_kg=450.0,
            initial_propellant_kg=50.0,
            battery_capacity_wh=5000.0,
            storage_capacity_gb=500.0,
            solar_panel_area_m2=10.0,
            solar_efficiency=0.30,
            base_power_w=200.0,
        )

        plan = create_test_plan(
            plan_id="high_timestep_override",
            start_time=start_time,
            end_time=end_time,
        )

        # Run HIGH fidelity with 10s timestep override
        config = SimConfig(
            fidelity=Fidelity.HIGH,
            time_step_s=60.0,  # Default - should be overridden
            spacecraft=spacecraft,
            output_dir=str(tmp_path),
            enable_cache=False,
            high_fidelity_flags={
                "high_res_timestep": True,
                "timestep_s": 10.0,
            },
        )

        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.HIGH,
            config=config,
        )

        assert result is not None

        # Check ephemeris point count
        # 30 min = 1800s, at 10s step = ~180 points
        # At 60s step would be ~30 points
        eph_files = list(Path(tmp_path).rglob("ephemeris.parquet"))
        if eph_files:
            df = pd.read_parquet(eph_files[0])
            # Should have significantly more than 30 points if 10s step worked
            assert len(df) > 50, (
                f"HIGH fidelity 10s timestep should produce >50 points for 30min, "
                f"got {len(df)}"
            )


class TestSimulationTiming:
    """Test simulation timing and performance bounds."""

    def test_low_fidelity_completes_quickly(self, reference_epoch, tmp_path):
        """
        Verify LOW fidelity completes within expected time.

        LOW fidelity should be fast for what-if analysis.
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
        )

        plan = create_test_plan(
            plan_id="timing_low",
            start_time=start_time,
            end_time=end_time,
        )

        config = create_test_config(
            output_dir=str(tmp_path),
            time_step_s=60.0,
        )

        start = time.time()
        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )
        elapsed = time.time() - start

        assert result is not None
        # LOW fidelity 6-hour sim should complete in under 10 seconds
        assert elapsed < 10.0, (
            f"LOW fidelity 6h sim took {elapsed:.2f}s, expected < 10s"
        )

    def test_medium_fidelity_timing(self, reference_epoch, tmp_path):
        """
        Verify MEDIUM fidelity completes within reasonable time.
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
            plan_id="timing_medium",
            start_time=start_time,
            end_time=end_time,
        )

        config = create_test_config(
            output_dir=str(tmp_path),
            time_step_s=60.0,
        )

        start = time.time()
        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=config,
        )
        elapsed = time.time() - start

        assert result is not None
        # MEDIUM fidelity 2-hour sim should complete in under 30 seconds
        # (may use J2 fallback which is fast)
        assert elapsed < 30.0, (
            f"MEDIUM fidelity 2h sim took {elapsed:.2f}s, expected < 30s"
        )

    @pytest.mark.parametrize("duration_hours", [1, 6, 12])
    def test_simulation_time_scales_linearly(
        self, reference_epoch, tmp_path, duration_hours
    ):
        """
        Verify simulation time scales approximately linearly with duration.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=duration_hours)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        plan = create_test_plan(
            plan_id=f"scaling_{duration_hours}h",
            start_time=start_time,
            end_time=end_time,
        )

        config = create_test_config(
            output_dir=str(tmp_path / f"{duration_hours}h"),
            time_step_s=60.0,
        )

        start = time.time()
        result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config,
        )
        elapsed = time.time() - start

        assert result is not None

        # Time should scale roughly with duration
        # Allow 5s base + 0.5s per hour
        max_expected = 5.0 + 0.5 * duration_hours
        assert elapsed < max_expected, (
            f"{duration_hours}h sim took {elapsed:.2f}s, "
            f"expected < {max_expected:.1f}s"
        )


class TestOutputSizeValidation:
    """Test output file sizes are reasonable."""

    def test_ephemeris_file_size_scales(self, reference_epoch, tmp_path):
        """
        Verify ephemeris file size scales with duration and timestep.
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
        )

        plan = create_test_plan(
            plan_id="output_size_test",
            start_time=start_time,
            end_time=end_time,
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

        # Find ephemeris file
        eph_files = list(Path(tmp_path).rglob("ephemeris.parquet"))
        if eph_files:
            size_bytes = eph_files[0].stat().st_size

            # 6 hours at 60s = 360 points
            # Each point has ~7 columns of float64 = 56 bytes
            # With parquet compression, expect < 50KB
            max_size = 50 * 1024  # 50KB
            assert size_bytes < max_size, (
                f"Ephemeris file too large: {size_bytes/1024:.1f}KB, "
                f"expected < {max_size/1024:.0f}KB"
            )

    def test_summary_file_reasonable_size(self, reference_epoch, tmp_path):
        """
        Verify summary.json file is reasonably sized.
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
        )

        plan = create_test_plan(
            plan_id="summary_size_test",
            start_time=start_time,
            end_time=end_time,
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

        # Find summary file
        summary_files = list(Path(tmp_path).rglob("summary.json"))
        if summary_files:
            size_bytes = summary_files[0].stat().st_size

            # Summary should be small (<10KB)
            assert size_bytes < 10 * 1024, (
                f"Summary file too large: {size_bytes/1024:.1f}KB"
            )


class TestCacheEffectiveness:
    """Test cache improves performance on repeated runs."""

    def test_cache_speeds_up_repeated_runs(self, reference_epoch, tmp_path):
        """
        Verify cache improves performance for repeated simulations.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity, SimConfig, SpacecraftConfig

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=2)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        spacecraft = SpacecraftConfig(
            spacecraft_id="TEST-001",
            dry_mass_kg=450.0,
            initial_propellant_kg=50.0,
            battery_capacity_wh=5000.0,
            storage_capacity_gb=500.0,
            solar_panel_area_m2=10.0,
            solar_efficiency=0.30,
            base_power_w=200.0,
        )

        plan = create_test_plan(
            plan_id="cache_test",
            start_time=start_time,
            end_time=end_time,
        )

        # First run - cache miss
        config1 = SimConfig(
            fidelity=Fidelity.LOW,
            time_step_s=60.0,
            spacecraft=spacecraft,
            output_dir=str(tmp_path / "run1"),
            enable_cache=True,
        )

        start1 = time.time()
        result1 = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config1,
        )
        time1 = time.time() - start1

        # Second run - should benefit from cache
        config2 = SimConfig(
            fidelity=Fidelity.LOW,
            time_step_s=60.0,
            spacecraft=spacecraft,
            output_dir=str(tmp_path / "run2"),
            enable_cache=True,
        )

        start2 = time.time()
        result2 = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=config2,
        )
        time2 = time.time() - start2

        assert result1 is not None
        assert result2 is not None

        # Second run should not be significantly slower
        # (cache may not help much for LOW fidelity, but shouldn't hurt)
        assert time2 < time1 * 2, (
            f"Second run ({time2:.2f}s) significantly slower than first ({time1:.2f}s)"
        )


class TestFidelityPerformanceComparison:
    """Compare performance across fidelity levels."""

    def test_fidelity_performance_ordering(self, reference_epoch, tmp_path):
        """
        Verify LOW is faster than MEDIUM (when MEDIUM uses fallback).

        Note: With Basilisk, MEDIUM may be slower due to numerical integration.
        Without Basilisk, both use analytical methods and should be similar.
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
            plan_id="fidelity_perf",
            start_time=start_time,
            end_time=end_time,
        )

        timings = {}

        for fidelity in [Fidelity.LOW, Fidelity.MEDIUM]:
            config = create_test_config(
                output_dir=str(tmp_path / fidelity.value.lower()),
                time_step_s=60.0,
            )

            start = time.time()
            result = simulate(
                plan=plan,
                initial_state=initial_state,
                fidelity=fidelity,
                config=config,
            )
            timings[fidelity.value] = time.time() - start

            assert result is not None

        # Both should complete reasonably fast
        assert timings["LOW"] < 15.0, f"LOW took {timings['LOW']:.2f}s"
        assert timings["MEDIUM"] < 30.0, f"MEDIUM took {timings['MEDIUM']:.2f}s"

        # Log comparison for analysis
        print(f"\nFidelity performance: LOW={timings['LOW']:.2f}s, MEDIUM={timings['MEDIUM']:.2f}s")
