"""Core data structures for spacecraft simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


class Fidelity(str, Enum):
    """Simulation fidelity levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EventType(str, Enum):
    """Types of simulation events."""

    INFO = "INFO"
    WARNING = "WARNING"
    VIOLATION = "VIOLATION"
    ERROR = "ERROR"


class ActivityType(str, Enum):
    """Types of activities."""

    ORBIT_LOWER = "orbit_lower"
    EO_COLLECT = "eo_collect"
    DOWNLINK = "downlink"
    IDLE = "idle"


@dataclass
class Quaternion:
    """Attitude quaternion (scalar-last convention: [x, y, z, w])."""

    x: float
    y: float
    z: float
    w: float

    def to_array(self) -> np.ndarray:
        """Convert to numpy array."""
        return np.array([self.x, self.y, self.z, self.w])

    @classmethod
    def identity(cls) -> "Quaternion":
        """Return identity quaternion."""
        return cls(x=0.0, y=0.0, z=0.0, w=1.0)

    @classmethod
    def from_array(cls, arr: np.ndarray) -> "Quaternion":
        """Create from numpy array."""
        return cls(x=arr[0], y=arr[1], z=arr[2], w=arr[3])


@dataclass
class InitialState:
    """Spacecraft initial state for simulation."""

    epoch: datetime
    position_eci: np.ndarray  # km, ECI J2000
    velocity_eci: np.ndarray  # km/s, ECI J2000
    attitude: Optional[Quaternion] = None
    mass_kg: float = 500.0
    propellant_kg: float = 50.0
    battery_soc: float = 1.0  # State of charge [0, 1]
    storage_used_gb: float = 0.0

    def __post_init__(self):
        """Validate state."""
        if not 0.0 <= self.battery_soc <= 1.0:
            raise ValueError(f"battery_soc must be in [0, 1], got {self.battery_soc}")
        if self.propellant_kg < 0:
            raise ValueError(f"propellant_kg must be >= 0, got {self.propellant_kg}")
        if self.storage_used_gb < 0:
            raise ValueError(f"storage_used_gb must be >= 0, got {self.storage_used_gb}")
        if self.attitude is None:
            self.attitude = Quaternion.identity()

    def copy(self) -> "InitialState":
        """Create a copy of this state."""
        return InitialState(
            epoch=self.epoch,
            position_eci=self.position_eci.copy(),
            velocity_eci=self.velocity_eci.copy(),
            attitude=Quaternion.from_array(self.attitude.to_array()),
            mass_kg=self.mass_kg,
            propellant_kg=self.propellant_kg,
            battery_soc=self.battery_soc,
            storage_used_gb=self.storage_used_gb,
        )


@dataclass
class Activity:
    """A scheduled activity in the mission plan."""

    activity_id: str
    activity_type: str  # "orbit_lower", "eo_collect", "downlink", etc.
    start_time: datetime
    end_time: datetime
    parameters: dict = field(default_factory=dict)

    def __post_init__(self):
        """Validate activity."""
        if self.end_time <= self.start_time:
            raise ValueError(
                f"end_time ({self.end_time}) must be after start_time ({self.start_time})"
            )

    @property
    def duration_s(self) -> float:
        """Duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()


@dataclass
class PlanInput:
    """Mission plan input for simulation."""

    spacecraft_id: str
    plan_id: str
    activities: list[Activity]

    def __post_init__(self):
        """Sort activities by start time."""
        self.activities = sorted(self.activities, key=lambda a: a.start_time)

    @property
    def start_time(self) -> datetime:
        """Plan start time."""
        if not self.activities:
            raise ValueError("Plan has no activities")
        return self.activities[0].start_time

    @property
    def end_time(self) -> datetime:
        """Plan end time."""
        if not self.activities:
            raise ValueError("Plan has no activities")
        return max(a.end_time for a in self.activities)


@dataclass
class Event:
    """A simulation event (violation, warning, info)."""

    timestamp: datetime
    event_type: EventType
    category: str
    message: str
    details: dict = field(default_factory=dict)


@dataclass
class PointTarget:
    """A point target for imaging."""

    target_id: str
    lat_deg: float
    lon_deg: float
    priority: int = 1
    min_sun_elevation_deg: float = 10.0

    def __post_init__(self):
        """Validate coordinates."""
        if not -90.0 <= self.lat_deg <= 90.0:
            raise ValueError(f"lat_deg must be in [-90, 90], got {self.lat_deg}")
        if not -180.0 <= self.lon_deg <= 180.0:
            raise ValueError(f"lon_deg must be in [-180, 180], got {self.lon_deg}")


class SpacecraftConfig(BaseModel):
    """Spacecraft configuration."""

    spacecraft_id: str
    dry_mass_kg: float = Field(default=450.0, ge=0)
    initial_propellant_kg: float = Field(default=50.0, ge=0)
    battery_capacity_wh: float = Field(default=5000.0, ge=0)
    storage_capacity_gb: float = Field(default=500.0, ge=0)
    solar_panel_area_m2: float = Field(default=10.0, ge=0)
    solar_efficiency: float = Field(default=0.30, ge=0, le=1)
    base_power_w: float = Field(default=200.0, ge=0)

    def config_hash(self) -> str:
        """Generate hash for caching."""
        import hashlib
        import json

        data = self.model_dump()
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]


class SimConfig(BaseModel):
    """Simulation configuration."""

    fidelity: Fidelity = Fidelity.LOW
    time_step_s: float = Field(default=60.0, gt=0)
    spacecraft: SpacecraftConfig
    output_dir: str = "runs"
    enable_cache: bool = True
    random_seed: Optional[int] = 42

    def config_hash(self) -> str:
        """Generate hash for caching."""
        import hashlib
        import json

        data = self.model_dump()
        data["fidelity"] = data["fidelity"].value
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class SimResults:
    """Simulation results."""

    profiles: pd.DataFrame  # Time-indexed resource profiles
    events: list[Event]  # Violations, notable events
    artifacts: dict[str, str]  # File paths for outputs
    final_state: InitialState  # For chaining simulations
    summary: dict[str, Any] = field(default_factory=dict)

    def has_violations(self) -> bool:
        """Check if any constraint violations occurred."""
        return any(e.event_type == EventType.VIOLATION for e in self.events)

    def violation_count(self) -> int:
        """Count constraint violations."""
        return sum(1 for e in self.events if e.event_type == EventType.VIOLATION)
