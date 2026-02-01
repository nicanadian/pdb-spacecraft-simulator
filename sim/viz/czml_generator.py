"""
CZML generator for CesiumJS visualization.

Generates CZML (Cesium Language) files from simulation outputs
for 3D globe visualization.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)


@dataclass
class CZMLStyle:
    """Style configuration for CZML entities."""

    satellite_color: Tuple[int, int, int, int] = (0, 255, 255, 255)  # Cyan
    satellite_scale: float = 1.5
    orbit_trail_color: Tuple[int, int, int, int] = (0, 200, 255, 128)
    orbit_trail_width: float = 2.0
    ground_station_color: Tuple[int, int, int, int] = (255, 165, 0, 255)  # Orange
    contact_line_color: Tuple[int, int, int, int] = (0, 255, 0, 200)  # Green
    eclipse_color: Tuple[int, int, int, int] = (100, 100, 100, 150)  # Gray


class CZMLGenerator:
    """
    Generator for CZML visualization files.

    Creates CZML documents compatible with CesiumJS for visualizing:
    - Satellite trajectory
    - Ground stations
    - Contact windows
    - Eclipse periods
    """

    def __init__(self, style: Optional[CZMLStyle] = None):
        self.style = style or CZMLStyle()
        self._packets: List[Dict[str, Any]] = []

    def add_document(
        self,
        name: str,
        start_time: datetime,
        end_time: datetime,
        description: str = "",
    ) -> None:
        """Add document header packet."""
        self._packets.append({
            "id": "document",
            "name": name,
            "version": "1.0",
            "clock": {
                "interval": f"{_iso(start_time)}/{_iso(end_time)}",
                "currentTime": _iso(start_time),
                "multiplier": 60,
                "range": "LOOP_STOP",
                "step": "SYSTEM_CLOCK_MULTIPLIER",
            },
            "description": description,
        })

    def add_satellite(
        self,
        satellite_id: str,
        name: str,
        ephemeris: pd.DataFrame,
        show_path: bool = True,
        path_lead_time: float = 3600,
        path_trail_time: float = 3600,
    ) -> None:
        """
        Add satellite with trajectory.

        Args:
            satellite_id: Unique ID for satellite
            name: Display name
            ephemeris: DataFrame with time, x_km, y_km, z_km columns
            show_path: Whether to show orbit path
            path_lead_time: Path lead time in seconds
            path_trail_time: Path trail time in seconds
        """
        if ephemeris.empty:
            return

        # Convert to CZML position format
        # CZML expects: [time, x, y, z, time, x, y, z, ...]
        positions = []

        if "time" in ephemeris.columns:
            times = ephemeris["time"]
        else:
            times = ephemeris.index

        start_time = times.iloc[0]

        for i, (_, row) in enumerate(ephemeris.iterrows()):
            t = times.iloc[i]
            if isinstance(t, datetime):
                epoch_offset = (t - start_time).total_seconds()
            else:
                epoch_offset = float(t)

            # Convert km to m for Cesium
            positions.extend([
                epoch_offset,
                row["x_km"] * 1000,
                row["y_km"] * 1000,
                row["z_km"] * 1000,
            ])

        end_time = times.iloc[-1]
        interval = f"{_iso(start_time)}/{_iso(end_time)}"

        packet = {
            "id": satellite_id,
            "name": name,
            "availability": interval,
            "position": {
                "epoch": _iso(start_time),
                "cartesian": positions,
                "interpolationAlgorithm": "LAGRANGE",
                "interpolationDegree": 5,
            },
            "point": {
                "color": {"rgba": list(self.style.satellite_color)},
                "pixelSize": 10 * self.style.satellite_scale,
                "outlineColor": {"rgba": [255, 255, 255, 255]},
                "outlineWidth": 2,
            },
            "label": {
                "text": name,
                "font": "14px sans-serif",
                "fillColor": {"rgba": [255, 255, 255, 255]},
                "outlineColor": {"rgba": [0, 0, 0, 255]},
                "outlineWidth": 2,
                "style": "FILL_AND_OUTLINE",
                "verticalOrigin": "BOTTOM",
                "pixelOffset": {"cartesian2": [0, -15]},
            },
        }

        if show_path:
            packet["path"] = {
                "material": {
                    "polylineOutline": {
                        "color": {"rgba": list(self.style.orbit_trail_color)},
                        "outlineColor": {"rgba": [0, 0, 0, 128]},
                        "outlineWidth": 1,
                    }
                },
                "width": self.style.orbit_trail_width,
                "leadTime": path_lead_time,
                "trailTime": path_trail_time,
                "resolution": 120,
            }

        self._packets.append(packet)

    def add_ground_station(
        self,
        station_id: str,
        name: str,
        lat_deg: float,
        lon_deg: float,
        alt_m: float = 0,
    ) -> None:
        """Add ground station marker."""
        # Convert to Cartesian (simplified - on ellipsoid)
        lat_rad = np.radians(lat_deg)
        lon_rad = np.radians(lon_deg)
        r = 6378137 + alt_m  # Earth radius in meters

        x = r * np.cos(lat_rad) * np.cos(lon_rad)
        y = r * np.cos(lat_rad) * np.sin(lon_rad)
        z = r * np.sin(lat_rad)

        self._packets.append({
            "id": f"station_{station_id}",
            "name": name,
            "position": {
                "cartesian": [x, y, z],
            },
            "point": {
                "color": {"rgba": list(self.style.ground_station_color)},
                "pixelSize": 12,
                "outlineColor": {"rgba": [255, 255, 255, 255]},
                "outlineWidth": 2,
            },
            "label": {
                "text": name,
                "font": "12px sans-serif",
                "fillColor": {"rgba": [255, 165, 0, 255]},
                "style": "FILL",
                "verticalOrigin": "BOTTOM",
                "pixelOffset": {"cartesian2": [0, -15]},
            },
        })

    def add_contact_window(
        self,
        contact_id: str,
        satellite_id: str,
        station_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Add contact window visualization (line between sat and station)."""
        interval = f"{_iso(start_time)}/{_iso(end_time)}"

        self._packets.append({
            "id": f"contact_{contact_id}",
            "name": f"Contact: {station_id}",
            "availability": interval,
            "polyline": {
                "positions": {
                    "references": [
                        f"{satellite_id}#position",
                        f"station_{station_id}#position",
                    ],
                },
                "material": {
                    "solidColor": {
                        "color": {"rgba": list(self.style.contact_line_color)},
                    },
                },
                "width": 2,
                "show": True,
            },
        })

    def add_eclipse_period(
        self,
        eclipse_id: str,
        satellite_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Add eclipse period indicator."""
        interval = f"{_iso(start_time)}/{_iso(end_time)}"

        # Change satellite color during eclipse
        self._packets.append({
            "id": f"eclipse_{eclipse_id}",
            "name": f"Eclipse {eclipse_id}",
            "availability": interval,
            "description": f"Eclipse from {_iso(start_time)} to {_iso(end_time)}",
        })

    def generate(self) -> List[Dict[str, Any]]:
        """Generate CZML document."""
        return self._packets

    def save(self, path: Path) -> None:
        """Save CZML to file."""
        with open(path, "w") as f:
            json.dump(self._packets, f, indent=2)


def generate_czml(
    run_dir: Path,
    satellite_name: str = "Satellite",
    output_name: str = "scene.czml",
) -> Path:
    """
    Generate CZML from simulation run outputs.

    Args:
        run_dir: Path to run directory
        satellite_name: Display name for satellite
        output_name: Output filename

    Returns:
        Path to generated CZML file
    """
    generator = CZMLGenerator()

    # Load ephemeris
    eph_path = run_dir / "ephemeris.parquet"
    if eph_path.exists():
        ephemeris = pd.read_parquet(eph_path)
    else:
        logger.warning("No ephemeris found")
        ephemeris = pd.DataFrame()

    # Load access windows
    access_path = run_dir / "access_windows.json"
    if access_path.exists():
        with open(access_path) as f:
            access_windows = json.load(f)
    else:
        access_windows = {}

    # Load eclipse windows
    eclipse_path = run_dir / "eclipse_windows.json"
    if eclipse_path.exists():
        with open(eclipse_path) as f:
            eclipse_windows = json.load(f)
    else:
        eclipse_windows = []

    # Load summary for time bounds
    summary_path = run_dir / "summary.json"
    if summary_path.exists():
        with open(summary_path) as f:
            summary = json.load(f)
        start_time = datetime.fromisoformat(summary["start_time"])
        end_time = datetime.fromisoformat(summary["end_time"])
    elif not ephemeris.empty:
        times = ephemeris["time"] if "time" in ephemeris.columns else ephemeris.index
        start_time = times.iloc[0]
        end_time = times.iloc[-1]
    else:
        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(hours=24)

    # Generate document
    generator.add_document(
        name="Simulation Visualization",
        start_time=start_time,
        end_time=end_time,
        description=f"Run: {run_dir.name}",
    )

    # Add satellite
    if not ephemeris.empty:
        generator.add_satellite(
            satellite_id="satellite_1",
            name=satellite_name,
            ephemeris=ephemeris,
        )

    # Add ground stations from access windows
    from sim.models.access import get_default_stations
    for station in get_default_stations():
        if station.station_id in access_windows:
            generator.add_ground_station(
                station_id=station.station_id,
                name=station.name,
                lat_deg=station.lat_deg,
                lon_deg=station.lon_deg,
            )

    # Add contact windows
    contact_id = 0
    for station_id, windows in access_windows.items():
        for window in windows:
            aos = datetime.fromisoformat(window["start_time"])
            los = datetime.fromisoformat(window["end_time"])
            generator.add_contact_window(
                contact_id=str(contact_id),
                satellite_id="satellite_1",
                station_id=station_id,
                start_time=aos,
                end_time=los,
            )
            contact_id += 1

    # Add eclipse periods
    for i, eclipse in enumerate(eclipse_windows):
        entry = datetime.fromisoformat(eclipse["start_time"])
        exit_time = datetime.fromisoformat(eclipse["end_time"])
        generator.add_eclipse_period(
            eclipse_id=str(i),
            satellite_id="satellite_1",
            start_time=entry,
            end_time=exit_time,
        )

    # Save
    viz_dir = run_dir / "viz"
    viz_dir.mkdir(exist_ok=True)
    output_path = viz_dir / output_name
    generator.save(output_path)

    logger.info(f"Generated CZML: {output_path}")
    return output_path


def _iso(dt: datetime) -> str:
    """Format datetime to ISO string for CZML."""
    if isinstance(dt, str):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")
