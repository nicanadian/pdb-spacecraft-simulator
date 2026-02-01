"""Adapter to convert GMAT case definitions to simulator inputs.

Maps GMAT validation scenarios to the simulator's data structures:
- CaseDefinition -> InitialState, PlanInput, SimConfig
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import numpy as np

from ..case_registry import (
    CaseDefinition,
    OrbitRegime,
    PropulsionType,
    get_case,
)


@dataclass
class SimScenario:
    """Complete scenario ready for simulator execution."""

    case_id: str
    case_def: CaseDefinition
    initial_state: "InitialState"
    plan: "PlanInput"
    config: "SimConfig"

    # Reference values for comparison
    epoch: datetime
    duration_s: float
    expected_final_sma_km: Optional[float] = None
    expected_propellant_used_kg: Optional[float] = None


class GmatToSimAdapter:
    """Converts GMAT case definitions to simulator inputs."""

    # Standard epoch for all validation cases (matches GMAT templates)
    DEFAULT_EPOCH = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

    # Earth parameters
    EARTH_RADIUS_KM = 6378.137
    MU_EARTH = 398600.4418  # km^3/s^2

    def __init__(self, epoch: Optional[datetime] = None):
        """
        Initialize adapter.

        Args:
            epoch: Override epoch for scenarios (default: 2025-01-15 00:00:00 UTC)
        """
        self.epoch = epoch or self.DEFAULT_EPOCH

    def create_scenario(
        self,
        case_id: str,
        overrides: Optional[Dict] = None,
    ) -> SimScenario:
        """
        Create a complete simulator scenario from a GMAT case.

        Args:
            case_id: GMAT case identifier (e.g., "R01", "N01")
            overrides: Optional parameter overrides

        Returns:
            SimScenario ready for execution
        """
        try:
            case_def = get_case(case_id)
        except KeyError:
            raise ValueError(f"Unknown case ID: {case_id}")

        overrides = overrides or {}

        # Get orbital parameters
        orbital_params = self._get_orbital_params(case_def, overrides)

        # Create initial state
        initial_state = self._create_initial_state(case_def, orbital_params)

        # Create activity plan
        plan = self._create_plan(case_def, orbital_params, overrides)

        # Create simulation config
        config = self._create_config(case_def, overrides)

        duration_s = case_def.duration_hours * 3600.0

        return SimScenario(
            case_id=case_id,
            case_def=case_def,
            initial_state=initial_state,
            plan=plan,
            config=config,
            epoch=self.epoch,
            duration_s=duration_s,
        )

    def _get_orbital_params(
        self,
        case_def: CaseDefinition,
        overrides: Dict,
    ) -> Dict:
        """Get orbital parameters for the case."""
        # Default parameters based on orbit regime
        if case_def.orbit_regime == OrbitRegime.VLEO:
            defaults = {
                "sma_km": 6678.137,  # ~300 km altitude
                "ecc": 0.0001,
                "inc_deg": 53.0,
                "raan_deg": 0.0,
                "aop_deg": 0.0,
                "ta_deg": 0.0,
            }
        elif case_def.orbit_regime == OrbitRegime.SSO:
            defaults = {
                "sma_km": 7078.137,  # ~700 km altitude
                "ecc": 0.0001,
                "inc_deg": 97.4,  # Sun-synchronous
                "raan_deg": 0.0,
                "aop_deg": 0.0,
                "ta_deg": 0.0,
            }
        else:  # LEO
            defaults = {
                "sma_km": 6878.137,  # ~500 km altitude
                "ecc": 0.0001,
                "inc_deg": 53.0,
                "raan_deg": 0.0,
                "aop_deg": 0.0,
                "ta_deg": 0.0,
            }

        # Apply overrides
        params = {**defaults, **overrides}
        return params

    def _create_initial_state(
        self,
        case_def: CaseDefinition,
        orbital_params: Dict,
    ) -> "InitialState":
        """Create InitialState from orbital parameters."""
        # Lazy import to avoid circular dependencies
        from sim.core.types import InitialState

        # Convert Keplerian to Cartesian
        position_eci, velocity_eci = self._keplerian_to_cartesian(
            sma_km=orbital_params["sma_km"],
            ecc=orbital_params["ecc"],
            inc_deg=orbital_params["inc_deg"],
            raan_deg=orbital_params["raan_deg"],
            aop_deg=orbital_params["aop_deg"],
            ta_deg=orbital_params["ta_deg"],
        )

        # Spacecraft mass properties
        dry_mass_kg = 450.0
        propellant_kg = 50.0

        return InitialState(
            epoch=self.epoch,
            position_eci=position_eci,
            velocity_eci=velocity_eci,
            mass_kg=dry_mass_kg + propellant_kg,
            propellant_kg=propellant_kg,
            battery_soc=1.0,
            storage_used_gb=0.0,
        )

    def _create_plan(
        self,
        case_def: CaseDefinition,
        orbital_params: Dict,
        overrides: Dict,
    ) -> "PlanInput":
        """Create activity plan based on case type."""
        from sim.core.types import Activity, PlanInput

        activities = []
        duration_s = case_def.duration_hours * 3600.0

        # Create activities based on propulsion type and category
        if case_def.propulsion == PropulsionType.EP:
            activities = self._create_ep_activities(
                case_def, orbital_params, duration_s, overrides
            )
        elif case_def.propulsion == PropulsionType.CHEMICAL_FB:
            activities = self._create_chemical_activities(
                case_def, orbital_params, duration_s, overrides
            )
        else:
            # Pure propagation - just idle
            activities = [
                Activity(
                    activity_id=f"{case_def.case_id}_coast",
                    activity_type="idle",
                    start_time=self.epoch,
                    end_time=self.epoch + timedelta(seconds=duration_s),
                    parameters={},
                )
            ]

        return PlanInput(
            spacecraft_id="ValidationSC",
            plan_id=f"gmat_{case_def.case_id}",
            activities=activities,
        )

    def _create_ep_activities(
        self,
        case_def: CaseDefinition,
        orbital_params: Dict,
        duration_s: float,
        overrides: Dict,
    ) -> List["Activity"]:
        """Create EP thrust activities."""
        from sim.core.types import Activity

        activities = []

        # EP parameters
        thrust_mN = overrides.get("thrust_mN", 100.0)
        thrust_n = thrust_mN / 1000.0
        isp_s = overrides.get("isp_s", 1500.0)
        power_w = overrides.get("power_w", 1500.0)

        # For drag makeup scenarios (N01, N02, N03), use continuous or periodic thrust
        if case_def.category in ["ep_modeling", "drag_makeup", "duty_cycle"]:
            # Simplified: periodic thrust arcs
            orbit_period_s = self._orbital_period(orbital_params["sma_km"])
            num_orbits = int(duration_s / orbit_period_s)

            # Thrust for 10 minutes per orbit at apogee
            thrust_duration_s = 600.0

            for i in range(min(num_orbits, 100)):  # Cap at 100 burns
                thrust_start = self.epoch + timedelta(
                    seconds=i * orbit_period_s + orbit_period_s / 2 - thrust_duration_s / 2
                )
                thrust_end = thrust_start + timedelta(seconds=thrust_duration_s)

                if thrust_end > self.epoch + timedelta(seconds=duration_s):
                    break

                activities.append(
                    Activity(
                        activity_id=f"{case_def.case_id}_thrust_{i:03d}",
                        activity_type="orbit_lower",  # Generic EP thrust
                        start_time=thrust_start,
                        end_time=thrust_end,
                        parameters={
                            "thrust_n": thrust_n,
                            "isp_s": isp_s,
                            "power_w": power_w,
                            "target_altitude_km": orbital_params["sma_km"] - self.EARTH_RADIUS_KM,
                        },
                    )
                )
        else:
            # Single thrust arc for simple cases
            thrust_duration_s = min(3600.0, duration_s / 2)
            activities.append(
                Activity(
                    activity_id=f"{case_def.case_id}_thrust",
                    activity_type="orbit_lower",
                    start_time=self.epoch,
                    end_time=self.epoch + timedelta(seconds=thrust_duration_s),
                    parameters={
                        "thrust_n": thrust_n,
                        "isp_s": isp_s,
                        "power_w": power_w,
                        "target_altitude_km": orbital_params["sma_km"] - self.EARTH_RADIUS_KM - 10,
                    },
                )
            )

        # Fill gaps with idle activities
        activities = self._fill_idle_gaps(activities, duration_s)

        return activities

    def _create_chemical_activities(
        self,
        case_def: CaseDefinition,
        orbital_params: Dict,
        duration_s: float,
        overrides: Dict,
    ) -> List["Activity"]:
        """Create chemical propulsion activities (station keeping)."""
        from sim.core.types import Activity

        activities = []

        # For station keeping, create periodic maintenance burns
        if case_def.category == "station_keeping":
            # SK burn every ~day
            sk_interval_s = 86400.0
            burn_duration_s = 10.0  # Impulsive-like

            current_time = self.epoch
            end_time = self.epoch + timedelta(seconds=duration_s)
            burn_count = 0

            while current_time < end_time and burn_count < 20:
                activities.append(
                    Activity(
                        activity_id=f"{case_def.case_id}_sk_{burn_count:03d}",
                        activity_type="station_keeping",
                        start_time=current_time,
                        end_time=current_time + timedelta(seconds=burn_duration_s),
                        parameters={
                            "delta_v_m_s": 0.1,  # Small SK maneuver
                            "target_altitude_km": orbital_params["sma_km"] - self.EARTH_RADIUS_KM,
                        },
                    )
                )
                current_time += timedelta(seconds=sk_interval_s)
                burn_count += 1
        else:
            # Single finite burn
            burn_duration_s = min(300.0, duration_s / 10)
            activities.append(
                Activity(
                    activity_id=f"{case_def.case_id}_burn",
                    activity_type="orbit_lower",
                    start_time=self.epoch,
                    end_time=self.epoch + timedelta(seconds=burn_duration_s),
                    parameters={
                        "delta_v_m_s": 10.0,
                    },
                )
            )

        # Fill gaps with idle
        activities = self._fill_idle_gaps(activities, duration_s)

        return activities

    def _fill_idle_gaps(
        self,
        activities: List["Activity"],
        total_duration_s: float,
    ) -> List["Activity"]:
        """Fill gaps between activities with idle periods."""
        from sim.core.types import Activity

        if not activities:
            return [
                Activity(
                    activity_id="idle_full",
                    activity_type="idle",
                    start_time=self.epoch,
                    end_time=self.epoch + timedelta(seconds=total_duration_s),
                    parameters={},
                )
            ]

        # Sort by start time
        activities = sorted(activities, key=lambda a: a.start_time)

        filled = []
        current_time = self.epoch

        for i, activity in enumerate(activities):
            # Add idle before this activity if there's a gap
            if activity.start_time > current_time:
                filled.append(
                    Activity(
                        activity_id=f"idle_{i}",
                        activity_type="idle",
                        start_time=current_time,
                        end_time=activity.start_time,
                        parameters={},
                    )
                )

            filled.append(activity)
            current_time = activity.end_time

        # Add final idle if needed
        end_time = self.epoch + timedelta(seconds=total_duration_s)
        if current_time < end_time:
            filled.append(
                Activity(
                    activity_id="idle_final",
                    activity_type="idle",
                    start_time=current_time,
                    end_time=end_time,
                    parameters={},
                )
            )

        return filled

    def _create_config(
        self,
        case_def: CaseDefinition,
        overrides: Dict,
    ) -> "SimConfig":
        """Create simulation configuration."""
        from sim.core.types import SimConfig, SpacecraftConfig, Fidelity

        # Determine fidelity based on case requirements
        if "high_fidelity" in case_def.force_models or case_def.orbit_regime == OrbitRegime.VLEO:
            fidelity = Fidelity.HIGH
        elif "drag" in case_def.force_models:
            fidelity = Fidelity.MEDIUM
        else:
            fidelity = Fidelity.LOW

        # Override fidelity if specified
        if "fidelity" in overrides:
            fidelity = Fidelity[overrides["fidelity"].upper()]

        # Time step based on fidelity
        time_step_s = {
            Fidelity.LOW: 60.0,
            Fidelity.MEDIUM: 30.0,
            Fidelity.HIGH: 10.0,
        }.get(fidelity, 60.0)

        spacecraft_config = SpacecraftConfig(
            spacecraft_id="ValidationSC",
            dry_mass_kg=450.0,
            initial_propellant_kg=50.0,
            battery_capacity_wh=1000.0,
            storage_capacity_gb=100.0,
            solar_panel_area_m2=10.0,
            solar_efficiency=0.28,
            base_power_w=100.0,
        )

        return SimConfig(
            fidelity=fidelity,
            time_step_s=time_step_s,
            spacecraft=spacecraft_config,
            output_dir=f"validation/output/{case_def.case_id}",
            enable_cache=False,  # Disable for validation
            random_seed=42,
        )

    def _keplerian_to_cartesian(
        self,
        sma_km: float,
        ecc: float,
        inc_deg: float,
        raan_deg: float,
        aop_deg: float,
        ta_deg: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert Keplerian orbital elements to Cartesian state vector.

        Returns:
            Tuple of (position_eci, velocity_eci) in km and km/s
        """
        # Convert angles to radians
        inc = np.radians(inc_deg)
        raan = np.radians(raan_deg)
        aop = np.radians(aop_deg)
        ta = np.radians(ta_deg)

        # Semi-latus rectum
        p = sma_km * (1 - ecc**2)

        # Position in orbital plane
        r = p / (1 + ecc * np.cos(ta))

        # Position and velocity in perifocal frame
        r_pqw = np.array([
            r * np.cos(ta),
            r * np.sin(ta),
            0.0
        ])

        v_pqw = np.sqrt(self.MU_EARTH / p) * np.array([
            -np.sin(ta),
            ecc + np.cos(ta),
            0.0
        ])

        # Rotation matrix from perifocal to ECI
        cos_raan, sin_raan = np.cos(raan), np.sin(raan)
        cos_aop, sin_aop = np.cos(aop), np.sin(aop)
        cos_inc, sin_inc = np.cos(inc), np.sin(inc)

        R = np.array([
            [cos_raan * cos_aop - sin_raan * sin_aop * cos_inc,
             -cos_raan * sin_aop - sin_raan * cos_aop * cos_inc,
             sin_raan * sin_inc],
            [sin_raan * cos_aop + cos_raan * sin_aop * cos_inc,
             -sin_raan * sin_aop + cos_raan * cos_aop * cos_inc,
             -cos_raan * sin_inc],
            [sin_aop * sin_inc,
             cos_aop * sin_inc,
             cos_inc]
        ])

        # Transform to ECI
        position_eci = R @ r_pqw
        velocity_eci = R @ v_pqw

        return position_eci, velocity_eci

    def _orbital_period(self, sma_km: float) -> float:
        """Calculate orbital period in seconds."""
        return 2 * np.pi * np.sqrt(sma_km**3 / self.MU_EARTH)
