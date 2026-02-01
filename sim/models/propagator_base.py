"""
Abstract base class for orbit propagators.

Defines the interface that all propagators must implement, enabling
swappable propagation backends (SGP4, Basilisk, etc.) based on fidelity.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray


@dataclass
class EphemerisPoint:
    """A single point in the ephemeris timeseries."""

    time: datetime
    position_eci: NDArray[np.float64]  # km, ECI frame
    velocity_eci: NDArray[np.float64]  # km/s, ECI frame
    altitude_km: float

    # Optional attitude (quaternion: w, x, y, z)
    attitude_quat: Optional[NDArray[np.float64]] = None
    # Optional angular velocity (rad/s, body frame)
    angular_velocity: Optional[NDArray[np.float64]] = None


@dataclass
class ManeuverResult:
    """Result of applying a maneuver."""

    delta_v_applied: NDArray[np.float64]  # km/s
    propellant_used_kg: float
    new_position: NDArray[np.float64]
    new_velocity: NDArray[np.float64]
    epoch: datetime


class PropagatorInterface(ABC):
    """
    Abstract interface for orbit propagators.

    All propagators must implement this interface to be usable
    by the simulation engine.
    """

    @abstractmethod
    def initialize(
        self,
        position_eci: NDArray[np.float64],
        velocity_eci: NDArray[np.float64],
        epoch: datetime,
    ) -> None:
        """
        Initialize the propagator with initial state.

        Args:
            position_eci: Initial position in ECI frame (km)
            velocity_eci: Initial velocity in ECI frame (km/s)
            epoch: Initial epoch (UTC)
        """
        pass

    @abstractmethod
    def propagate(self, epoch: datetime) -> EphemerisPoint:
        """
        Propagate to a specific epoch.

        Args:
            epoch: Target epoch (UTC)

        Returns:
            EphemerisPoint at the target epoch
        """
        pass

    @abstractmethod
    def propagate_range(
        self,
        start: datetime,
        end: datetime,
        step_s: float,
    ) -> List[EphemerisPoint]:
        """
        Propagate over a time range with fixed step.

        Args:
            start: Start epoch (UTC)
            end: End epoch (UTC)
            step_s: Time step in seconds

        Returns:
            List of EphemerisPoints
        """
        pass

    @abstractmethod
    def apply_maneuver(
        self,
        delta_v: NDArray[np.float64],
        epoch: datetime,
    ) -> ManeuverResult:
        """
        Apply an impulsive maneuver.

        Args:
            delta_v: Delta-V vector in velocity frame (km/s)
            epoch: Maneuver epoch

        Returns:
            ManeuverResult with new state
        """
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Get the propagator version string."""
        pass

    @property
    @abstractmethod
    def current_epoch(self) -> datetime:
        """Get the current propagator epoch."""
        pass

    @property
    @abstractmethod
    def current_state(self) -> Tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Get current (position, velocity) in ECI frame."""
        pass


class PropagatorConfig:
    """Base configuration for propagators."""

    def __init__(
        self,
        gravity_model: str = "spherical",
        atmosphere_model: Optional[str] = None,
        third_body_sun: bool = False,
        third_body_moon: bool = False,
        solar_radiation_pressure: bool = False,
        drag_coefficient: float = 2.2,
        srp_coefficient: float = 1.2,
        area_m2: float = 10.0,
        mass_kg: float = 500.0,
    ):
        self.gravity_model = gravity_model
        self.atmosphere_model = atmosphere_model
        self.third_body_sun = third_body_sun
        self.third_body_moon = third_body_moon
        self.solar_radiation_pressure = solar_radiation_pressure
        self.drag_coefficient = drag_coefficient
        self.srp_coefficient = srp_coefficient
        self.area_m2 = area_m2
        self.mass_kg = mass_kg

    @classmethod
    def for_fidelity(cls, fidelity: str) -> "PropagatorConfig":
        """Create config appropriate for fidelity level."""
        if fidelity == "LOW":
            return cls(
                gravity_model="spherical",
                atmosphere_model=None,
            )
        elif fidelity == "MEDIUM":
            return cls(
                gravity_model="j2",
                atmosphere_model="exponential",
                third_body_sun=True,
                third_body_moon=True,
            )
        elif fidelity == "HIGH":
            return cls(
                gravity_model="egm96",
                atmosphere_model="nrlmsise00",
                third_body_sun=True,
                third_body_moon=True,
                solar_radiation_pressure=True,
            )
        return cls()
