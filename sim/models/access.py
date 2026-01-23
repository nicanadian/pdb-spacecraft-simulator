"""Ground station access model."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import numpy as np

from sim.core.time_utils import datetime_to_jd, gmst
from sim.models.orbit import EARTH_RADIUS_KM


@dataclass
class GroundStation:
    """Ground station definition."""

    station_id: str
    name: str
    lat_deg: float
    lon_deg: float
    alt_m: float = 0.0
    min_elevation_deg: float = 5.0
    bands: List[str] = None  # e.g., ["S", "X", "Ka"]

    def __post_init__(self):
        if self.bands is None:
            self.bands = ["S", "X"]


@dataclass
class AccessWindow:
    """A ground station access window."""

    station_id: str
    start_time: datetime
    end_time: datetime
    max_elevation_deg: float
    aos_azimuth_deg: float  # Azimuth at acquisition of signal
    los_azimuth_deg: float  # Azimuth at loss of signal

    @property
    def duration_s(self) -> float:
        """Duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()

    def __post_init__(self):
        """Validate AOS < LOS."""
        if self.end_time <= self.start_time:
            raise ValueError(
                f"end_time ({self.end_time}) must be after start_time ({self.start_time})"
            )


class AccessModel:
    """
    Ground station access model.

    Computes visibility windows between spacecraft and ground stations.
    """

    def __init__(self, stations: Optional[List[GroundStation]] = None):
        """
        Initialize access model.

        Args:
            stations: List of ground stations
        """
        self.stations = stations or []

    def add_station(self, station: GroundStation):
        """Add a ground station."""
        self.stations.append(station)

    def station_position_eci(self, station: GroundStation, epoch: datetime) -> np.ndarray:
        """
        Get ground station position in ECI.

        Args:
            station: Ground station
            epoch: Time for transformation

        Returns:
            Position in ECI (km)
        """
        lat_rad = np.radians(station.lat_deg)
        lon_rad = np.radians(station.lon_deg)

        # Station radius (Earth radius + altitude)
        r_station = EARTH_RADIUS_KM + station.alt_m / 1000.0

        # Position in ECEF
        x_ecef = r_station * np.cos(lat_rad) * np.cos(lon_rad)
        y_ecef = r_station * np.cos(lat_rad) * np.sin(lon_rad)
        z_ecef = r_station * np.sin(lat_rad)

        # Rotate to ECI
        jd = datetime_to_jd(epoch)
        theta = gmst(jd)

        cos_theta = np.cos(theta)
        sin_theta = np.sin(theta)

        x_eci = cos_theta * x_ecef - sin_theta * y_ecef
        y_eci = sin_theta * x_ecef + cos_theta * y_ecef
        z_eci = z_ecef

        return np.array([x_eci, y_eci, z_eci])

    def compute_elevation_azimuth(
        self,
        sc_position_eci: np.ndarray,
        station: GroundStation,
        epoch: datetime,
    ) -> tuple[float, float]:
        """
        Compute elevation and azimuth from station to spacecraft.

        Args:
            sc_position_eci: Spacecraft position in ECI (km)
            station: Ground station
            epoch: Time for calculation

        Returns:
            Tuple of (elevation_deg, azimuth_deg)
        """
        # Station position in ECI
        station_eci = self.station_position_eci(station, epoch)

        # Vector from station to spacecraft
        los = sc_position_eci - station_eci
        los_mag = np.linalg.norm(los)

        if los_mag < 1e-10:
            return 90.0, 0.0

        # Station local frame (ENU - East, North, Up)
        lat_rad = np.radians(station.lat_deg)
        lon_rad = np.radians(station.lon_deg)

        # Get GMST for ECEF calculation
        jd = datetime_to_jd(epoch)
        theta = gmst(jd)

        # Local longitude in ECI frame
        local_lon = lon_rad + theta

        # Up vector (radial from Earth center through station)
        up = np.array([
            np.cos(lat_rad) * np.cos(local_lon),
            np.cos(lat_rad) * np.sin(local_lon),
            np.sin(lat_rad),
        ])

        # East vector
        east = np.array([
            -np.sin(local_lon),
            np.cos(local_lon),
            0.0,
        ])

        # North vector
        north = np.cross(up, east)

        # Project LOS onto local frame
        los_up = np.dot(los, up)
        los_east = np.dot(los, east)
        los_north = np.dot(los, north)

        # Elevation angle
        horizontal_dist = np.sqrt(los_east**2 + los_north**2)
        elevation_rad = np.arctan2(los_up, horizontal_dist)
        elevation_deg = np.degrees(elevation_rad)

        # Azimuth (measured from North, clockwise)
        azimuth_rad = np.arctan2(los_east, los_north)
        azimuth_deg = np.degrees(azimuth_rad)
        if azimuth_deg < 0:
            azimuth_deg += 360.0

        return elevation_deg, azimuth_deg

    def compute_access_windows(
        self,
        ephemeris: list,
        station: GroundStation,
    ) -> List[AccessWindow]:
        """
        Compute access windows for a single station.

        Args:
            ephemeris: List of EphemerisPoint objects
            station: Ground station

        Returns:
            List of AccessWindow objects
        """
        windows = []
        in_access = False
        window_start = None
        aos_azimuth = 0.0
        max_elevation = 0.0

        for point in ephemeris:
            elevation, azimuth = self.compute_elevation_azimuth(
                point.position_eci, station, point.time
            )

            visible = elevation >= station.min_elevation_deg

            if visible and not in_access:
                # AOS (Acquisition of Signal)
                window_start = point.time
                aos_azimuth = azimuth
                max_elevation = elevation
                in_access = True
            elif visible and in_access:
                # Continue in access
                max_elevation = max(max_elevation, elevation)
            elif not visible and in_access:
                # LOS (Loss of Signal)
                if window_start:
                    windows.append(AccessWindow(
                        station_id=station.station_id,
                        start_time=window_start,
                        end_time=point.time,
                        max_elevation_deg=max_elevation,
                        aos_azimuth_deg=aos_azimuth,
                        los_azimuth_deg=azimuth,
                    ))
                in_access = False
                window_start = None

        # Handle case where ephemeris ends in access
        if in_access and window_start and ephemeris:
            end_time = ephemeris[-1].time
            # Skip windows with zero or negative duration
            if end_time > window_start:
                _, final_azimuth = self.compute_elevation_azimuth(
                    ephemeris[-1].position_eci, station, end_time
                )
                windows.append(AccessWindow(
                    station_id=station.station_id,
                    start_time=window_start,
                    end_time=end_time,
                    max_elevation_deg=max_elevation,
                    aos_azimuth_deg=aos_azimuth,
                    los_azimuth_deg=final_azimuth,
                ))

        return windows

    def compute_all_access_windows(
        self,
        ephemeris: list,
    ) -> dict[str, List[AccessWindow]]:
        """
        Compute access windows for all stations.

        Args:
            ephemeris: List of EphemerisPoint objects

        Returns:
            Dict mapping station_id to list of AccessWindow objects
        """
        result = {}
        for station in self.stations:
            windows = self.compute_access_windows(ephemeris, station)
            result[station.station_id] = windows
        return result


def get_default_stations() -> List[GroundStation]:
    """
    Get a default set of ground stations.

    Returns:
        List of common ground stations
    """
    return [
        GroundStation(
            station_id="svalbard",
            name="Svalbard",
            lat_deg=78.2306,
            lon_deg=15.3894,
            bands=["S", "X", "Ka"],
        ),
        GroundStation(
            station_id="fairbanks",
            name="Fairbanks",
            lat_deg=64.8601,
            lon_deg=-147.8522,
            bands=["S", "X"],
        ),
        GroundStation(
            station_id="mcmurdo",
            name="McMurdo",
            lat_deg=-77.8467,
            lon_deg=166.6683,
            bands=["S", "X"],
        ),
        GroundStation(
            station_id="santiago",
            name="Santiago",
            lat_deg=-33.1507,
            lon_deg=-70.6682,
            bands=["S", "X"],
        ),
        GroundStation(
            station_id="alice_springs",
            name="Alice Springs",
            lat_deg=-23.7628,
            lon_deg=133.8744,
            bands=["S", "X", "Ka"],
        ),
    ]
