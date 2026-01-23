"""Tests for EO imaging model."""

from datetime import datetime, timezone

import numpy as np
import pytest

from sim.models.imaging import (
    EOSensorConfig,
    FrameSensor,
    ImagingAccessModel,
)


class TestEOSensorConfig:
    """Test EO sensor configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = EOSensorConfig()

        assert config.focal_length_mm == 1000.0
        assert config.pixel_size_um == 10.0
        assert config.detector_rows == 4096
        assert config.detector_cols == 4096


class TestFrameSensor:
    """Test frame sensor calculations."""

    @pytest.fixture
    def sensor(self):
        """Create sensor for testing."""
        config = EOSensorConfig(
            focal_length_mm=1000.0,
            pixel_size_um=10.0,
            detector_rows=4096,
            detector_cols=4096,
            bits_per_pixel=12,
            compression_ratio=4.0,
        )
        return FrameSensor(config)

    def test_compute_gsd(self, sensor):
        """Test GSD calculation at 500 km."""
        gsd = sensor.compute_gsd(500.0)

        # GSD = (pixel_size * altitude) / focal_length
        # = (10e-6 m * 500e3 m) / 1.0 m = 5.0 m
        assert abs(gsd - 5.0) < 0.01

    def test_compute_gsd_lower_altitude(self, sensor):
        """Lower altitude should give better GSD."""
        gsd_500 = sensor.compute_gsd(500.0)
        gsd_400 = sensor.compute_gsd(400.0)

        assert gsd_400 < gsd_500

    def test_compute_swath(self, sensor):
        """Test swath width calculation."""
        swath = sensor.compute_swath(500.0)

        # Swath = GSD * detector_cols = 5.0 m * 4096 = 20.48 km
        assert abs(swath - 20.48) < 0.1

    def test_compute_frame_footprint(self, sensor):
        """Test frame footprint calculation."""
        along, cross = sensor.compute_frame_footprint(500.0)

        # Square detector, so footprint should be equal
        assert abs(along - cross) < 0.01
        assert abs(along - 20.48) < 0.1

    def test_compute_data_volume(self, sensor):
        """Test data volume calculation."""
        # Single frame
        data_gb = sensor.compute_data_volume(1)

        # 4096 * 4096 * 12 bits / 4 (compression) / 8 / 1e9
        expected = (4096 * 4096 * 12 / 4) / (8 * 1e9)
        assert abs(data_gb - expected) < 1e-6

    def test_compute_frame_data_mb(self, sensor):
        """Test single frame data size."""
        data_mb = sensor.compute_frame_data_mb()

        # 4096*4096*12 bits / 4 (compression) / 8 / 1e6 = ~6.3 MB
        assert 5 < data_mb < 8

    def test_compute_off_nadir_gsd(self, sensor):
        """Test off-nadir GSD degradation."""
        nadir_gsd = sensor.compute_gsd(500.0)
        off_nadir_gsd = sensor.compute_off_nadir_gsd(500.0, 30.0)

        # GSD should be worse off-nadir
        assert off_nadir_gsd > nadir_gsd

        # At 30 deg, should be ~15% worse (1/cos(30))
        expected_factor = 1 / np.cos(np.radians(30))
        assert abs(off_nadir_gsd / nadir_gsd - expected_factor) < 0.01


class TestImagingAccessModel:
    """Test imaging access model."""

    @pytest.fixture
    def access_model(self):
        """Create access model for testing."""
        return ImagingAccessModel(
            max_cross_track_deg=30.0,
            max_along_track_deg=5.0,
        )

    def test_is_valid_collect_nadir(self, access_model):
        """Test nadir pointing is valid."""
        assert access_model.is_valid_collect(0.0, 0.0)

    def test_is_valid_collect_cross_track(self, access_model):
        """Test cross-track within limits."""
        assert access_model.is_valid_collect(25.0, 0.0)
        assert access_model.is_valid_collect(-25.0, 0.0)

    def test_is_invalid_collect_cross_track(self, access_model):
        """Test cross-track beyond limits."""
        assert not access_model.is_valid_collect(35.0, 0.0)
        assert not access_model.is_valid_collect(-35.0, 0.0)

    def test_is_invalid_collect_along_track(self, access_model):
        """Test along-track beyond limits."""
        assert not access_model.is_valid_collect(0.0, 10.0)
        assert not access_model.is_valid_collect(0.0, -10.0)

    def test_decompose_off_nadir(self, access_model):
        """Test off-nadir angle decomposition."""
        # Spacecraft at (6878, 0, 0) km, moving in +y
        # Nadir points to -x
        sc_pos = np.array([6878.0, 0.0, 0.0])
        sc_vel = np.array([0.0, 7.6, 0.0])

        # Target directly below spacecraft
        target = np.array([6378.0, 0.0, 0.0])

        cross, along = access_model.decompose_off_nadir(sc_pos, sc_vel, target)

        # Should be near nadir
        assert abs(cross) < 5.0
        assert abs(along) < 5.0
