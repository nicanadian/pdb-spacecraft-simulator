"""Power and battery model for spacecraft."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

import numpy as np


@dataclass
class PowerConfig:
    """Power system configuration."""

    battery_capacity_wh: float = 5000.0  # Battery capacity in Wh
    solar_panel_area_m2: float = 10.0  # Solar panel area
    solar_efficiency: float = 0.30  # Solar cell efficiency
    base_power_w: float = 200.0  # Base power consumption (always on)
    max_charge_rate_w: float = 500.0  # Maximum charge rate
    max_discharge_rate_w: float = 2000.0  # Maximum discharge rate
    min_soc: float = 0.1  # Minimum allowed state of charge
    battery_efficiency: float = 0.95  # Round-trip efficiency


@dataclass
class EclipseWindow:
    """Eclipse window (spacecraft in Earth's shadow)."""

    start_time: datetime
    end_time: datetime

    @property
    def duration_s(self) -> float:
        """Duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()


@dataclass
class PowerState:
    """Current power system state."""

    soc: float  # State of charge [0, 1]
    power_generation_w: float  # Current solar generation
    power_consumption_w: float  # Current consumption
    in_eclipse: bool  # True if in eclipse


class PowerModel:
    """
    Power and battery model for spacecraft.

    Tracks state of charge, solar generation, and power consumption.
    """

    # Solar constant at 1 AU
    SOLAR_FLUX_W_M2 = 1361.0

    def __init__(self, config: PowerConfig):
        """
        Initialize power model.

        Args:
            config: Power system configuration
        """
        self.config = config

    def compute_solar_generation(
        self,
        in_eclipse: bool,
        sun_angle_deg: float = 0.0,
    ) -> float:
        """
        Compute solar power generation.

        Args:
            in_eclipse: True if spacecraft is in eclipse
            sun_angle_deg: Angle between sun and panel normal (0 = optimal)

        Returns:
            Power generation in Watts
        """
        if in_eclipse:
            return 0.0

        # Cosine loss for off-pointing
        cos_angle = np.cos(np.radians(sun_angle_deg))
        if cos_angle <= 0:
            return 0.0

        power = (
            self.SOLAR_FLUX_W_M2
            * self.config.solar_panel_area_m2
            * self.config.solar_efficiency
            * cos_angle
        )

        return power

    def update_soc(
        self,
        current_soc: float,
        power_generation_w: float,
        power_consumption_w: float,
        duration_s: float,
    ) -> Tuple[float, bool]:
        """
        Update state of charge over a time interval.

        Args:
            current_soc: Current state of charge [0, 1]
            power_generation_w: Solar power generation in W
            power_consumption_w: Total power consumption in W
            duration_s: Time interval in seconds

        Returns:
            Tuple of (new_soc, power_limited) where power_limited is True
            if consumption was limited by available power
        """
        # Net power (positive = charging, negative = discharging)
        net_power_w = power_generation_w - power_consumption_w

        # Apply efficiency
        if net_power_w > 0:
            # Charging: limited by charge rate and efficiency
            net_power_w = min(net_power_w, self.config.max_charge_rate_w)
            net_power_w *= self.config.battery_efficiency
        else:
            # Discharging: limited by discharge rate
            net_power_w = max(net_power_w, -self.config.max_discharge_rate_w)

        # Energy change in Wh
        energy_change_wh = net_power_w * duration_s / 3600.0

        # New SOC
        new_soc = current_soc + energy_change_wh / self.config.battery_capacity_wh

        # Check for power limiting
        power_limited = False
        if new_soc < self.config.min_soc:
            new_soc = self.config.min_soc
            power_limited = True
        elif new_soc > 1.0:
            new_soc = 1.0

        return new_soc, power_limited

    def can_support_load(
        self,
        current_soc: float,
        power_consumption_w: float,
        duration_s: float,
    ) -> bool:
        """
        Check if battery can support a load for given duration.

        Args:
            current_soc: Current state of charge
            power_consumption_w: Required power consumption
            duration_s: Duration in seconds

        Returns:
            True if load can be supported without hitting min SOC
        """
        energy_required_wh = power_consumption_w * duration_s / 3600.0
        available_wh = (current_soc - self.config.min_soc) * self.config.battery_capacity_wh
        return available_wh >= energy_required_wh

    def compute_eclipse_intervals(
        self,
        ephemeris: list,
        time_step_s: float = 60.0,
    ) -> List[EclipseWindow]:
        """
        Compute eclipse intervals from ephemeris.

        Uses simple cylindrical shadow model.

        Args:
            ephemeris: List of EphemerisPoint objects
            time_step_s: Time step used in ephemeris

        Returns:
            List of EclipseWindow objects
        """
        from sim.models.orbit import EARTH_RADIUS_KM

        windows = []
        in_eclipse = False
        eclipse_start = None

        for point in ephemeris:
            # Simple cylindrical shadow check
            # Eclipse when: r_perp <= R_earth and r_parallel < 0 (behind Earth)

            r = point.position_eci
            r_mag = np.linalg.norm(r)

            # Sun direction (approximate: assume sun at +X in ECI)
            # For more accuracy, compute sun position from ephemeris
            sun_dir = np.array([1.0, 0.0, 0.0])

            # Component along sun direction
            r_parallel = np.dot(r, sun_dir)

            # Perpendicular component
            r_perp_vec = r - r_parallel * sun_dir
            r_perp = np.linalg.norm(r_perp_vec)

            # In eclipse if behind Earth and within shadow cylinder
            currently_in_eclipse = (r_parallel < 0) and (r_perp < EARTH_RADIUS_KM)

            if currently_in_eclipse and not in_eclipse:
                # Eclipse start
                eclipse_start = point.time
                in_eclipse = True
            elif not currently_in_eclipse and in_eclipse:
                # Eclipse end
                if eclipse_start:
                    windows.append(EclipseWindow(
                        start_time=eclipse_start,
                        end_time=point.time,
                    ))
                in_eclipse = False
                eclipse_start = None

        # Handle case where ephemeris ends in eclipse
        if in_eclipse and eclipse_start:
            windows.append(EclipseWindow(
                start_time=eclipse_start,
                end_time=ephemeris[-1].time,
            ))

        return windows

    def is_in_eclipse(self, position_eci: np.ndarray) -> bool:
        """
        Check if spacecraft is in eclipse.

        Args:
            position_eci: Position in ECI frame (km)

        Returns:
            True if in eclipse
        """
        from sim.models.orbit import EARTH_RADIUS_KM

        # Sun direction (approximate)
        sun_dir = np.array([1.0, 0.0, 0.0])

        r_parallel = np.dot(position_eci, sun_dir)
        r_perp_vec = position_eci - r_parallel * sun_dir
        r_perp = np.linalg.norm(r_perp_vec)

        return (r_parallel < 0) and (r_perp < EARTH_RADIUS_KM)

    def get_state(
        self,
        soc: float,
        position_eci: np.ndarray,
        additional_load_w: float = 0.0,
    ) -> PowerState:
        """
        Get current power state.

        Args:
            soc: Current state of charge
            position_eci: Current position in ECI
            additional_load_w: Additional power load on top of base

        Returns:
            PowerState object
        """
        in_eclipse = self.is_in_eclipse(position_eci)
        generation = self.compute_solar_generation(in_eclipse)
        consumption = self.config.base_power_w + additional_load_w

        return PowerState(
            soc=soc,
            power_generation_w=generation,
            power_consumption_w=consumption,
            in_eclipse=in_eclipse,
        )
