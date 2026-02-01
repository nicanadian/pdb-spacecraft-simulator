"""Stable schema for GMAT baseline storage."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class GMATEphemerisRecord:
    """Single ephemeris point - stable schema."""

    epoch_utc: str  # ISO8601 format
    epoch_jd: float  # Julian date
    x_km: float  # ECI position
    y_km: float
    z_km: float
    vx_km_s: float  # ECI velocity
    vy_km_s: float
    vz_km_s: float

    @classmethod
    def from_dict(cls, data: Dict) -> "GMATEphemerisRecord":
        """Create from dictionary."""
        return cls(
            epoch_utc=data["epoch_utc"],
            epoch_jd=data["epoch_jd"],
            x_km=data["x_km"],
            y_km=data["y_km"],
            z_km=data["z_km"],
            vx_km_s=data["vx_km_s"],
            vy_km_s=data["vy_km_s"],
            vz_km_s=data["vz_km_s"],
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class GMATBaselineMetadata:
    """Provenance metadata for baselines."""

    scenario_id: str
    scenario_hash: str  # Hash of ScenarioConfig for reproducibility
    gmat_version: Optional[str]
    execution_timestamp: str  # ISO8601 format
    frame: str = "EarthMJ2000Eq"
    units: Dict[str, str] = field(default_factory=lambda: {
        "position": "km",
        "velocity": "km/s",
        "time": "UTC",
    })

    @classmethod
    def from_dict(cls, data: Dict) -> "GMATBaselineMetadata":
        """Create from dictionary."""
        return cls(
            scenario_id=data["scenario_id"],
            scenario_hash=data["scenario_hash"],
            gmat_version=data.get("gmat_version"),
            execution_timestamp=data["execution_timestamp"],
            frame=data.get("frame", "EarthMJ2000Eq"),
            units=data.get("units", {"position": "km", "velocity": "km/s", "time": "UTC"}),
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class GMATBaseline:
    """Complete baseline for storage."""

    metadata: GMATBaselineMetadata
    ephemeris: List[GMATEphemerisRecord]
    schema_version: str = "1.0"

    @property
    def num_points(self) -> int:
        """Number of ephemeris points."""
        return len(self.ephemeris)

    @property
    def start_epoch(self) -> Optional[str]:
        """First epoch in baseline."""
        if self.ephemeris:
            return self.ephemeris[0].epoch_utc
        return None

    @property
    def end_epoch(self) -> Optional[str]:
        """Last epoch in baseline."""
        if self.ephemeris:
            return self.ephemeris[-1].epoch_utc
        return None

    @classmethod
    def from_dict(cls, data: Dict) -> "GMATBaseline":
        """Create from dictionary."""
        metadata = GMATBaselineMetadata.from_dict(data["metadata"])
        ephemeris = [
            GMATEphemerisRecord.from_dict(rec) for rec in data["ephemeris"]
        ]
        return cls(
            metadata=metadata,
            ephemeris=ephemeris,
            schema_version=data.get("schema_version", "1.0"),
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "schema_version": self.schema_version,
            "metadata": self.metadata.to_dict(),
            "ephemeris": [rec.to_dict() for rec in self.ephemeris],
        }

    @classmethod
    def from_json(cls, path: Path) -> "GMATBaseline":
        """Load baseline from JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def to_json(self, path: Path, indent: int = 2) -> None:
        """Save baseline to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=indent)

    def to_dataframe(self):
        """Convert ephemeris to pandas DataFrame."""
        import pandas as pd

        records = []
        for rec in self.ephemeris:
            records.append({
                "time": pd.to_datetime(rec.epoch_utc),
                "epoch_jd": rec.epoch_jd,
                "x_km": rec.x_km,
                "y_km": rec.y_km,
                "z_km": rec.z_km,
                "vx_km_s": rec.vx_km_s,
                "vy_km_s": rec.vy_km_s,
                "vz_km_s": rec.vz_km_s,
            })

        df = pd.DataFrame(records)
        if len(df) > 0:
            df = df.sort_values("time").reset_index(drop=True)
        return df


def datetime_to_jd(dt: datetime) -> float:
    """
    Convert datetime to Julian Date.

    Uses the standard algorithm for JD conversion.
    """
    year = dt.year
    month = dt.month
    day = dt.day
    hour = dt.hour
    minute = dt.minute
    second = dt.second + dt.microsecond / 1_000_000

    if month <= 2:
        year -= 1
        month += 12

    a = int(year / 100)
    b = 2 - a + int(a / 4)

    jd = int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524.5
    jd += (hour + minute / 60 + second / 3600) / 24

    return jd
