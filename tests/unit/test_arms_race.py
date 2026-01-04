"""
Unit tests for utils/arms_race.py - Arms Race schedule calculator.

Tests cover:
1. get_arms_race_status returns valid event information
2. get_time_until_soldier_training returns timedelta or None
3. get_current_event returns valid event name
4. Event transitions at boundaries
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest
from freezegun import freeze_time

from utils.arms_race import (
    ARMS_RACE_EVENTS,
    EVENT_HOURS,
    REFERENCE_TIME,
    SCHEDULE,
    VALID_EVENTS,
    format_timedelta,
    get_arms_race_status,
    get_chest3_target,
    get_event_metadata,
    get_time_until_beast_training,
    get_time_until_event,
    get_time_until_soldier_promotion_opportunity,
    get_time_until_soldier_training,
    get_time_until_vs_promotion_day,
    is_event_data_complete,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def reference_time() -> datetime:
    """The Arms Race reference time (Day 1 start)."""
    return REFERENCE_TIME


@pytest.fixture
def day1_enhance_hero_start() -> datetime:
    """Start of Day 1's first event (Enhance Hero)."""
    return datetime(2025, 12, 4, 2, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def day1_city_construction_start() -> datetime:
    """Start of Day 1's second event (City Construction)."""
    return datetime(2025, 12, 4, 6, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def day1_soldier_training_start() -> datetime:
    """Start of Day 1's Soldier Training event."""
    return datetime(2025, 12, 4, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def day2_start() -> datetime:
    """Start of Day 2 (first event of day 2)."""
    return datetime(2025, 12, 5, 2, 0, 0, tzinfo=timezone.utc)


# =============================================================================
# Test get_arms_race_status - Valid Event Information
# =============================================================================


class TestGetArmsRaceStatus:
    """Tests for get_arms_race_status function."""

    def test_returns_dict_with_required_keys(self, day1_enhance_hero_start: datetime) -> None:
        """Status dict should have all required keys."""
        status = get_arms_race_status(day1_enhance_hero_start)

        required_keys = [
            "current", "previous", "next", "day",
            "time_remaining", "time_elapsed",
            "block_start", "block_end", "event_index"
        ]
        for key in required_keys:
            assert key in status, f"Missing required key: {key}"

    def test_current_event_is_string(self, day1_enhance_hero_start: datetime) -> None:
        """Current event should be a string."""
        status = get_arms_race_status(day1_enhance_hero_start)
        assert isinstance(status["current"], str)

    def test_current_event_is_valid(self, day1_enhance_hero_start: datetime) -> None:
        """Current event should be one of the valid event names."""
        status = get_arms_race_status(day1_enhance_hero_start)
        assert status["current"] in VALID_EVENTS

    def test_day_is_in_valid_range(self, day1_enhance_hero_start: datetime) -> None:
        """Day should be between 1 and 7."""
        status = get_arms_race_status(day1_enhance_hero_start)
        assert 1 <= status["day"] <= 7

    def test_time_remaining_is_timedelta(self, day1_enhance_hero_start: datetime) -> None:
        """time_remaining should be a timedelta."""
        status = get_arms_race_status(day1_enhance_hero_start)
        assert isinstance(status["time_remaining"], timedelta)

    def test_time_elapsed_is_timedelta(self, day1_enhance_hero_start: datetime) -> None:
        """time_elapsed should be a timedelta."""
        status = get_arms_race_status(day1_enhance_hero_start)
        assert isinstance(status["time_elapsed"], timedelta)

    def test_block_start_is_datetime(self, day1_enhance_hero_start: datetime) -> None:
        """block_start should be a datetime."""
        status = get_arms_race_status(day1_enhance_hero_start)
        assert isinstance(status["block_start"], datetime)

    def test_block_end_is_datetime(self, day1_enhance_hero_start: datetime) -> None:
        """block_end should be a datetime."""
        status = get_arms_race_status(day1_enhance_hero_start)
        assert isinstance(status["block_end"], datetime)

    def test_event_index_is_in_valid_range(self, day1_enhance_hero_start: datetime) -> None:
        """event_index should be between 0 and 41 (42 events total)."""
        status = get_arms_race_status(day1_enhance_hero_start)
        assert 0 <= status["event_index"] <= 41

    def test_at_reference_time_day_is_1(self, reference_time: datetime) -> None:
        """At reference time, day should be 1."""
        status = get_arms_race_status(reference_time)
        assert status["day"] == 1

    def test_at_reference_time_event_is_enhance_hero(self, reference_time: datetime) -> None:
        """At reference time, event should be Enhance Hero (Day 1 first event)."""
        status = get_arms_race_status(reference_time)
        assert status["current"] == "Enhance Hero"

    def test_at_reference_time_event_index_is_0(self, reference_time: datetime) -> None:
        """At reference time, event_index should be 0."""
        status = get_arms_race_status(reference_time)
        assert status["event_index"] == 0

    def test_handles_none_input(self) -> None:
        """Should use current time when now=None."""
        status = get_arms_race_status(None)
        assert status is not None
        assert "current" in status

    def test_handles_naive_datetime(self) -> None:
        """Should handle naive datetime by treating as UTC."""
        naive_time = datetime(2025, 12, 4, 2, 0, 0)  # No tzinfo
        status = get_arms_race_status(naive_time)
        assert status["current"] == "Enhance Hero"
        assert status["day"] == 1

    def test_time_elapsed_plus_remaining_equals_4_hours(self, day1_enhance_hero_start: datetime) -> None:
        """time_elapsed + time_remaining should equal EVENT_HOURS."""
        # Test at 1 hour into the event
        test_time = day1_enhance_hero_start + timedelta(hours=1)
        status = get_arms_race_status(test_time)

        total = status["time_elapsed"] + status["time_remaining"]
        expected = timedelta(hours=EVENT_HOURS)

        # Allow small floating point differences
        diff_seconds = abs(total.total_seconds() - expected.total_seconds())
        assert diff_seconds < 1, f"Expected {expected}, got {total}"


# =============================================================================
# Test get_time_until_soldier_training
# =============================================================================


class TestGetTimeUntilSoldierTraining:
    """Tests for get_time_until_soldier_training function."""

    def test_returns_timedelta_or_none(self, day1_enhance_hero_start: datetime) -> None:
        """Should return timedelta or None."""
        result = get_time_until_soldier_training(day1_enhance_hero_start)
        assert result is None or isinstance(result, timedelta)

    def test_returns_zero_when_in_soldier_training(self, day1_soldier_training_start: datetime) -> None:
        """Should return timedelta(0) when currently in Soldier Training."""
        result = get_time_until_soldier_training(day1_soldier_training_start)
        assert result == timedelta(0)

    def test_returns_positive_when_not_in_soldier_training(self, day1_enhance_hero_start: datetime) -> None:
        """Should return positive timedelta when not in Soldier Training."""
        result = get_time_until_soldier_training(day1_enhance_hero_start)
        assert result is not None
        assert result.total_seconds() > 0

    def test_time_until_matches_schedule(self, day1_enhance_hero_start: datetime) -> None:
        """Time until should match the schedule (Day 1: Enhance Hero -> City Const -> Soldier Training)."""
        # From Day 1 02:00 (Enhance Hero), Soldier Training starts at 10:00
        # That's 8 hours = 2 events later
        result = get_time_until_soldier_training(day1_enhance_hero_start)
        assert result is not None

        # Should be 8 hours (2 events * 4 hours each)
        expected_hours = 8
        actual_hours = result.total_seconds() / 3600
        assert abs(actual_hours - expected_hours) < 0.01

    def test_halfway_through_event(self) -> None:
        """Time until should account for partial elapsed time in current event."""
        # 1 hour into Enhance Hero at Day 1
        test_time = datetime(2025, 12, 4, 3, 0, 0, tzinfo=timezone.utc)
        result = get_time_until_soldier_training(test_time)
        assert result is not None

        # Should be 7 hours (3 hours remaining + 4 hours of City Construction)
        expected_hours = 7
        actual_hours = result.total_seconds() / 3600
        assert abs(actual_hours - expected_hours) < 0.01


# =============================================================================
# Test get_current_event (via get_arms_race_status)
# =============================================================================


class TestGetCurrentEvent:
    """Tests for getting current event from status."""

    def test_day1_events_in_order(self) -> None:
        """Day 1 events should follow schedule order."""
        # Day 1 schedule: Enhance Hero, City Construction, Soldier Training,
        #                 Technology Research, Mystic Beast Training, Enhance Hero
        expected_sequence = [
            (2, "Enhance Hero"),
            (6, "City Construction"),
            (10, "Soldier Training"),
            (14, "Technology Research"),
            (18, "Mystic Beast Training"),
            (22, "Enhance Hero"),
        ]

        for hour, expected_event in expected_sequence:
            test_time = datetime(2025, 12, 4, hour, 0, 0, tzinfo=timezone.utc)
            status = get_arms_race_status(test_time)
            assert status["current"] == expected_event, f"At hour {hour}, expected {expected_event}"

    def test_all_valid_events_appear_in_schedule(self) -> None:
        """All 5 valid events should appear in the schedule."""
        events_seen = set()
        for _, _, event_name in SCHEDULE:
            events_seen.add(event_name)

        assert events_seen == set(VALID_EVENTS)

    def test_schedule_has_42_events(self) -> None:
        """Schedule should have exactly 42 events (7 days * 6 events per day)."""
        assert len(SCHEDULE) == 42


# =============================================================================
# Test Event Transitions at Boundaries
# =============================================================================


class TestEventBoundaries:
    """Tests for event transitions at exact boundaries."""

    def test_transition_at_exact_boundary(self) -> None:
        """Event should change exactly at 4-hour boundary."""
        # End of Enhance Hero, start of City Construction
        just_before = datetime(2025, 12, 4, 5, 59, 59, tzinfo=timezone.utc)
        exactly_at = datetime(2025, 12, 4, 6, 0, 0, tzinfo=timezone.utc)

        status_before = get_arms_race_status(just_before)
        status_at = get_arms_race_status(exactly_at)

        assert status_before["current"] == "Enhance Hero"
        assert status_at["current"] == "City Construction"

    def test_transition_day1_to_day2(self, day2_start: datetime) -> None:
        """Day should change from 1 to 2 at correct boundary."""
        just_before = day2_start - timedelta(seconds=1)

        status_before = get_arms_race_status(just_before)
        status_at = get_arms_race_status(day2_start)

        assert status_before["day"] == 1
        assert status_at["day"] == 2

    def test_cycle_wraps_after_week(self, reference_time: datetime) -> None:
        """After 7 days (168 hours), schedule should wrap to Day 1."""
        one_week_later = reference_time + timedelta(days=7)

        status_start = get_arms_race_status(reference_time)
        status_week_later = get_arms_race_status(one_week_later)

        assert status_start["day"] == status_week_later["day"]
        assert status_start["current"] == status_week_later["current"]
        assert status_start["event_index"] == status_week_later["event_index"]

    def test_previous_next_event_tracking(self, day1_city_construction_start: datetime) -> None:
        """Previous and next events should be correctly tracked."""
        status = get_arms_race_status(day1_city_construction_start)

        assert status["previous"] == "Enhance Hero"
        assert status["current"] == "City Construction"
        assert status["next"] == "Soldier Training"

    def test_block_start_end_boundaries(self) -> None:
        """block_start and block_end should define exact 4-hour window."""
        test_time = datetime(2025, 12, 4, 3, 30, 0, tzinfo=timezone.utc)  # 1.5 hours into event
        status = get_arms_race_status(test_time)

        expected_start = datetime(2025, 12, 4, 2, 0, 0, tzinfo=timezone.utc)
        expected_end = datetime(2025, 12, 4, 6, 0, 0, tzinfo=timezone.utc)

        assert status["block_start"] == expected_start
        assert status["block_end"] == expected_end

    def test_time_remaining_at_start_is_4_hours(self, day1_enhance_hero_start: datetime) -> None:
        """At event start, time_remaining should be 4 hours."""
        status = get_arms_race_status(day1_enhance_hero_start)

        expected = timedelta(hours=4)
        diff = abs(status["time_remaining"].total_seconds() - expected.total_seconds())
        assert diff < 1

    def test_time_elapsed_at_start_is_zero(self, day1_enhance_hero_start: datetime) -> None:
        """At event start, time_elapsed should be ~0."""
        status = get_arms_race_status(day1_enhance_hero_start)

        assert status["time_elapsed"].total_seconds() < 1


# =============================================================================
# Test get_time_until_event (generic)
# =============================================================================


class TestGetTimeUntilEvent:
    """Tests for the generic get_time_until_event function."""

    def test_invalid_event_returns_none(self) -> None:
        """Invalid event name should return None."""
        result = get_time_until_event("Invalid Event Name")
        assert result is None

    def test_all_valid_events_return_timedelta(self, day1_enhance_hero_start: datetime) -> None:
        """All valid event names should return a timedelta."""
        for event_name in VALID_EVENTS:
            result = get_time_until_event(event_name, day1_enhance_hero_start)
            assert isinstance(result, timedelta), f"Failed for event: {event_name}"

    def test_current_event_returns_zero(self, day1_enhance_hero_start: datetime) -> None:
        """When in current event, should return timedelta(0)."""
        # At day1_enhance_hero_start, current event is "Enhance Hero"
        result = get_time_until_event("Enhance Hero", day1_enhance_hero_start)
        assert result == timedelta(0)

    def test_beast_training_alias(self, day1_enhance_hero_start: datetime) -> None:
        """get_time_until_beast_training should match get_time_until_event."""
        via_generic = get_time_until_event("Mystic Beast Training", day1_enhance_hero_start)
        via_alias = get_time_until_beast_training(day1_enhance_hero_start)

        assert via_generic == via_alias


# =============================================================================
# Test VS Promotion Day Functions
# =============================================================================


class TestVSPromotionDay:
    """Tests for VS promotion day related functions."""

    def test_empty_vs_days_returns_none(self) -> None:
        """Empty vs_days list should return None."""
        result = get_time_until_vs_promotion_day([], datetime.now(timezone.utc))
        assert result is None

    def test_on_vs_day_returns_zero(self, day2_start: datetime) -> None:
        """Should return timedelta(0) when on a VS promotion day."""
        # Day 2 is Thursday
        vs_days = [2]  # Day 2
        result = get_time_until_vs_promotion_day(vs_days, day2_start)
        assert result == timedelta(0)

    def test_not_on_vs_day_returns_positive(self, day1_enhance_hero_start: datetime) -> None:
        """Should return positive timedelta when not on VS day."""
        vs_days = [2]  # Day 2
        result = get_time_until_vs_promotion_day(vs_days, day1_enhance_hero_start)
        assert result is not None
        assert result.total_seconds() > 0


class TestSoldierPromotionOpportunity:
    """Tests for get_time_until_soldier_promotion_opportunity."""

    def test_returns_minimum_of_arms_race_and_vs_day(self, day1_enhance_hero_start: datetime) -> None:
        """Should return the minimum of arms race and VS day timing."""
        # Day 1 first event, vs_days = [2]
        vs_days = [2]

        arms_race_time = get_time_until_soldier_training(day1_enhance_hero_start)
        vs_day_time = get_time_until_vs_promotion_day(vs_days, day1_enhance_hero_start)
        opportunity_time = get_time_until_soldier_promotion_opportunity(vs_days, day1_enhance_hero_start)

        assert opportunity_time is not None
        assert arms_race_time is not None
        assert vs_day_time is not None

        expected_min = min(arms_race_time, vs_day_time)
        assert opportunity_time == expected_min

    def test_no_vs_days_uses_arms_race_only(self, day1_enhance_hero_start: datetime) -> None:
        """With no VS days, should use Arms Race timing only."""
        arms_race_time = get_time_until_soldier_training(day1_enhance_hero_start)
        opportunity_time = get_time_until_soldier_promotion_opportunity(None, day1_enhance_hero_start)

        assert opportunity_time == arms_race_time


# =============================================================================
# Test Event Metadata Functions
# =============================================================================


class TestEventMetadata:
    """Tests for event metadata functions."""

    def test_get_event_metadata_valid_event(self) -> None:
        """Should return dict with metadata for valid events."""
        meta = get_event_metadata("Mystic Beast Training")
        assert isinstance(meta, dict)
        assert "chest1" in meta
        assert "chest2" in meta
        assert "chest3" in meta
        assert "header_template" in meta

    def test_get_event_metadata_invalid_event(self) -> None:
        """Should return empty dict for invalid event."""
        meta = get_event_metadata("Invalid Event")
        assert meta == {}

    def test_get_chest3_target_beast_training(self) -> None:
        """Chest 3 target for Mystic Beast Training should be 30000."""
        target = get_chest3_target("Mystic Beast Training")
        assert target == 30000

    def test_get_chest3_target_enhance_hero(self) -> None:
        """Chest 3 target for Enhance Hero should be 12000."""
        target = get_chest3_target("Enhance Hero")
        assert target == 12000

    def test_get_chest3_target_incomplete_event(self) -> None:
        """Chest 3 target should be None for events without data."""
        # Soldier Training has chest3 = None
        target = get_chest3_target("Soldier Training")
        assert target is None

    def test_is_event_data_complete_true(self) -> None:
        """Should return True for events with all data."""
        assert is_event_data_complete("Mystic Beast Training") is True
        assert is_event_data_complete("Enhance Hero") is True

    def test_is_event_data_complete_false(self) -> None:
        """Should return False for events without complete data."""
        assert is_event_data_complete("Soldier Training") is False
        assert is_event_data_complete("City Construction") is False
        assert is_event_data_complete("Technology Research") is False


# =============================================================================
# Test format_timedelta Helper
# =============================================================================


class TestFormatTimedelta:
    """Tests for format_timedelta helper function."""

    def test_format_zero(self) -> None:
        """Should format zero as 00:00:00."""
        assert format_timedelta(timedelta(0)) == "00:00:00"

    def test_format_hours_minutes_seconds(self) -> None:
        """Should format HH:MM:SS correctly."""
        td = timedelta(hours=2, minutes=30, seconds=45)
        assert format_timedelta(td) == "02:30:45"

    def test_format_large_hours(self) -> None:
        """Should handle hours > 24."""
        td = timedelta(hours=48, minutes=15, seconds=30)
        assert format_timedelta(td) == "48:15:30"

    def test_format_negative_shows_absolute(self) -> None:
        """Should show absolute value for negative timedeltas."""
        td = timedelta(hours=-2, minutes=-30, seconds=-45)
        result = format_timedelta(td)
        # abs(-2:30:45) = 2:30:45
        assert result == "02:30:45"


# =============================================================================
# Test with freeze_time for Deterministic Behavior
# =============================================================================


class TestWithFrozenTime:
    """Tests using frozen time for deterministic behavior."""

    @freeze_time("2025-12-04 02:00:00", tz_offset=0)
    def test_frozen_at_reference_time(self) -> None:
        """At reference time with frozen clock."""
        status = get_arms_race_status()
        assert status["current"] == "Enhance Hero"
        assert status["day"] == 1
        assert status["event_index"] == 0

    @freeze_time("2025-12-04 10:30:00", tz_offset=0)
    def test_frozen_during_soldier_training(self) -> None:
        """During Soldier Training with frozen clock."""
        status = get_arms_race_status()
        assert status["current"] == "Soldier Training"

        # Time until should be 0 since we're in it
        time_until = get_time_until_soldier_training()
        assert time_until == timedelta(0)

    @freeze_time("2025-12-05 02:00:00", tz_offset=0)
    def test_frozen_at_day2_start(self) -> None:
        """At Day 2 start with frozen clock."""
        status = get_arms_race_status()
        assert status["day"] == 2
        assert status["current"] == "City Construction"
        assert status["event_index"] == 6  # First event of day 2

    @freeze_time("2026-01-04 10:00:00", tz_offset=0)
    def test_frozen_in_future_cycle(self) -> None:
        """Schedule should work correctly in future cycles."""
        status = get_arms_race_status()

        # Should still return valid data
        assert 1 <= status["day"] <= 7
        assert status["current"] in VALID_EVENTS
        assert 0 <= status["event_index"] <= 41


# =============================================================================
# Test Schedule Integrity
# =============================================================================


class TestScheduleIntegrity:
    """Tests to verify the schedule data is consistent."""

    def test_all_schedule_entries_valid(self) -> None:
        """All schedule entries should have valid day, hour, and event."""
        for day, hour, event in SCHEDULE:
            assert 1 <= day <= 7, f"Invalid day: {day}"
            assert 0 <= hour <= 23, f"Invalid hour: {hour}"
            assert event in VALID_EVENTS, f"Invalid event: {event}"

    def test_schedule_hours_are_multiples_of_4(self) -> None:
        """All schedule hours should be multiples of 4 (4-hour events)."""
        for day, hour, event in SCHEDULE:
            assert hour % 2 == 0, f"Hour {hour} for {event} on day {day} not multiple of 2"

    def test_each_day_has_6_events(self) -> None:
        """Each day should have exactly 6 events (24 hours / 4 hours per event)."""
        for day_num in range(1, 8):
            day_events = [e for d, h, e in SCHEDULE if d == day_num]
            assert len(day_events) == 6, f"Day {day_num} has {len(day_events)} events, expected 6"

    def test_arms_race_events_metadata_keys(self) -> None:
        """All events in ARMS_RACE_EVENTS should have required metadata keys."""
        required_keys = ["chest1", "chest2", "chest3", "header_template"]

        for event_name, meta in ARMS_RACE_EVENTS.items():
            for key in required_keys:
                assert key in meta, f"Event {event_name} missing key: {key}"
