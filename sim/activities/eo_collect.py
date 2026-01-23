"""EO imaging collection activity handler."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from sim.activities.base import ActivityHandler, ActivityResult
from sim.core.types import Activity, Event, EventType, InitialState, PointTarget
from sim.models.imaging import (
    EOSensorConfig,
    FrameSensor,
    ImageFrame,
    ImagingAccessModel,
)
from sim.models.power import PowerConfig, PowerModel


@dataclass
class EOCollectParams:
    """Parameters for EO collection activity."""

    target_lat_deg: float
    target_lon_deg: float
    target_id: str = ""
    priority: int = 1
    max_cross_track_deg: float = 30.0
    max_along_track_deg: float = 5.0
    num_frames: int = 1
    sensor_power_w: float = 100.0

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EOCollectParams":
        """Create from dictionary."""
        return cls(
            target_lat_deg=d.get("target_lat_deg", 0.0),
            target_lon_deg=d.get("target_lon_deg", 0.0),
            target_id=d.get("target_id", ""),
            priority=d.get("priority", 1),
            max_cross_track_deg=d.get("max_cross_track_deg", 30.0),
            max_along_track_deg=d.get("max_along_track_deg", 5.0),
            num_frames=d.get("num_frames", 1),
            sensor_power_w=d.get("sensor_power_w", 100.0),
        )


class EOCollectHandler(ActivityHandler):
    """
    Handler for EO imaging collection activities.

    Supports cross-track pointing for point targets.
    """

    def __init__(self, sensor_config: Optional[EOSensorConfig] = None):
        """
        Initialize handler.

        Args:
            sensor_config: EO sensor configuration
        """
        self.sensor_config = sensor_config or EOSensorConfig()
        self.sensor = FrameSensor(self.sensor_config)

    @property
    def activity_type(self) -> str:
        return "eo_collect"

    def validate(self, activity: Activity) -> List[Event]:
        """Validate EO collection parameters."""
        events = []
        params = activity.parameters

        if "target_lat_deg" not in params or "target_lon_deg" not in params:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.ERROR,
                category="validation",
                message="Missing required parameters: target_lat_deg and/or target_lon_deg",
                details={"activity_id": activity.activity_id},
            ))
            return events

        lat = params.get("target_lat_deg", 0)
        lon = params.get("target_lon_deg", 0)

        if not -90 <= lat <= 90:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.ERROR,
                category="validation",
                message=f"Invalid latitude: {lat} (must be in [-90, 90])",
                details={"activity_id": activity.activity_id},
            ))

        if not -180 <= lon <= 180:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.ERROR,
                category="validation",
                message=f"Invalid longitude: {lon} (must be in [-180, 180])",
                details={"activity_id": activity.activity_id},
            ))

        return events

    def get_power_consumption(self, activity: Activity) -> float:
        """Get power consumption during imaging."""
        return activity.parameters.get("sensor_power_w", 100.0)

    def process(
        self,
        activity: Activity,
        state: InitialState,
        ephemeris: list,
        config: Any,
    ) -> ActivityResult:
        """
        Process EO collection activity.

        Args:
            activity: EO collect activity
            state: Current spacecraft state
            ephemeris: Ephemeris for activity duration
            config: Simulation configuration

        Returns:
            ActivityResult with collected frames and data volume
        """
        params = EOCollectParams.from_dict(activity.parameters)

        # Initialize models
        access_model = ImagingAccessModel(
            max_cross_track_deg=params.max_cross_track_deg,
            max_along_track_deg=params.max_along_track_deg,
        )

        power_config = PowerConfig(
            battery_capacity_wh=config.spacecraft.battery_capacity_wh,
            solar_panel_area_m2=config.spacecraft.solar_panel_area_m2,
            solar_efficiency=config.spacecraft.solar_efficiency,
            base_power_w=config.spacecraft.base_power_w,
        )
        power_model = PowerModel(power_config)

        events: List[Event] = []
        collected_frames: List[ImageFrame] = []

        # Find access windows to target
        windows = access_model.compute_target_access(
            ephemeris,
            params.target_lat_deg,
            params.target_lon_deg,
        )

        if not windows:
            events.append(self.create_warning_event(
                timestamp=activity.start_time,
                category="access",
                message=f"No access to target ({params.target_lat_deg}, {params.target_lon_deg})",
                details={"target_id": params.target_id},
            ))
            return ActivityResult(
                activity_id=activity.activity_id,
                success=False,
                events=events,
                message="No access windows to target",
            )

        # Collect frames during access windows
        current_soc = state.battery_soc
        current_storage = state.storage_used_gb
        storage_capacity = config.spacecraft.storage_capacity_gb
        frames_collected = 0
        frame_data_mb = self.sensor.compute_frame_data_mb()
        time_step_s = config.time_step_s

        for window in windows:
            if frames_collected >= params.num_frames:
                break

            # Find ephemeris points within window
            for point in ephemeris:
                if point.time < window.start_time:
                    continue
                if point.time > window.end_time:
                    break
                if frames_collected >= params.num_frames:
                    break

                # Update power state
                in_eclipse = power_model.is_in_eclipse(point.position_eci)
                generation = power_model.compute_solar_generation(in_eclipse)
                total_power = power_config.base_power_w + params.sensor_power_w
                current_soc, power_limited = power_model.update_soc(
                    current_soc, generation, total_power, time_step_s
                )

                if power_limited:
                    events.append(self.create_warning_event(
                        timestamp=point.time,
                        category="power",
                        message="Power limited during imaging",
                        details={"soc": current_soc},
                    ))
                    continue

                # Check storage capacity
                new_storage = current_storage + frame_data_mb / 1000.0  # MB to GB
                if new_storage > storage_capacity:
                    events.append(self.create_violation_event(
                        timestamp=point.time,
                        category="storage",
                        message="Storage capacity exceeded",
                        details={
                            "current_gb": current_storage,
                            "required_gb": new_storage,
                            "capacity_gb": storage_capacity,
                        },
                    ))
                    break

                # Compute pointing angles
                target_eci = access_model._latlon_to_eci(
                    params.target_lat_deg,
                    params.target_lon_deg,
                    point.time,
                )
                cross_track, along_track = access_model.decompose_off_nadir(
                    point.position_eci,
                    point.velocity_eci,
                    target_eci,
                )

                # Compute imaging geometry
                altitude = point.altitude_km
                gsd = self.sensor.compute_gsd(altitude)
                off_nadir_gsd = self.sensor.compute_off_nadir_gsd(
                    altitude, abs(cross_track)
                )
                footprint = self.sensor.compute_frame_footprint(altitude)

                # Create frame
                frame = ImageFrame(
                    frame_id=f"{activity.activity_id}_frame_{frames_collected}",
                    capture_time=point.time,
                    target_lat_deg=params.target_lat_deg,
                    target_lon_deg=params.target_lon_deg,
                    altitude_km=altitude,
                    gsd_m=off_nadir_gsd,
                    cross_track_angle_deg=cross_track,
                    along_track_angle_deg=along_track,
                    data_volume_mb=frame_data_mb,
                    footprint_km=footprint,
                )
                collected_frames.append(frame)
                frames_collected += 1
                current_storage = new_storage

                events.append(self.create_info_event(
                    timestamp=point.time,
                    category="imaging",
                    message=f"Captured frame at ({params.target_lat_deg:.2f}, {params.target_lon_deg:.2f})",
                    details={
                        "frame_id": frame.frame_id,
                        "gsd_m": frame.gsd_m,
                        "cross_track_deg": cross_track,
                        "along_track_deg": along_track,
                    },
                ))

                # Only collect one frame per ephemeris point
                # (in real life, frame rate would be higher)
                break

        # Validate constraints
        if current_soc < 0:
            events.append(self.create_violation_event(
                timestamp=activity.end_time,
                category="power",
                message="Battery SOC went negative",
                details={"final_soc": current_soc},
            ))
            current_soc = 0.0

        if current_storage < 0:
            events.append(self.create_violation_event(
                timestamp=activity.end_time,
                category="storage",
                message="Storage went negative",
                details={"final_storage": current_storage},
            ))
            current_storage = 0.0

        # Create result
        total_data_mb = sum(f.data_volume_mb for f in collected_frames)
        success = frames_collected > 0 and not any(
            e.event_type == EventType.VIOLATION for e in events
        )

        return ActivityResult(
            activity_id=activity.activity_id,
            success=success,
            events=events,
            state_updates={
                "battery_soc": max(0.0, min(1.0, current_soc)),
                "storage_used_gb": current_storage,
            },
            artifacts={
                "frames": [
                    {
                        "frame_id": f.frame_id,
                        "capture_time": f.capture_time.isoformat(),
                        "target_lat": f.target_lat_deg,
                        "target_lon": f.target_lon_deg,
                        "gsd_m": f.gsd_m,
                        "cross_track_deg": f.cross_track_angle_deg,
                        "along_track_deg": f.along_track_angle_deg,
                        "data_mb": f.data_volume_mb,
                    }
                    for f in collected_frames
                ],
            },
            message=(
                f"EO collect: {frames_collected}/{params.num_frames} frames, "
                f"data={total_data_mb:.1f} MB, "
                f"target=({params.target_lat_deg:.2f}, {params.target_lon_deg:.2f})"
            ),
        )
