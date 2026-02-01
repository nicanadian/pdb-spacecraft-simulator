"""Tests for activity mappers."""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from sim.core.types import Activity, SimConfig, SpacecraftConfig
from sim.runners.activity_mappers import (
    ActivityMapper,
    AttitudeProfile,
    DataProfile,
    DownlinkMapper,
    IdleMapper,
    ImagingMapper,
    PowerProfile,
    SimulationSegmentSpec,
    StationKeepingMapper,
    ThrustMapper,
    ThrustProfile,
    get_mapper,
    map_activity,
    register_mapper,
)


@pytest.fixture
def sim_config():
    """Create simulation config for testing."""
    return SimConfig(
        spacecraft=SpacecraftConfig(
            spacecraft_id="test_sc",
            base_power_w=200.0,
        ),
    )


@pytest.fixture
def timestamp():
    """Create base timestamp for testing."""
    return datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


class TestAttitudeProfile:
    """Test AttitudeProfile dataclass."""

    def test_default_values(self):
        """Test default attitude profile values."""
        profile = AttitudeProfile(profile_type="nadir")

        assert profile.profile_type == "nadir"
        assert profile.target_vector is None
        assert profile.slew_rate_deg_s == 1.0
        assert profile.settling_time_s == 10.0

    def test_with_target(self):
        """Test attitude profile with target vector."""
        target = np.array([1.0, 0.0, 0.0])
        profile = AttitudeProfile(
            profile_type="target",
            target_vector=target,
            slew_rate_deg_s=2.0,
        )

        assert profile.profile_type == "target"
        np.testing.assert_array_equal(profile.target_vector, target)


class TestPowerProfile:
    """Test PowerProfile dataclass."""

    def test_default_values(self):
        """Test default power profile values."""
        profile = PowerProfile()

        assert profile.base_power_w == 100.0
        assert profile.peak_power_w == 100.0
        assert profile.duty_cycle == 1.0
        assert profile.solar_generation_w == 0.0

    def test_custom_values(self):
        """Test custom power profile values."""
        profile = PowerProfile(
            base_power_w=200.0,
            peak_power_w=500.0,
            duty_cycle=0.5,
            solar_generation_w=300.0,
        )

        assert profile.base_power_w == 200.0
        assert profile.peak_power_w == 500.0
        assert profile.duty_cycle == 0.5


class TestThrustProfile:
    """Test ThrustProfile dataclass."""

    def test_default_values(self):
        """Test default thrust profile values."""
        profile = ThrustProfile()

        assert profile.thrust_n == 0.0
        assert profile.isp_s == 1500.0
        assert profile.duty_cycle == 1.0
        assert profile.power_w == 500.0

    def test_with_direction(self):
        """Test thrust profile with custom direction."""
        direction = np.array([0.0, 1.0, 0.0])
        profile = ThrustProfile(
            thrust_n=0.1,
            direction=direction,
        )

        assert profile.thrust_n == 0.1
        np.testing.assert_array_equal(profile.direction, direction)


class TestDataProfile:
    """Test DataProfile dataclass."""

    def test_default_values(self):
        """Test default data profile values."""
        profile = DataProfile()

        assert profile.generation_rate_mbps == 0.0
        assert profile.transmission_rate_mbps == 0.0
        assert profile.processing_mode == "none"
        assert profile.compression_ratio == 1.0


class TestSimulationSegmentSpec:
    """Test SimulationSegmentSpec dataclass."""

    def test_duration_property(self, timestamp):
        """Test segment duration calculation."""
        segment = SimulationSegmentSpec(
            start_time=timestamp,
            end_time=timestamp + timedelta(minutes=10),
            segment_type="test",
            attitude=AttitudeProfile(profile_type="nadir"),
            power=PowerProfile(),
            thrust=ThrustProfile(),
            data=DataProfile(),
        )

        assert segment.duration_s == 600.0

    def test_default_profiles(self, timestamp):
        """Test segment with specified profiles."""
        segment = SimulationSegmentSpec(
            start_time=timestamp,
            end_time=timestamp + timedelta(minutes=5),
            segment_type="idle",
            attitude=AttitudeProfile(profile_type="nadir"),
            power=PowerProfile(),
            thrust=ThrustProfile(),
            data=DataProfile(),
        )

        assert segment.attitude.profile_type == "nadir"
        assert segment.power.base_power_w == 100.0
        assert segment.thrust.thrust_n == 0.0
        assert segment.data.generation_rate_mbps == 0.0


class TestIdleMapper:
    """Test IdleMapper."""

    def test_activity_type(self):
        """Test activity type property."""
        mapper = IdleMapper()
        assert mapper.activity_type == "idle"

    def test_map_idle_activity(self, sim_config, timestamp):
        """Test mapping idle activity to segments."""
        activity = Activity(
            activity_id="idle_001",
            activity_type="idle",
            start_time=timestamp,
            end_time=timestamp + timedelta(hours=1),
        )

        mapper = IdleMapper()
        segments = mapper.map(activity, sim_config)

        assert len(segments) == 1
        segment = segments[0]

        assert segment.segment_type == "idle"
        assert segment.activity_id == "idle_001"
        assert segment.attitude.profile_type == "nadir"
        assert segment.power.base_power_w == 200.0
        assert segment.duration_s == 3600.0


class TestImagingMapper:
    """Test ImagingMapper."""

    def test_activity_type(self):
        """Test activity type property."""
        mapper = ImagingMapper()
        assert mapper.activity_type == "eo_collect"

    def test_map_imaging_activity(self, sim_config, timestamp):
        """Test mapping imaging activity to segments."""
        activity = Activity(
            activity_id="eo_001",
            activity_type="eo_collect",
            start_time=timestamp,
            end_time=timestamp + timedelta(minutes=5),
            parameters={
                "target_lat": 37.5,
                "target_lon": -122.4,
                "duration_s": 180,
                "gsd_m": 1.0,
            },
        )

        mapper = ImagingMapper()
        segments = mapper.map(activity, sim_config)

        # Should have slew + imaging segments
        assert len(segments) >= 1

        # Check imaging segment
        imaging_segments = [s for s in segments if s.segment_type == "imaging"]
        assert len(imaging_segments) == 1

        imaging = imaging_segments[0]
        assert imaging.attitude.profile_type == "target"
        assert imaging.data.generation_rate_mbps > 0
        assert imaging.parameters["target_lat"] == 37.5
        assert imaging.parameters["gsd_m"] == 1.0

    def test_map_imaging_with_slew(self, sim_config, timestamp):
        """Test imaging activity includes slew segment."""
        activity = Activity(
            activity_id="eo_002",
            activity_type="eo_collect",
            start_time=timestamp,
            end_time=timestamp + timedelta(minutes=5),
            parameters={
                "target_lat": 40.0,
                "target_lon": -74.0,
                "duration_s": 120,
                "slew_angle_deg": 45.0,
            },
        )

        mapper = ImagingMapper()
        segments = mapper.map(activity, sim_config)

        slew_segments = [s for s in segments if s.segment_type == "slew"]
        assert len(slew_segments) == 1

        slew = slew_segments[0]
        assert slew.attitude.slew_rate_deg_s > 0

    def test_data_rate_varies_with_gsd(self, sim_config, timestamp):
        """Test data rate increases with better resolution."""
        activity_1m = Activity(
            activity_id="eo_1m",
            activity_type="eo_collect",
            start_time=timestamp,
            end_time=timestamp + timedelta(minutes=3),
            parameters={"gsd_m": 1.0, "target_lat": 0, "target_lon": 0},
        )

        activity_50cm = Activity(
            activity_id="eo_50cm",
            activity_type="eo_collect",
            start_time=timestamp,
            end_time=timestamp + timedelta(minutes=3),
            parameters={"gsd_m": 0.5, "target_lat": 0, "target_lon": 0},
        )

        mapper = ImagingMapper()
        segments_1m = mapper.map(activity_1m, sim_config)
        segments_50cm = mapper.map(activity_50cm, sim_config)

        imaging_1m = [s for s in segments_1m if s.segment_type == "imaging"][0]
        imaging_50cm = [s for s in segments_50cm if s.segment_type == "imaging"][0]

        # Higher resolution = more data
        assert imaging_50cm.data.generation_rate_mbps > imaging_1m.data.generation_rate_mbps

    def test_validate_missing_target(self, sim_config, timestamp):
        """Test validation with missing target coordinates."""
        activity = Activity(
            activity_id="eo_003",
            activity_type="eo_collect",
            start_time=timestamp,
            end_time=timestamp + timedelta(minutes=3),
            parameters={"duration_s": 120},  # No target_lat/lon
        )

        mapper = ImagingMapper()
        events = mapper.validate(activity, sim_config)

        assert len(events) == 1
        assert "coordinates" in events[0].message.lower()


class TestDownlinkMapper:
    """Test DownlinkMapper."""

    def test_activity_type(self):
        """Test activity type property."""
        mapper = DownlinkMapper()
        assert mapper.activity_type == "downlink"

    def test_map_downlink_activity(self, sim_config, timestamp):
        """Test mapping downlink activity to segments."""
        activity = Activity(
            activity_id="dl_001",
            activity_type="downlink",
            start_time=timestamp,
            end_time=timestamp + timedelta(minutes=10),
            parameters={
                "station_id": "SVALBARD",
                "duration_s": 600,
                "data_rate_mbps": 800,
                "band": "X",
            },
        )

        mapper = DownlinkMapper()
        segments = mapper.map(activity, sim_config)

        # Should have acquisition + main transmission segments
        assert len(segments) >= 1

        # Check transmission segment
        downlink_segments = [s for s in segments if s.segment_type == "downlink"]
        assert len(downlink_segments) == 1

        dl = downlink_segments[0]
        assert dl.data.transmission_rate_mbps == 800
        assert dl.parameters["band"] == "X"
        assert dl.parameters["station_id"] == "SVALBARD"

    def test_power_varies_by_band(self, sim_config, timestamp):
        """Test power consumption varies by band."""
        activity_x = Activity(
            activity_id="dl_x",
            activity_type="downlink",
            start_time=timestamp,
            end_time=timestamp + timedelta(minutes=10),
            parameters={"station_id": "TEST", "band": "X"},
        )

        activity_ka = Activity(
            activity_id="dl_ka",
            activity_type="downlink",
            start_time=timestamp,
            end_time=timestamp + timedelta(minutes=10),
            parameters={"station_id": "TEST", "band": "Ka"},
        )

        mapper = DownlinkMapper()
        segments_x = mapper.map(activity_x, sim_config)
        segments_ka = mapper.map(activity_ka, sim_config)

        dl_x = [s for s in segments_x if s.segment_type == "downlink"][0]
        dl_ka = [s for s in segments_ka if s.segment_type == "downlink"][0]

        # Ka band uses more power
        assert dl_ka.power.peak_power_w > dl_x.power.peak_power_w

    def test_validate_missing_station(self, sim_config, timestamp):
        """Test validation with missing station ID."""
        activity = Activity(
            activity_id="dl_002",
            activity_type="downlink",
            start_time=timestamp,
            end_time=timestamp + timedelta(minutes=10),
            parameters={},  # No station_id
        )

        mapper = DownlinkMapper()
        events = mapper.validate(activity, sim_config)

        assert len(events) == 1
        assert "station" in events[0].message.lower()


class TestThrustMapper:
    """Test ThrustMapper."""

    def test_activity_type(self):
        """Test activity type property."""
        mapper = ThrustMapper()
        assert mapper.activity_type == "orbit_lower"

    def test_map_orbit_lower_activity(self, sim_config, timestamp):
        """Test mapping orbit lowering activity to segments."""
        activity = Activity(
            activity_id="thrust_001",
            activity_type="orbit_lower",
            start_time=timestamp,
            end_time=timestamp + timedelta(minutes=30),
            parameters={
                "delta_altitude_km": -2.0,
                "thrust_duration_s": 1200,
            },
        )

        mapper = ThrustMapper()
        segments = mapper.map(activity, sim_config)

        # Should have thrust arc segments
        assert len(segments) >= 1

        thrust_segments = [s for s in segments if s.segment_type == "thrust"]
        assert len(thrust_segments) >= 1

        thrust = thrust_segments[0]
        assert thrust.thrust.thrust_n > 0
        assert thrust.thrust.isp_s == 1500.0
        assert thrust.power.peak_power_w > thrust.power.base_power_w

    def test_long_thrust_creates_multiple_arcs(self, sim_config, timestamp):
        """Test long thrust duration creates multiple arcs."""
        activity = Activity(
            activity_id="thrust_002",
            activity_type="orbit_lower",
            start_time=timestamp,
            end_time=timestamp + timedelta(hours=2),
            parameters={
                "delta_altitude_km": -5.0,
                "thrust_duration_s": 5400,  # 90 minutes > 30 min max
            },
        )

        mapper = ThrustMapper()
        segments = mapper.map(activity, sim_config)

        thrust_segments = [s for s in segments if s.segment_type == "thrust"]
        assert len(thrust_segments) > 1  # Should split into multiple arcs

        # Should also have coast segments between arcs
        coast_segments = [s for s in segments if s.segment_type == "coast"]
        assert len(coast_segments) >= 1

    def test_thrust_direction_for_lowering(self, sim_config, timestamp):
        """Test thrust direction is retrograde for lowering."""
        activity = Activity(
            activity_id="thrust_003",
            activity_type="orbit_lower",
            start_time=timestamp,
            end_time=timestamp + timedelta(minutes=10),
            parameters={"delta_altitude_km": -1.0, "thrust_duration_s": 300},
        )

        mapper = ThrustMapper()
        segments = mapper.map(activity, sim_config)

        thrust = [s for s in segments if s.segment_type == "thrust"][0]
        # Retrograde = negative x direction
        assert thrust.thrust.direction[0] < 0

    def test_validate_large_maneuver(self, sim_config, timestamp):
        """Test validation warning for large altitude change."""
        activity = Activity(
            activity_id="thrust_004",
            activity_type="orbit_lower",
            start_time=timestamp,
            end_time=timestamp + timedelta(hours=5),
            parameters={"delta_altitude_km": -100.0},  # Very large change
        )

        mapper = ThrustMapper()
        events = mapper.validate(activity, sim_config)

        assert len(events) == 1
        assert "large" in events[0].message.lower()


class TestStationKeepingMapper:
    """Test StationKeepingMapper."""

    def test_activity_type(self):
        """Test activity type property."""
        mapper = StationKeepingMapper()
        assert mapper.activity_type == "station_keeping"

    def test_map_station_keeping(self, sim_config, timestamp):
        """Test mapping station keeping activity."""
        activity = Activity(
            activity_id="sk_001",
            activity_type="station_keeping",
            start_time=timestamp,
            end_time=timestamp + timedelta(minutes=15),
            parameters={"mode": "drag_makeup"},
        )

        mapper = StationKeepingMapper()
        segments = mapper.map(activity, sim_config)

        assert len(segments) == 1
        segment = segments[0]

        assert segment.segment_type == "station_keeping"
        assert segment.thrust.thrust_n > 0
        assert segment.thrust.duty_cycle == 0.5


class TestMapperRegistry:
    """Test mapper registry functions."""

    def test_get_mapper_exists(self):
        """Test getting existing mapper."""
        mapper = get_mapper("idle")
        assert mapper is not None
        assert mapper.activity_type == "idle"

    def test_get_mapper_not_exists(self):
        """Test getting non-existent mapper."""
        mapper = get_mapper("unknown_type")
        assert mapper is None

    def test_register_custom_mapper(self, sim_config, timestamp):
        """Test registering a custom mapper."""

        class CustomMapper(ActivityMapper):
            @property
            def activity_type(self) -> str:
                return "custom"

            def map(self, activity, config):
                return [
                    SimulationSegmentSpec(
                        start_time=activity.start_time,
                        end_time=activity.end_time,
                        segment_type="custom",
                    )
                ]

        register_mapper(CustomMapper())

        mapper = get_mapper("custom")
        assert mapper is not None
        assert mapper.activity_type == "custom"


class TestMapActivity:
    """Test map_activity function."""

    def test_map_known_activity(self, sim_config, timestamp):
        """Test mapping known activity type."""
        activity = Activity(
            activity_id="test_001",
            activity_type="idle",
            start_time=timestamp,
            end_time=timestamp + timedelta(hours=1),
        )

        segments = map_activity(activity, sim_config)
        assert len(segments) >= 1
        assert segments[0].segment_type == "idle"

    def test_map_unknown_activity_defaults_to_idle(self, sim_config, timestamp):
        """Test unknown activity type defaults to idle behavior."""
        activity = Activity(
            activity_id="test_002",
            activity_type="unknown_activity",
            start_time=timestamp,
            end_time=timestamp + timedelta(hours=1),
        )

        segments = map_activity(activity, sim_config)
        assert len(segments) >= 1
        assert segments[0].segment_type == "idle"
