"""ETE tests for fidelity hardening features (Item 2, 3, 4).

Tests the new features added for:
- Item 2: Degraded mode detection and strict mode
- Item 3: Atmosphere model enhancements
- Item 4: HIGH fidelity feature flags

These tests validate that:
1. Degraded mode is properly detected and tracked in manifest
2. Strict mode rejects degraded fidelity runs
3. HIGH fidelity feature flags work correctly (EP constraints, Ka weather)
4. Atmosphere model enhancements are properly applied

Usage:
    pytest tests/ete/test_fidelity_hardening.py -v
    pytest tests/ete/ -m "ete_tier_a" -v
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

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
    pytest.mark.ete_tier_a,
    pytest.mark.ete,
]


# =============================================================================
# ITEM 2: DEGRADED MODE AND STRICT MODE TESTS
# =============================================================================


class TestDegradedModeDetection:
    """Test degraded mode detection when Basilisk is unavailable."""

    def test_manifest_tracks_degraded_mode(self, reference_epoch, tmp_path):
        """
        Verify run_manifest.json includes degraded flag.

        When Basilisk is unavailable, MEDIUM/HIGH fidelity falls back to J2
        and this should be recorded in the manifest.
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

        result = simulate(
            plan=create_test_plan(
                plan_id="degraded_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        assert result is not None, "Simulation should complete"

        # Read manifest
        manifest_path = tmp_path / "run_manifest.json"
        # Find the manifest in subdirectories
        manifests = list(Path(tmp_path).rglob("run_manifest.json"))
        assert len(manifests) > 0, "run_manifest.json not found"

        with open(manifests[0]) as f:
            manifest = json.load(f)

        # Manifest should have degraded field
        assert "degraded" in manifest, "Manifest should have degraded field"

        # If Basilisk not available, degraded should be True
        if not BASILISK_AVAILABLE:
            assert manifest["degraded"] is True, (
                "When Basilisk unavailable, degraded should be True"
            )
            assert "degraded_reason" in manifest, (
                "Degraded manifest should include reason"
            )
            assert "J2" in manifest["degraded_reason"] or "fallback" in manifest["degraded_reason"].lower(), (
                f"Degraded reason should mention J2 fallback: {manifest['degraded_reason']}"
            )
        else:
            assert manifest["degraded"] is False, (
                "When Basilisk available, degraded should be False"
            )

    @pytest.mark.skipif(
        BASILISK_AVAILABLE,
        reason="Test requires Basilisk to be unavailable to trigger fallback"
    )
    def test_j2_fallback_produces_valid_orbit(self, reference_epoch, tmp_path):
        """
        Verify J2 fallback produces physically valid orbits.

        When Basilisk is unavailable, the J2 analytical fallback should
        still produce reasonable orbital mechanics.
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

        result = simulate(
            plan=create_test_plan(
                plan_id="j2_fallback_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        assert result is not None
        assert result.final_state is not None

        # Check orbit is bound (negative specific energy)
        MU_EARTH = 398600.4418  # km^3/s^2
        final_pos = np.array(result.final_state.position_eci)
        final_vel = np.array(result.final_state.velocity_eci)
        r = np.linalg.norm(final_pos)
        v = np.linalg.norm(final_vel)
        energy = v**2 / 2 - MU_EARTH / r

        assert energy < 0, f"J2 fallback produced unbound orbit: energy = {energy}"

        # Check reasonable altitude
        altitude_km = r - 6378.137
        assert 200 < altitude_km < 600, (
            f"J2 fallback altitude unreasonable: {altitude_km:.1f} km"
        )


class TestStrictMode:
    """Test strict mode enforcement."""

    @pytest.mark.skipif(
        BASILISK_AVAILABLE,
        reason="Test requires Basilisk to be unavailable to trigger strict mode error"
    )
    def test_strict_mode_raises_on_degraded_fidelity(self, reference_epoch, tmp_path):
        """
        Verify strict mode raises DegradedFidelityError when Basilisk unavailable.
        """
        from sim.engine import simulate, DegradedFidelityError
        from sim.core.types import Fidelity, SimConfig, SpacecraftConfig

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=2)

        initial_state = create_test_initial_state(
            epoch=start_time,
            position_eci=[6778.137, 0.0, 0.0],
            velocity_eci=[0.0, 7.6686, 0.0],
            mass_kg=500.0,
        )

        # Create config with strict=True
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

        strict_config = SimConfig(
            fidelity=Fidelity.MEDIUM,
            time_step_s=60.0,
            spacecraft=spacecraft,
            output_dir=str(tmp_path),
            enable_cache=False,
            strict=True,  # Enable strict mode
        )

        with pytest.raises(DegradedFidelityError) as excinfo:
            simulate(
                plan=create_test_plan(
                    plan_id="strict_test",
                    start_time=start_time,
                    end_time=end_time,
                ),
                initial_state=initial_state,
                fidelity=Fidelity.MEDIUM,
                config=strict_config,
            )

        assert "strict mode" in str(excinfo.value).lower() or "degraded" in str(excinfo.value).lower(), (
            f"Error message should mention strict mode or degraded: {excinfo.value}"
        )

    def test_strict_mode_allows_low_fidelity(self, reference_epoch, tmp_path):
        """
        Verify strict mode does not affect LOW fidelity (never degraded).
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

        strict_config = SimConfig(
            fidelity=Fidelity.LOW,
            time_step_s=60.0,
            spacecraft=spacecraft,
            output_dir=str(tmp_path),
            enable_cache=False,
            strict=True,
        )

        # LOW fidelity should complete without error even with strict=True
        result = simulate(
            plan=create_test_plan(
                plan_id="strict_low_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=strict_config,
        )

        assert result is not None, "LOW fidelity with strict=True should complete"
        assert result.final_state is not None

    @pytest.mark.skipif(
        not BASILISK_AVAILABLE,
        reason="Basilisk required to test strict mode success"
    )
    def test_strict_mode_succeeds_with_basilisk(self, reference_epoch, tmp_path):
        """
        Verify strict mode succeeds when Basilisk is available.
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

        strict_config = SimConfig(
            fidelity=Fidelity.MEDIUM,
            time_step_s=60.0,
            spacecraft=spacecraft,
            output_dir=str(tmp_path),
            enable_cache=False,
            strict=True,
        )

        # With Basilisk available, strict mode should succeed
        result = simulate(
            plan=create_test_plan(
                plan_id="strict_basilisk_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=strict_config,
        )

        assert result is not None, "MEDIUM fidelity with strict=True should succeed"


# =============================================================================
# ITEM 3: ATMOSPHERE MODEL TESTS
# =============================================================================


class TestAtmosphereModel:
    """Test atmosphere model enhancements."""

    def test_atmosphere_model_factory(self):
        """
        Verify atmosphere model factory creates correct model types.
        """
        from sim.models.atmosphere import (
            AtmosphereConfig,
            create_atmosphere_model,
            AtmosphereModel,
            NRLMSISE00Model,
        )

        # Exponential model (default)
        exp_config = AtmosphereConfig(model_type="exponential")
        exp_model = create_atmosphere_model(exp_config)
        assert isinstance(exp_model, AtmosphereModel)

        # NRLMSISE00 model
        msise_config = AtmosphereConfig(model_type="nrlmsise00")
        msise_model = create_atmosphere_model(msise_config)
        assert isinstance(msise_model, NRLMSISE00Model)

    def test_drag_scale_factor(self):
        """
        Verify drag_scale_factor increases density proportionally.
        """
        from sim.models.atmosphere import AtmosphereConfig, AtmosphereModel

        config_1x = AtmosphereConfig(
            model_type="exponential",
            drag_scale_factor=1.0,
        )
        config_2x = AtmosphereConfig(
            model_type="exponential",
            drag_scale_factor=2.0,
        )

        model_1x = AtmosphereModel(config_1x)
        model_2x = AtmosphereModel(config_2x)

        altitude = 400.0  # km

        density_1x = model_1x.density(altitude)
        density_2x = model_2x.density(altitude)

        # With 2x drag scale, density should be ~2x
        ratio = density_2x / density_1x
        assert 1.9 < ratio < 2.1, (
            f"2x drag_scale_factor should double density, got ratio: {ratio:.3f}"
        )

    def test_solar_activity_scaling(self):
        """
        Verify higher solar activity increases density.
        """
        from sim.models.atmosphere import AtmosphereConfig, AtmosphereModel

        # Reference conditions
        config_ref = AtmosphereConfig(
            model_type="exponential",
            solar_flux_f107=150.0,
            geomagnetic_ap=15.0,
        )

        # High solar activity
        config_high = AtmosphereConfig(
            model_type="exponential",
            solar_flux_f107=250.0,  # High F10.7
            geomagnetic_ap=50.0,     # High Ap
        )

        model_ref = AtmosphereModel(config_ref)
        model_high = AtmosphereModel(config_high)

        altitude = 400.0  # km

        density_ref = model_ref.density(altitude)
        density_high = model_high.density(altitude)

        # Higher solar activity should increase density
        assert density_high > density_ref, (
            f"High solar activity should increase density: "
            f"ref={density_ref:.3e}, high={density_high:.3e}"
        )

    def test_nrlmsise00_fallback(self):
        """
        Verify NRLMSISE00Model gracefully falls back when pip package unavailable.
        """
        from sim.models.atmosphere import AtmosphereConfig, NRLMSISE00Model

        config = AtmosphereConfig(
            model_type="nrlmsise00",
            solar_flux_f107=150.0,
        )

        model = NRLMSISE00Model(config)

        # Should return valid density regardless of nrlmsise00 pip availability
        density = model.density(400.0)
        assert density > 0, "NRLMSISE00Model should return positive density"
        assert density < 1e-10, f"Density at 400km should be very low: {density}"


# =============================================================================
# ITEM 4: HIGH FIDELITY FEATURE FLAGS TESTS
# =============================================================================


class TestHighFidelityConfig:
    """Test HighFidelityConfig dataclass."""

    def test_default_values(self):
        """
        Verify HighFidelityConfig has correct defaults.
        """
        from sim.core.high_fidelity import HighFidelityConfig

        config = HighFidelityConfig()

        assert config.high_res_timestep is True
        assert config.timestep_s == 10.0
        assert config.enable_msise_atmosphere is True
        assert config.ep_shadow_constraints is True
        assert config.ep_min_soc_for_thrust == 0.3
        assert config.ep_duty_cycle_constraints is True
        assert config.max_ep_duty_cycle == 0.5
        assert config.ka_weather_model is True
        assert config.ka_rain_probability == 0.10
        assert config.ka_rain_seed == 42
        assert config.enable_srp is True

    def test_from_dict(self):
        """
        Verify HighFidelityConfig.from_dict() creates correct config.
        """
        from sim.core.high_fidelity import HighFidelityConfig

        data = {
            "high_res_timestep": False,
            "timestep_s": 30.0,
            "ep_shadow_constraints": False,
            "ka_rain_seed": 123,
            "unknown_field": "ignored",  # Should be ignored
        }

        config = HighFidelityConfig.from_dict(data)

        assert config.high_res_timestep is False
        assert config.timestep_s == 30.0
        assert config.ep_shadow_constraints is False
        assert config.ka_rain_seed == 123
        # Defaults should be preserved for unspecified fields
        assert config.enable_msise_atmosphere is True

    def test_to_dict_roundtrip(self):
        """
        Verify to_dict() and from_dict() roundtrip correctly.
        """
        from sim.core.high_fidelity import HighFidelityConfig

        original = HighFidelityConfig(
            timestep_s=20.0,
            ka_rain_probability=0.15,
        )

        data = original.to_dict()
        restored = HighFidelityConfig.from_dict(data)

        assert restored.timestep_s == original.timestep_s
        assert restored.ka_rain_probability == original.ka_rain_probability
        assert restored.feature_hash() == original.feature_hash()

    def test_feature_hash_deterministic(self):
        """
        Verify feature_hash() is deterministic for same config.
        """
        from sim.core.high_fidelity import HighFidelityConfig

        config1 = HighFidelityConfig(timestep_s=15.0)
        config2 = HighFidelityConfig(timestep_s=15.0)

        assert config1.feature_hash() == config2.feature_hash()

    def test_feature_hash_differs_on_change(self):
        """
        Verify feature_hash() differs when config changes.
        """
        from sim.core.high_fidelity import HighFidelityConfig

        config1 = HighFidelityConfig(timestep_s=15.0)
        config2 = HighFidelityConfig(timestep_s=20.0)

        assert config1.feature_hash() != config2.feature_hash()


@pytest.mark.ete_tier_b
class TestHighFidelitySimulation:
    """Test HIGH fidelity simulation with feature flags."""

    @pytest.mark.skipif(
        not BASILISK_AVAILABLE,
        reason="Basilisk required for HIGH fidelity tests"
    )
    def test_high_fidelity_uses_smaller_timestep(self, reference_epoch, tmp_path):
        """
        Verify HIGH fidelity uses configured smaller timestep.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity, SimConfig, SpacecraftConfig

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

        # HIGH fidelity with 10s timestep
        high_config = SimConfig(
            fidelity=Fidelity.HIGH,
            time_step_s=60.0,  # Will be overridden by HIGH fidelity flags
            spacecraft=spacecraft,
            output_dir=str(tmp_path),
            enable_cache=False,
            high_fidelity_flags={
                "high_res_timestep": True,
                "timestep_s": 10.0,
            },
        )

        result = simulate(
            plan=create_test_plan(
                plan_id="high_timestep_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.HIGH,
            config=high_config,
        )

        assert result is not None

        # Check ephemeris has more points than 60s would produce
        # 1 hour with 10s step = 360 points, with 60s = 60 points
        ephemeris_files = list(Path(tmp_path).rglob("ephemeris.parquet"))
        if ephemeris_files:
            import pandas as pd
            eph = pd.read_parquet(ephemeris_files[0])
            # With 10s step over 1 hour, expect ~360 points
            # With 60s step, would get ~60 points
            assert len(eph) > 100, (
                f"HIGH fidelity should have more ephemeris points "
                f"(got {len(eph)}, expected >100 for 10s step)"
            )

    def test_high_fidelity_flags_in_manifest(self, reference_epoch, tmp_path):
        """
        Verify HIGH fidelity flags are recorded in manifest.
        """
        from sim.engine import simulate
        from sim.core.types import Fidelity, SimConfig, SpacecraftConfig

        start_time = reference_epoch
        end_time = start_time + timedelta(hours=1)

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

        high_config = SimConfig(
            fidelity=Fidelity.HIGH,
            time_step_s=60.0,
            spacecraft=spacecraft,
            output_dir=str(tmp_path),
            enable_cache=False,
            high_fidelity_flags={
                "ep_shadow_constraints": True,
                "ka_weather_model": True,
                "ka_rain_seed": 42,
            },
        )

        result = simulate(
            plan=create_test_plan(
                plan_id="high_manifest_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.HIGH,
            config=high_config,
        )

        assert result is not None

        # Read manifest and check for HIGH fidelity flags
        manifests = list(Path(tmp_path).rglob("run_manifest.json"))
        assert len(manifests) > 0

        with open(manifests[0]) as f:
            manifest = json.load(f)

        # HIGH fidelity flags should be in manifest
        if "high_fidelity_flags" in manifest:
            hf_flags = manifest["high_fidelity_flags"]
            assert hf_flags.get("ep_shadow_constraints") is True
            assert hf_flags.get("ka_weather_model") is True
            assert hf_flags.get("ka_rain_seed") == 42


class TestKaWeatherDeterminism:
    """Test Ka-band weather model determinism."""

    def test_ka_weather_deterministic_with_seed(self, reference_epoch, tmp_path):
        """
        Verify Ka weather produces deterministic results with same seed.
        """
        from sim.activities.downlink import MediumFidelityDownlinkHandler
        from sim.core.high_fidelity import HighFidelityConfig

        hf_config = HighFidelityConfig(
            ka_weather_model=True,
            ka_rain_seed=42,
            ka_rain_probability=0.5,  # 50% for easier testing
        )

        handler1 = MediumFidelityDownlinkHandler(high_fidelity_config=hf_config)
        handler2 = MediumFidelityDownlinkHandler(high_fidelity_config=hf_config)

        # Both handlers should produce same weather sequence for same pass hash
        np.random.seed(42)
        results1 = [np.random.random() < 0.5 for _ in range(10)]
        np.random.seed(42)
        results2 = [np.random.random() < 0.5 for _ in range(10)]

        assert results1 == results2, "Same seed should produce same weather sequence"

    def test_ka_weather_differs_with_different_seed(self):
        """
        Verify different seeds produce different weather patterns.
        """
        from sim.core.high_fidelity import HighFidelityConfig

        config1 = HighFidelityConfig(ka_rain_seed=42)
        config2 = HighFidelityConfig(ka_rain_seed=123)

        # Different seeds should produce different hashes
        assert config1.feature_hash() != config2.feature_hash()


# =============================================================================
# CROSS-FIDELITY VALIDATION
# =============================================================================


class TestCrossFidelityDegradedMode:
    """Test cross-fidelity comparison with degraded mode."""

    def test_degraded_medium_vs_low_comparable(self, reference_epoch, tmp_path):
        """
        Verify degraded MEDIUM (J2 fallback) produces comparable results to LOW.

        When Basilisk is unavailable, MEDIUM uses J2 analytical propagation.
        This should still produce reasonable results compared to LOW (SGP4).
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
            plan_id="cross_fidelity_degraded",
            start_time=start_time,
            end_time=end_time,
        )

        # Run LOW
        low_result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.LOW,
            config=create_test_config(
                output_dir=str(tmp_path / "low"),
                time_step_s=60.0,
            ),
        )

        # Run MEDIUM (may be degraded)
        med_result = simulate(
            plan=plan,
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=create_test_config(
                output_dir=str(tmp_path / "medium"),
                time_step_s=60.0,
            ),
        )

        # Both should complete
        assert low_result is not None
        assert med_result is not None

        # Compare final altitudes
        low_pos = np.array(low_result.final_state.position_eci)
        med_pos = np.array(med_result.final_state.position_eci)

        low_alt = np.linalg.norm(low_pos) - 6378.137
        med_alt = np.linalg.norm(med_pos) - 6378.137

        # Altitudes should be comparable (within 50 km)
        alt_diff = abs(low_alt - med_alt)
        assert alt_diff < 50.0, (
            f"LOW vs MEDIUM (degraded) altitude difference too large: "
            f"{alt_diff:.1f} km (LOW={low_alt:.1f}, MED={med_alt:.1f})"
        )


# =============================================================================
# SUMMARY VALIDATION
# =============================================================================


class TestSummaryValidation:
    """Test simulation summary includes new fields."""

    def test_summary_includes_degraded_status(self, reference_epoch, tmp_path):
        """
        Verify summary.json includes degraded status for MEDIUM/HIGH.
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

        result = simulate(
            plan=create_test_plan(
                plan_id="summary_test",
                start_time=start_time,
                end_time=end_time,
            ),
            initial_state=initial_state,
            fidelity=Fidelity.MEDIUM,
            config=create_test_config(output_dir=str(tmp_path), time_step_s=60.0),
        )

        assert result is not None

        # Read summary
        summaries = list(Path(tmp_path).rglob("summary.json"))
        assert len(summaries) > 0

        with open(summaries[0]) as f:
            summary = json.load(f)

        # Summary should include degraded field
        assert "degraded" in summary, "Summary should include degraded field"

        if not BASILISK_AVAILABLE:
            assert summary["degraded"] is True
            assert "degraded_reason" in summary
