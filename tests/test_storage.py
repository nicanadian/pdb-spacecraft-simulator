"""Tests for SSR storage model."""

from datetime import datetime, timezone
from typing import List

import pytest

from sim.core.types import Event, EventType
from sim.models.storage import (
    DataPacket,
    DataPriority,
    SSRConfig,
    SSRModel,
    StorageTransaction,
)


class TestSSRConfig:
    """Test SSR configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SSRConfig()

        assert config.capacity_gb == 256.0
        assert config.max_write_rate_mbps == 2000.0
        assert config.max_read_rate_mbps == 2000.0
        assert config.reserved_gb == 10.0
        assert config.enable_priority_queue is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = SSRConfig(
            capacity_gb=512.0,
            reserved_gb=20.0,
            enable_priority_queue=False,
        )

        assert config.capacity_gb == 512.0
        assert config.reserved_gb == 20.0
        assert config.enable_priority_queue is False


class TestSSRModel:
    """Test SSR model operations."""

    @pytest.fixture
    def ssr_model(self):
        """Create SSR model for testing."""
        config = SSRConfig(capacity_gb=100.0, reserved_gb=10.0)
        return SSRModel(config)

    @pytest.fixture
    def timestamp(self):
        """Create timestamp for testing."""
        return datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    def test_initial_state(self, ssr_model):
        """Test initial state of SSR model."""
        assert ssr_model.current_level_gb == 0.0
        assert ssr_model.available_gb == 90.0  # 100 - 10 reserved
        assert ssr_model.fill_fraction == 0.0
        assert len(ssr_model.transactions) == 0

    def test_fill_basic(self, ssr_model, timestamp):
        """Test basic fill operation."""
        volume, events = ssr_model.fill(
            volume_gb=10.0,
            timestamp=timestamp,
            source="test_activity",
        )

        assert volume == 10.0
        assert ssr_model.current_level_gb == 10.0
        assert ssr_model.available_gb == 80.0
        assert len(events) == 0  # No violations
        assert len(ssr_model.transactions) == 1

    def test_fill_with_priority(self, ssr_model, timestamp):
        """Test fill with specific priority."""
        volume, events = ssr_model.fill(
            volume_gb=5.0,
            timestamp=timestamp,
            source="high_priority_data",
            priority=DataPriority.HIGH,
            data_type="science",
        )

        assert volume == 5.0
        summary = ssr_model.get_summary()
        assert summary["by_priority"].get("HIGH", 0) == 5.0
        assert summary["by_type"].get("science", 0) == 5.0

    def test_fill_overflow(self, ssr_model, timestamp):
        """Test fill operation that exceeds capacity."""
        # Try to fill more than usable capacity (90 GB)
        volume, events = ssr_model.fill(
            volume_gb=100.0,
            timestamp=timestamp,
            source="overflow_test",
        )

        # Should only fill to capacity
        assert volume == 90.0
        assert ssr_model.current_level_gb == 90.0
        assert ssr_model.available_gb == 0.0

        # Should generate violation event
        assert len(events) >= 1
        violation_events = [e for e in events if e.event_type == EventType.VIOLATION]
        assert len(violation_events) == 1

    def test_fill_high_level_warning(self, ssr_model, timestamp):
        """Test warning at high fill levels (>90% of total capacity)."""
        # The SSR model generates a warning when fill_fraction > 0.9
        # fill_fraction = current_level_gb / capacity_gb
        # With capacity 100 GB, we need > 90 GB fill to trigger warning

        # First fill 85 GB
        ssr_model.fill(85.0, timestamp, "initial_fill")

        # Now fill 6 more - this goes to 91 GB (91% of 100 GB capacity)
        # This should trigger a violation (overflow) since usable is only 90 GB
        # Let's use a config with no reserved space to test the warning
        config = SSRConfig(capacity_gb=100.0, reserved_gb=0.0)
        model = SSRModel(config)

        # Fill to 91% of capacity
        volume, events = model.fill(
            volume_gb=91.0,
            timestamp=timestamp,
            source="high_fill_test",
        )

        # Check for warning event (fill_fraction > 0.9)
        warning_events = [e for e in events if e.event_type == EventType.WARNING]
        assert len(warning_events) >= 1

    def test_drain_basic(self, ssr_model, timestamp):
        """Test basic drain operation."""
        # Fill first
        ssr_model.fill(20.0, timestamp, "source")

        # Drain
        volume, events = ssr_model.drain(
            volume_gb=10.0,
            timestamp=timestamp,
            source="downlink",
        )

        assert volume == 10.0
        assert ssr_model.current_level_gb == 10.0
        assert len(ssr_model.transactions) == 2

    def test_drain_more_than_available(self, ssr_model, timestamp):
        """Test drain that exceeds available data."""
        # Fill 10 GB
        ssr_model.fill(10.0, timestamp, "source")

        # Try to drain 20 GB
        volume, events = ssr_model.drain(
            volume_gb=20.0,
            timestamp=timestamp,
            source="downlink",
        )

        # Should only drain what's available
        assert volume == 10.0
        assert ssr_model.current_level_gb == 0.0

        # Should generate info event
        info_events = [e for e in events if e.event_type == EventType.INFO]
        assert len(info_events) == 1

    def test_drain_empty_storage(self, ssr_model, timestamp):
        """Test drain on empty storage."""
        volume, events = ssr_model.drain(
            volume_gb=10.0,
            timestamp=timestamp,
            source="downlink",
        )

        assert volume == 0.0
        assert ssr_model.current_level_gb == 0.0

    def test_drain_priority_order(self, ssr_model, timestamp):
        """Test that drain removes lowest priority data first."""
        # Fill with different priorities
        ssr_model.fill(10.0, timestamp, "low", priority=DataPriority.LOW)
        ssr_model.fill(10.0, timestamp, "high", priority=DataPriority.HIGH)
        ssr_model.fill(10.0, timestamp, "critical", priority=DataPriority.CRITICAL)

        # Drain 15 GB with priority order
        volume, events = ssr_model.drain(
            volume_gb=15.0,
            timestamp=timestamp,
            source="downlink",
            priority_order=True,
        )

        assert volume == 15.0

        # Check remaining data - should be mostly high priority
        summary = ssr_model.get_summary()
        # Low priority (10) should be mostly gone, high (10) partially gone
        assert summary["by_priority"].get("LOW", 0) == 0.0

    def test_priority_management_on_fill(self, ssr_model, timestamp):
        """Test priority-based eviction when storage is full."""
        # Fill storage with LOW priority data
        ssr_model.fill(90.0, timestamp, "low_data", priority=DataPriority.LOW)

        # Now try to add HIGH priority data - should evict LOW
        volume, events = ssr_model.fill(
            volume_gb=20.0,
            timestamp=timestamp,
            source="high_data",
            priority=DataPriority.HIGH,
        )

        # Should have added the high priority data by evicting low priority
        assert volume == 20.0

        # Check transactions for delete operations
        delete_txns = [t for t in ssr_model.transactions if t.transaction_type == "delete"]
        assert len(delete_txns) > 0

    def test_transaction_history(self, ssr_model, timestamp):
        """Test transaction logging."""
        ssr_model.fill(10.0, timestamp, "source1")
        ssr_model.fill(20.0, timestamp, "source2")
        ssr_model.drain(5.0, timestamp, "dest1")

        transactions = ssr_model.transactions
        assert len(transactions) == 3

        # Check fill transactions
        assert transactions[0].transaction_type == "fill"
        assert transactions[0].volume_gb == 10.0
        assert transactions[0].pre_level_gb == 0.0
        assert transactions[0].post_level_gb == 10.0
        assert transactions[0].success is True

        # Check drain transaction
        assert transactions[2].transaction_type == "drain"
        assert transactions[2].volume_gb == 5.0
        assert transactions[2].pre_level_gb == 30.0
        assert transactions[2].post_level_gb == 25.0

    def test_get_summary(self, ssr_model, timestamp):
        """Test summary generation."""
        ssr_model.fill(10.0, timestamp, "imaging", data_type="imaging")
        ssr_model.fill(5.0, timestamp, "telemetry", data_type="telemetry")

        summary = ssr_model.get_summary()

        assert summary["current_level_gb"] == 15.0
        assert summary["available_gb"] == 75.0
        assert summary["capacity_gb"] == 100.0
        assert summary["fill_fraction"] == 0.15
        assert summary["packet_count"] == 2
        assert summary["transaction_count"] == 2
        assert summary["by_type"]["imaging"] == 10.0
        assert summary["by_type"]["telemetry"] == 5.0

    def test_reset(self, ssr_model, timestamp):
        """Test storage reset."""
        ssr_model.fill(50.0, timestamp, "data")
        ssr_model.reset()

        assert ssr_model.current_level_gb == 0.0
        assert len(ssr_model.transactions) == 0


class TestDataPacket:
    """Test DataPacket dataclass."""

    def test_create_packet(self):
        """Test packet creation."""
        timestamp = datetime(2025, 1, 15, tzinfo=timezone.utc)
        packet = DataPacket(
            packet_id="test_001",
            timestamp=timestamp,
            size_gb=5.0,
            priority=DataPriority.HIGH,
            source_activity="imaging_01",
            data_type="science",
        )

        assert packet.packet_id == "test_001"
        assert packet.size_gb == 5.0
        assert packet.priority == DataPriority.HIGH
        assert packet.data_type == "science"

    def test_packet_defaults(self):
        """Test packet default values."""
        timestamp = datetime(2025, 1, 15, tzinfo=timezone.utc)
        packet = DataPacket(
            packet_id="test",
            timestamp=timestamp,
            size_gb=1.0,
        )

        assert packet.priority == DataPriority.MEDIUM
        assert packet.data_type == "imaging"
        assert packet.expiry is None


class TestDataPriority:
    """Test DataPriority enum."""

    def test_priority_ordering(self):
        """Test priority ordering (lower value = higher priority)."""
        assert DataPriority.CRITICAL.value < DataPriority.HIGH.value
        assert DataPriority.HIGH.value < DataPriority.MEDIUM.value
        assert DataPriority.MEDIUM.value < DataPriority.LOW.value
        assert DataPriority.LOW.value < DataPriority.HOUSEKEEPING.value


class TestStorageTransaction:
    """Test StorageTransaction dataclass."""

    def test_create_transaction(self):
        """Test transaction creation."""
        timestamp = datetime(2025, 1, 15, tzinfo=timezone.utc)
        txn = StorageTransaction(
            timestamp=timestamp,
            transaction_type="fill",
            volume_gb=10.0,
            source="imaging_01",
            pre_level_gb=5.0,
            post_level_gb=15.0,
            success=True,
            message="",
        )

        assert txn.transaction_type == "fill"
        assert txn.volume_gb == 10.0
        assert txn.pre_level_gb == 5.0
        assert txn.post_level_gb == 15.0
        assert txn.success is True

    def test_transaction_defaults(self):
        """Test transaction default values."""
        timestamp = datetime(2025, 1, 15, tzinfo=timezone.utc)
        txn = StorageTransaction(
            timestamp=timestamp,
            transaction_type="drain",
            volume_gb=5.0,
            source="downlink",
            pre_level_gb=20.0,
            post_level_gb=15.0,
        )

        assert txn.success is True
        assert txn.message == ""
