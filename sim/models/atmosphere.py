"""Atmospheric drag models for LEO/VLEO orbits."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from sim.models.orbit import EARTH_RADIUS_KM


@dataclass
class AtmosphereConfig:
    """Configuration for atmosphere model."""

    model_type: str = "exponential"  # "exponential" or "nrlmsise00"
    solar_flux_f107: float = 150.0  # F10.7 solar flux index
    geomagnetic_ap: float = 15.0  # Geomagnetic Ap index


class AtmosphereModel:
    """
    Atmospheric density model for drag calculations.

    Uses exponential atmosphere model for LOW fidelity.
    """

    # Exponential atmosphere parameters (Harris-Priester style)
    # Reference: Vallado, "Fundamentals of Astrodynamics and Applications"
    REFERENCE_ALTITUDES_KM = [
        100, 120, 130, 140, 150, 180, 200, 250, 300, 350,
        400, 450, 500, 600, 700, 800, 900, 1000
    ]

    REFERENCE_DENSITIES_KG_M3 = [
        5.297e-07, 2.546e-08, 8.770e-09, 3.614e-09, 1.667e-09,
        3.396e-10, 1.585e-10, 3.725e-11, 1.069e-11, 3.561e-12,
        1.265e-12, 4.753e-13, 1.879e-13, 3.372e-14, 7.380e-15,
        1.905e-15, 5.881e-16, 2.135e-16
    ]

    SCALE_HEIGHTS_KM = [
        5.9, 7.4, 8.1, 8.6, 9.0, 10.2, 11.3, 14.9, 22.5, 29.7,
        37.6, 45.5, 53.6, 63.3, 72.3, 81.5, 90.5, 100.0
    ]

    def __init__(self, config: Optional[AtmosphereConfig] = None):
        """
        Initialize atmosphere model.

        Args:
            config: Atmosphere configuration
        """
        self.config = config or AtmosphereConfig()

    def density(self, altitude_km: float) -> float:
        """
        Compute atmospheric density at given altitude.

        Args:
            altitude_km: Altitude above Earth surface in km

        Returns:
            Atmospheric density in kg/m^3
        """
        if altitude_km < 100:
            # Below 100 km, use exponential extrapolation
            h0 = 100.0
            rho0 = self.REFERENCE_DENSITIES_KG_M3[0]
            H = self.SCALE_HEIGHTS_KM[0]
            return rho0 * np.exp((h0 - altitude_km) / H)

        if altitude_km > 1000:
            # Above 1000 km, use exponential extrapolation
            h0 = 1000.0
            rho0 = self.REFERENCE_DENSITIES_KG_M3[-1]
            H = self.SCALE_HEIGHTS_KM[-1]
            return rho0 * np.exp((h0 - altitude_km) / H)

        # Find bracketing altitudes
        for i in range(len(self.REFERENCE_ALTITUDES_KM) - 1):
            h_low = self.REFERENCE_ALTITUDES_KM[i]
            h_high = self.REFERENCE_ALTITUDES_KM[i + 1]

            if h_low <= altitude_km < h_high:
                rho_low = self.REFERENCE_DENSITIES_KG_M3[i]
                H = self.SCALE_HEIGHTS_KM[i]
                return rho_low * np.exp((h_low - altitude_km) / H)

        # Fallback (should not reach here)
        return self.REFERENCE_DENSITIES_KG_M3[-1]

    def drag_acceleration(
        self,
        position_eci: np.ndarray,
        velocity_eci: np.ndarray,
        area_m2: float,
        mass_kg: float,
        cd: float = 2.2,
    ) -> np.ndarray:
        """
        Compute drag acceleration vector.

        Args:
            position_eci: Position in ECI frame (km)
            velocity_eci: Velocity in ECI frame (km/s)
            area_m2: Cross-sectional area (m^2)
            mass_kg: Spacecraft mass (kg)
            cd: Drag coefficient (default 2.2)

        Returns:
            Drag acceleration in ECI frame (km/s^2)
        """
        # Altitude
        r = np.linalg.norm(position_eci)
        altitude_km = r - EARTH_RADIUS_KM

        # Atmospheric density
        rho = self.density(altitude_km)  # kg/m^3

        # Velocity relative to atmosphere (approximate: ignore atmospheric rotation)
        v_rel = velocity_eci * 1000.0  # Convert to m/s
        v_rel_mag = np.linalg.norm(v_rel)

        if v_rel_mag < 1e-10:
            return np.zeros(3)

        # Drag acceleration magnitude: a = -0.5 * rho * Cd * A * v^2 / m
        a_mag = 0.5 * rho * cd * area_m2 * v_rel_mag**2 / mass_kg  # m/s^2

        # Drag direction (opposite to velocity)
        drag_direction = -v_rel / v_rel_mag

        # Convert back to km/s^2
        return drag_direction * a_mag / 1000.0

    def orbital_decay_rate(
        self,
        altitude_km: float,
        area_m2: float,
        mass_kg: float,
        cd: float = 2.2,
    ) -> float:
        """
        Estimate orbital decay rate in km/day.

        This is a simplified analytical estimate for circular orbits.

        Args:
            altitude_km: Orbital altitude in km
            area_m2: Cross-sectional area (m^2)
            mass_kg: Spacecraft mass (kg)
            cd: Drag coefficient

        Returns:
            Decay rate in km/day (negative = altitude decreasing)
        """
        from sim.models.orbit import circular_velocity, orbital_period

        rho = self.density(altitude_km)  # kg/m^3
        v = circular_velocity(altitude_km) * 1000.0  # m/s
        T = orbital_period(altitude_km)  # seconds

        # Ballistic coefficient
        BC = mass_kg / (cd * area_m2)  # kg/m^2

        # Semi-major axis decay per orbit (simplified)
        # da/dt = -rho * v * a / BC
        r = (EARTH_RADIUS_KM + altitude_km) * 1000.0  # m
        da_per_orbit = -np.pi * rho * r**2 / BC  # m

        # Convert to km/day
        orbits_per_day = 86400.0 / T
        da_per_day = da_per_orbit * orbits_per_day / 1000.0  # km/day

        return da_per_day
