"""
Basilisk simulation runner for MEDIUM/HIGH fidelity simulations.

Orchestrates simulation segments including:
- Orbit propagation with configurable force models (Basilisk or J2 fallback)
- Activity execution with subsystem effects
- Eclipse-aware power modeling
- State continuity between segments
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from sim.core.types import (
    Activity,
    Event,
    EventType,
    Fidelity,
    InitialState,
    PlanInput,
    SimConfig,
    SimResults,
)
from sim.models.propagator_base import EphemerisPoint, PropagatorInterface
from sim.models.basilisk_propagator import BasiliskPropagator, BasiliskConfig, BASILISK_AVAILABLE
from sim.runners.activity_mappers import (
    map_activity,
    SimulationSegmentSpec,
    ThrustProfile,
)


logger = logging.getLogger(__name__)

# Constants
EARTH_RADIUS_KM = 6378.137
SUN_DIRECTION = np.array([1.0, 0.0, 0.0])  # Simplified: Sun in +X direction
SOLAR_FLUX_W_M2 = 1361.0  # Solar constant at 1 AU


@dataclass
class SimulationSegment:
    """A segment of simulation between activities."""

    start_time: datetime
    end_time: datetime
    segment_type: str  # "idle", "imaging", "downlink", "thrust", etc.
    activity: Optional[Activity] = None
    ephemeris: List[EphemerisPoint] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)
    state_updates: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunnerState:
    """Current state tracked by the runner."""

    epoch: datetime
    position_eci: NDArray[np.float64]
    velocity_eci: NDArray[np.float64]
    mass_kg: float
    propellant_kg: float
    battery_soc: float
    storage_used_gb: float
    mode: str = "nominal"

    def copy(self) -> "RunnerState":
        return RunnerState(
            epoch=self.epoch,
            position_eci=self.position_eci.copy(),
            velocity_eci=self.velocity_eci.copy(),
            mass_kg=self.mass_kg,
            propellant_kg=self.propellant_kg,
            battery_soc=self.battery_soc,
            storage_used_gb=self.storage_used_gb,
            mode=self.mode,
        )

    @classmethod
    def from_initial_state(cls, state: InitialState) -> "RunnerState":
        return cls(
            epoch=state.epoch,
            position_eci=np.array(state.position_eci),
            velocity_eci=np.array(state.velocity_eci),
            mass_kg=state.mass_kg,
            propellant_kg=state.propellant_kg,
            battery_soc=state.battery_soc,
            storage_used_gb=state.storage_used_gb,
        )

    def to_initial_state(self) -> InitialState:
        """Convert back to InitialState for chaining."""
        return InitialState(
            epoch=self.epoch,
            position_eci=self.position_eci.copy(),
            velocity_eci=self.velocity_eci.copy(),
            mass_kg=self.mass_kg,
            propellant_kg=self.propellant_kg,
            battery_soc=self.battery_soc,
            storage_used_gb=self.storage_used_gb,
        )


class BasiliskRunner:
    """
    Simulation runner using Basilisk propagator.

    Manages the execution of a complete simulation, breaking it into
    segments around activities and maintaining state continuity.

    Uses the Basilisk astrodynamics framework for numerical propagation
    when available, falling back to J2 analytical propagation otherwise.
    """

    def __init__(
        self,
        fidelity: Fidelity = Fidelity.MEDIUM,
        config: Optional[BasiliskConfig] = None,
    ):
        self.fidelity = fidelity
        self.propagator_config = config or BasiliskConfig.for_fidelity(fidelity.value)
        self._propagator: Optional[BasiliskPropagator] = None
        self._state: Optional[RunnerState] = None
        self._segments: List[SimulationSegment] = []
        self._sim_config: Optional[SimConfig] = None
        self._run_info: Dict[str, Any] = {}

    def initialize(
        self,
        initial_state: InitialState,
        plan: PlanInput,
        config: SimConfig,
    ) -> None:
        """
        Initialize the runner with initial conditions.

        Args:
            initial_state: Initial spacecraft state
            plan: Mission plan
            config: Simulation configuration
        """
        self._state = RunnerState.from_initial_state(initial_state)
        self._sim_config = config

        # Create propagator with Basilisk or J2 fallback
        self._propagator = BasiliskPropagator(
            initial_state=initial_state,
            epoch=plan.start_time,
            fidelity=self.fidelity,
            config=self.propagator_config,
        )

        # Record run info
        self._run_info = {
            "fidelity": self.fidelity.value,
            "propagator_backend": self._propagator.version,
            "basilisk_available": BASILISK_AVAILABLE,
            "using_basilisk": self._propagator.is_using_basilisk,
            "gravity_degree": self.propagator_config.gravity_degree,
            "drag_enabled": self.propagator_config.enable_drag,
            "plan_id": plan.plan_id,
            "spacecraft_id": plan.spacecraft_id,
        }

        logger.info(
            f"Basilisk runner initialized: fidelity={self.fidelity.value}, "
            f"backend={self._propagator.version}, "
            f"using_basilisk={self._propagator.is_using_basilisk}"
        )

    def run(
        self,
        plan: PlanInput,
        config: SimConfig,
    ) -> Tuple[List[SimulationSegment], List[Event]]:
        """
        Run the complete simulation.

        Args:
            plan: Mission plan with activities
            config: Simulation configuration

        Returns:
            Tuple of (segments, events)
        """
        if self._propagator is None or self._state is None:
            raise RuntimeError("Runner not initialized")

        all_events: List[Event] = []
        self._segments = []

        # Sort activities by start time
        sorted_activities = sorted(plan.activities, key=lambda a: a.start_time)

        current_time = plan.start_time
        activity_idx = 0

        while current_time < plan.end_time:
            # Determine next segment end time
            if activity_idx < len(sorted_activities):
                next_activity = sorted_activities[activity_idx]
                segment_end = min(next_activity.start_time, plan.end_time)
            else:
                segment_end = plan.end_time

            # Run idle segment if there's a gap
            if segment_end > current_time:
                segment = self._run_idle_segment(current_time, segment_end, config)
                self._segments.append(segment)
                all_events.extend(segment.events)
                current_time = segment_end

            # Run activity segment
            if activity_idx < len(sorted_activities):
                activity = sorted_activities[activity_idx]
                if activity.start_time <= current_time < activity.end_time:
                    segment = self._run_activity_segment(activity, config)
                    self._segments.append(segment)
                    all_events.extend(segment.events)
                    current_time = activity.end_time
                    activity_idx += 1
                elif activity.start_time <= current_time:
                    activity_idx += 1

        return self._segments, all_events

    def run_simulation(
        self,
        initial_state: InitialState,
        plan: PlanInput,
        config: SimConfig,
    ) -> SimResults:
        """
        Complete simulation entry point.

        Args:
            initial_state: Initial spacecraft state
            plan: Mission plan
            config: Simulation configuration

        Returns:
            SimResults with profiles, events, and final state
        """
        # Initialize
        self.initialize(initial_state, plan, config)

        # Run simulation
        segments, events = self.run(plan, config)

        # Build profiles DataFrame
        profiles = self._build_profiles(segments)

        # Build summary
        summary = self._build_summary(segments, events)

        # Get final state
        final_state = self._state.to_initial_state()

        return SimResults(
            profiles=profiles,
            events=events,
            artifacts={},  # Would be populated by output writers
            final_state=final_state,
            summary=summary,
        )

    def _run_idle_segment(
        self,
        start: datetime,
        end: datetime,
        config: SimConfig,
    ) -> SimulationSegment:
        """Run an idle (coasting) segment with eclipse-aware power."""
        logger.debug(f"Running idle segment: {start} to {end}")

        # Propagate through segment
        ephemeris = self._propagator.propagate_range(
            start=start,
            end=end,
            step_s=config.time_step_s,
        )

        events = []

        # Update state and compute power with eclipse awareness
        if ephemeris:
            self._state.epoch = ephemeris[-1].time
            self._state.position_eci = ephemeris[-1].position_eci
            self._state.velocity_eci = ephemeris[-1].velocity_eci

            # Eclipse-aware power computation
            soc_change = self._compute_power_for_ephemeris(
                ephemeris,
                config,
                power_load_w=config.spacecraft.base_power_w,
            )
            self._state.battery_soc += soc_change

            # Clamp SOC and generate events
            if self._state.battery_soc > 1.0:
                self._state.battery_soc = 1.0
            elif self._state.battery_soc < 0.0:
                events.append(Event(
                    timestamp=end,
                    event_type=EventType.VIOLATION,
                    category="power",
                    message="Battery depleted during idle",
                    details={"soc": self._state.battery_soc},
                ))
                self._state.battery_soc = 0.0

        return SimulationSegment(
            start_time=start,
            end_time=end,
            segment_type="idle",
            ephemeris=ephemeris,
            events=events,
            state_updates={
                "battery_soc": self._state.battery_soc,
            },
        )

    def _run_activity_segment(
        self,
        activity: Activity,
        config: SimConfig,
    ) -> SimulationSegment:
        """Run an activity segment using activity mappers."""
        logger.debug(f"Running activity segment: {activity.activity_type}")

        # Get segment specs from mapper
        segment_specs = map_activity(activity, config)

        # Propagate through activity duration
        ephemeris = self._propagator.propagate_range(
            start=activity.start_time,
            end=activity.end_time,
            step_s=config.time_step_s,
        )

        events = []
        state_updates = {}

        # Activity-specific processing
        if activity.activity_type == "orbit_lower":
            evts, updates = self._process_thrust_activity(
                activity, segment_specs, ephemeris, config
            )
            events.extend(evts)
            state_updates.update(updates)
        elif activity.activity_type == "eo_collect":
            evts, updates = self._process_imaging_activity(
                activity, segment_specs, ephemeris, config
            )
            events.extend(evts)
            state_updates.update(updates)
        elif activity.activity_type == "downlink":
            evts, updates = self._process_downlink_activity(
                activity, segment_specs, ephemeris, config
            )
            events.extend(evts)
            state_updates.update(updates)
        elif activity.activity_type == "station_keeping":
            evts, updates = self._process_station_keeping_activity(
                activity, segment_specs, ephemeris, config
            )
            events.extend(evts)
            state_updates.update(updates)
        else:
            # Generic activity processing
            evts, updates = self._process_generic_activity(
                activity, ephemeris, config
            )
            events.extend(evts)
            state_updates.update(updates)

        # Update position from ephemeris
        if ephemeris:
            self._state.epoch = ephemeris[-1].time
            self._state.position_eci = ephemeris[-1].position_eci
            self._state.velocity_eci = ephemeris[-1].velocity_eci

        return SimulationSegment(
            start_time=activity.start_time,
            end_time=activity.end_time,
            segment_type=activity.activity_type,
            activity=activity,
            ephemeris=ephemeris,
            events=events,
            state_updates=state_updates,
        )

    def _process_thrust_activity(
        self,
        activity: Activity,
        segment_specs: List[SimulationSegmentSpec],
        ephemeris: List[EphemerisPoint],
        config: SimConfig,
    ) -> Tuple[List[Event], Dict[str, Any]]:
        """Process orbit lowering/thrust activity with proper finite burn."""
        events = []
        state_updates = {}

        delta_alt_km = activity.parameters.get("delta_altitude_km", -1.0)
        thrust_duration_s = activity.parameters.get("thrust_duration_s", 300)

        # Get thrust profile from mapper
        thrust_profile = None
        for spec in segment_specs:
            if spec.thrust.thrust_n > 0:
                thrust_profile = spec.thrust
                break

        if thrust_profile is None:
            thrust_profile = ThrustProfile(thrust_n=0.05, isp_s=1500)

        # Compute delta-V needed (simplified Hohmann-like)
        r = np.linalg.norm(self._state.position_eci)
        # Delta-V for altitude change: dV ≈ sqrt(mu/r) * (1 - sqrt(r/(r+dh)))
        mu = 398600.4418  # km^3/s^2
        v_circ = np.sqrt(mu / r)
        r_new = r + delta_alt_km
        delta_v = abs(v_circ * (1 - np.sqrt(r / r_new)))

        # Apply maneuver at midpoint of thrust window
        thrust_direction = thrust_profile.direction
        if delta_alt_km < 0:
            thrust_direction = -thrust_direction  # Retrograde for lowering

        delta_v_vec = thrust_direction * delta_v

        result = self._propagator.apply_maneuver(
            delta_v=delta_v_vec,
            epoch=activity.start_time + timedelta(seconds=thrust_duration_s / 2),
            isp=thrust_profile.isp_s,
        )

        # Update propellant
        self._state.propellant_kg -= result.propellant_used_kg
        if self._state.propellant_kg < 0:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.VIOLATION,
                category="propulsion",
                message="Insufficient propellant for maneuver",
                details={
                    "required_kg": result.propellant_used_kg,
                    "available_kg": self._state.propellant_kg + result.propellant_used_kg,
                },
            ))
            self._state.propellant_kg = 0

        # Power consumption during thrust
        ep_power_w = thrust_profile.power_w
        power_consumed_wh = ep_power_w * thrust_duration_s / 3600
        soc_delta = power_consumed_wh / config.spacecraft.battery_capacity_wh
        self._state.battery_soc = max(0.0, self._state.battery_soc - soc_delta)

        if self._state.battery_soc < 0.1:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.WARNING,
                category="power",
                message="Low battery during thrust",
                details={"soc": self._state.battery_soc},
            ))

        state_updates["propellant_kg"] = self._state.propellant_kg
        state_updates["battery_soc"] = self._state.battery_soc
        state_updates["delta_v_applied_m_s"] = delta_v * 1000

        events.append(Event(
            timestamp=activity.start_time,
            event_type=EventType.INFO,
            category="propulsion",
            message=f"Applied {delta_v*1000:.2f} m/s delta-V",
            details={
                "delta_v_m_s": delta_v * 1000,
                "propellant_used_kg": result.propellant_used_kg,
            },
        ))

        return events, state_updates

    def _process_imaging_activity(
        self,
        activity: Activity,
        segment_specs: List[SimulationSegmentSpec],
        ephemeris: List[EphemerisPoint],
        config: SimConfig,
    ) -> Tuple[List[Event], Dict[str, Any]]:
        """Process Earth observation imaging activity."""
        events = []
        state_updates = {}

        duration_s = activity.parameters.get("duration_s", 180)
        data_rate_mbps = activity.parameters.get("data_rate_mbps", 800)

        # Get data rate from mapper if available
        for spec in segment_specs:
            if spec.data.generation_rate_mbps > 0:
                data_rate_mbps = spec.data.generation_rate_mbps
                break

        # Calculate data volume
        data_volume_gb = data_rate_mbps * duration_s / 8 / 1000

        # Update storage
        self._state.storage_used_gb += data_volume_gb
        max_storage = config.spacecraft.storage_capacity_gb

        if self._state.storage_used_gb > max_storage:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.VIOLATION,
                category="storage",
                message="Storage capacity exceeded",
                details={
                    "required_gb": data_volume_gb,
                    "available_gb": max_storage - (self._state.storage_used_gb - data_volume_gb),
                },
            ))
            self._state.storage_used_gb = max_storage

        state_updates["storage_used_gb"] = self._state.storage_used_gb

        # Eclipse-aware power consumption
        imaging_power_w = activity.parameters.get("power_w", 200) + config.spacecraft.base_power_w
        soc_change = self._compute_power_for_ephemeris(
            ephemeris, config, power_load_w=imaging_power_w
        )
        self._state.battery_soc += soc_change
        self._state.battery_soc = max(0.0, min(1.0, self._state.battery_soc))
        state_updates["battery_soc"] = self._state.battery_soc

        events.append(Event(
            timestamp=activity.start_time,
            event_type=EventType.INFO,
            category="imaging",
            message=f"Collected {data_volume_gb:.2f} GB of imagery",
            details={
                "volume_gb": data_volume_gb,
                "target_lat": activity.parameters.get("target_lat"),
                "target_lon": activity.parameters.get("target_lon"),
            },
        ))

        return events, state_updates

    def _process_downlink_activity(
        self,
        activity: Activity,
        segment_specs: List[SimulationSegmentSpec],
        ephemeris: List[EphemerisPoint],
        config: SimConfig,
    ) -> Tuple[List[Event], Dict[str, Any]]:
        """Process downlink activity."""
        events = []
        state_updates = {}

        duration_s = activity.parameters.get("duration_s", 600)
        data_rate_mbps = activity.parameters.get("data_rate_mbps", 800)

        # Get data rate from mapper
        for spec in segment_specs:
            if spec.data.transmission_rate_mbps > 0:
                data_rate_mbps = spec.data.transmission_rate_mbps
                break

        # Calculate data volume that can be downlinked
        max_downlink_gb = data_rate_mbps * duration_s / 8 / 1000
        actual_downlink_gb = min(max_downlink_gb, self._state.storage_used_gb)

        # Update storage
        self._state.storage_used_gb -= actual_downlink_gb
        state_updates["storage_used_gb"] = self._state.storage_used_gb

        # Eclipse-aware power consumption
        downlink_power_w = activity.parameters.get("power_w", 150) + config.spacecraft.base_power_w
        soc_change = self._compute_power_for_ephemeris(
            ephemeris, config, power_load_w=downlink_power_w
        )
        self._state.battery_soc += soc_change
        self._state.battery_soc = max(0.0, min(1.0, self._state.battery_soc))
        state_updates["battery_soc"] = self._state.battery_soc

        events.append(Event(
            timestamp=activity.start_time,
            event_type=EventType.INFO,
            category="downlink",
            message=f"Downlinked {actual_downlink_gb:.2f} GB",
            details={
                "volume_gb": actual_downlink_gb,
                "station_id": activity.parameters.get("station_id"),
                "band": activity.parameters.get("band", "X"),
            },
        ))

        return events, state_updates

    def _process_station_keeping_activity(
        self,
        activity: Activity,
        segment_specs: List[SimulationSegmentSpec],
        ephemeris: List[EphemerisPoint],
        config: SimConfig,
    ) -> Tuple[List[Event], Dict[str, Any]]:
        """Process station keeping activity (drag makeup)."""
        events = []
        state_updates = {}

        duration_s = (activity.end_time - activity.start_time).total_seconds()

        # Get thrust profile
        thrust_profile = None
        for spec in segment_specs:
            if spec.thrust.thrust_n > 0:
                thrust_profile = spec.thrust
                break

        if thrust_profile is None:
            thrust_profile = ThrustProfile(thrust_n=0.025, isp_s=1500, duty_cycle=0.5)

        # Compute propellant usage for continuous low thrust
        effective_thrust_time = duration_s * thrust_profile.duty_cycle
        mass_flow_rate = thrust_profile.thrust_n / (thrust_profile.isp_s * 9.80665)  # kg/s
        propellant_used = mass_flow_rate * effective_thrust_time

        self._state.propellant_kg -= propellant_used
        if self._state.propellant_kg < 0:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.WARNING,
                category="propulsion",
                message="Low propellant during station keeping",
                details={"remaining_kg": self._state.propellant_kg + propellant_used},
            ))
            self._state.propellant_kg = 0

        # Power consumption
        avg_power_w = (config.spacecraft.base_power_w +
                       thrust_profile.power_w * thrust_profile.duty_cycle)
        soc_change = self._compute_power_for_ephemeris(
            ephemeris, config, power_load_w=avg_power_w
        )
        self._state.battery_soc += soc_change
        self._state.battery_soc = max(0.0, min(1.0, self._state.battery_soc))

        state_updates["propellant_kg"] = self._state.propellant_kg
        state_updates["battery_soc"] = self._state.battery_soc

        events.append(Event(
            timestamp=activity.start_time,
            event_type=EventType.INFO,
            category="station_keeping",
            message=f"Station keeping used {propellant_used*1000:.1f} g propellant",
            details={"propellant_used_g": propellant_used * 1000},
        ))

        return events, state_updates

    def _process_generic_activity(
        self,
        activity: Activity,
        ephemeris: List[EphemerisPoint],
        config: SimConfig,
    ) -> Tuple[List[Event], Dict[str, Any]]:
        """Process generic/unknown activity types."""
        events = []
        state_updates = {}

        power_w = activity.parameters.get("power_w", config.spacecraft.base_power_w * 1.5)
        soc_change = self._compute_power_for_ephemeris(
            ephemeris, config, power_load_w=power_w
        )
        self._state.battery_soc += soc_change
        self._state.battery_soc = max(0.0, min(1.0, self._state.battery_soc))
        state_updates["battery_soc"] = self._state.battery_soc

        return events, state_updates

    def _compute_power_for_ephemeris(
        self,
        ephemeris: List[EphemerisPoint],
        config: SimConfig,
        power_load_w: float,
    ) -> float:
        """
        Compute net SOC change for an ephemeris segment with eclipse awareness.

        Returns:
            Net SOC change (positive = charging, negative = discharging)
        """
        if not ephemeris or len(ephemeris) < 2:
            return 0.0

        total_energy_wh = 0.0
        battery_capacity_wh = config.spacecraft.battery_capacity_wh

        for i in range(len(ephemeris) - 1):
            pt = ephemeris[i]
            dt_s = (ephemeris[i + 1].time - pt.time).total_seconds()

            # Check eclipse
            in_eclipse = self._is_in_eclipse(pt.position_eci)

            # Solar generation (zero in eclipse)
            if in_eclipse:
                generation_w = 0.0
            else:
                generation_w = self._compute_solar_generation(
                    pt.position_eci, config
                )

            # Net power (positive = generating more than consuming)
            net_power_w = generation_w - power_load_w
            energy_wh = net_power_w * dt_s / 3600

            total_energy_wh += energy_wh

        return total_energy_wh / battery_capacity_wh

    def _is_in_eclipse(self, position_eci: NDArray[np.float64]) -> bool:
        """
        Check if spacecraft is in Earth's shadow (simplified cylindrical model).

        Uses a simplified cylindrical shadow model where eclipse occurs when
        the spacecraft is behind Earth relative to the Sun.
        """
        r = np.linalg.norm(position_eci)

        # Simplified: Sun is in +X direction
        # Eclipse if spacecraft is behind Earth (negative X) and within Earth's shadow cylinder
        if position_eci[0] > 0:
            # On sunlit side
            return False

        # Distance from Sun-Earth line (Y-Z plane distance)
        perp_dist = np.sqrt(position_eci[1]**2 + position_eci[2]**2)

        # In shadow if within Earth's radius (simplified - ignores umbra/penumbra)
        return perp_dist < EARTH_RADIUS_KM

    def _compute_solar_generation(
        self,
        position_eci: NDArray[np.float64],
        config: SimConfig,
    ) -> float:
        """Compute solar power generation based on sun angle."""
        # Simplified: assume nadir pointing, sun angle affects generation
        r_hat = position_eci / np.linalg.norm(position_eci)

        # Sun direction (simplified as +X)
        sun_dir = SUN_DIRECTION

        # Cosine of sun angle (dot product)
        cos_sun_angle = np.dot(r_hat, sun_dir)

        # Generation is maximum when sun is overhead, reduced at angles
        # Clamp to positive values only
        effective_illumination = max(0.0, cos_sun_angle)

        # Panel area and efficiency
        panel_area = config.spacecraft.solar_panel_area_m2
        efficiency = config.spacecraft.solar_efficiency

        # Power generation
        return SOLAR_FLUX_W_M2 * panel_area * efficiency * effective_illumination

    def _build_profiles(self, segments: List[SimulationSegment]) -> pd.DataFrame:
        """Build time-indexed profiles DataFrame from segments."""
        records = []

        for segment in segments:
            for pt in segment.ephemeris:
                record = {
                    "time": pt.time,
                    "x_km": pt.position_eci[0],
                    "y_km": pt.position_eci[1],
                    "z_km": pt.position_eci[2],
                    "vx_km_s": pt.velocity_eci[0],
                    "vy_km_s": pt.velocity_eci[1],
                    "vz_km_s": pt.velocity_eci[2],
                    "altitude_km": pt.altitude_km,
                    "segment_type": segment.segment_type,
                    "in_eclipse": self._is_in_eclipse(pt.position_eci),
                }
                records.append(record)

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = df.set_index("time")
        return df

    def _build_summary(
        self,
        segments: List[SimulationSegment],
        events: List[Event],
    ) -> Dict[str, Any]:
        """Build run summary."""
        violations = [e for e in events if e.event_type == EventType.VIOLATION]
        warnings = [e for e in events if e.event_type == EventType.WARNING]

        # Count segment types
        segment_counts = {}
        total_duration = 0.0
        for seg in segments:
            segment_counts[seg.segment_type] = segment_counts.get(seg.segment_type, 0) + 1
            total_duration += (seg.end_time - seg.start_time).total_seconds()

        return {
            **self._run_info,
            "total_segments": len(segments),
            "segment_counts": segment_counts,
            "total_duration_hours": total_duration / 3600,
            "violation_count": len(violations),
            "warning_count": len(warnings),
            "final_soc": self._state.battery_soc if self._state else None,
            "final_propellant_kg": self._state.propellant_kg if self._state else None,
            "final_storage_gb": self._state.storage_used_gb if self._state else None,
        }

    def get_ephemeris(self) -> List[EphemerisPoint]:
        """Get combined ephemeris from all segments."""
        all_points = []
        for segment in self._segments:
            all_points.extend(segment.ephemeris)
        return all_points

    def get_final_state(self) -> Optional[RunnerState]:
        """Get final state after simulation."""
        return self._state.copy() if self._state else None

    def get_run_info(self) -> Dict[str, Any]:
        """Get information about the simulation run."""
        return self._run_info.copy()
