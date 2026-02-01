"""
Basilisk-based orbit propagator for MEDIUM and HIGH fidelity simulations.

This module provides a propagator implementation using the Basilisk
simulation framework when available. Falls back to a stub implementation
if Basilisk is not installed.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
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
    enable_albedo: bool = False
    enable_earth_ir: bool = False
    # Spacecraft properties for maneuver calculations
    mass_kg: float = 500.0
    area_m2: float = 10.0


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

        # Basilisk simulation objects (if available)
        self._bsk_sim = None
        self._bsk_spacecraft = None

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

        if BASILISK_AVAILABLE:
            self._init_basilisk()
        else:
            logger.info("Basilisk not available, using J2 analytical fallback")

    def _init_basilisk(self) -> None:
        """Initialize Basilisk simulation environment."""
        try:
            from Basilisk.utilities import SimulationBaseClass
            from Basilisk.utilities import macros as mc
            from Basilisk.simulation import spacecraft
            from Basilisk.simulation import gravityEffector
            from Basilisk.simulation import exponentialAtmosphere

            # Create simulation
            self._bsk_sim = SimulationBaseClass.SimBaseClass()

            # Create spacecraft
            self._bsk_spacecraft = spacecraft.Spacecraft()
            self._bsk_spacecraft.ModelTag = "spacecraft"

            # Set initial state
            self._bsk_spacecraft.hub.r_CN_NInit = self._position * 1000  # m
            self._bsk_spacecraft.hub.v_CN_NInit = self._velocity * 1000  # m/s

            # Add gravity
            gravity = gravityEffector.GravityEffector()
            gravity.ModelTag = "gravity"
            # Configure based on fidelity...

            logger.info("Basilisk simulation initialized")

        except Exception as e:
            logger.warning(f"Basilisk initialization failed: {e}")
            self._bsk_sim = None

    def propagate(self, epoch: datetime) -> EphemerisPoint:
        """Propagate to target epoch."""
        if self._epoch is None:
            raise RuntimeError("Propagator not initialized")

        if epoch.tzinfo is None:
            epoch = epoch.replace(tzinfo=timezone.utc)

        dt = (epoch - self._epoch).total_seconds()

        if BASILISK_AVAILABLE and self._bsk_sim is not None:
            return self._propagate_basilisk(epoch, dt)
        else:
            return self._propagate_j2(epoch, dt)

    def _propagate_basilisk(self, epoch: datetime, dt: float) -> EphemerisPoint:
        """Propagate using Basilisk (stub - full implementation needs Basilisk)."""
        # For now, fall back to J2
        return self._propagate_j2(epoch, dt)

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
    ) -> ManeuverResult:
        """Apply impulsive maneuver."""
        # Propagate to maneuver epoch if needed
        if epoch != self._epoch:
            point = self.propagate(epoch)
            self._position = point.position_eci
            self._velocity = point.velocity_eci
            self._epoch = epoch

        # Apply delta-V (assuming velocity frame aligned with ECI for simplicity)
        old_velocity = self._velocity.copy()
        self._velocity = self._velocity + delta_v

        # Estimate propellant (simplified Tsiolkovsky)
        dv_mag = np.linalg.norm(delta_v)
        isp = 1500.0  # s, typical for EP
        g0 = 9.80665e-3  # km/s^2
        mass_ratio = np.exp(dv_mag / (isp * g0))
        propellant_used = self._config.mass_kg * (1 - 1/mass_ratio)

        return ManeuverResult(
            delta_v_applied=delta_v,
            propellant_used_kg=propellant_used,
            new_position=self._position.copy(),
            new_velocity=self._velocity.copy(),
            epoch=epoch,
        )

    @property
    def version(self) -> str:
        """Get propagator version."""
        if BASILISK_AVAILABLE:
            try:
                import Basilisk
                return f"basilisk-{getattr(Basilisk, '__version__', '2.0')}"
            except:
                pass
        return "j2-analytical-1.0"

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
