"""Data downlink activity handler for ground station contacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from sim.activities.base import ActivityHandler, ActivityResult
from sim.core.types import Activity, Event, EventType, InitialState
from sim.models.access import AccessModel, GroundStation
from sim.models.power import PowerConfig, PowerModel


@dataclass
class DownlinkParams:
    """Parameters for downlink activity."""

    station_id: str
    band: str = "X"  # S, X, or Ka
    data_rate_mbps: float = 150.0  # Downlink data rate
    tx_power_w: float = 50.0  # Transmitter power consumption
    min_elevation_deg: float = 10.0  # Minimum elevation for contact
    priority_data_first: bool = True  # Downlink high priority data first

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DownlinkParams":
        """Create from dictionary."""
        return cls(
            station_id=d.get("station_id", ""),
            band=d.get("band", "X"),
            data_rate_mbps=d.get("data_rate_mbps", 150.0),
            tx_power_w=d.get("tx_power_w", 50.0),
            min_elevation_deg=d.get("min_elevation_deg", 10.0),
            priority_data_first=d.get("priority_data_first", True),
        )


# Rate vs elevation lookup for different bands (Mbps at elevation)
RATE_VS_ELEVATION = {
    "S": {5: 2.0, 10: 4.0, 20: 8.0, 45: 10.0, 90: 10.0},
    "X": {5: 50.0, 10: 100.0, 20: 150.0, 45: 200.0, 90: 250.0},
    "Ka": {5: 100.0, 10: 300.0, 20: 500.0, 45: 800.0, 90: 1000.0},
}


def get_data_rate_at_elevation(band: str, elevation_deg: float) -> float:
    """
    Get effective data rate at given elevation angle.

    Uses linear interpolation between reference points.

    Args:
        band: Communication band (S, X, Ka)
        elevation_deg: Elevation angle in degrees

    Returns:
        Data rate in Mbps
    """
    if band not in RATE_VS_ELEVATION:
        band = "X"

    rates = RATE_VS_ELEVATION[band]
    elevations = sorted(rates.keys())

    if elevation_deg <= elevations[0]:
        return rates[elevations[0]]
    if elevation_deg >= elevations[-1]:
        return rates[elevations[-1]]

    # Linear interpolation
    for i in range(len(elevations) - 1):
        if elevations[i] <= elevation_deg < elevations[i + 1]:
            e1, e2 = elevations[i], elevations[i + 1]
            r1, r2 = rates[e1], rates[e2]
            frac = (elevation_deg - e1) / (e2 - e1)
            return r1 + frac * (r2 - r1)

    return rates[elevations[-1]]


class DownlinkHandler(ActivityHandler):
    """
    Handler for data downlink activities during ground station contacts.

    Models:
    - Contact geometry (elevation-dependent data rates)
    - Power consumption during transmission
    - Storage depletion as data is downlinked
    """

    @property
    def activity_type(self) -> str:
        return "downlink"

    def validate(self, activity: Activity) -> List[Event]:
        """Validate downlink parameters."""
        events = []
        params = activity.parameters

        if "station_id" not in params:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.ERROR,
                category="validation",
                message="Missing required parameter: station_id",
                details={"activity_id": activity.activity_id},
            ))

        band = params.get("band", "X")
        if band not in ["S", "X", "Ka"]:
            events.append(Event(
                timestamp=activity.start_time,
                event_type=EventType.WARNING,
                category="validation",
                message=f"Unknown band '{band}', defaulting to X-band",
                details={"activity_id": activity.activity_id},
            ))

        return events

    def get_power_consumption(self, activity: Activity) -> float:
        """Get power consumption during downlink."""
        return activity.parameters.get("tx_power_w", 50.0)

    def process(
        self,
        activity: Activity,
        state: InitialState,
        ephemeris: list,
        config: Any,
    ) -> ActivityResult:
        """
        Process downlink activity.

        Args:
            activity: Downlink activity
            state: Current spacecraft state
            ephemeris: Ephemeris for activity duration
            config: Simulation configuration

        Returns:
            ActivityResult with data downlinked and storage freed
        """
        params = DownlinkParams.from_dict(activity.parameters)

        # Initialize power model
        power_config = PowerConfig(
            battery_capacity_wh=config.spacecraft.battery_capacity_wh,
            solar_panel_area_m2=config.spacecraft.solar_panel_area_m2,
            solar_efficiency=config.spacecraft.solar_efficiency,
            base_power_w=config.spacecraft.base_power_w,
        )
        power_model = PowerModel(power_config)

        # Create ground station for access calculation
        station = GroundStation(
            station_id=params.station_id,
            name=params.station_id,
            lat_deg=0.0,  # Will be looked up from defaults
            lon_deg=0.0,
            min_elevation_deg=params.min_elevation_deg,
            bands=[params.band],
        )

        # Try to find station in defaults
        from sim.models.access import get_default_stations
        for default_station in get_default_stations():
            if default_station.station_id == params.station_id:
                station = default_station
                break

        access_model = AccessModel([station])

        events: List[Event] = []
        current_soc = state.battery_soc
        current_storage = state.storage_used_gb
        total_downlinked_mb = 0.0
        contact_duration_s = 0.0
        time_step_s = config.time_step_s

        # Track contact periods
        in_contact = False
        contact_start = None

        for point in ephemeris:
            # Compute elevation to station
            elevation, azimuth = access_model.compute_elevation_azimuth(
                point.position_eci, station, point.time
            )

            if elevation >= params.min_elevation_deg:
                if not in_contact:
                    in_contact = True
                    contact_start = point.time
                    events.append(self.create_info_event(
                        timestamp=point.time,
                        category="contact",
                        message=f"AOS with {params.station_id} at {elevation:.1f}° elevation",
                        details={"station_id": params.station_id, "elevation": elevation},
                    ))

                # Calculate data rate at current elevation
                data_rate_mbps = get_data_rate_at_elevation(params.band, elevation)

                # Check if we have data to downlink
                if current_storage <= 0:
                    continue

                # Check power availability
                in_eclipse = power_model.is_in_eclipse(point.position_eci)
                generation = power_model.compute_solar_generation(in_eclipse)
                total_power = power_config.base_power_w + params.tx_power_w

                current_soc, power_limited = power_model.update_soc(
                    current_soc, generation, total_power, time_step_s
                )

                if power_limited:
                    events.append(self.create_warning_event(
                        timestamp=point.time,
                        category="power",
                        message="Power limited during downlink",
                        details={"soc": current_soc},
                    ))
                    continue

                # Calculate data downlinked in this time step
                data_mb = data_rate_mbps * time_step_s / 8.0  # Mbps to MB
                data_gb = data_mb / 1000.0

                # Limit to available storage
                actual_data_gb = min(data_gb, current_storage)
                actual_data_mb = actual_data_gb * 1000.0

                current_storage -= actual_data_gb
                total_downlinked_mb += actual_data_mb
                contact_duration_s += time_step_s

            elif in_contact:
                # Lost contact
                in_contact = False
                events.append(self.create_info_event(
                    timestamp=point.time,
                    category="contact",
                    message=f"LOS with {params.station_id}",
                    details={"station_id": params.station_id},
                ))

        # Validate constraints
        if current_storage < 0:
            events.append(self.create_violation_event(
                timestamp=activity.end_time,
                category="storage",
                message="Storage went negative",
                details={"final_storage": current_storage},
            ))
            current_storage = 0.0

        # Create result
        success = total_downlinked_mb > 0 and not any(
            e.event_type == EventType.VIOLATION for e in events
        )

        return ActivityResult(
            activity_id=activity.activity_id,
            success=success,
            events=events,
            state_updates={
                "battery_soc": max(0.0, min(1.0, current_soc)),
                "storage_used_gb": max(0.0, current_storage),
            },
            artifacts={
                "station_id": params.station_id,
                "band": params.band,
                "total_downlinked_mb": total_downlinked_mb,
                "contact_duration_s": contact_duration_s,
            },
            message=(
                f"Downlink to {params.station_id}: {total_downlinked_mb:.1f} MB, "
                f"contact={contact_duration_s:.0f}s, "
                f"storage remaining={current_storage:.2f} GB"
            ),
        )
