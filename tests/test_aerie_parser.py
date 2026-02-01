"""Tests for Aerie plan parser."""

import pytest
from datetime import datetime, timedelta, timezone

from sim.io.aerie_parser import (
    parse_iso_duration,
    resolve_activity_times,
    parse_aerie_plan,
    detect_plan_format,
    load_plan_file,
    DEFAULT_DURATIONS,
)
from sim.core.types import PlanInput, Activity


class TestParseIsoDuration:
    """Tests for ISO 8601 duration parsing."""

    def test_parse_hours(self):
        """Parse hours only."""
        assert parse_iso_duration("PT1H") == timedelta(hours=1)
        assert parse_iso_duration("PT2H") == timedelta(hours=2)
        assert parse_iso_duration("PT12H") == timedelta(hours=12)

    def test_parse_minutes(self):
        """Parse minutes only."""
        assert parse_iso_duration("PT30M") == timedelta(minutes=30)
        assert parse_iso_duration("PT45M") == timedelta(minutes=45)
        assert parse_iso_duration("PT5M") == timedelta(minutes=5)

    def test_parse_seconds(self):
        """Parse seconds only."""
        assert parse_iso_duration("PT30S") == timedelta(seconds=30)
        assert parse_iso_duration("PT90S") == timedelta(seconds=90)
        assert parse_iso_duration("PT1.5S") == timedelta(seconds=1.5)

    def test_parse_days(self):
        """Parse days only."""
        assert parse_iso_duration("P1D") == timedelta(days=1)
        assert parse_iso_duration("P7D") == timedelta(days=7)

    def test_parse_combined(self):
        """Parse combined duration components."""
        assert parse_iso_duration("PT1H30M") == timedelta(hours=1, minutes=30)
        assert parse_iso_duration("PT1H30M45S") == timedelta(hours=1, minutes=30, seconds=45)
        assert parse_iso_duration("P1DT2H") == timedelta(days=1, hours=2)
        assert parse_iso_duration("P1DT2H30M45S") == timedelta(days=1, hours=2, minutes=30, seconds=45)

    def test_parse_zero(self):
        """Parse zero durations."""
        assert parse_iso_duration("PT0S") == timedelta(0)
        assert parse_iso_duration("PT0M") == timedelta(0)
        assert parse_iso_duration("PT0H") == timedelta(0)

    def test_invalid_format_raises(self):
        """Invalid formats raise ValueError."""
        with pytest.raises(ValueError):
            parse_iso_duration("")
        with pytest.raises(ValueError):
            parse_iso_duration("1H")  # Missing P
        with pytest.raises(ValueError):
            parse_iso_duration("P1H")  # Missing T before time
        with pytest.raises(ValueError):
            parse_iso_duration("invalid")


class TestResolveActivityTimes:
    """Tests for anchor chain resolution."""

    def test_no_anchors(self):
        """Activities without anchors use plan start + offset."""
        plan_start = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        activities = [
            {"id": 1, "type": "test", "start_offset": "PT1H", "arguments": {"duration": "PT30M"}},
            {"id": 2, "type": "test", "start_offset": "PT3H", "arguments": {"duration": "PT30M"}},
        ]

        result = resolve_activity_times(activities, plan_start)

        assert result[0]["resolved_start"] == plan_start + timedelta(hours=1)
        assert result[0]["resolved_end"] == plan_start + timedelta(hours=1, minutes=30)
        assert result[1]["resolved_start"] == plan_start + timedelta(hours=3)

    def test_anchor_to_start(self):
        """Activity anchored to start of another activity."""
        plan_start = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        activities = [
            {"id": 1, "type": "test", "start_offset": "PT1H", "arguments": {"duration": "PT30M"}},
            {
                "id": 2,
                "type": "test",
                "anchor_id": 1,
                "anchored_to_start": True,
                "start_offset": "PT15M",
                "arguments": {"duration": "PT30M"},
            },
        ]

        result = resolve_activity_times(activities, plan_start)

        # Activity 2 starts 15 minutes after activity 1 starts
        expected_start = plan_start + timedelta(hours=1) + timedelta(minutes=15)
        assert result[1]["resolved_start"] == expected_start

    def test_anchor_to_end(self):
        """Activity anchored to end of another activity."""
        plan_start = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        activities = [
            {"id": 1, "type": "test", "start_offset": "PT1H", "arguments": {"duration": "PT30M"}},
            {
                "id": 2,
                "type": "test",
                "anchor_id": 1,
                "anchored_to_start": False,
                "start_offset": "PT15M",
                "arguments": {"duration": "PT30M"},
            },
        ]

        result = resolve_activity_times(activities, plan_start)

        # Activity 2 starts 15 minutes after activity 1 ends (1h + 30m + 15m)
        expected_start = plan_start + timedelta(hours=1, minutes=45)
        assert result[1]["resolved_start"] == expected_start

    def test_anchor_chain(self):
        """Resolve chain of anchored activities."""
        plan_start = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        activities = [
            {"id": 1, "type": "test", "start_offset": "PT0S", "arguments": {"duration": "PT30M"}},
            {
                "id": 2,
                "type": "test",
                "anchor_id": 1,
                "anchored_to_start": False,
                "start_offset": "PT0S",
                "arguments": {"duration": "PT30M"},
            },
            {
                "id": 3,
                "type": "test",
                "anchor_id": 2,
                "anchored_to_start": False,
                "start_offset": "PT0S",
                "arguments": {"duration": "PT30M"},
            },
        ]

        result = resolve_activity_times(activities, plan_start)

        assert result[0]["resolved_start"] == plan_start
        assert result[1]["resolved_start"] == plan_start + timedelta(minutes=30)
        assert result[2]["resolved_start"] == plan_start + timedelta(hours=1)

    def test_default_duration(self):
        """Uses default duration when not specified."""
        plan_start = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        activities = [
            {"id": 1, "type": "eo_collect", "start_offset": "PT0S"},  # No duration arg
        ]

        result = resolve_activity_times(activities, plan_start)

        expected_end = plan_start + DEFAULT_DURATIONS["eo_collect"]
        assert result[0]["resolved_end"] == expected_end


class TestParseAeriePlan:
    """Tests for full Aerie plan parsing."""

    def test_parse_simple_plan(self):
        """Parse a simple Aerie plan."""
        data = {
            "plan_id": 123,
            "start_time": "2025-01-15T00:00:00Z",
            "activities": [
                {
                    "id": 1,
                    "type": "eo_collect",
                    "start_offset": "PT1H",
                    "arguments": {
                        "duration": "PT15M",
                        "target_lat_deg": 40.7,
                    },
                }
            ],
        }

        result = parse_aerie_plan(data)

        assert isinstance(result, PlanInput)
        assert result.plan_id == "123"
        assert len(result.activities) == 1

        act = result.activities[0]
        assert act.activity_id == "1"
        assert act.activity_type == "eo_collect"
        assert act.start_time == datetime(2025, 1, 15, 1, 0, 0, tzinfo=timezone.utc)
        assert act.end_time == datetime(2025, 1, 15, 1, 15, 0, tzinfo=timezone.utc)
        assert act.parameters["target_lat_deg"] == 40.7
        assert "duration" not in act.parameters  # Duration removed from params

    def test_parse_with_metadata(self):
        """Parse plan with Aerie metadata and tags."""
        data = {
            "plan_id": 123,
            "start_time": "2025-01-15T00:00:00Z",
            "activities": [
                {
                    "id": 1,
                    "type": "eo_collect",
                    "name": "Test Activity",
                    "start_offset": "PT1H",
                    "arguments": {"duration": "PT15M"},
                    "metadata": {"customer": "NASA"},
                    "tags": ["imaging", "priority-1"],
                }
            ],
        }

        result = parse_aerie_plan(data)

        act = result.activities[0]
        assert act.parameters["_aerie_name"] == "Test Activity"
        assert act.parameters["_aerie_metadata"] == {"customer": "NASA"}
        assert act.parameters["_aerie_tags"] == ["imaging", "priority-1"]

    def test_parse_with_override_start(self):
        """Override plan start time."""
        data = {
            "plan_id": 123,
            "start_time": "2025-01-15T00:00:00Z",
            "activities": [
                {
                    "id": 1,
                    "type": "eo_collect",
                    "start_offset": "PT1H",
                    "arguments": {"duration": "PT15M"},
                }
            ],
        }

        override_start = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = parse_aerie_plan(data, plan_start=override_start)

        assert result.activities[0].start_time == override_start + timedelta(hours=1)

    def test_missing_start_time_raises(self):
        """Raise error when start_time missing and not provided."""
        data = {
            "plan_id": 123,
            "activities": [
                {"id": 1, "type": "test", "start_offset": "PT0S", "arguments": {}},
            ],
        }

        with pytest.raises(ValueError, match="start_time not found"):
            parse_aerie_plan(data)

    def test_empty_activities_raises(self):
        """Raise error for empty activities list."""
        data = {
            "plan_id": 123,
            "start_time": "2025-01-15T00:00:00Z",
            "activities": [],
        }

        with pytest.raises(ValueError, match="No activities found"):
            parse_aerie_plan(data)


class TestDetectPlanFormat:
    """Tests for plan format detection."""

    def test_detect_aerie_format(self):
        """Detect Aerie format from start_offset."""
        data = {
            "activities": [
                {"id": 1, "type": "test", "start_offset": "PT1H", "arguments": {}},
            ]
        }
        assert detect_plan_format(data) == "aerie"

    def test_detect_aerie_format_by_structure(self):
        """Detect Aerie format from id/type/arguments structure."""
        data = {
            "activities": [
                {"id": 1, "type": "test", "arguments": {"foo": "bar"}},
            ]
        }
        assert detect_plan_format(data) == "aerie"

    def test_detect_normalized_format(self):
        """Detect normalized format from start_time/activity_id."""
        data = {
            "activities": [
                {
                    "activity_id": "1",
                    "activity_type": "test",
                    "start_time": "2025-01-15T00:00:00Z",
                    "end_time": "2025-01-15T01:00:00Z",
                },
            ]
        }
        assert detect_plan_format(data) == "normalized"

    def test_detect_empty_plan(self):
        """Empty plan defaults to normalized."""
        assert detect_plan_format({"activities": []}) == "normalized"
        assert detect_plan_format({}) == "normalized"


class TestLoadPlanFile:
    """Tests for loading plan files."""

    def test_load_aerie_export(self, tmp_path):
        """Load Aerie export file."""
        import json

        plan_data = {
            "plan_id": 123,
            "start_time": "2025-01-15T00:00:00Z",
            "activities": [
                {
                    "id": 1,
                    "type": "eo_collect",
                    "start_offset": "PT1H",
                    "arguments": {"duration": "PT15M"},
                }
            ],
        }

        plan_file = tmp_path / "test_plan.json"
        plan_file.write_text(json.dumps(plan_data))

        result = load_plan_file(str(plan_file))

        assert isinstance(result, PlanInput)
        assert result.activities[0].activity_type == "eo_collect"

    def test_load_normalized_plan(self, tmp_path):
        """Load normalized plan file."""
        import json

        plan_data = {
            "spacecraft_id": "SC001",
            "plan_id": "test_plan",
            "activities": [
                {
                    "activity_id": "1",
                    "activity_type": "eo_collect",
                    "start_time": "2025-01-15T01:00:00+00:00",
                    "end_time": "2025-01-15T01:15:00+00:00",
                    "parameters": {},
                }
            ],
        }

        plan_file = tmp_path / "test_plan.json"
        plan_file.write_text(json.dumps(plan_data))

        result = load_plan_file(str(plan_file))

        assert isinstance(result, PlanInput)
        assert result.spacecraft_id == "SC001"
        assert result.activities[0].activity_type == "eo_collect"

    def test_load_with_format_hint(self, tmp_path):
        """Load with explicit format hint."""
        import json

        plan_data = {
            "plan_id": 123,
            "start_time": "2025-01-15T00:00:00Z",
            "activities": [
                {
                    "id": 1,
                    "type": "eo_collect",
                    "start_offset": "PT1H",
                    "arguments": {"duration": "PT15M"},
                }
            ],
        }

        plan_file = tmp_path / "test_plan.json"
        plan_file.write_text(json.dumps(plan_data))

        result = load_plan_file(str(plan_file), format_hint="aerie")

        assert isinstance(result, PlanInput)


class TestRoundTrip:
    """Tests for round-trip consistency."""

    def test_aerie_to_normalized_timing(self):
        """Verify timing consistency in Aerie to normalized conversion."""
        data = {
            "plan_id": 123,
            "start_time": "2025-01-15T00:00:00Z",
            "activities": [
                {
                    "id": 1,
                    "type": "eo_collect",
                    "start_offset": "PT1H",
                    "arguments": {"duration": "PT15M", "target_lat_deg": 40.7},
                },
                {
                    "id": 2,
                    "type": "downlink",
                    "anchor_id": 1,
                    "anchored_to_start": False,
                    "start_offset": "PT30M",
                    "arguments": {"duration": "PT15M", "station_id": "svalbard"},
                },
            ],
        }

        result = parse_aerie_plan(data)

        # Activity 1: starts at 01:00, ends at 01:15
        assert result.activities[0].start_time.hour == 1
        assert result.activities[0].start_time.minute == 0
        assert result.activities[0].end_time.hour == 1
        assert result.activities[0].end_time.minute == 15

        # Activity 2: starts at 01:45 (01:15 + 30min), ends at 02:00
        assert result.activities[1].start_time.hour == 1
        assert result.activities[1].start_time.minute == 45
        assert result.activities[1].end_time.hour == 2
        assert result.activities[1].end_time.minute == 0
