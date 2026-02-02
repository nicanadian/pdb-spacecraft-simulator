"""
Activity to Basilisk segment mappers.

Maps high-level activities from mission plans to low-level simulation
segments including attitude profiles, power consumption, and resource usage.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

from sim.core.types import Activity, Event, EventType, SimConfig


@dataclass
class AttitudeProfile:
    """Attitude profile for a simulation segment."""

    profile_type: str  # "nadir", "target", "sun", "inertial"
    target_vector: Optional[NDArray[np.float64]] = None  # Target direction
    slew_rate_deg_s: float = 1.0  # Maximum slew rate
    settling_time_s: float = 10.0  # Time to settle after slew


@dataclass
class PowerProfile:
    """Power consumption profile for a segment."""

    base_power_w: float = 100.0
    peak_power_w: float = 100.0
    duty_cycle: float = 1.0  # Fraction of time at peak
    solar_generation_w: float = 0.0  # Expected generation (0 in eclipse)


@dataclass
class ThrustProfile:
    """Thrust profile for propulsion segments."""

    thrust_n: float = 0.0
    isp_s: float = 1500.0
    direction: NDArray[np.float64] = field(default_factory=lambda: np.array([1, 0, 0]))
    duty_cycle: float = 1.0
    power_w: float = 500.0  # EP power consumption


@dataclass
class DataProfile:
    """Data flow profile for the segment."""

    generation_rate_mbps: float = 0.0  # SSR fill rate
    transmission_rate_mbps: float = 0.0  # SSR drain rate
    processing_mode: str = "none"  # "none", "onboard", "compress"
    compression_ratio: float = 1.0


@dataclass
class SimulationSegmentSpec:
    """Complete specification for a simulation segment."""

    start_time: datetime
    end_time: datetime
    segment_type: str
    activity_id: Optional[str] = None

    # Profiles
    attitude: AttitudeProfile = field(default_factory=AttitudeProfile)
    power: PowerProfile = field(default_factory=PowerProfile)
    thrust: ThrustProfile = field(default_factory=ThrustProfile)
    data: DataProfile = field(default_factory=DataProfile)

    # Additional parameters
    parameters: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_s(self) -> float:
        return (self.end_time - self.start_time).total_seconds()


class ActivityMapper(ABC):
    """Base class for activity mappers."""

    @property
    @abstractmethod
    def activity_type(self) -> str:
        """Activity type this mapper handles."""
        pass

    @abstractmethod
    def map(
        self,
        activity: Activity,
        config: SimConfig,
    ) -> List[SimulationSegmentSpec]:
        """
        Map an activity to simulation segment specifications.

        Args:
            activity: Activity to map
            config: Simulation configuration

        Returns:
            List of segment specifications
        """
        pass

    def validate(self, activity: Activity, config: SimConfig) -> List[Event]:
        """Validate activity parameters."""
        return []


class IdleMapper(ActivityMapper):
    """Maps idle/coast periods to simulation segments."""

    @property
    def activity_type(self) -> str:
        return "idle"

    def map(
        self,
        activity: Activity,
        config: SimConfig,
    ) -> List[SimulationSegmentSpec]:
        return [
            SimulationSegmentSpec(
                start_time=activity.start_time,
                end_time=activity.end_time,
                segment_type="idle",
                activity_id=activity.activity_id,
                attitude=AttitudeProfile(profile_type="nadir"),
                power=PowerProfile(
                    base_power_w=config.spacecraft.base_power_w,
                    peak_power_w=config.spacecraft.base_power_w,
                ),
            )
        ]


class ImagingMapper(ActivityMapper):
    """
    Maps EO imaging activities to simulation segments.

    Produces:
    1. Pre-imaging slew segment (if needed)
    2. Imaging segment with target-pointing attitude
    3. Post-imaging return slew (if needed)
    """

    @property
    def activity_type(self) -> str:
        return "eo_collect"

    def map(
        self,
        activity: Activity,
        config: SimConfig,
    ) -> List[SimulationSegmentSpec]:
        segments = []
        params = activity.parameters

        # Target location
        target_lat = params.get("target_lat", 0.0)
        target_lon = params.get("target_lon", 0.0)
        duration_s = params.get("duration_s", 180)
        gsd_m = params.get("gsd_m", 1.0)

        # Calculate target vector (simplified - would need ephemeris for accurate calculation)
        target_vector = self._lat_lon_to_ecef(target_lat, target_lon)

        # Slew time estimation (simplified)
        slew_angle_deg = params.get("slew_angle_deg", 30.0)  # Assumed off-nadir angle
        slew_rate = 1.0  # deg/s
        slew_time_s = slew_angle_deg / slew_rate + 10  # Plus settling

        # Pre-slew segment
        if slew_time_s > 0:
            slew_end = activity.start_time + timedelta(seconds=slew_time_s)
            segments.append(
                SimulationSegmentSpec(
                    start_time=activity.start_time,
                    end_time=slew_end,
                    segment_type="slew",
                    activity_id=f"{activity.activity_id}_slew",
                    attitude=AttitudeProfile(
                        profile_type="target",
                        target_vector=target_vector,
                        slew_rate_deg_s=slew_rate,
                    ),
                    power=PowerProfile(
                        base_power_w=config.spacecraft.base_power_w,
                        peak_power_w=config.spacecraft.base_power_w * 1.2,  # CMGs active
                    ),
                )
            )
            imaging_start = slew_end
        else:
            imaging_start = activity.start_time

        # Imaging segment
        imaging_end = activity.start_time + timedelta(seconds=duration_s)

        # Data generation rate based on GSD
        # Higher resolution = more data
        data_rate_mbps = self._estimate_data_rate(gsd_m)

        segments.append(
            SimulationSegmentSpec(
                start_time=imaging_start,
                end_time=imaging_end,
                segment_type="imaging",
                activity_id=activity.activity_id,
                attitude=AttitudeProfile(
                    profile_type="target",
                    target_vector=target_vector,
                ),
                power=PowerProfile(
                    base_power_w=config.spacecraft.base_power_w,
                    peak_power_w=config.spacecraft.base_power_w + 200,  # Imaging payload
                    duty_cycle=1.0,
                ),
                data=DataProfile(
                    generation_rate_mbps=data_rate_mbps,
                    processing_mode=params.get("processing_level", "raw"),
                ),
                parameters={
                    "target_lat": target_lat,
                    "target_lon": target_lon,
                    "gsd_m": gsd_m,
                },
            )
        )

        return segments

    def _lat_lon_to_ecef(self, lat: float, lon: float) -> NDArray[np.float64]:
        """Convert lat/lon to ECEF unit vector."""
        lat_rad = np.radians(lat)
        lon_rad = np.radians(lon)
        return np.array([
            np.cos(lat_rad) * np.cos(lon_rad),
            np.cos(lat_rad) * np.sin(lon_rad),
            np.sin(lat_rad),
        ])

    def _estimate_data_rate(self, gsd_m: float) -> float:
        """Estimate data rate based on GSD."""
        # Simplified: smaller GSD = more pixels = more data
        base_rate = 800.0  # Mbps at 1m GSD
        return base_rate * (1.0 / gsd_m)

    def validate(self, activity: Activity, config: SimConfig) -> List[Event]:
        events = []
        params = activity.parameters

        if "target_lat" not in params or "target_lon" not in params:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.WARNING,
                category="imaging",
                message="Target coordinates not specified, using nadir",
                details={"activity_id": activity.activity_id},
            ))

        return events


class DownlinkMapper(ActivityMapper):
    """
    Maps downlink activities to simulation segments.

    Produces:
    1. Acquisition of signal (AOS) tracking segment
    2. Data transmission segment (rate-limited by elevation)
    3. Loss of signal (LOS) segment
    """

    @property
    def activity_type(self) -> str:
        return "downlink"

    def map(
        self,
        activity: Activity,
        config: SimConfig,
    ) -> List[SimulationSegmentSpec]:
        segments = []
        params = activity.parameters

        station_id = params.get("station_id", "default")
        duration_s = params.get("duration_s", 600)
        data_rate_mbps = params.get("data_rate_mbps", 800)
        band = params.get("band", "X")

        # Power consumption varies by band
        band_power = {
            "S": 50,
            "X": 100,
            "Ka": 200,
        }
        tx_power_w = band_power.get(band, 100)

        # Acquisition segment (first 30s)
        acq_duration = min(30, duration_s * 0.05)
        if acq_duration > 0:
            segments.append(
                SimulationSegmentSpec(
                    start_time=activity.start_time,
                    end_time=activity.start_time + timedelta(seconds=acq_duration),
                    segment_type="contact_acquisition",
                    activity_id=f"{activity.activity_id}_acq",
                    attitude=AttitudeProfile(
                        profile_type="target",  # Track station
                    ),
                    power=PowerProfile(
                        base_power_w=config.spacecraft.base_power_w,
                        peak_power_w=config.spacecraft.base_power_w + tx_power_w * 0.5,
                    ),
                    parameters={"station_id": station_id},
                )
            )
            data_start = activity.start_time + timedelta(seconds=acq_duration)
        else:
            data_start = activity.start_time

        # Main transmission segment
        data_end = activity.end_time - timedelta(seconds=10)  # Reserve for LOS

        segments.append(
            SimulationSegmentSpec(
                start_time=data_start,
                end_time=data_end,
                segment_type="downlink",
                activity_id=activity.activity_id,
                attitude=AttitudeProfile(profile_type="target"),
                power=PowerProfile(
                    base_power_w=config.spacecraft.base_power_w,
                    peak_power_w=config.spacecraft.base_power_w + tx_power_w,
                    duty_cycle=0.9,  # Some margin for link variations
                ),
                data=DataProfile(
                    transmission_rate_mbps=data_rate_mbps,
                ),
                parameters={
                    "station_id": station_id,
                    "band": band,
                },
            )
        )

        return segments

    def validate(self, activity: Activity, config: SimConfig) -> List[Event]:
        events = []
        params = activity.parameters

        if "station_id" not in params:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.WARNING,
                category="downlink",
                message="Station ID not specified",
                details={"activity_id": activity.activity_id},
            ))

        return events


class ThrustMapper(ActivityMapper):
    """
    Maps orbit adjustment activities to thrust segments.

    Handles:
    - Orbit lowering (atmospheric drag compensation)
    - Station keeping
    - Collision avoidance maneuvers
    """

    @property
    def activity_type(self) -> str:
        return "orbit_lower"

    def map(
        self,
        activity: Activity,
        config: SimConfig,
    ) -> List[SimulationSegmentSpec]:
        segments = []
        params = activity.parameters

        delta_alt_km = params.get("delta_altitude_km", -1.0)
        thrust_duration_s = params.get("thrust_duration_s", 300)

        # EP thruster parameters (from spacecraft config if available)
        thrust_n = getattr(config.spacecraft, 'ep_thrust_n', 0.05)
        isp_s = getattr(config.spacecraft, 'ep_isp_s', 1500)
        ep_power_w = getattr(config.spacecraft, 'ep_power_w', 500)

        # Determine thrust direction
        # Negative delta_alt = lowering = retrograde thrust
        direction = np.array([-1, 0, 0]) if delta_alt_km < 0 else np.array([1, 0, 0])

        # Split into thrust arcs if duration is long
        max_arc_duration = 1800  # 30 min max continuous thrust
        num_arcs = max(1, int(np.ceil(thrust_duration_s / max_arc_duration)))
        arc_duration = thrust_duration_s / num_arcs
        arc_gap = 60  # 1 min between arcs

        current_time = activity.start_time

        for i in range(num_arcs):
            # Thrust arc
            arc_end = current_time + timedelta(seconds=arc_duration)

            segments.append(
                SimulationSegmentSpec(
                    start_time=current_time,
                    end_time=arc_end,
                    segment_type="thrust",
                    activity_id=f"{activity.activity_id}_arc{i}",
                    attitude=AttitudeProfile(
                        profile_type="inertial",  # Hold attitude during thrust
                    ),
                    thrust=ThrustProfile(
                        thrust_n=thrust_n,
                        isp_s=isp_s,
                        direction=direction,
                        duty_cycle=0.95,  # Small margin
                        power_w=ep_power_w,
                    ),
                    power=PowerProfile(
                        base_power_w=config.spacecraft.base_power_w,
                        peak_power_w=config.spacecraft.base_power_w + ep_power_w,
                    ),
                    parameters={
                        "delta_altitude_km": delta_alt_km / num_arcs,
                        "arc_number": i,
                        "total_arcs": num_arcs,
                    },
                )
            )

            current_time = arc_end

            # Add coast gap between arcs (thermal management)
            if i < num_arcs - 1:
                gap_end = current_time + timedelta(seconds=arc_gap)
                segments.append(
                    SimulationSegmentSpec(
                        start_time=current_time,
                        end_time=gap_end,
                        segment_type="coast",
                        activity_id=f"{activity.activity_id}_coast{i}",
                        attitude=AttitudeProfile(profile_type="nadir"),
                        power=PowerProfile(
                            base_power_w=config.spacecraft.base_power_w,
                        ),
                    )
                )
                current_time = gap_end

        return segments

    def validate(self, activity: Activity, config: SimConfig) -> List[Event]:
        events = []
        params = activity.parameters

        delta_alt = params.get("delta_altitude_km", 0)
        if abs(delta_alt) > 50:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.WARNING,
                category="propulsion",
                message=f"Large altitude change requested: {delta_alt} km",
                details={"activity_id": activity.activity_id},
            ))

        return events


class StationKeepingMapper(ActivityMapper):
    """Maps station keeping activities."""

    @property
    def activity_type(self) -> str:
        return "station_keeping"

    def map(
        self,
        activity: Activity,
        config: SimConfig,
    ) -> List[SimulationSegmentSpec]:
        params = activity.parameters
        mode = params.get("mode", "drag_makeup")
        duration_s = params.get("duration_s", 600)

        # Station keeping uses lower thrust levels
        thrust_n = getattr(config.spacecraft, 'ep_thrust_n', 0.05) * 0.5
        ep_power_w = getattr(config.spacecraft, 'ep_power_w', 500) * 0.5

        return [
            SimulationSegmentSpec(
                start_time=activity.start_time,
                end_time=activity.end_time,
                segment_type="station_keeping",
                activity_id=activity.activity_id,
                attitude=AttitudeProfile(profile_type="nadir"),
                thrust=ThrustProfile(
                    thrust_n=thrust_n,
                    isp_s=1500,
                    direction=np.array([1, 0, 0]),
                    duty_cycle=0.5,
                    power_w=ep_power_w,
                ),
                power=PowerProfile(
                    base_power_w=config.spacecraft.base_power_w,
                    peak_power_w=config.spacecraft.base_power_w + ep_power_w,
                    duty_cycle=0.5,
                ),
                parameters={"mode": mode},
            )
        ]


# Mapper registry
_MAPPERS: Dict[str, ActivityMapper] = {}


def register_mapper(mapper: ActivityMapper) -> None:
    """Register an activity mapper."""
    _MAPPERS[mapper.activity_type] = mapper


def get_mapper(activity_type: str) -> Optional[ActivityMapper]:
    """Get mapper for activity type."""
    return _MAPPERS.get(activity_type)


def map_activity(
    activity: Activity,
    config: SimConfig,
) -> List[SimulationSegmentSpec]:
    """Map an activity to simulation segments using registered mapper."""
    mapper = get_mapper(activity.activity_type)
    if mapper is None:
        # Default to idle behavior
        return IdleMapper().map(activity, config)
    return mapper.map(activity, config)


# Register default mappers
register_mapper(IdleMapper())
register_mapper(ImagingMapper())
register_mapper(DownlinkMapper())
register_mapper(ThrustMapper())
register_mapper(StationKeepingMapper())
