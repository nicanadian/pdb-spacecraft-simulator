"""Electric propulsion model for Hall-effect thrusters."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

import numpy as np

from sim.models.orbit import MU_EARTH, EARTH_RADIUS_KM


# Constants
G0 = 9.80665e-3  # Standard gravity in km/s^2


@dataclass
class EPConfig:
    """Electric propulsion (Hall thruster) configuration."""

    thrust_n: float = 0.1  # Thrust in Newtons
    isp_s: float = 1500.0  # Specific impulse in seconds
    power_w: float = 1500.0  # Power consumption in Watts
    efficiency: float = 0.6  # Thruster efficiency
    thrusts_per_orbit: int = 2  # Number of thrust arcs per orbit
    thrust_arc_deg: float = 30.0  # Duration of each thrust arc in degrees

    @property
    def thrust_km_s2(self) -> float:
        """Thrust in km/s^2 for 1 kg spacecraft (for scaling)."""
        return self.thrust_n / 1000.0  # N to kN, gives km/s^2 per kg

    @property
    def exhaust_velocity_km_s(self) -> float:
        """Exhaust velocity in km/s."""
        return self.isp_s * G0


@dataclass
class ThrustArc:
    """A single thrust arc in an orbit."""

    start_time: datetime
    end_time: datetime
    start_true_anomaly_deg: float
    end_true_anomaly_deg: float
    delta_v_km_s: float
    propellant_used_kg: float
    power_used_wh: float

    @property
    def duration_s(self) -> float:
        """Duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()


@dataclass
class ThrustPlan:
    """Plan for multiple thrust arcs."""

    arcs: List[ThrustArc] = field(default_factory=list)
    total_delta_v_km_s: float = 0.0
    total_propellant_kg: float = 0.0
    total_power_wh: float = 0.0

    def add_arc(self, arc: ThrustArc):
        """Add a thrust arc to the plan."""
        self.arcs.append(arc)
        self.total_delta_v_km_s += arc.delta_v_km_s
        self.total_propellant_kg += arc.propellant_used_kg
        self.total_power_wh += arc.power_used_wh


class EPModel:
    """
    Electric propulsion model for Hall-effect thrusters.

    Supports duty-cycled thrusting with power constraints.
    """

    def __init__(self, config: EPConfig):
        """
        Initialize EP model.

        Args:
            config: EP configuration
        """
        self.config = config

    def compute_delta_v(self, thrust_duration_s: float, spacecraft_mass_kg: float) -> float:
        """
        Compute delta-V from thrust duration.

        Args:
            thrust_duration_s: Thrust duration in seconds
            spacecraft_mass_kg: Current spacecraft mass in kg

        Returns:
            Delta-V in km/s
        """
        # F = m * a, so a = F / m
        thrust_km_s2 = self.config.thrust_n / 1e6 / spacecraft_mass_kg  # N to kN to km/s^2
        return thrust_km_s2 * thrust_duration_s

    def compute_propellant_used(self, delta_v_km_s: float, spacecraft_mass_kg: float) -> float:
        """
        Compute propellant consumed for given delta-V.

        Uses Tsiolkovsky rocket equation: dv = ve * ln(m0 / m1)
        Rearranged: m1 = m0 * exp(-dv / ve)
        Propellant = m0 - m1

        Args:
            delta_v_km_s: Delta-V in km/s
            spacecraft_mass_kg: Initial spacecraft mass in kg

        Returns:
            Propellant used in kg
        """
        ve = self.config.exhaust_velocity_km_s
        mass_ratio = np.exp(-delta_v_km_s / ve)
        final_mass = spacecraft_mass_kg * mass_ratio
        return spacecraft_mass_kg - final_mass

    def compute_power_used(self, thrust_duration_s: float) -> float:
        """
        Compute power consumed during thrust.

        Args:
            thrust_duration_s: Thrust duration in seconds

        Returns:
            Energy used in Wh
        """
        return self.config.power_w * thrust_duration_s / 3600.0

    def compute_thrust_duration_for_delta_v(
        self, delta_v_km_s: float, spacecraft_mass_kg: float
    ) -> float:
        """
        Compute thrust duration needed for given delta-V.

        Args:
            delta_v_km_s: Target delta-V in km/s
            spacecraft_mass_kg: Spacecraft mass in kg

        Returns:
            Required thrust duration in seconds
        """
        thrust_km_s2 = self.config.thrust_n / 1e6 / spacecraft_mass_kg
        return delta_v_km_s / thrust_km_s2

    def check_power_available(self, battery_soc: float, battery_capacity_wh: float) -> bool:
        """
        Check if sufficient power is available for one thrust arc.

        Args:
            battery_soc: Current battery state of charge [0, 1]
            battery_capacity_wh: Battery capacity in Wh

        Returns:
            True if power is available
        """
        available_wh = battery_soc * battery_capacity_wh
        # Check if we have enough for at least 1 minute of thrust
        min_required_wh = self.config.power_w * 60.0 / 3600.0
        return available_wh >= min_required_wh

    def schedule_thrust_arcs(
        self,
        orbit_period_s: float,
        start_time: datetime,
        num_orbits: int = 1,
    ) -> List[Tuple[datetime, datetime, float]]:
        """
        Schedule thrust arcs within orbits.

        Default: 2 thrusts per orbit at 0° and 180° true anomaly.

        Args:
            orbit_period_s: Orbital period in seconds
            start_time: Start time of first orbit
            num_orbits: Number of orbits to schedule

        Returns:
            List of (start_time, end_time, center_true_anomaly_deg) tuples
        """
        arc_duration_s = (self.config.thrust_arc_deg / 360.0) * orbit_period_s
        half_arc_s = arc_duration_s / 2.0

        # Positions for thrust arcs (evenly distributed)
        positions_deg = np.linspace(0, 360, self.config.thrusts_per_orbit, endpoint=False)

        arcs = []
        for orbit in range(num_orbits):
            orbit_start = start_time + timedelta(seconds=orbit * orbit_period_s)

            for pos_deg in positions_deg:
                # Time from orbit start to thrust center
                center_time_s = (pos_deg / 360.0) * orbit_period_s
                arc_start = orbit_start + timedelta(seconds=center_time_s - half_arc_s)
                arc_end = orbit_start + timedelta(seconds=center_time_s + half_arc_s)

                arcs.append((arc_start, arc_end, pos_deg))

        return arcs

    def plan_orbit_lowering(
        self,
        start_altitude_km: float,
        end_altitude_km: float,
        spacecraft_mass_kg: float,
        start_time: datetime,
        orbit_period_s: float,
        battery_capacity_wh: float,
        initial_soc: float = 1.0,
    ) -> ThrustPlan:
        """
        Plan thrust arcs for orbit lowering maneuver.

        Args:
            start_altitude_km: Starting altitude in km
            end_altitude_km: Target altitude in km
            spacecraft_mass_kg: Spacecraft mass in kg
            start_time: Maneuver start time
            orbit_period_s: Current orbital period in seconds
            battery_capacity_wh: Battery capacity in Wh
            initial_soc: Initial state of charge

        Returns:
            ThrustPlan with scheduled thrust arcs
        """
        from sim.models.orbit import compute_lowering_delta_v

        # Total delta-V needed
        total_dv = compute_lowering_delta_v(start_altitude_km, end_altitude_km)

        # Create thrust plan
        plan = ThrustPlan()

        # Calculate arc duration
        arc_duration_s = (self.config.thrust_arc_deg / 360.0) * orbit_period_s

        # Delta-V per arc
        dv_per_arc = self.compute_delta_v(arc_duration_s, spacecraft_mass_kg)

        # Number of arcs needed
        num_arcs = int(np.ceil(total_dv / dv_per_arc))

        # Schedule arcs
        current_time = start_time
        current_mass = spacecraft_mass_kg
        remaining_dv = total_dv

        for arc_idx in range(num_arcs):
            # Determine which orbit and position in orbit
            orbit_num = arc_idx // self.config.thrusts_per_orbit
            arc_in_orbit = arc_idx % self.config.thrusts_per_orbit

            # True anomaly for this arc
            position_deg = (arc_in_orbit * 360.0 / self.config.thrusts_per_orbit)

            # Calculate arc timing
            orbit_start = start_time + timedelta(seconds=orbit_num * orbit_period_s)
            center_time_s = (position_deg / 360.0) * orbit_period_s
            half_arc_s = arc_duration_s / 2.0

            arc_start = orbit_start + timedelta(seconds=center_time_s - half_arc_s)
            arc_end = orbit_start + timedelta(seconds=center_time_s + half_arc_s)

            # Delta-V for this arc (may be less for final arc)
            arc_dv = min(dv_per_arc, remaining_dv)

            # Propellant and power
            propellant = self.compute_propellant_used(arc_dv, current_mass)
            power_wh = self.compute_power_used(arc_duration_s)

            # Create arc
            arc = ThrustArc(
                start_time=arc_start,
                end_time=arc_end,
                start_true_anomaly_deg=position_deg - self.config.thrust_arc_deg / 2,
                end_true_anomaly_deg=position_deg + self.config.thrust_arc_deg / 2,
                delta_v_km_s=arc_dv,
                propellant_used_kg=propellant,
                power_used_wh=power_wh,
            )
            plan.add_arc(arc)

            # Update state
            current_mass -= propellant
            remaining_dv -= arc_dv

            if remaining_dv <= 0:
                break

        return plan


def compute_thrust_direction(
    position_eci: np.ndarray,
    velocity_eci: np.ndarray,
    thrust_type: str = "prograde",
) -> np.ndarray:
    """
    Compute thrust direction unit vector.

    Args:
        position_eci: Position in ECI (km)
        velocity_eci: Velocity in ECI (km/s)
        thrust_type: "prograde", "retrograde", "radial_in", "radial_out"

    Returns:
        Unit vector in ECI frame
    """
    v_unit = velocity_eci / np.linalg.norm(velocity_eci)
    r_unit = position_eci / np.linalg.norm(position_eci)

    if thrust_type == "prograde":
        return v_unit
    elif thrust_type == "retrograde":
        return -v_unit
    elif thrust_type == "radial_in":
        return -r_unit
    elif thrust_type == "radial_out":
        return r_unit
    else:
        raise ValueError(f"Unknown thrust type: {thrust_type}")
