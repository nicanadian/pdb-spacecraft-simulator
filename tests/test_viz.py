"""Tests for visualization modules."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from sim.viz.czml_generator import CZMLGenerator, CZMLStyle, _iso
from sim.viz.diff import (
    RunDiff,
    _compute_contact_diff,
    _compute_position_diff,
    _compute_profile_diff,
    compute_run_diff,
)
from sim.viz.manifest_generator import (
    VizArtifact,
    VizManifest,
    generate_viz_manifest,
)


class TestCZMLStyle:
    """Test CZMLStyle dataclass."""

    def test_default_values(self):
        """Test default style values."""
        style = CZMLStyle()

        assert style.satellite_color == (0, 255, 255, 255)
        assert style.satellite_scale == 1.5
        assert style.orbit_trail_width == 2.0
        assert style.ground_station_color == (255, 165, 0, 255)

    def test_custom_values(self):
        """Test custom style values."""
        style = CZMLStyle(
            satellite_color=(255, 0, 0, 255),
            satellite_scale=2.0,
        )

        assert style.satellite_color == (255, 0, 0, 255)
        assert style.satellite_scale == 2.0


class TestCZMLGenerator:
    """Test CZMLGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create generator for testing."""
        return CZMLGenerator()

    @pytest.fixture
    def start_time(self):
        """Create start time for testing."""
        return datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

    @pytest.fixture
    def end_time(self, start_time):
        """Create end time for testing."""
        return start_time + timedelta(hours=24)

    @pytest.fixture
    def ephemeris(self, start_time):
        """Create sample ephemeris DataFrame."""
        times = [start_time + timedelta(minutes=i * 10) for i in range(10)]
        return pd.DataFrame({
            "time": times,
            "x_km": [6878 + i * 10 for i in range(10)],
            "y_km": [0.0] * 10,
            "z_km": [0.0] * 10,
        })

    def test_add_document(self, generator, start_time, end_time):
        """Test adding document header."""
        generator.add_document(
            name="Test Simulation",
            start_time=start_time,
            end_time=end_time,
            description="Test description",
        )

        packets = generator.generate()
        assert len(packets) == 1

        doc = packets[0]
        assert doc["id"] == "document"
        assert doc["name"] == "Test Simulation"
        assert doc["version"] == "1.0"
        assert "clock" in doc

    def test_add_satellite(self, generator, ephemeris, start_time, end_time):
        """Test adding satellite with trajectory."""
        generator.add_document("Test", start_time, end_time)
        generator.add_satellite(
            satellite_id="sat_1",
            name="Test Satellite",
            ephemeris=ephemeris,
            show_path=True,
        )

        packets = generator.generate()
        assert len(packets) == 2

        sat = packets[1]
        assert sat["id"] == "sat_1"
        assert sat["name"] == "Test Satellite"
        assert "position" in sat
        assert "point" in sat
        assert "path" in sat
        assert "label" in sat

        # Check position data format
        position = sat["position"]
        assert "cartesian" in position
        assert len(position["cartesian"]) == 10 * 4  # 10 points, 4 values each

    def test_add_satellite_no_path(self, generator, ephemeris, start_time, end_time):
        """Test adding satellite without orbit path."""
        generator.add_document("Test", start_time, end_time)
        generator.add_satellite(
            satellite_id="sat_1",
            name="Test Satellite",
            ephemeris=ephemeris,
            show_path=False,
        )

        packets = generator.generate()
        sat = packets[1]
        assert "path" not in sat

    def test_add_satellite_empty_ephemeris(self, generator, start_time, end_time):
        """Test adding satellite with empty ephemeris."""
        generator.add_document("Test", start_time, end_time)
        generator.add_satellite(
            satellite_id="sat_1",
            name="Test Satellite",
            ephemeris=pd.DataFrame(),
        )

        # Should not add satellite packet
        packets = generator.generate()
        assert len(packets) == 1  # Only document

    def test_add_ground_station(self, generator, start_time, end_time):
        """Test adding ground station."""
        generator.add_document("Test", start_time, end_time)
        generator.add_ground_station(
            station_id="SVALBARD",
            name="Svalbard Ground Station",
            lat_deg=78.23,
            lon_deg=15.39,
            alt_m=500,
        )

        packets = generator.generate()
        assert len(packets) == 2

        station = packets[1]
        assert station["id"] == "station_SVALBARD"
        assert station["name"] == "Svalbard Ground Station"
        assert "position" in station
        assert "point" in station

    def test_add_contact_window(self, generator, start_time, end_time):
        """Test adding contact window."""
        generator.add_document("Test", start_time, end_time)
        generator.add_contact_window(
            contact_id="contact_001",
            satellite_id="sat_1",
            station_id="SVALBARD",
            start_time=start_time,
            end_time=start_time + timedelta(minutes=10),
        )

        packets = generator.generate()
        assert len(packets) == 2

        contact = packets[1]
        assert contact["id"] == "contact_contact_001"
        assert "polyline" in contact
        assert "availability" in contact

    def test_add_eclipse_period(self, generator, start_time, end_time):
        """Test adding eclipse period."""
        generator.add_document("Test", start_time, end_time)
        generator.add_eclipse_period(
            eclipse_id="eclipse_001",
            satellite_id="sat_1",
            start_time=start_time,
            end_time=start_time + timedelta(minutes=35),
        )

        packets = generator.generate()
        assert len(packets) == 2

        eclipse = packets[1]
        assert eclipse["id"] == "eclipse_eclipse_001"
        assert "availability" in eclipse

    def test_save(self, generator, start_time, end_time, tmp_path):
        """Test saving CZML to file."""
        generator.add_document("Test", start_time, end_time)

        output_path = tmp_path / "test.czml"
        generator.save(output_path)

        assert output_path.exists()

        with open(output_path) as f:
            data = json.load(f)

        assert len(data) == 1
        assert data[0]["id"] == "document"

    def test_generate_returns_copy(self, generator, start_time, end_time):
        """Test that generate returns the packet list."""
        generator.add_document("Test", start_time, end_time)

        packets1 = generator.generate()
        packets2 = generator.generate()

        assert packets1 == packets2


class TestIsoHelper:
    """Test _iso helper function."""

    def test_datetime_with_timezone(self):
        """Test formatting datetime with timezone."""
        dt = datetime(2025, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
        result = _iso(dt)

        assert result == "2025-01-15T12:30:45Z"

    def test_datetime_without_timezone(self):
        """Test formatting datetime without timezone (assumes UTC)."""
        dt = datetime(2025, 1, 15, 12, 30, 45)
        result = _iso(dt)

        assert "2025-01-15T12:30:45" in result
        assert result.endswith("Z")

    def test_string_passthrough(self):
        """Test that strings are passed through."""
        s = "2025-01-15T12:30:45Z"
        result = _iso(s)
        assert result == s


class TestRunDiff:
    """Test RunDiff dataclass."""

    def test_create_diff(self):
        """Test creating run diff."""
        diff = RunDiff(
            run_a_id="run_001",
            run_b_id="run_002",
            run_a_fidelity="LOW",
            run_b_fidelity="MEDIUM",
            position_rmse_km=0.5,
            max_position_diff_km=1.2,
            altitude_rmse_km=0.3,
        )

        assert diff.run_a_id == "run_001"
        assert diff.position_rmse_km == 0.5

    def test_to_dict(self):
        """Test converting diff to dictionary."""
        diff = RunDiff(
            run_a_id="run_001",
            run_b_id="run_002",
            run_a_fidelity="LOW",
            run_b_fidelity="MEDIUM",
            position_rmse_km=0.5,
            max_position_diff_km=1.2,
            altitude_rmse_km=0.3,
            contact_timing_rmse_s=5.0,
            soc_rmse=0.02,
            comparable=True,
        )

        d = diff.to_dict()

        assert d["runs"]["a"]["id"] == "run_001"
        assert d["runs"]["b"]["fidelity"] == "MEDIUM"
        assert d["position"]["rmse_km"] == 0.5
        assert d["contacts"]["timing_rmse_s"] == 5.0
        assert d["state"]["soc_rmse"] == 0.02
        assert d["comparable"] is True


class TestComputePositionDiff:
    """Test position diff computation."""

    def test_compute_position_diff(self):
        """Test computing position differences."""
        times = pd.to_datetime([
            "2025-01-15T00:00:00Z",
            "2025-01-15T00:10:00Z",
            "2025-01-15T00:20:00Z",
        ])

        eph_a = pd.DataFrame({
            "time": times,
            "x_km": [6878.0, 6880.0, 6882.0],
            "y_km": [0.0, 100.0, 200.0],
            "z_km": [0.0, 0.0, 0.0],
            "altitude_km": [500.0, 502.0, 504.0],
        })

        eph_b = pd.DataFrame({
            "time": times,
            "x_km": [6878.0, 6880.1, 6882.2],
            "y_km": [0.0, 100.1, 200.2],
            "z_km": [0.0, 0.0, 0.0],
            "altitude_km": [500.0, 502.1, 504.2],
        })

        pos_rmse, max_diff, alt_rmse = _compute_position_diff(eph_a, eph_b)

        assert pos_rmse >= 0
        assert max_diff >= pos_rmse
        assert alt_rmse >= 0

    def test_compute_position_diff_no_overlap(self):
        """Test position diff with no time overlap."""
        eph_a = pd.DataFrame({
            "time": pd.to_datetime(["2025-01-15T00:00:00Z"]),
            "x_km": [6878.0],
            "y_km": [0.0],
            "z_km": [0.0],
            "altitude_km": [500.0],
        })

        eph_b = pd.DataFrame({
            "time": pd.to_datetime(["2025-01-16T00:00:00Z"]),
            "x_km": [6878.0],
            "y_km": [0.0],
            "z_km": [0.0],
            "altitude_km": [500.0],
        })

        pos_rmse, max_diff, alt_rmse = _compute_position_diff(eph_a, eph_b)

        assert np.isnan(pos_rmse)
        assert np.isnan(max_diff)


class TestComputeContactDiff:
    """Test contact diff computation."""

    def test_compute_contact_diff(self):
        """Test computing contact timing differences."""
        contacts_a = {
            "SVALBARD": [
                {"start_time": "2025-01-15T00:00:00Z", "end_time": "2025-01-15T00:10:00Z", "duration_s": 600},
            ]
        }

        contacts_b = {
            "SVALBARD": [
                {"start_time": "2025-01-15T00:00:05Z", "end_time": "2025-01-15T00:10:03Z", "duration_s": 598},
            ]
        }

        diffs, timing_rmse = _compute_contact_diff(contacts_a, contacts_b)

        assert len(diffs) >= 1
        assert timing_rmse >= 0

    def test_compute_contact_diff_no_match(self):
        """Test contact diff with no matching contacts."""
        contacts_a = {
            "SVALBARD": [
                {"start_time": "2025-01-15T00:00:00Z", "end_time": "2025-01-15T00:10:00Z"},
            ]
        }

        contacts_b = {
            "HAWAII": [
                {"start_time": "2025-01-15T06:00:00Z", "end_time": "2025-01-15T06:10:00Z"},
            ]
        }

        diffs, timing_rmse = _compute_contact_diff(contacts_a, contacts_b)

        # No matching station contacts
        assert len(diffs) == 0
        assert timing_rmse == 0.0


class TestComputeProfileDiff:
    """Test profile diff computation."""

    def test_compute_profile_diff(self):
        """Test computing profile differences."""
        times = pd.to_datetime([
            "2025-01-15T00:00:00Z",
            "2025-01-15T01:00:00Z",
            "2025-01-15T02:00:00Z",
        ])

        profiles_a = pd.DataFrame({
            "time": times,
            "battery_soc": [1.0, 0.95, 0.90],
            "storage_gb": [0.0, 10.0, 20.0],
        })

        profiles_b = pd.DataFrame({
            "time": times,
            "battery_soc": [1.0, 0.94, 0.88],
            "storage_gb": [0.0, 10.5, 21.0],
        })

        soc_rmse, storage_rmse = _compute_profile_diff(profiles_a, profiles_b)

        assert soc_rmse >= 0
        assert storage_rmse >= 0

    def test_compute_profile_diff_none_input(self):
        """Test profile diff with None input."""
        soc_rmse, storage_rmse = _compute_profile_diff(None, None)

        assert np.isnan(soc_rmse)
        assert np.isnan(storage_rmse)


class TestVizArtifact:
    """Test VizArtifact dataclass."""

    def test_create_artifact(self):
        """Test artifact creation."""
        artifact = VizArtifact(
            name="scene.czml",
            path="viz/scene.czml",
            type="czml",
            description="3D scene",
            size_bytes=1024,
        )

        assert artifact.name == "scene.czml"
        assert artifact.type == "czml"
        assert artifact.size_bytes == 1024


class TestVizManifest:
    """Test VizManifest dataclass."""

    def test_create_manifest(self):
        """Test manifest creation."""
        manifest = VizManifest(
            run_id="run_001",
            plan_id="plan_001",
            fidelity="LOW",
            created_at="2025-01-15T00:00:00Z",
            start_time="2025-01-15T00:00:00Z",
            end_time="2025-01-15T24:00:00Z",
            duration_hours=24.0,
        )

        assert manifest.run_id == "run_001"
        assert manifest.fidelity == "LOW"
        assert manifest.duration_hours == 24.0

    def test_to_dict(self):
        """Test manifest to_dict."""
        artifact = VizArtifact(
            name="scene.czml",
            path="viz/scene.czml",
            type="czml",
        )

        manifest = VizManifest(
            run_id="run_001",
            plan_id="plan_001",
            fidelity="LOW",
            created_at="2025-01-15T00:00:00Z",
            start_time="2025-01-15T00:00:00Z",
            end_time="2025-01-15T24:00:00Z",
            duration_hours=24.0,
            artifacts=[artifact],
            summary={"activities": {"count": 5}},
        )

        d = manifest.to_dict()

        assert d["run_id"] == "run_001"
        assert d["time_range"]["duration_hours"] == 24.0
        assert len(d["artifacts"]) == 1
        assert d["artifacts"][0]["name"] == "scene.czml"

    def test_save(self, tmp_path):
        """Test saving manifest to file."""
        manifest = VizManifest(
            run_id="run_001",
            plan_id="plan_001",
            fidelity="LOW",
            created_at="2025-01-15T00:00:00Z",
            start_time="2025-01-15T00:00:00Z",
            end_time="2025-01-15T24:00:00Z",
            duration_hours=24.0,
        )

        output_path = tmp_path / "manifest.json"
        manifest.save(output_path)

        assert output_path.exists()

        with open(output_path) as f:
            data = json.load(f)

        assert data["run_id"] == "run_001"


class TestGenerateVizManifest:
    """Test generate_viz_manifest function."""

    def test_generate_manifest(self, tmp_path):
        """Test generating manifest from run directory."""
        run_dir = tmp_path / "run_001"
        run_dir.mkdir()
        viz_dir = run_dir / "viz"
        viz_dir.mkdir()

        # Create summary file
        summary = {
            "plan_id": "test_plan",
            "start_time": "2025-01-15T00:00:00Z",
            "end_time": "2025-01-15T24:00:00Z",
            "duration_hours": 24.0,
        }
        with open(run_dir / "summary.json", "w") as f:
            json.dump(summary, f)

        # Create events file
        with open(run_dir / "events.json", "w") as f:
            json.dump([], f)

        manifest = generate_viz_manifest(run_dir)

        assert manifest.run_id == "run_001"
        assert manifest.plan_id == "test_plan"
        assert len(manifest.artifacts) >= 1

        # Check manifest was saved
        assert (viz_dir / "run_manifest.json").exists()
