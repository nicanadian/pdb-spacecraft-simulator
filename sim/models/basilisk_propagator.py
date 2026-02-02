"""
Basilisk-based orbit propagator for MEDIUM and HIGH fidelity simulations.

This module provides a propagator implementation using the Basilisk
simulation framework when available. Falls back to a J2-perturbed
analytical propagation if Basilisk is not installed.

Basilisk Integration Features:
- Numerical orbit propagation with RK4 integration
- Earth gravity with optional spherical harmonics (J2)
- Exponential atmosphere model for drag effects
- Drag effector with configurable area and Cd
- Forward propagation with state extraction at arbitrary epochs

Configuration:
- gravity_degree: Spherical harmonics degree (0=point mass, 2=J2)
- enable_drag: Enable atmospheric drag modeling
- integration_step_s: RK4 integration timestep
- area_m2, cd: Drag parameters
- mass_kg: Spacecraft mass for drag and maneuvers

Usage:
    from sim.models.basilisk_propagator import BasiliskPropagator, BasiliskConfig

    config = BasiliskConfig(gravity_degree=2, enable_drag=True)
    prop = BasiliskPropagator(config=config)
    prop.initialize(position_eci, velocity_eci, epoch)

    result = prop.propagate(target_epoch)
    print(f"Altitude: {result.altitude_km} km")

Requirements:
- Basilisk astrodynamics framework (https://github.com/AVSLab/basilisk)
- Build from source: python3 conanfile.py
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

from sim.core.types import Fidelity, InitialState
from sim.models.propagator_base import (
    EphemerisPoint,
    ManeuverResult,
    PropagatorConfig,
    PropagatorInterface,
)


logger = logging.getLogger(__name__)

# Earth constants
EARTH_MU = 398600.4418  # km^3/s^2
EARTH_RADIUS = 6378.137  # km
EARTH_J2 = 1.08263e-3
EARTH_OMEGA = 7.2921150e-5  # rad/s - Earth rotation rate


def _check_basilisk_available() -> bool:
    """Check if Basilisk is installed and available."""
    try:
        import Basilisk
        return True
    except ImportError:
        return False


BASILISK_AVAILABLE = _check_basilisk_available()


@dataclass
class BasiliskConfig(PropagatorConfig):
    """Configuration specific to Basilisk propagator."""

    integration_method: str = "rk4"
    integration_step_s: float = 10.0
    gravity_degree: int = 20
    gravity_order: int = 20
    enable_drag: bool = True
    enable_srp: bool = False
    enable_albedo: bool = False
    enable_earth_ir: bool = False
    enable_third_body: bool = False
    # Spacecraft properties
    mass_kg: float = 500.0
    area_m2: float = 10.0
    cd: float = 2.2  # Drag coefficient
    cr: float = 1.2  # SRP coefficient
    # Atmosphere model
    atmosphere_model: str = "exponential"  # exponential or msise
    base_density: float = 1e-12  # kg/m^3 at reference altitude
    scale_height: float = 8500.0  # m


class BasiliskPropagator(PropagatorInterface):
    """
    Basilisk-based orbit propagator.

    Provides numerical propagation with configurable force models
    for MEDIUM and HIGH fidelity simulations.

    If Basilisk is not installed, this class provides a fallback
    J2-perturbed analytical propagation.
    """

    def __init__(
        self,
        initial_state: Optional[InitialState] = None,
        epoch: Optional[datetime] = None,
        fidelity: Fidelity = Fidelity.MEDIUM,
        config: Optional[BasiliskConfig] = None,
    ):
        self._fidelity = fidelity
        self._config = config or BasiliskConfig.for_fidelity(fidelity.value)

        self._epoch: Optional[datetime] = None
        self._position: Optional[NDArray[np.float64]] = None
        self._velocity: Optional[NDArray[np.float64]] = None
        self._initial_epoch: Optional[datetime] = None

        # Basilisk simulation objects (if available)
        self._bsk_sim = None
        self._bsk_spacecraft = None
        self._bsk_gravity = None
        self._bsk_atmo = None
        self._bsk_drag = None
        self._bsk_process = None
        self._bsk_task = None
        self._sim_time_ns: int = 0  # Current simulation time in nanoseconds

        if initial_state is not None:
            self.initialize(
                position_eci=np.array(initial_state.position_eci),
                velocity_eci=np.array(initial_state.velocity_eci),
                epoch=epoch or initial_state.epoch,
            )

    def initialize(
        self,
        position_eci: NDArray[np.float64],
        velocity_eci: NDArray[np.float64],
        epoch: datetime,
    ) -> None:
        """Initialize propagator with state vector."""
        self._position = np.array(position_eci, dtype=np.float64)
        self._velocity = np.array(velocity_eci, dtype=np.float64)
        if epoch.tzinfo is None:
            epoch = epoch.replace(tzinfo=timezone.utc)
        self._epoch = epoch
        self._initial_epoch = epoch
        self._sim_time_ns = 0

        if BASILISK_AVAILABLE:
            self._init_basilisk()
        else:
            logger.info("Basilisk not available, using J2 analytical fallback")

    def _init_basilisk(self) -> None:
        """Initialize Basilisk simulation environment with full force models."""
        try:
            from Basilisk.utilities import SimulationBaseClass
            from Basilisk.utilities import macros as mc
            from Basilisk.utilities import orbitalMotion
            from Basilisk.utilities import simIncludeGravBody
            from Basilisk.utilities import simSetPlanetEnvironment
            from Basilisk.simulation import spacecraft
            from Basilisk.simulation import exponentialAtmosphere
            from Basilisk.simulation import dragDynamicEffector

            # Create simulation
            self._bsk_sim = SimulationBaseClass.SimBaseClass()

            # Create process and task
            process_name = "DynamicsProcess"
            task_name = "DynamicsTask"
            self._bsk_process = self._bsk_sim.CreateNewProcess(process_name)

            # Integration timestep in nanoseconds (sec2nano is a function)
            dt_ns = int(mc.sec2nano(self._config.integration_step_s))
            self._bsk_task = self._bsk_sim.CreateNewTask(task_name, dt_ns)
            self._bsk_process.addTask(self._bsk_task)

            # Create spacecraft
            self._bsk_spacecraft = spacecraft.Spacecraft()
            self._bsk_spacecraft.ModelTag = "spacecraft"

            # Set spacecraft mass properties
            self._bsk_spacecraft.hub.mHub = self._config.mass_kg

            # Set initial state (Basilisk uses meters internally)
            # Position and velocity must be lists, not numpy arrays
            pos_m = (self._position * 1000).tolist()  # km -> m
            vel_m_s = (self._velocity * 1000).tolist()  # km/s -> m/s
            self._bsk_spacecraft.hub.r_CN_NInit = pos_m
            self._bsk_spacecraft.hub.v_CN_NInit = vel_m_s

            # Add spacecraft to simulation task
            self._bsk_sim.AddModelToTask(task_name, self._bsk_spacecraft)

            # Set up gravity using the gravBodyFactory utility
            gravFactory = simIncludeGravBody.gravBodyFactory()
            planet = gravFactory.createEarth()
            planet.isCentralBody = True

            # Enable spherical harmonics if degree > 0
            if self._config.gravity_degree > 0:
                from Basilisk.utilities.supportDataTools.dataFetcher import get_path, DataFile
                try:
                    ggm03s_path = get_path(DataFile.LocalGravData.GGM03S_J2_only)
                    planet.useSphericalHarmonicsGravityModel(
                        str(ggm03s_path),
                        min(self._config.gravity_degree, 2)  # GGM03S_J2_only has only J2
                    )
                    logger.debug(f"Using spherical harmonics gravity (deg={self._config.gravity_degree})")
                except Exception as e:
                    logger.warning(f"Could not load spherical harmonics: {e}, using point mass")

            # Attach gravity to spacecraft
            gravFactory.addBodiesTo(self._bsk_spacecraft)
            self._bsk_gravity = gravFactory

            # Configure drag if enabled
            if self._config.enable_drag:
                self._setup_drag_model(mc, task_name)

            # Initialize simulation
            self._bsk_sim.InitializeSimulation()

            logger.info(
                f"Basilisk simulation initialized: gravity_deg={self._config.gravity_degree}, "
                f"drag={self._config.enable_drag}"
            )

        except Exception as e:
            logger.warning(f"Basilisk initialization failed: {e}, falling back to J2")
            import traceback
            logger.debug(traceback.format_exc())
            self._bsk_sim = None

    def _setup_drag_model(self, mc, task_name: str) -> None:
        """Set up atmospheric drag model."""
        try:
            from Basilisk.simulation import exponentialAtmosphere
            from Basilisk.simulation import dragDynamicEffector
            from Basilisk.utilities import simSetPlanetEnvironment

            # Create exponential atmosphere model
            self._bsk_atmo = exponentialAtmosphere.ExponentialAtmosphere()
            self._bsk_atmo.ModelTag = "ExpAtmo"

            # Use the utility to configure Earth atmosphere with proper parameters
            simSetPlanetEnvironment.exponentialAtmosphere(self._bsk_atmo, "earth")

            # Add atmosphere to task
            self._bsk_sim.AddModelToTask(task_name, self._bsk_atmo)

            # Subscribe atmosphere to spacecraft state
            self._bsk_atmo.addSpacecraftToModel(self._bsk_spacecraft.scStateOutMsg)

            # Create drag effector
            self._bsk_drag = dragDynamicEffector.DragDynamicEffector()
            self._bsk_drag.ModelTag = "DragEffector"
            self._bsk_drag.coreParams.projectedArea = self._config.area_m2
            self._bsk_drag.coreParams.dragCoeff = self._config.cd

            # Connect drag to atmosphere
            self._bsk_drag.atmoDensInMsg.subscribeTo(self._bsk_atmo.envOutMsgs[0])

            # Add drag as dynamic effector to spacecraft
            self._bsk_spacecraft.addDynamicEffector(self._bsk_drag)

            # Create separate task for drag (following Basilisk example pattern)
            drag_task_name = "DragTask"
            dt_ns = int(mc.sec2nano(self._config.integration_step_s))
            self._bsk_process.addTask(self._bsk_sim.CreateNewTask(drag_task_name, dt_ns))
            self._bsk_sim.AddModelToTask(drag_task_name, self._bsk_drag)

            logger.debug("Drag model configured")

        except Exception as e:
            logger.warning(f"Drag model setup failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            self._bsk_drag = None
            self._bsk_atmo = None

    def propagate(self, epoch: datetime) -> EphemerisPoint:
        """Propagate to target epoch."""
        if self._epoch is None:
            raise RuntimeError("Propagator not initialized")

        if epoch.tzinfo is None:
            epoch = epoch.replace(tzinfo=timezone.utc)

        # Calculate dt from initial epoch for Basilisk (simulation time)
        dt_from_initial = (epoch - self._initial_epoch).total_seconds()

        if BASILISK_AVAILABLE and self._bsk_sim is not None:
            return self._propagate_basilisk(epoch, dt_from_initial)
        else:
            dt_from_current = (epoch - self._epoch).total_seconds()
            return self._propagate_j2(epoch, dt_from_current)

    def _propagate_basilisk(self, epoch: datetime, dt_from_initial: float) -> EphemerisPoint:
        """
        Propagate using Basilisk simulation.

        Args:
            epoch: Target epoch for propagation
            dt_from_initial: Seconds from initial epoch to target epoch

        Returns:
            EphemerisPoint with propagated state
        """
        try:
            from Basilisk.utilities import macros as mc

            # Calculate target simulation time in nanoseconds (sec2nano is a function)
            target_time_ns = int(mc.sec2nano(dt_from_initial))

            # Only propagate forward (Basilisk doesn't support backward propagation easily)
            if target_time_ns < self._sim_time_ns:
                logger.warning(
                    f"Backward propagation requested ({dt_from_initial}s < {self._sim_time_ns * 1e-9}s), "
                    "falling back to J2"
                )
                dt_from_current = (epoch - self._epoch).total_seconds()
                return self._propagate_j2(epoch, dt_from_current)

            # Run simulation to target time
            if target_time_ns > self._sim_time_ns:
                self._bsk_sim.ConfigureStopTime(target_time_ns)
                self._bsk_sim.ExecuteSimulation()
                self._sim_time_ns = target_time_ns

            # Extract state from spacecraft
            pos_m = np.array(self._bsk_spacecraft.scStateOutMsg.read().r_BN_N)  # meters
            vel_m_s = np.array(self._bsk_spacecraft.scStateOutMsg.read().v_BN_N)  # m/s

            # Convert to km and km/s
            position_eci = pos_m / 1000.0
            velocity_eci = vel_m_s / 1000.0

            # Update internal state
            self._position = position_eci
            self._velocity = velocity_eci
            self._epoch = epoch

            # Calculate altitude
            altitude_km = np.linalg.norm(position_eci) - EARTH_RADIUS

            return EphemerisPoint(
                time=epoch,
                position_eci=position_eci,
                velocity_eci=velocity_eci,
                altitude_km=altitude_km,
            )

        except Exception as e:
            logger.warning(f"Basilisk propagation failed: {e}, falling back to J2")
            import traceback
            logger.debug(traceback.format_exc())
            dt_from_current = (epoch - self._epoch).total_seconds()
            return self._propagate_j2(epoch, dt_from_current)

    def _propagate_j2(self, epoch: datetime, dt: float) -> EphemerisPoint:
        """
        J2-perturbed analytical propagation.

        Uses simplified J2 secular perturbations for medium-fidelity
        when Basilisk is not available.
        """
        # Convert to orbital elements
        r = np.linalg.norm(self._position)
        v = np.linalg.norm(self._velocity)
        h = np.cross(self._position, self._velocity)
        h_mag = np.linalg.norm(h)

        # Semi-major axis
        energy = v**2 / 2 - EARTH_MU / r
        a = -EARTH_MU / (2 * energy)

        # Eccentricity
        e_vec = np.cross(self._velocity, h) / EARTH_MU - self._position / r
        e = np.linalg.norm(e_vec)

        # Inclination
        i = np.arccos(h[2] / h_mag)

        # Mean motion
        n = np.sqrt(EARTH_MU / a**3)

        # J2 secular rates
        p = a * (1 - e**2)
        Omega_dot = -1.5 * n * EARTH_J2 * (EARTH_RADIUS / p)**2 * np.cos(i)
        omega_dot = 0.75 * n * EARTH_J2 * (EARTH_RADIUS / p)**2 * (5 * np.cos(i)**2 - 1)
        M_dot = n + 0.75 * n * EARTH_J2 * (EARTH_RADIUS / p)**2 * np.sqrt(1 - e**2) * (3 * np.cos(i)**2 - 1)

        # Propagate mean anomaly
        M0 = self._compute_mean_anomaly()
        M = M0 + M_dot * dt

        # Simple position propagation (circular approximation for efficiency)
        theta = M  # True anomaly ≈ mean anomaly for low e
        r_new = a * (1 - e**2) / (1 + e * np.cos(theta))

        # Rotate position
        cos_theta = np.cos(theta + omega_dot * dt)
        sin_theta = np.sin(theta + omega_dot * dt)

        # Simplified position in orbital plane, rotated to ECI
        Omega = np.arctan2(h[0], -h[1]) + Omega_dot * dt

        x_orb = r_new * cos_theta
        y_orb = r_new * sin_theta

        # Transform to ECI
        cos_O, sin_O = np.cos(Omega), np.sin(Omega)
        cos_i, sin_i = np.cos(i), np.sin(i)
        cos_w, sin_w = np.cos(omega_dot * dt), np.sin(omega_dot * dt)

        # Rotation matrix
        pos_eci = np.array([
            (cos_O * cos_w - sin_O * sin_w * cos_i) * x_orb +
            (-cos_O * sin_w - sin_O * cos_w * cos_i) * y_orb,
            (sin_O * cos_w + cos_O * sin_w * cos_i) * x_orb +
            (-sin_O * sin_w + cos_O * cos_w * cos_i) * y_orb,
            sin_w * sin_i * x_orb + cos_w * sin_i * y_orb,
        ])

        # Velocity (simplified)
        v_mag = np.sqrt(EARTH_MU * (2/r_new - 1/a))
        vel_dir = np.cross([0, 0, 1], pos_eci)
        vel_dir = vel_dir / np.linalg.norm(vel_dir) if np.linalg.norm(vel_dir) > 0 else np.array([0, 1, 0])
        vel_eci = vel_dir * v_mag

        altitude = np.linalg.norm(pos_eci) - EARTH_RADIUS

        return EphemerisPoint(
            time=epoch,
            position_eci=pos_eci,
            velocity_eci=vel_eci,
            altitude_km=altitude,
        )

    def _compute_mean_anomaly(self) -> float:
        """Compute mean anomaly from current state."""
        r = np.linalg.norm(self._position)
        v = np.linalg.norm(self._velocity)

        # Energy and semi-major axis
        energy = v**2 / 2 - EARTH_MU / r
        a = -EARTH_MU / (2 * energy)

        # Eccentricity vector
        h = np.cross(self._position, self._velocity)
        e_vec = np.cross(self._velocity, h) / EARTH_MU - self._position / r
        e = np.linalg.norm(e_vec)

        # True anomaly
        if e > 1e-8:
            cos_nu = np.dot(e_vec, self._position) / (e * r)
            cos_nu = np.clip(cos_nu, -1, 1)
            nu = np.arccos(cos_nu)
            if np.dot(self._position, self._velocity) < 0:
                nu = 2 * np.pi - nu
        else:
            nu = 0.0

        # Eccentric anomaly
        if e < 1:
            E = 2 * np.arctan(np.sqrt((1 - e) / (1 + e)) * np.tan(nu / 2))
            M = E - e * np.sin(E)
        else:
            M = nu  # Parabolic/hyperbolic approximation

        return M

    def propagate_range(
        self,
        start: datetime,
        end: datetime,
        step_s: float,
    ) -> List[EphemerisPoint]:
        """Propagate over time range."""
        points = []
        current = start

        while current <= end:
            point = self.propagate(current)
            points.append(point)
            current += timedelta(seconds=step_s)

        return points

    def apply_maneuver(
        self,
        delta_v: NDArray[np.float64],
        epoch: datetime,
        isp: float = 1500.0,
    ) -> ManeuverResult:
        """
        Apply impulsive maneuver.

        Args:
            delta_v: Delta-V vector in ECI frame [km/s]
            epoch: Maneuver epoch
            isp: Specific impulse [s], default 1500s for EP

        Returns:
            ManeuverResult with applied delta-v and propellant usage
        """
        # Propagate to maneuver epoch if needed
        if epoch != self._epoch:
            point = self.propagate(epoch)
            self._position = point.position_eci
            self._velocity = point.velocity_eci
            self._epoch = epoch

        # Apply delta-V (assuming velocity frame aligned with ECI for simplicity)
        old_velocity = self._velocity.copy()
        self._velocity = self._velocity + delta_v

        # Estimate propellant (Tsiolkovsky rocket equation)
        dv_mag = np.linalg.norm(delta_v)
        g0 = 9.80665e-3  # km/s^2
        mass_ratio = np.exp(dv_mag / (isp * g0))
        propellant_used = self._config.mass_kg * (1 - 1/mass_ratio)

        # After maneuver, need to reinitialize Basilisk with new state
        if BASILISK_AVAILABLE and self._bsk_sim is not None:
            self._reinit_basilisk_after_maneuver()

        return ManeuverResult(
            delta_v_applied=delta_v,
            propellant_used_kg=propellant_used,
            new_position=self._position.copy(),
            new_velocity=self._velocity.copy(),
            epoch=epoch,
        )

    def _reinit_basilisk_after_maneuver(self) -> None:
        """Reinitialize Basilisk simulation after a maneuver."""
        # Store current state
        pos = self._position.copy()
        vel = self._velocity.copy()
        epoch = self._epoch

        # Clear old simulation
        self._bsk_sim = None
        self._bsk_spacecraft = None
        self._bsk_gravity = None
        self._bsk_atmo = None
        self._bsk_drag = None
        self._sim_time_ns = 0

        # Reinitialize with post-maneuver state
        self._initial_epoch = epoch
        self._init_basilisk()

    def reset(
        self,
        position_eci: Optional[NDArray[np.float64]] = None,
        velocity_eci: Optional[NDArray[np.float64]] = None,
        epoch: Optional[datetime] = None,
    ) -> None:
        """
        Reset propagator to a new state.

        Useful for restarting propagation from a different state
        or after external state updates.
        """
        if position_eci is not None:
            self._position = np.array(position_eci, dtype=np.float64)
        if velocity_eci is not None:
            self._velocity = np.array(velocity_eci, dtype=np.float64)
        if epoch is not None:
            if epoch.tzinfo is None:
                epoch = epoch.replace(tzinfo=timezone.utc)
            self._epoch = epoch
            self._initial_epoch = epoch

        # Reinitialize Basilisk with new state
        if BASILISK_AVAILABLE:
            self._bsk_sim = None
            self._sim_time_ns = 0
            self._init_basilisk()

    @property
    def version(self) -> str:
        """Get propagator version."""
        if BASILISK_AVAILABLE and self._bsk_sim is not None:
            try:
                import Basilisk
                return f"basilisk-{getattr(Basilisk, '__version__', '2.0')}"
            except:
                pass
        return "j2-analytical-1.0"

    @property
    def is_using_basilisk(self) -> bool:
        """Check if propagator is using Basilisk (vs J2 fallback)."""
        return BASILISK_AVAILABLE and self._bsk_sim is not None

    def get_status(self) -> dict:
        """Get propagator status for diagnostics."""
        return {
            "backend": "basilisk" if self.is_using_basilisk else "j2-analytical",
            "version": self.version,
            "fidelity": self._fidelity.value if self._fidelity else None,
            "basilisk_available": BASILISK_AVAILABLE,
            "basilisk_initialized": self._bsk_sim is not None,
            "epoch": self._epoch.isoformat() if self._epoch else None,
            "sim_time_s": self._sim_time_ns / 1e9 if self._sim_time_ns else 0,
            "config": {
                "gravity_degree": self._config.gravity_degree,
                "gravity_order": self._config.gravity_order,
                "enable_drag": self._config.enable_drag,
                "integration_step_s": self._config.integration_step_s,
            },
        }

    @property
    def current_epoch(self) -> datetime:
        """Get current epoch."""
        if self._epoch is None:
            raise RuntimeError("Propagator not initialized")
        return self._epoch

    @property
    def current_state(self) -> Tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Get current state."""
        if self._position is None or self._velocity is None:
            raise RuntimeError("Propagator not initialized")
        return self._position.copy(), self._velocity.copy()
