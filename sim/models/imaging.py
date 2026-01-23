"""Electro-optical imaging sensor model."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple, Optional

import numpy as np

from sim.models.orbit import EARTH_RADIUS_KM


@dataclass
class EOSensorConfig:
    """Electro-optical sensor configuration."""

    focal_length_mm: float = 1000.0  # Focal length in mm
    pixel_size_um: float = 10.0  # Pixel size in micrometers
    detector_rows: int = 4096  # Detector rows (along-track)
    detector_cols: int = 4096  # Detector columns (cross-track)
    integration_time_ms: float = 1.0  # Integration time
    data_rate_mbps: float = 1000.0  # Raw data rate
    bits_per_pixel: int = 12  # Bits per pixel
    compression_ratio: float = 4.0  # Compression ratio


@dataclass
class ImageFrame:
    """A single image frame."""

    frame_id: str
    capture_time: datetime
    target_lat_deg: float
    target_lon_deg: float
    altitude_km: float
    gsd_m: float
    cross_track_angle_deg: float
    along_track_angle_deg: float
    data_volume_mb: float
    footprint_km: Tuple[float, float]  # (along-track, cross-track)


@dataclass
class ImagingWindow:
    """Window where target is accessible for imaging."""

    target_id: str
    start_time: datetime
    end_time: datetime
    min_cross_track_deg: float
    max_cross_track_deg: float
    min_along_track_deg: float
    max_along_track_deg: float

    @property
    def duration_s(self) -> float:
        """Duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()


class FrameSensor:
    """
    Frame-based electro-optical sensor model.

    Computes imaging geometry and data volumes.
    """

    def __init__(self, config: EOSensorConfig):
        """
        Initialize frame sensor.

        Args:
            config: Sensor configuration
        """
        self.config = config

    def compute_gsd(self, altitude_km: float) -> float:
        """
        Compute ground sample distance at nadir.

        GSD = (pixel_size * altitude) / focal_length

        Args:
            altitude_km: Altitude above ground in km

        Returns:
            GSD in meters
        """
        altitude_m = altitude_km * 1000.0
        focal_length_m = self.config.focal_length_mm / 1000.0
        pixel_size_m = self.config.pixel_size_um / 1e6

        gsd_m = (pixel_size_m * altitude_m) / focal_length_m
        return gsd_m

    def compute_swath(self, altitude_km: float) -> float:
        """
        Compute cross-track swath width at nadir.

        Args:
            altitude_km: Altitude above ground in km

        Returns:
            Swath width in km
        """
        gsd_m = self.compute_gsd(altitude_km)
        swath_m = gsd_m * self.config.detector_cols
        return swath_m / 1000.0

    def compute_frame_footprint(self, altitude_km: float) -> Tuple[float, float]:
        """
        Compute frame footprint at nadir.

        Args:
            altitude_km: Altitude above ground in km

        Returns:
            Tuple of (along-track, cross-track) dimensions in km
        """
        gsd_m = self.compute_gsd(altitude_km)
        along_track_m = gsd_m * self.config.detector_rows
        cross_track_m = gsd_m * self.config.detector_cols
        return (along_track_m / 1000.0, cross_track_m / 1000.0)

    def compute_data_volume(self, num_frames: int) -> float:
        """
        Compute data volume for given number of frames.

        Args:
            num_frames: Number of frames

        Returns:
            Data volume in GB
        """
        pixels_per_frame = self.config.detector_rows * self.config.detector_cols
        bits_per_frame = pixels_per_frame * self.config.bits_per_pixel

        # Apply compression
        compressed_bits = bits_per_frame / self.config.compression_ratio

        # Total in GB
        total_bits = compressed_bits * num_frames
        return total_bits / (8 * 1e9)

    def compute_frame_data_mb(self) -> float:
        """
        Compute data volume for a single frame in MB.

        Returns:
            Data volume in MB
        """
        pixels_per_frame = self.config.detector_rows * self.config.detector_cols
        bits_per_frame = pixels_per_frame * self.config.bits_per_pixel
        compressed_bits = bits_per_frame / self.config.compression_ratio
        return compressed_bits / (8 * 1e6)

    def compute_off_nadir_gsd(
        self,
        altitude_km: float,
        off_nadir_angle_deg: float,
    ) -> float:
        """
        Compute GSD for off-nadir pointing.

        GSD degrades with off-nadir angle due to:
        1. Increased slant range
        2. Geometric foreshortening

        Args:
            altitude_km: Altitude above ground in km
            off_nadir_angle_deg: Off-nadir pointing angle in degrees

        Returns:
            GSD in meters
        """
        nadir_gsd = self.compute_gsd(altitude_km)

        # Slant range effect
        cos_angle = np.cos(np.radians(off_nadir_angle_deg))
        if cos_angle <= 0.1:  # Avoid extreme angles
            return float('inf')

        # GSD scales with 1/cos for slant range, and 1/cos for foreshortening
        # Combined effect approximately scales as 1/cos^2 in cross-track
        return nadir_gsd / cos_angle


class ImagingAccessModel:
    """
    Model for computing imaging access windows to targets.

    Handles cross-track and along-track pointing constraints.
    """

    def __init__(
        self,
        max_cross_track_deg: float = 30.0,
        max_along_track_deg: float = 5.0,
        min_elevation_deg: float = 20.0,
    ):
        """
        Initialize access model.

        Args:
            max_cross_track_deg: Maximum cross-track pointing angle
            max_along_track_deg: Maximum along-track pointing angle
            min_elevation_deg: Minimum elevation angle for target
        """
        self.max_cross_track_deg = max_cross_track_deg
        self.max_along_track_deg = max_along_track_deg
        self.min_elevation_deg = min_elevation_deg

    def decompose_off_nadir(
        self,
        sc_position_eci: np.ndarray,
        sc_velocity_eci: np.ndarray,
        target_position_eci: np.ndarray,
    ) -> Tuple[float, float]:
        """
        Decompose off-nadir angle into cross-track and along-track components.

        Args:
            sc_position_eci: Spacecraft position in ECI (km)
            sc_velocity_eci: Spacecraft velocity in ECI (km/s)
            target_position_eci: Target position in ECI (km)

        Returns:
            Tuple of (cross_track_angle_deg, along_track_angle_deg)
        """
        # Spacecraft nadir vector (points to Earth center)
        r_sc = sc_position_eci
        r_sc_unit = -r_sc / np.linalg.norm(r_sc)

        # Vector from spacecraft to target
        los = target_position_eci - sc_position_eci
        los_unit = los / np.linalg.norm(los)

        # Along-track direction (velocity direction projected to local horizontal)
        v_unit = sc_velocity_eci / np.linalg.norm(sc_velocity_eci)

        # Cross-track direction (perpendicular to both nadir and along-track)
        cross_track_unit = np.cross(r_sc_unit, v_unit)
        cross_track_unit = cross_track_unit / np.linalg.norm(cross_track_unit)

        # Recalculate along-track to ensure orthogonality
        along_track_unit = np.cross(cross_track_unit, r_sc_unit)
        along_track_unit = along_track_unit / np.linalg.norm(along_track_unit)

        # Project LOS onto the local reference frame
        los_nadir = np.dot(los_unit, r_sc_unit)
        los_cross = np.dot(los_unit, cross_track_unit)
        los_along = np.dot(los_unit, along_track_unit)

        # Compute angles
        # Cross-track angle: angle in the nadir-cross plane
        cross_track_rad = np.arctan2(los_cross, los_nadir)

        # Along-track angle: angle in the nadir-along plane
        along_track_rad = np.arctan2(los_along, los_nadir)

        return (np.degrees(cross_track_rad), np.degrees(along_track_rad))

    def is_valid_collect(
        self,
        cross_track_deg: float,
        along_track_deg: float,
    ) -> bool:
        """
        Check if pointing angles are within constraints.

        Args:
            cross_track_deg: Cross-track angle in degrees
            along_track_deg: Along-track angle in degrees

        Returns:
            True if valid for collection
        """
        return (
            abs(cross_track_deg) <= self.max_cross_track_deg
            and abs(along_track_deg) <= self.max_along_track_deg
        )

    def compute_target_access(
        self,
        ephemeris: list,
        target_lat_deg: float,
        target_lon_deg: float,
    ) -> List[ImagingWindow]:
        """
        Compute access windows to a target.

        Args:
            ephemeris: List of EphemerisPoint objects
            target_lat_deg: Target latitude in degrees
            target_lon_deg: Target longitude in degrees

        Returns:
            List of ImagingWindow objects
        """
        from sim.core.time_utils import datetime_to_jd, gmst

        windows = []
        in_access = False
        window_start = None
        min_cross = float('inf')
        max_cross = float('-inf')
        min_along = float('inf')
        max_along = float('-inf')

        for point in ephemeris:
            # Convert target lat/lon to ECI
            target_eci = self._latlon_to_eci(
                target_lat_deg, target_lon_deg, point.time
            )

            # Compute pointing angles
            cross_track, along_track = self.decompose_off_nadir(
                point.position_eci,
                point.velocity_eci,
                target_eci,
            )

            valid = self.is_valid_collect(cross_track, along_track)

            if valid and not in_access:
                # Access start
                window_start = point.time
                in_access = True
                min_cross = cross_track
                max_cross = cross_track
                min_along = along_track
                max_along = along_track
            elif valid and in_access:
                # Continue in access
                min_cross = min(min_cross, cross_track)
                max_cross = max(max_cross, cross_track)
                min_along = min(min_along, along_track)
                max_along = max(max_along, along_track)
            elif not valid and in_access:
                # Access end
                if window_start:
                    windows.append(ImagingWindow(
                        target_id="",
                        start_time=window_start,
                        end_time=point.time,
                        min_cross_track_deg=min_cross,
                        max_cross_track_deg=max_cross,
                        min_along_track_deg=min_along,
                        max_along_track_deg=max_along,
                    ))
                in_access = False
                window_start = None

        # Handle case where ephemeris ends in access
        if in_access and window_start:
            windows.append(ImagingWindow(
                target_id="",
                start_time=window_start,
                end_time=ephemeris[-1].time,
                min_cross_track_deg=min_cross,
                max_cross_track_deg=max_cross,
                min_along_track_deg=min_along,
                max_along_track_deg=max_along,
            ))

        return windows

    def _latlon_to_eci(
        self,
        lat_deg: float,
        lon_deg: float,
        epoch: datetime,
    ) -> np.ndarray:
        """
        Convert lat/lon to ECI coordinates.

        Args:
            lat_deg: Latitude in degrees
            lon_deg: Longitude in degrees
            epoch: Time for coordinate transformation

        Returns:
            Position in ECI (km)
        """
        from sim.core.time_utils import datetime_to_jd, gmst

        lat_rad = np.radians(lat_deg)
        lon_rad = np.radians(lon_deg)

        # Position in ECEF
        x_ecef = EARTH_RADIUS_KM * np.cos(lat_rad) * np.cos(lon_rad)
        y_ecef = EARTH_RADIUS_KM * np.cos(lat_rad) * np.sin(lon_rad)
        z_ecef = EARTH_RADIUS_KM * np.sin(lat_rad)

        # Rotate to ECI using GMST
        jd = datetime_to_jd(epoch)
        theta = gmst(jd)

        cos_theta = np.cos(theta)
        sin_theta = np.sin(theta)

        x_eci = cos_theta * x_ecef - sin_theta * y_ecef
        y_eci = sin_theta * x_ecef + cos_theta * y_ecef
        z_eci = z_ecef

        return np.array([x_eci, y_eci, z_eci])
