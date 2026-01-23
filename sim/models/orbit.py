"""Orbit propagation models using SGP4."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

import numpy as np
from sgp4.api import Satrec, jday
from sgp4.exporter import export_tle

from sim.core.time_utils import datetime_to_jd, ensure_utc, epoch_to_tle_format

# Constants
EARTH_RADIUS_KM = 6378.137  # WGS84 equatorial radius
MU_EARTH = 398600.4418  # km^3/s^2
J2 = 1.08263e-3  # J2 perturbation coefficient
SECONDS_PER_DAY = 86400.0


@dataclass
class OrbitalElements:
    """Classical orbital elements."""

    semi_major_axis_km: float
    eccentricity: float
    inclination_deg: float
    raan_deg: float  # Right Ascension of Ascending Node
    arg_perigee_deg: float  # Argument of Perigee
    true_anomaly_deg: float
    epoch: datetime

    @property
    def altitude_km(self) -> float:
        """Approximate altitude (assumes circular orbit)."""
        return self.semi_major_axis_km - EARTH_RADIUS_KM

    @property
    def period_s(self) -> float:
        """Orbital period in seconds."""
        return 2 * np.pi * np.sqrt(self.semi_major_axis_km**3 / MU_EARTH)

    @property
    def mean_motion_rev_per_day(self) -> float:
        """Mean motion in revolutions per day."""
        return SECONDS_PER_DAY / self.period_s


@dataclass
class EphemerisPoint:
    """A single point in the ephemeris."""

    time: datetime
    position_eci: np.ndarray  # km
    velocity_eci: np.ndarray  # km/s

    @property
    def altitude_km(self) -> float:
        """Altitude above Earth's surface."""
        return np.linalg.norm(self.position_eci) - EARTH_RADIUS_KM


def generate_synthetic_tle(
    altitude_km: float,
    inclination_deg: float,
    epoch: datetime,
    raan_deg: float = 0.0,
    arg_perigee_deg: float = 0.0,
    mean_anomaly_deg: float = 0.0,
    norad_id: int = 99999,
    intl_designator: str = "00001A",
) -> Tuple[str, str]:
    """
    Generate a synthetic TLE from orbital elements.

    Assumes circular orbit (eccentricity ~ 0).

    Args:
        altitude_km: Orbital altitude in km
        inclination_deg: Inclination in degrees
        epoch: TLE epoch (UTC)
        raan_deg: Right Ascension of Ascending Node in degrees
        arg_perigee_deg: Argument of perigee in degrees
        mean_anomaly_deg: Mean anomaly in degrees
        norad_id: NORAD catalog ID
        intl_designator: International designator

    Returns:
        Tuple of (TLE line 1, TLE line 2)
    """
    epoch = ensure_utc(epoch)

    # Compute orbital parameters
    semi_major_axis_km = EARTH_RADIUS_KM + altitude_km
    period_s = 2 * np.pi * np.sqrt(semi_major_axis_km**3 / MU_EARTH)
    mean_motion = SECONDS_PER_DAY / period_s  # rev/day

    # Near-circular orbit
    eccentricity = 0.0001

    # TLE epoch format
    epoch_str = epoch_to_tle_format(epoch)

    # Create TLE lines
    # Line 1: Catalog number, classification, intl designator, epoch, derivatives, element set
    line1 = f"1 {norad_id:05d}U {intl_designator:8s} {epoch_str} "
    line1 += " .00000000  00000-0  00000-0 0  9990"

    # Line 2: Catalog number, inclination, RAAN, eccentricity, arg perigee, mean anomaly, mean motion
    ecc_str = f"{eccentricity:.7f}"[2:]  # Remove "0."
    line2 = f"2 {norad_id:05d} {inclination_deg:8.4f} {raan_deg:8.4f} {ecc_str} "
    line2 += f"{arg_perigee_deg:8.4f} {mean_anomaly_deg:8.4f} {mean_motion:11.8f}000010"

    # Compute checksums
    def tle_checksum(line: str) -> int:
        checksum = 0
        for char in line[:-1]:
            if char.isdigit():
                checksum += int(char)
            elif char == "-":
                checksum += 1
        return checksum % 10

    line1 = line1[:-1] + str(tle_checksum(line1))
    line2 = line2[:-1] + str(tle_checksum(line2))

    return line1, line2


def tle_to_state(
    tle_line1: str, tle_line2: str, epoch: datetime
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Propagate TLE to get state vector at given epoch.

    Args:
        tle_line1: TLE line 1
        tle_line2: TLE line 2
        epoch: Target epoch (UTC)

    Returns:
        Tuple of (position_eci_km, velocity_eci_km_s)
    """
    epoch = ensure_utc(epoch)

    # Create satellite object from TLE
    satellite = Satrec.twoline2rv(tle_line1, tle_line2)

    # Convert datetime to Julian date components
    jd, fr = jday(
        epoch.year,
        epoch.month,
        epoch.day,
        epoch.hour,
        epoch.minute,
        epoch.second + epoch.microsecond / 1e6,
    )

    # Propagate
    error, position, velocity = satellite.sgp4(jd, fr)

    if error != 0:
        raise RuntimeError(f"SGP4 propagation error: code {error}")

    return np.array(position), np.array(velocity)


class OrbitPropagator:
    """SGP4-based orbit propagator for LOW fidelity simulations."""

    def __init__(
        self,
        tle_line1: Optional[str] = None,
        tle_line2: Optional[str] = None,
        altitude_km: Optional[float] = None,
        inclination_deg: Optional[float] = None,
        epoch: Optional[datetime] = None,
    ):
        """
        Initialize propagator from TLE or orbital elements.

        Either provide TLE lines, or provide altitude, inclination, and epoch
        to generate a synthetic TLE.

        Args:
            tle_line1: TLE line 1
            tle_line2: TLE line 2
            altitude_km: Orbital altitude (for synthetic TLE)
            inclination_deg: Inclination (for synthetic TLE)
            epoch: Epoch (for synthetic TLE)
        """
        if tle_line1 and tle_line2:
            self.tle_line1 = tle_line1
            self.tle_line2 = tle_line2
        elif altitude_km is not None and inclination_deg is not None and epoch is not None:
            self.tle_line1, self.tle_line2 = generate_synthetic_tle(
                altitude_km=altitude_km,
                inclination_deg=inclination_deg,
                epoch=epoch,
            )
        else:
            raise ValueError("Must provide either TLE lines or orbital elements")

        self.satellite = Satrec.twoline2rv(self.tle_line1, self.tle_line2)

    def propagate(self, epoch: datetime) -> EphemerisPoint:
        """
        Propagate to a single epoch.

        Args:
            epoch: Target epoch (UTC)

        Returns:
            EphemerisPoint with position and velocity
        """
        epoch = ensure_utc(epoch)

        jd, fr = jday(
            epoch.year,
            epoch.month,
            epoch.day,
            epoch.hour,
            epoch.minute,
            epoch.second + epoch.microsecond / 1e6,
        )

        error, position, velocity = self.satellite.sgp4(jd, fr)

        if error != 0:
            raise RuntimeError(f"SGP4 propagation error: code {error}")

        return EphemerisPoint(
            time=epoch,
            position_eci=np.array(position),
            velocity_eci=np.array(velocity),
        )

    def propagate_range(
        self, start: datetime, end: datetime, step_s: float = 60.0
    ) -> list[EphemerisPoint]:
        """
        Propagate over a time range.

        Args:
            start: Start epoch (UTC)
            end: End epoch (UTC)
            step_s: Time step in seconds

        Returns:
            List of EphemerisPoints
        """
        start = ensure_utc(start)
        end = ensure_utc(end)

        duration_s = (end - start).total_seconds()
        n_steps = int(np.ceil(duration_s / step_s)) + 1

        ephemeris = []
        for i in range(n_steps):
            t = start.timestamp() + i * step_s
            if t <= end.timestamp():
                epoch = datetime.fromtimestamp(t, tz=timezone.utc)
                ephemeris.append(self.propagate(epoch))

        return ephemeris

    def get_orbital_elements(self, epoch: datetime) -> OrbitalElements:
        """
        Get classical orbital elements at epoch.

        Args:
            epoch: Target epoch (UTC)

        Returns:
            OrbitalElements
        """
        point = self.propagate(epoch)
        r = point.position_eci
        v = point.velocity_eci

        # Compute orbital elements from state vector
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
        e = np.linalg.norm(e_vec)

        # Semi-major axis
        energy = v_mag**2 / 2 - MU_EARTH / r_mag
        if abs(e - 1.0) > 1e-10:
            a = -MU_EARTH / (2 * energy)
        else:
            a = float("inf")

        # Inclination
        inc = np.arccos(h[2] / h_mag)

        # RAAN
        if n_mag > 1e-10:
            raan = np.arccos(n[0] / n_mag)
            if n[1] < 0:
                raan = 2 * np.pi - raan
        else:
            raan = 0.0

        # Argument of perigee
        if n_mag > 1e-10 and e > 1e-10:
            argp = np.arccos(np.dot(n, e_vec) / (n_mag * e))
            if e_vec[2] < 0:
                argp = 2 * np.pi - argp
        else:
            argp = 0.0

        # True anomaly
        if e > 1e-10:
            nu = np.arccos(np.dot(e_vec, r) / (e * r_mag))
            if np.dot(r, v) < 0:
                nu = 2 * np.pi - nu
        else:
            nu = np.arccos(np.dot(n, r) / (n_mag * r_mag))
            if r[2] < 0:
                nu = 2 * np.pi - nu

        return OrbitalElements(
            semi_major_axis_km=a,
            eccentricity=e,
            inclination_deg=np.degrees(inc),
            raan_deg=np.degrees(raan),
            arg_perigee_deg=np.degrees(argp),
            true_anomaly_deg=np.degrees(nu),
            epoch=epoch,
        )

    def get_period_s(self) -> float:
        """Get orbital period in seconds."""
        # Mean motion is in radians per minute in SGP4
        mean_motion_rad_min = self.satellite.no_kozai
        mean_motion_rad_s = mean_motion_rad_min / 60.0
        return 2 * np.pi / mean_motion_rad_s


def compute_lowering_delta_v(alt_start_km: float, alt_end_km: float) -> float:
    """
    Compute delta-V for low-thrust spiral altitude change.

    For circular orbit altitude change, the delta-V is approximately
    the difference in orbital velocities: dV = |v1 - v2|

    Args:
        alt_start_km: Starting altitude in km
        alt_end_km: Ending altitude in km

    Returns:
        Delta-V in km/s
    """
    r1 = EARTH_RADIUS_KM + alt_start_km
    r2 = EARTH_RADIUS_KM + alt_end_km

    v1 = np.sqrt(MU_EARTH / r1)
    v2 = np.sqrt(MU_EARTH / r2)

    return abs(v1 - v2)


def circular_velocity(altitude_km: float) -> float:
    """
    Compute circular orbital velocity at given altitude.

    Args:
        altitude_km: Altitude in km

    Returns:
        Velocity in km/s
    """
    r = EARTH_RADIUS_KM + altitude_km
    return np.sqrt(MU_EARTH / r)


def orbital_period(altitude_km: float) -> float:
    """
    Compute orbital period at given altitude.

    Args:
        altitude_km: Altitude in km

    Returns:
        Period in seconds
    """
    r = EARTH_RADIUS_KM + altitude_km
    return 2 * np.pi * np.sqrt(r**3 / MU_EARTH)
