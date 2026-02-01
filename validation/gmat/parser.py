"""Parser for GMAT output report files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class GMATEphemerisPoint:
    """A single point from GMAT ephemeris output."""

    time: datetime
    position_eci: np.ndarray  # km
    velocity_eci: np.ndarray  # km/s

    @property
    def altitude_km(self) -> float:
        """Altitude above Earth's surface."""
        EARTH_RADIUS_KM = 6378.137
        return np.linalg.norm(self.position_eci) - EARTH_RADIUS_KM


@dataclass
class GMATKeplerianPoint:
    """A single point from GMAT Keplerian output."""

    time: datetime
    sma_km: float
    ecc: float
    inc_deg: float
    raan_deg: float
    aop_deg: float
    ta_deg: float
    altitude_km: float


@dataclass
class GMATAccessWindow:
    """A ground station access window from GMAT."""

    station_id: str
    start_time: datetime
    end_time: datetime
    duration_s: float


class GMATOutputParser:
    """Parser for GMAT report files."""

    # GMAT date format: "01 Jan 2025 00:00:00.000"
    GMAT_DATE_FORMAT = "%d %b %Y %H:%M:%S.%f"

    # Alternate format without milliseconds
    GMAT_DATE_FORMAT_ALT = "%d %b %Y %H:%M:%S"

    def __init__(self):
        """Initialize parser."""
        pass

    def parse_datetime(self, date_str: str) -> datetime:
        """
        Parse GMAT datetime string.

        Args:
            date_str: GMAT datetime string

        Returns:
            datetime object (UTC)
        """
        date_str = date_str.strip()

        try:
            dt = datetime.strptime(date_str, self.GMAT_DATE_FORMAT)
        except ValueError:
            try:
                dt = datetime.strptime(date_str, self.GMAT_DATE_FORMAT_ALT)
            except ValueError:
                # Try ISO format as fallback
                dt = datetime.fromisoformat(date_str.replace(" ", "T"))

        return dt.replace(tzinfo=timezone.utc)

    def parse_ephemeris_report(self, filepath: Path) -> pd.DataFrame:
        """
        Parse GMAT ephemeris report file.

        Expected format (space-delimited):
        UTCGregorian X Y Z VX VY VZ

        Args:
            filepath: Path to ephemeris report file

        Returns:
            DataFrame with columns: time, x_km, y_km, z_km, vx_km_s, vy_km_s, vz_km_s
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"Ephemeris file not found: {filepath}")

        records = []
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()

                # Skip empty lines and headers
                if not line or line.startswith("#") or "UTCGregorian" in line:
                    continue

                # Parse space-delimited values
                parts = line.split()
                if len(parts) < 10:  # Date takes 4 parts + 6 values
                    continue

                try:
                    # Date is first 4 parts: "15 Jan 2025 00:00:00.000"
                    date_str = " ".join(parts[:4])
                    dt = self.parse_datetime(date_str)

                    # Position and velocity
                    x = float(parts[4])
                    y = float(parts[5])
                    z = float(parts[6])
                    vx = float(parts[7])
                    vy = float(parts[8])
                    vz = float(parts[9])

                    records.append({
                        "time": dt,
                        "x_km": x,
                        "y_km": y,
                        "z_km": z,
                        "vx_km_s": vx,
                        "vy_km_s": vy,
                        "vz_km_s": vz,
                    })
                except (ValueError, IndexError) as e:
                    continue  # Skip malformed lines

        df = pd.DataFrame(records)

        if len(df) > 0:
            df = df.sort_values("time").reset_index(drop=True)
            # Calculate altitude
            df["altitude_km"] = np.sqrt(
                df["x_km"]**2 + df["y_km"]**2 + df["z_km"]**2
            ) - 6378.137

        return df

    def parse_keplerian_report(self, filepath: Path) -> pd.DataFrame:
        """
        Parse GMAT Keplerian elements report file.

        Expected format (space-delimited):
        UTCGregorian SMA ECC INC RAAN AOP TA Altitude

        Args:
            filepath: Path to Keplerian report file

        Returns:
            DataFrame with orbital elements
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"Keplerian file not found: {filepath}")

        records = []
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()

                # Skip empty lines and headers
                if not line or line.startswith("#") or "UTCGregorian" in line:
                    continue

                parts = line.split()
                if len(parts) < 11:  # Date (4) + 7 values
                    continue

                try:
                    date_str = " ".join(parts[:4])
                    dt = self.parse_datetime(date_str)

                    records.append({
                        "time": dt,
                        "sma_km": float(parts[4]),
                        "ecc": float(parts[5]),
                        "inc_deg": float(parts[6]),
                        "raan_deg": float(parts[7]),
                        "aop_deg": float(parts[8]),
                        "ta_deg": float(parts[9]),
                        "altitude_km": float(parts[10]),
                    })
                except (ValueError, IndexError):
                    continue

        df = pd.DataFrame(records)

        if len(df) > 0:
            df = df.sort_values("time").reset_index(drop=True)

        return df

    def parse_access_report(self, filepath: Path) -> List[GMATAccessWindow]:
        """
        Parse GMAT contact locator output file.

        GMAT ContactLocator output format varies, but typically:
        Start time, Stop time, Duration

        Args:
            filepath: Path to access report file

        Returns:
            List of access windows
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"Access file not found: {filepath}")

        # Extract station ID from filename (e.g., access_Svalbard_scenario.txt)
        station_id = filepath.stem.split("_")[1] if "_" in filepath.stem else "unknown"

        windows = []
        with open(filepath, "r") as f:
            content = f.read()

        # Parse GMAT contact report format
        # Look for lines with start/stop times
        for line in content.split("\n"):
            line = line.strip()

            # Skip headers and empty lines
            if not line or line.startswith("#") or "Start" in line:
                continue

            # Try to parse as: StartTime StopTime Duration
            parts = line.split()
            if len(parts) >= 8:  # Two dates (4 parts each)
                try:
                    start_str = " ".join(parts[:4])
                    end_str = " ".join(parts[4:8])
                    start = self.parse_datetime(start_str)
                    end = self.parse_datetime(end_str)

                    if end > start:
                        windows.append(GMATAccessWindow(
                            station_id=station_id,
                            start_time=start,
                            end_time=end,
                            duration_s=(end - start).total_seconds(),
                        ))
                except (ValueError, IndexError):
                    continue

        return windows

    def parse_propellant_report(self, filepath: Path) -> pd.DataFrame:
        """
        Parse GMAT propellant/mass report file.

        Expected format:
        UTCGregorian FuelMass TotalMass Altitude

        Args:
            filepath: Path to propellant report file

        Returns:
            DataFrame with propellant data
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"Propellant file not found: {filepath}")

        records = []
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()

                if not line or line.startswith("#") or "UTCGregorian" in line:
                    continue

                parts = line.split()
                if len(parts) < 7:  # Date (4) + 3 values
                    continue

                try:
                    date_str = " ".join(parts[:4])
                    dt = self.parse_datetime(date_str)

                    records.append({
                        "time": dt,
                        "fuel_mass_kg": float(parts[4]),
                        "total_mass_kg": float(parts[5]),
                        "altitude_km": float(parts[6]),
                    })
                except (ValueError, IndexError):
                    continue

        df = pd.DataFrame(records)

        if len(df) > 0:
            df = df.sort_values("time").reset_index(drop=True)

        return df

    def parse_thrust_report(self, filepath: Path) -> pd.DataFrame:
        """
        Parse GMAT thrust report file.

        Expected format:
        UTCGregorian TrueAnomaly ThrustOn FuelMass

        Args:
            filepath: Path to thrust report file

        Returns:
            DataFrame with thrust data
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"Thrust file not found: {filepath}")

        records = []
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()

                if not line or line.startswith("#") or "UTCGregorian" in line:
                    continue

                parts = line.split()
                if len(parts) < 7:  # Date (4) + 3 values
                    continue

                try:
                    date_str = " ".join(parts[:4])
                    dt = self.parse_datetime(date_str)

                    records.append({
                        "time": dt,
                        "true_anomaly_deg": float(parts[4]),
                        "thrust_on": float(parts[5]) > 0.5,
                        "fuel_mass_kg": float(parts[6]),
                    })
                except (ValueError, IndexError):
                    continue

        df = pd.DataFrame(records)

        if len(df) > 0:
            df = df.sort_values("time").reset_index(drop=True)

        return df

    def ephemeris_to_points(self, df: pd.DataFrame) -> List[GMATEphemerisPoint]:
        """
        Convert ephemeris DataFrame to list of GMATEphemerisPoint.

        Args:
            df: Ephemeris DataFrame

        Returns:
            List of ephemeris points
        """
        points = []
        for _, row in df.iterrows():
            points.append(GMATEphemerisPoint(
                time=row["time"],
                position_eci=np.array([row["x_km"], row["y_km"], row["z_km"]]),
                velocity_eci=np.array([row["vx_km_s"], row["vy_km_s"], row["vz_km_s"]]),
            ))
        return points

    def keplerian_to_points(self, df: pd.DataFrame) -> List[GMATKeplerianPoint]:
        """
        Convert Keplerian DataFrame to list of GMATKeplerianPoint.

        Args:
            df: Keplerian DataFrame

        Returns:
            List of Keplerian points
        """
        points = []
        for _, row in df.iterrows():
            points.append(GMATKeplerianPoint(
                time=row["time"],
                sma_km=row["sma_km"],
                ecc=row["ecc"],
                inc_deg=row["inc_deg"],
                raan_deg=row["raan_deg"],
                aop_deg=row["aop_deg"],
                ta_deg=row["ta_deg"],
                altitude_km=row["altitude_km"],
            ))
        return points

    def to_baseline(
        self,
        ephemeris_df: pd.DataFrame,
        scenario_id: str,
        scenario_config,
        gmat_version: Optional[str] = None,
    ):
        """
        Convert parsed ephemeris DataFrame to GMATBaseline.

        Args:
            ephemeris_df: Parsed ephemeris DataFrame with time, x_km, etc.
            scenario_id: Scenario identifier
            scenario_config: ScenarioConfig used to generate the data
            gmat_version: Optional GMAT version string

        Returns:
            GMATBaseline ready for storage
        """
        from .baseline_manager import create_baseline_from_ephemeris

        return create_baseline_from_ephemeris(
            scenario_id=scenario_id,
            scenario_config=scenario_config,
            ephemeris_df=ephemeris_df,
            gmat_version=gmat_version,
        )


def load_reference_ephemeris(scenario_id: str, reference_dir: Optional[Path] = None) -> pd.DataFrame:
    """
    Load reference ephemeris for a scenario.

    Args:
        scenario_id: Scenario identifier
        reference_dir: Path to reference data directory

    Returns:
        Ephemeris DataFrame
    """
    if reference_dir is None:
        reference_dir = Path(__file__).parent.parent / "reference"

    parser = GMATOutputParser()

    # Try different locations
    possible_paths = [
        reference_dir / "pure_propagation" / f"ephemeris_{scenario_id}.txt",
        reference_dir / "orbit_lowering" / f"ephemeris_{scenario_id}.txt",
        reference_dir / f"ephemeris_{scenario_id}.txt",
    ]

    for path in possible_paths:
        if path.exists():
            return parser.parse_ephemeris_report(path)

    raise FileNotFoundError(f"Reference ephemeris not found for scenario: {scenario_id}")


def load_reference_access(
    scenario_id: str,
    station_id: str,
    reference_dir: Optional[Path] = None
) -> List[GMATAccessWindow]:
    """
    Load reference access windows for a scenario and station.

    Args:
        scenario_id: Scenario identifier
        station_id: Ground station identifier
        reference_dir: Path to reference data directory

    Returns:
        List of access windows
    """
    if reference_dir is None:
        reference_dir = Path(__file__).parent.parent / "reference"

    parser = GMATOutputParser()

    possible_paths = [
        reference_dir / "access_windows" / f"access_{station_id}_{scenario_id}.txt",
        reference_dir / f"access_{station_id}_{scenario_id}.txt",
    ]

    for path in possible_paths:
        if path.exists():
            return parser.parse_access_report(path)

    raise FileNotFoundError(
        f"Reference access not found for scenario: {scenario_id}, station: {station_id}"
    )
