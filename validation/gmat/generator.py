"""GMAT script generator using Jinja2 templates."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import numpy as np
from jinja2 import Environment, FileSystemLoader

from sim.core.types import InitialState
from sim.models.orbit import EARTH_RADIUS_KM, MU_EARTH


@dataclass
class GroundStationDef:
    """Ground station definition for GMAT scripts."""

    id: str
    lat_deg: float
    lon_deg: float
    alt_km: float = 0.0
    min_el_deg: float = 5.0


@dataclass
class ThrustArcDef:
    """Thrust arc definition for GMAT scripts."""

    arc_id: int
    start_elapsed_s: float
    end_elapsed_s: float
    start_ta_deg: float
    end_ta_deg: float


@dataclass
class ScenarioConfig:
    """Configuration for a validation scenario."""

    scenario_id: str
    scenario_name: str
    epoch: datetime
    duration_hours: float
    spacecraft_name: str = "ValidationSC"

    # Orbital elements
    sma_km: float = 6878.137  # 500 km altitude
    ecc: float = 0.0001
    inc_deg: float = 53.0
    raan_deg: float = 0.0
    aop_deg: float = 0.0
    ta_deg: float = 0.0

    # Physical properties
    dry_mass_kg: float = 450.0
    propellant_kg: float = 50.0
    drag_area_m2: float = 5.0
    srp_area_m2: float = 10.0

    # EP thruster (optional)
    has_ep_thruster: bool = False
    thrust_mN: float = 100.0  # milliNewtons
    isp_s: float = 1500.0
    max_power_kw: float = 1.5
    thrusts_per_orbit: int = 2
    thrust_arc_deg: float = 30.0

    # Thrust arcs for orbit lowering
    thrust_arcs: List[ThrustArcDef] = field(default_factory=list)

    # Ground stations
    ground_stations: List[GroundStationDef] = field(default_factory=list)

    # Propagator settings
    high_fidelity: bool = False
    include_drag: bool = True
    f107: float = 150.0
    f107a: float = 150.0
    kp: float = 3.0
    integrator_type: str = "RungeKutta89"
    initial_step_s: float = 60.0
    accuracy: float = 1e-12
    min_step_s: float = 0.001
    max_step_s: float = 2700.0

    # Output settings
    report_step_s: float = 60.0
    locator_step_s: float = 10.0
    output_dir: str = "validation/gmat/output"

    @property
    def duration_s(self) -> float:
        """Duration in seconds."""
        return self.duration_hours * 3600.0

    @property
    def thrust_arc_s(self) -> float:
        """Duration of each thrust arc in seconds."""
        orbit_period = 2 * np.pi * np.sqrt(self.sma_km**3 / MU_EARTH)
        return (self.thrust_arc_deg / 360.0) * orbit_period

    @property
    def mass_flow_coeff(self) -> float:
        """Mass flow rate coefficient (kg/s per kW)."""
        # mass_flow = thrust / (Isp * g0)
        thrust_n = self.thrust_mN / 1000.0
        g0 = 9.80665  # m/s^2
        mass_flow = thrust_n / (self.isp_s * g0)
        return mass_flow * 1000.0  # per kW

    @property
    def thrust_dir_1(self) -> float:
        """Thrust direction velocity component (retrograde for lowering)."""
        return -1.0 if self.sma_km > EARTH_RADIUS_KM + 400 else 1.0

    @property
    def thrust_dir_2(self) -> float:
        """Thrust direction normal component."""
        return 0.0

    @property
    def thrust_dir_3(self) -> float:
        """Thrust direction binormal component."""
        return 0.0

    @property
    def end_epoch(self) -> str:
        """End epoch as GMAT string."""
        end = self.epoch + timedelta(hours=self.duration_hours)
        return end.strftime("%d %b %Y %H:%M:%S.000")

    @classmethod
    def from_initial_state(
        cls,
        scenario_id: str,
        initial_state: InitialState,
        duration_hours: float = 12.0,
        **kwargs
    ) -> "ScenarioConfig":
        """Create config from simulator InitialState."""
        from sim.models.orbit import OrbitPropagator

        # Get orbital elements from state vector
        r = initial_state.position_eci
        v = initial_state.velocity_eci

        r_mag = np.linalg.norm(r)
        v_mag = np.linalg.norm(v)

        # Specific angular momentum
        h = np.cross(r, v)
        h_mag = np.linalg.norm(h)

        # Node vector
        n = np.cross([0, 0, 1], h)
        n_mag = np.linalg.norm(n)

        # Eccentricity vector
        e_vec = ((v_mag**2 - MU_EARTH / r_mag) * r - np.dot(r, v) * v) / MU_EARTH
        ecc = np.linalg.norm(e_vec)

        # Semi-major axis
        energy = v_mag**2 / 2 - MU_EARTH / r_mag
        sma = -MU_EARTH / (2 * energy) if abs(ecc - 1.0) > 1e-10 else float("inf")

        # Inclination
        inc = np.degrees(np.arccos(h[2] / h_mag))

        # RAAN
        if n_mag > 1e-10:
            raan = np.arccos(n[0] / n_mag)
            if n[1] < 0:
                raan = 2 * np.pi - raan
            raan = np.degrees(raan)
        else:
            raan = 0.0

        # Argument of perigee
        if n_mag > 1e-10 and ecc > 1e-10:
            aop = np.arccos(np.dot(n, e_vec) / (n_mag * ecc))
            if e_vec[2] < 0:
                aop = 2 * np.pi - aop
            aop = np.degrees(aop)
        else:
            aop = 0.0

        # True anomaly
        if ecc > 1e-10:
            ta = np.arccos(np.dot(e_vec, r) / (ecc * r_mag))
            if np.dot(r, v) < 0:
                ta = 2 * np.pi - ta
            ta = np.degrees(ta)
        else:
            ta = np.arccos(np.dot(n, r) / (n_mag * r_mag))
            if r[2] < 0:
                ta = 2 * np.pi - ta
            ta = np.degrees(ta)

        return cls(
            scenario_id=scenario_id,
            scenario_name=f"Scenario_{scenario_id}",
            epoch=initial_state.epoch,
            duration_hours=duration_hours,
            sma_km=sma,
            ecc=max(ecc, 0.0001),  # GMAT needs small non-zero ecc
            inc_deg=inc,
            raan_deg=raan,
            aop_deg=aop,
            ta_deg=ta,
            dry_mass_kg=initial_state.mass_kg - initial_state.propellant_kg,
            propellant_kg=initial_state.propellant_kg,
            **kwargs
        )


class GMATScriptGenerator:
    """Generator for GMAT validation scripts."""

    def __init__(self, template_dir: Optional[Path] = None):
        """
        Initialize generator.

        Args:
            template_dir: Path to template directory. Defaults to
                validation/gmat/templates.
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"

        self.template_dir = Path(template_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        self.env.filters["gmat_epoch"] = self._format_gmat_epoch

    def _format_gmat_epoch(self, dt: datetime) -> str:
        """Format datetime as GMAT epoch string."""
        return dt.strftime("%d %b %Y %H:%M:%S.000")

    def generate_pure_propagation_script(
        self,
        config: ScenarioConfig,
        output_path: Optional[Path] = None,
    ) -> str:
        """
        Generate pure propagation validation script.

        Args:
            config: Scenario configuration
            output_path: Path to write script (optional)

        Returns:
            Generated script content
        """
        template = self.env.get_template("pure_propagation.tpl")

        context = {
            # Scenario
            "scenario_id": config.scenario_id,
            "scenario_name": config.scenario_name,
            "epoch": self._format_gmat_epoch(config.epoch),
            "duration_hours": config.duration_hours,
            "duration_s": config.duration_s,
            "report_step_s": config.report_step_s,

            # Spacecraft
            "spacecraft_name": config.spacecraft_name,
            "sma_km": config.sma_km,
            "ecc": config.ecc,
            "inc_deg": config.inc_deg,
            "raan_deg": config.raan_deg,
            "aop_deg": config.aop_deg,
            "ta_deg": config.ta_deg,
            "dry_mass_kg": config.dry_mass_kg,
            "drag_area_m2": config.drag_area_m2,
            "srp_area_m2": config.srp_area_m2,
            "has_ep_thruster": False,

            # Propagator
            "force_model_name": "FM_Validation",
            "propagator_name": "Prop_Validation",
            "high_fidelity": config.high_fidelity,
            "include_drag": config.include_drag,
            "f107": config.f107,
            "f107a": config.f107a,
            "kp": config.kp,
            "integrator_type": config.integrator_type,
            "initial_step_s": config.initial_step_s,
            "accuracy": config.accuracy,
            "min_step_s": config.min_step_s,
            "max_step_s": config.max_step_s,

            # Output
            "output_dir": config.output_dir,
        }

        script = template.render(**context)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(script)

        return script

    def generate_orbit_lowering_script(
        self,
        config: ScenarioConfig,
        output_path: Optional[Path] = None,
    ) -> str:
        """
        Generate orbit lowering validation script.

        Args:
            config: Scenario configuration with EP thruster settings
            output_path: Path to write script (optional)

        Returns:
            Generated script content
        """
        template = self.env.get_template("orbit_lowering.tpl")

        # Ensure EP thruster is enabled
        config.has_ep_thruster = True

        # Calculate thrust arcs if not provided
        if not config.thrust_arcs:
            config.thrust_arcs = self._calculate_thrust_arcs(config)

        context = {
            # Scenario
            "scenario_id": config.scenario_id,
            "scenario_name": config.scenario_name,
            "epoch": self._format_gmat_epoch(config.epoch),
            "duration_hours": config.duration_hours,
            "duration_s": config.duration_s,
            "report_step_s": config.report_step_s,
            "start_altitude_km": config.sma_km - EARTH_RADIUS_KM,
            "target_altitude_km": config.sma_km - EARTH_RADIUS_KM - 100,

            # Spacecraft
            "spacecraft_name": config.spacecraft_name,
            "sma_km": config.sma_km,
            "ecc": config.ecc,
            "inc_deg": config.inc_deg,
            "raan_deg": config.raan_deg,
            "aop_deg": config.aop_deg,
            "ta_deg": config.ta_deg,
            "dry_mass_kg": config.dry_mass_kg,
            "propellant_kg": config.propellant_kg,
            "drag_area_m2": config.drag_area_m2,
            "srp_area_m2": config.srp_area_m2,

            # EP Thruster
            "has_ep_thruster": True,
            "thrust_mN": config.thrust_mN,
            "isp_s": config.isp_s,
            "max_power_kw": config.max_power_kw,
            "mass_flow_coeff": config.mass_flow_coeff,
            "thrust_dir_1": config.thrust_dir_1,
            "thrust_dir_2": config.thrust_dir_2,
            "thrust_dir_3": config.thrust_dir_3,
            "thrusts_per_orbit": config.thrusts_per_orbit,
            "thrust_arc_s": config.thrust_arc_s,
            "thrust_arcs": config.thrust_arcs,

            # Propagator
            "force_model_name": "FM_Validation",
            "propagator_name": "Prop_Validation",
            "high_fidelity": config.high_fidelity,
            "include_drag": config.include_drag,
            "f107": config.f107,
            "f107a": config.f107a,
            "kp": config.kp,
            "integrator_type": config.integrator_type,
            "initial_step_s": config.initial_step_s,
            "accuracy": config.accuracy,
            "min_step_s": config.min_step_s,
            "max_step_s": config.max_step_s,

            # Output
            "output_dir": config.output_dir,
        }

        script = template.render(**context)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(script)

        return script

    def generate_ground_station_access_script(
        self,
        config: ScenarioConfig,
        output_path: Optional[Path] = None,
    ) -> str:
        """
        Generate ground station access validation script.

        Args:
            config: Scenario configuration with ground stations
            output_path: Path to write script (optional)

        Returns:
            Generated script content
        """
        template = self.env.get_template("ground_station_access.tpl")

        # Add default ground stations if none provided
        if not config.ground_stations:
            config.ground_stations = self._get_default_stations()

        context = {
            # Scenario
            "scenario_id": config.scenario_id,
            "scenario_name": config.scenario_name,
            "epoch": self._format_gmat_epoch(config.epoch),
            "end_epoch": config.end_epoch,
            "duration_hours": config.duration_hours,
            "duration_s": config.duration_s,
            "report_step_s": config.report_step_s,
            "locator_step_s": config.locator_step_s,

            # Spacecraft
            "spacecraft_name": config.spacecraft_name,
            "sma_km": config.sma_km,
            "ecc": config.ecc,
            "inc_deg": config.inc_deg,
            "raan_deg": config.raan_deg,
            "aop_deg": config.aop_deg,
            "ta_deg": config.ta_deg,
            "dry_mass_kg": config.dry_mass_kg,
            "drag_area_m2": config.drag_area_m2,
            "srp_area_m2": config.srp_area_m2,
            "has_ep_thruster": False,

            # Ground stations
            "ground_stations": config.ground_stations,

            # Propagator
            "force_model_name": "FM_Validation",
            "propagator_name": "Prop_Validation",
            "high_fidelity": config.high_fidelity,
            "include_drag": config.include_drag,
            "f107": config.f107,
            "f107a": config.f107a,
            "kp": config.kp,
            "integrator_type": config.integrator_type,
            "initial_step_s": config.initial_step_s,
            "accuracy": config.accuracy,
            "min_step_s": config.min_step_s,
            "max_step_s": config.max_step_s,

            # Output
            "output_dir": config.output_dir,
        }

        script = template.render(**context)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(script)

        return script

    def _calculate_thrust_arcs(self, config: ScenarioConfig) -> List[ThrustArcDef]:
        """Calculate thrust arc schedule for orbit lowering."""
        arcs = []

        orbit_period = 2 * np.pi * np.sqrt(config.sma_km**3 / MU_EARTH)
        arc_duration = config.thrust_arc_s
        half_arc = arc_duration / 2.0

        # Positions for thrust arcs (evenly distributed)
        positions_deg = np.linspace(0, 360, config.thrusts_per_orbit, endpoint=False)

        num_orbits = int(config.duration_s / orbit_period) + 1
        arc_id = 0

        for orbit in range(num_orbits):
            orbit_start_s = orbit * orbit_period

            for pos_deg in positions_deg:
                center_time_s = orbit_start_s + (pos_deg / 360.0) * orbit_period
                start_s = center_time_s - half_arc
                end_s = center_time_s + half_arc

                if start_s < 0:
                    continue
                if end_s > config.duration_s:
                    break

                arcs.append(ThrustArcDef(
                    arc_id=arc_id,
                    start_elapsed_s=start_s,
                    end_elapsed_s=end_s,
                    start_ta_deg=pos_deg - config.thrust_arc_deg / 2,
                    end_ta_deg=pos_deg + config.thrust_arc_deg / 2,
                ))
                arc_id += 1

        return arcs

    def _get_default_stations(self) -> List[GroundStationDef]:
        """Get default ground stations for access validation."""
        return [
            GroundStationDef(
                id="Svalbard",
                lat_deg=78.2306,
                lon_deg=15.3894,
                alt_km=0.0,
                min_el_deg=5.0,
            ),
            GroundStationDef(
                id="Fairbanks",
                lat_deg=64.8601,
                lon_deg=-147.8522,
                alt_km=0.0,
                min_el_deg=5.0,
            ),
            GroundStationDef(
                id="McMurdo",
                lat_deg=-77.8467,
                lon_deg=166.6683,
                alt_km=0.0,
                min_el_deg=5.0,
            ),
        ]


def generate_all_scripts(output_dir: Optional[Path] = None):
    """Generate all validation scripts with default scenarios."""
    from datetime import timezone

    if output_dir is None:
        output_dir = Path(__file__).parent / "scripts"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generator = GMATScriptGenerator()

    # Base epoch for all scenarios
    epoch = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

    # Pure propagation scenario
    prop_config = ScenarioConfig(
        scenario_id="pure_prop_12h",
        scenario_name="Pure Propagation 12-hour",
        epoch=epoch,
        duration_hours=12.0,
        sma_km=EARTH_RADIUS_KM + 500,
        inc_deg=53.0,
    )
    generator.generate_pure_propagation_script(
        prop_config,
        output_dir / "pure_propagation.script"
    )

    # Orbit lowering scenario
    lowering_config = ScenarioConfig(
        scenario_id="orbit_lowering_12h",
        scenario_name="Orbit Lowering 500-400 km",
        epoch=epoch,
        duration_hours=12.0,
        sma_km=EARTH_RADIUS_KM + 500,
        inc_deg=53.0,
        has_ep_thruster=True,
        thrust_mN=100.0,
        isp_s=1500.0,
    )
    generator.generate_orbit_lowering_script(
        lowering_config,
        output_dir / "orbit_lowering.script"
    )

    # Ground station access scenario
    access_config = ScenarioConfig(
        scenario_id="access_24h",
        scenario_name="Ground Station Access 24-hour",
        epoch=epoch,
        duration_hours=24.0,
        sma_km=EARTH_RADIUS_KM + 500,
        inc_deg=53.0,
    )
    generator.generate_ground_station_access_script(
        access_config,
        output_dir / "ground_station_access.script"
    )

    print(f"Generated scripts in {output_dir}")


if __name__ == "__main__":
    generate_all_scripts()
