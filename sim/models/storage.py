"""
Solid State Recorder (SSR) storage model.

Models onboard data storage including:
- Fill/drain tracking from imaging and downlink activities
- Storage capacity limits and violations
- Data aging and prioritization
- Transaction logging for validation
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sim.core.types import Event, EventType


logger = logging.getLogger(__name__)


class DataPriority(Enum):
    """Priority levels for stored data."""

    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    HOUSEKEEPING = 5


@dataclass
class DataPacket:
    """A packet of data in the SSR."""

    packet_id: str
    timestamp: datetime
    size_gb: float
    priority: DataPriority = DataPriority.MEDIUM
    source_activity: Optional[str] = None
    data_type: str = "imaging"  # imaging, telemetry, science
    expiry: Optional[datetime] = None  # Optional data expiry


@dataclass
class StorageTransaction:
    """Record of a storage operation."""

    timestamp: datetime
    transaction_type: str  # "fill", "drain", "delete"
    volume_gb: float
    source: str  # Activity or system that caused the transaction
    pre_level_gb: float
    post_level_gb: float
    success: bool = True
    message: str = ""


@dataclass
class SSRConfig:
    """Configuration for SSR model."""

    capacity_gb: float = 256.0
    max_write_rate_mbps: float = 2000.0  # Internal bus speed
    max_read_rate_mbps: float = 2000.0
    reserved_gb: float = 10.0  # Reserved for housekeeping
    enable_priority_queue: bool = True


class SSRModel:
    """
    Solid State Recorder model.

    Tracks storage fill level with transaction history,
    enforces capacity limits, and supports prioritized data management.
    """

    def __init__(self, config: Optional[SSRConfig] = None):
        self.config = config or SSRConfig()
        self._current_level_gb: float = 0.0
        self._packets: List[DataPacket] = []
        self._transactions: List[StorageTransaction] = []
        self._events: List[Event] = []

    @property
    def current_level_gb(self) -> float:
        """Current storage fill level in GB."""
        return self._current_level_gb

    @property
    def available_gb(self) -> float:
        """Available storage capacity in GB."""
        usable = self.config.capacity_gb - self.config.reserved_gb
        return max(0.0, usable - self._current_level_gb)

    @property
    def fill_fraction(self) -> float:
        """Storage fill level as fraction [0, 1]."""
        return self._current_level_gb / self.config.capacity_gb

    @property
    def transactions(self) -> List[StorageTransaction]:
        """Get transaction history."""
        return self._transactions.copy()

    def fill(
        self,
        volume_gb: float,
        timestamp: datetime,
        source: str,
        priority: DataPriority = DataPriority.MEDIUM,
        data_type: str = "imaging",
    ) -> tuple[float, List[Event]]:
        """
        Add data to storage.

        Args:
            volume_gb: Amount of data to add
            timestamp: Time of operation
            source: Source activity ID
            priority: Data priority level
            data_type: Type of data

        Returns:
            Tuple of (actual_volume_added, events)
        """
        events = []
        pre_level = self._current_level_gb

        # Check capacity
        usable_capacity = self.config.capacity_gb - self.config.reserved_gb
        space_available = usable_capacity - self._current_level_gb

        if volume_gb > space_available:
            if self.config.enable_priority_queue:
                # Try to make room by deleting lower priority data
                freed = self._free_space_by_priority(
                    needed_gb=volume_gb - space_available,
                    min_priority=priority,
                    timestamp=timestamp,
                )
                space_available += freed

            actual_volume = min(volume_gb, space_available)

            if actual_volume < volume_gb:
                events.append(Event(
                    timestamp=timestamp,
                    event_type=EventType.VIOLATION,
                    category="storage",
                    message=f"Storage overflow: requested {volume_gb:.2f} GB, only {actual_volume:.2f} GB available",
                    details={
                        "requested_gb": volume_gb,
                        "available_gb": space_available,
                        "actual_gb": actual_volume,
                        "source": source,
                    },
                ))
        else:
            actual_volume = volume_gb

        # Update level
        self._current_level_gb += actual_volume

        # Create packet record
        packet = DataPacket(
            packet_id=f"{source}_{timestamp.timestamp()}",
            timestamp=timestamp,
            size_gb=actual_volume,
            priority=priority,
            source_activity=source,
            data_type=data_type,
        )
        self._packets.append(packet)

        # Log transaction
        self._transactions.append(StorageTransaction(
            timestamp=timestamp,
            transaction_type="fill",
            volume_gb=actual_volume,
            source=source,
            pre_level_gb=pre_level,
            post_level_gb=self._current_level_gb,
            success=actual_volume == volume_gb,
            message="" if actual_volume == volume_gb else "Partial fill due to capacity limit",
        ))

        # Warning at high fill levels
        if self.fill_fraction > 0.9:
            events.append(Event(
                timestamp=timestamp,
                event_type=EventType.WARNING,
                category="storage",
                message=f"Storage at {self.fill_fraction:.0%} capacity",
                details={"level_gb": self._current_level_gb},
            ))

        return actual_volume, events

    def drain(
        self,
        volume_gb: float,
        timestamp: datetime,
        source: str,
        priority_order: bool = True,
    ) -> tuple[float, List[Event]]:
        """
        Remove data from storage (e.g., downlink).

        Args:
            volume_gb: Amount of data to remove
            timestamp: Time of operation
            source: Destination/activity ID
            priority_order: If True, drain lowest priority first

        Returns:
            Tuple of (actual_volume_removed, events)
        """
        events = []
        pre_level = self._current_level_gb

        # Can only drain what we have
        actual_volume = min(volume_gb, self._current_level_gb)

        if actual_volume < volume_gb:
            events.append(Event(
                timestamp=timestamp,
                event_type=EventType.INFO,
                category="storage",
                message=f"Drain limited: requested {volume_gb:.2f} GB, only {actual_volume:.2f} GB available",
                details={
                    "requested_gb": volume_gb,
                    "available_gb": self._current_level_gb,
                    "actual_gb": actual_volume,
                },
            ))

        # Update level
        self._current_level_gb -= actual_volume

        # Remove packets (FIFO or priority order)
        self._remove_packets(actual_volume, priority_order, timestamp)

        # Log transaction
        self._transactions.append(StorageTransaction(
            timestamp=timestamp,
            transaction_type="drain",
            volume_gb=actual_volume,
            source=source,
            pre_level_gb=pre_level,
            post_level_gb=self._current_level_gb,
            success=True,
        ))

        return actual_volume, events

    def _remove_packets(
        self,
        volume_gb: float,
        priority_order: bool,
        timestamp: datetime,
    ) -> None:
        """Remove packets totaling the specified volume."""
        if not self._packets:
            return

        if priority_order:
            # Sort by priority (highest number = lowest priority first)
            self._packets.sort(key=lambda p: -p.priority.value)

        remaining = volume_gb
        packets_to_remove = []

        for packet in self._packets:
            if remaining <= 0:
                break
            if packet.size_gb <= remaining:
                remaining -= packet.size_gb
                packets_to_remove.append(packet)
            else:
                # Partial packet removal
                packet.size_gb -= remaining
                remaining = 0

        for packet in packets_to_remove:
            self._packets.remove(packet)

    def _free_space_by_priority(
        self,
        needed_gb: float,
        min_priority: DataPriority,
        timestamp: datetime,
    ) -> float:
        """Free space by deleting lower priority data."""
        freed = 0.0

        # Find packets with lower priority (higher enum value)
        deletable = [
            p for p in self._packets
            if p.priority.value > min_priority.value
        ]

        # Sort by priority (lowest first) then by age (oldest first)
        deletable.sort(key=lambda p: (p.priority.value, p.timestamp))

        for packet in deletable:
            if freed >= needed_gb:
                break

            freed += packet.size_gb
            self._current_level_gb -= packet.size_gb
            self._packets.remove(packet)

            self._transactions.append(StorageTransaction(
                timestamp=timestamp,
                transaction_type="delete",
                volume_gb=packet.size_gb,
                source=f"priority_management:{packet.packet_id}",
                pre_level_gb=self._current_level_gb + packet.size_gb,
                post_level_gb=self._current_level_gb,
                message=f"Deleted to make room for priority {min_priority.name}",
            ))

        return freed

    def get_summary(self) -> Dict[str, Any]:
        """Get storage summary."""
        return {
            "current_level_gb": self._current_level_gb,
            "available_gb": self.available_gb,
            "capacity_gb": self.config.capacity_gb,
            "fill_fraction": self.fill_fraction,
            "packet_count": len(self._packets),
            "transaction_count": len(self._transactions),
            "by_type": self._summarize_by_type(),
            "by_priority": self._summarize_by_priority(),
        }

    def _summarize_by_type(self) -> Dict[str, float]:
        """Summarize storage by data type."""
        by_type: Dict[str, float] = {}
        for packet in self._packets:
            by_type[packet.data_type] = by_type.get(packet.data_type, 0) + packet.size_gb
        return by_type

    def _summarize_by_priority(self) -> Dict[str, float]:
        """Summarize storage by priority."""
        by_priority: Dict[str, float] = {}
        for packet in self._packets:
            by_priority[packet.priority.name] = by_priority.get(packet.priority.name, 0) + packet.size_gb
        return by_priority

    def reset(self) -> None:
        """Reset storage to empty state."""
        self._current_level_gb = 0.0
        self._packets.clear()
        self._transactions.clear()
        self._events.clear()
