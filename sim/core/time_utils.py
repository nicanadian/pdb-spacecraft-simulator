"""Time handling utilities for spacecraft simulation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Union

import numpy as np

# Julian date of J2000 epoch (2000-01-01 12:00:00 TT)
J2000_JD = 2451545.0

# Seconds per day
SECONDS_PER_DAY = 86400.0


def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is UTC-aware."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def datetime_to_jd(dt: datetime) -> float:
    """
    Convert datetime to Julian Date.

    Args:
        dt: UTC datetime

    Returns:
        Julian date as float
    """
    dt = ensure_utc(dt)

    year = dt.year
    month = dt.month
    day = dt.day
    hour = dt.hour
    minute = dt.minute
    second = dt.second + dt.microsecond / 1e6

    # Handle January/February as months 13/14 of previous year
    if month <= 2:
        year -= 1
        month += 12

    # Gregorian calendar
    A = int(year / 100)
    B = 2 - A + int(A / 4)

    jd = (
        int(365.25 * (year + 4716))
        + int(30.6001 * (month + 1))
        + day
        + B
        - 1524.5
        + (hour + minute / 60 + second / 3600) / 24
    )

    return jd


def jd_to_datetime(jd: float) -> datetime:
    """
    Convert Julian Date to UTC datetime.

    Args:
        jd: Julian date

    Returns:
        UTC datetime
    """
    jd = jd + 0.5
    Z = int(jd)
    F = jd - Z

    if Z < 2299161:
        A = Z
    else:
        alpha = int((Z - 1867216.25) / 36524.25)
        A = Z + 1 + alpha - int(alpha / 4)

    B = A + 1524
    C = int((B - 122.1) / 365.25)
    D = int(365.25 * C)
    E = int((B - D) / 30.6001)

    day = B - D - int(30.6001 * E)

    if E < 14:
        month = E - 1
    else:
        month = E - 13

    if month > 2:
        year = C - 4716
    else:
        year = C - 4715

    # Extract time
    day_fraction = F
    hour = int(day_fraction * 24)
    day_fraction = day_fraction * 24 - hour
    minute = int(day_fraction * 60)
    day_fraction = day_fraction * 60 - minute
    second = day_fraction * 60
    microsecond = int((second - int(second)) * 1e6)
    second = int(second)

    return datetime(year, month, day, hour, minute, second, microsecond, tzinfo=timezone.utc)


def datetime_to_j2000_seconds(dt: datetime) -> float:
    """
    Convert datetime to seconds since J2000 epoch.

    Args:
        dt: UTC datetime

    Returns:
        Seconds since J2000
    """
    jd = datetime_to_jd(dt)
    return (jd - J2000_JD) * SECONDS_PER_DAY


def j2000_seconds_to_datetime(seconds: float) -> datetime:
    """
    Convert seconds since J2000 to datetime.

    Args:
        seconds: Seconds since J2000

    Returns:
        UTC datetime
    """
    jd = J2000_JD + seconds / SECONDS_PER_DAY
    return jd_to_datetime(jd)


def datetime_range(
    start: datetime, end: datetime, step_s: float
) -> list[datetime]:
    """
    Generate a range of datetimes.

    Args:
        start: Start datetime
        end: End datetime
        step_s: Step size in seconds

    Returns:
        List of datetimes
    """
    start = ensure_utc(start)
    end = ensure_utc(end)

    duration_s = (end - start).total_seconds()
    n_steps = int(np.ceil(duration_s / step_s)) + 1

    times = []
    for i in range(n_steps):
        t = start.timestamp() + i * step_s
        if t <= end.timestamp():
            times.append(datetime.fromtimestamp(t, tz=timezone.utc))

    return times


def epoch_to_tle_format(dt: datetime) -> str:
    """
    Convert datetime to TLE epoch format (YYDDD.DDDDDDDD).

    Args:
        dt: UTC datetime

    Returns:
        TLE epoch string
    """
    dt = ensure_utc(dt)
    year_2digit = dt.year % 100
    day_of_year = dt.timetuple().tm_yday
    fraction_of_day = (
        dt.hour / 24 + dt.minute / 1440 + dt.second / 86400 + dt.microsecond / 86400e6
    )
    return f"{year_2digit:02d}{day_of_year + fraction_of_day:012.8f}"


def tle_epoch_to_datetime(epoch_str: str) -> datetime:
    """
    Convert TLE epoch string to datetime.

    Args:
        epoch_str: TLE epoch in YYDDD.DDDDDDDD format

    Returns:
        UTC datetime
    """
    year_2digit = int(epoch_str[:2])
    # Handle Y2K: 00-56 -> 2000-2056, 57-99 -> 1957-1999
    if year_2digit < 57:
        year = 2000 + year_2digit
    else:
        year = 1900 + year_2digit

    day_float = float(epoch_str[2:])
    day_of_year = int(day_float)
    fraction_of_day = day_float - day_of_year

    # Start of year
    dt = datetime(year, 1, 1, tzinfo=timezone.utc)

    # Add days and fraction
    from datetime import timedelta

    dt = dt + timedelta(days=day_of_year - 1 + fraction_of_day)

    return dt


def gmst(jd: float) -> float:
    """
    Compute Greenwich Mean Sidereal Time.

    Args:
        jd: Julian date

    Returns:
        GMST in radians
    """
    # Centuries since J2000
    T = (jd - J2000_JD) / 36525.0

    # GMST in seconds
    gmst_seconds = (
        67310.54841
        + (876600.0 * 3600.0 + 8640184.812866) * T
        + 0.093104 * T**2
        - 6.2e-6 * T**3
    )

    # Convert to radians (mod 2*pi)
    gmst_rad = (gmst_seconds / 86400.0 * 2.0 * np.pi) % (2.0 * np.pi)

    return gmst_rad
