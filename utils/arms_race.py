"""
Arms Race schedule calculator.

The Arms Race follows a complex 7-day cycle with 6 events per day (every 4 hours).
Day 1 always starts on Wednesday at 02:00 UTC (Tuesday 6PM PT).

Schedule pattern (42 total events over 7 days):
- Each day has 6 events at: 02:00, 06:00, 10:00, 14:00, 18:00, 22:00 UTC
- Pattern shifts by one activity each day
- Day 5 has a special case: Soldier Training appears twice (10:00 slot)

Activity types:
1. City Construction
2. Soldier Training
3. Technology Research (Tech Research)
4. Mystic Beast Training (Mystic Beast)
5. Enhance Hero
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any

# Full 7-day schedule (42 events)
# Each entry: (day, hour_utc, activity_name)
SCHEDULE = [
    # Day 1 (Wednesday)
    (1, 2, "Enhance Hero"),
    (1, 6, "City Construction"),
    (1, 10, "Soldier Training"),
    (1, 14, "Technology Research"),
    (1, 18, "Mystic Beast Training"),
    (1, 22, "Enhance Hero"),

    # Day 2 (Thursday)
    (2, 2, "City Construction"),
    (2, 6, "Soldier Training"),
    (2, 10, "Technology Research"),
    (2, 14, "Mystic Beast Training"),
    (2, 18, "Enhance Hero"),
    (2, 22, "City Construction"),

    # Day 3 (Friday)
    (3, 2, "Soldier Training"),
    (3, 6, "Technology Research"),
    (3, 10, "Mystic Beast Training"),
    (3, 14, "Enhance Hero"),
    (3, 18, "City Construction"),
    (3, 22, "Soldier Training"),

    # Day 4 (Saturday)
    (4, 2, "Technology Research"),
    (4, 6, "Mystic Beast Training"),
    (4, 10, "Enhance Hero"),
    (4, 14, "City Construction"),
    (4, 18, "Soldier Training"),
    (4, 22, "Technology Research"),

    # Day 5 (Sunday) - SPECIAL: Soldier Training repeats at 10:00
    (5, 2, "Mystic Beast Training"),
    (5, 6, "Enhance Hero"),
    (5, 10, "City Construction"),
    (5, 14, "Soldier Training"),
    (5, 18, "Soldier Training"),  # Pattern break: ST appears twice
    (5, 22, "Technology Research"),

    # Day 6 (Monday)
    (6, 2, "Enhance Hero"),
    (6, 6, "City Construction"),
    (6, 10, "Soldier Training"),
    (6, 14, "Technology Research"),
    (6, 18, "Mystic Beast Training"),
    (6, 22, "Enhance Hero"),

    # Day 7 (Tuesday)
    (7, 2, "City Construction"),
    (7, 6, "Soldier Training"),
    (7, 10, "Technology Research"),
    (7, 14, "Mystic Beast Training"),
    (7, 18, "Enhance Hero"),
    (7, 22, "City Construction"),
]

# Reference point: Day 1 starts December 4, 2025, 02:00 UTC
# (which is December 3, 2025, 6PM PT)
REFERENCE_TIME = datetime(2025, 12, 4, 2, 0, 0, tzinfo=timezone.utc)

# Event duration
EVENT_HOURS = 4


def get_arms_race_status(now: datetime = None) -> Dict[str, Any]:
    """
    Get the current Arms Race status.

    Args:
        now: Optional datetime (UTC). Defaults to current UTC time.

    Returns:
        Dict with:
            - current: Current activity name
            - previous: Previous activity name
            - next: Next activity name
            - day: Current day in Arms Race cycle (1-7)
            - time_remaining: Time until next activity (timedelta)
            - time_elapsed: Time since activity started (timedelta)
            - block_start: When current activity started (datetime)
            - block_end: When current activity ends (datetime)
            - event_index: Index in SCHEDULE list (0-41)
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Calculate hours since reference
    delta = now - REFERENCE_TIME
    hours_since_ref = delta.total_seconds() / 3600

    # Calculate which event we're in (0-41, then wraps)
    # 42 events total, each 4 hours = 168 hour cycle (7 days)
    cycle_hours = 42 * EVENT_HOURS  # 168 hours
    hours_in_cycle = hours_since_ref % cycle_hours
    event_index = int(hours_in_cycle // EVENT_HOURS)

    # Get current event
    day, hour, current_activity = SCHEDULE[event_index]

    # Get previous and next events (with wrapping)
    prev_index = (event_index - 1) % 42
    next_index = (event_index + 1) % 42
    _, _, previous_activity = SCHEDULE[prev_index]
    _, _, next_activity = SCHEDULE[next_index]

    # Calculate block timing
    hours_into_event = hours_in_cycle % EVENT_HOURS
    block_start = now - timedelta(hours=hours_into_event)
    block_end = block_start + timedelta(hours=EVENT_HOURS)
    time_remaining = block_end - now
    time_elapsed = now - block_start

    return {
        "current": current_activity,
        "previous": previous_activity,
        "next": next_activity,
        "day": day,
        "time_remaining": time_remaining,
        "time_elapsed": time_elapsed,
        "block_start": block_start,
        "block_end": block_end,
        "event_index": event_index,
    }


def format_timedelta(td: timedelta) -> str:
    """Format a timedelta as HH:MM:SS."""
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(abs(total_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def print_status(status: Dict[str, Any] = None):
    """Print the current Arms Race status."""
    if status is None:
        status = get_arms_race_status()

    print(f"=== Arms Race Status (Day {status['day']}) ===")
    print(f"Current:  {status['current']}")
    print(f"Previous: {status['previous']}")
    print(f"Next:     {status['next']}")
    print(f"")
    print(f"Time elapsed:   {format_timedelta(status['time_elapsed'])}")
    print(f"Time remaining: {format_timedelta(status['time_remaining'])}")
    print(f"")
    print(f"Started:  {status['block_start'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Ends:     {status['block_end'].strftime('%Y-%m-%d %H:%M:%S UTC')}")


def get_time_until_soldier_training(now: datetime = None) -> timedelta | None:
    """
    Get time until next Soldier Training arms race period.

    Args:
        now: Optional datetime (UTC). Defaults to current UTC time.

    Returns:
        timedelta: Time until Soldier Training starts (0 if active now)
        None: If unable to determine
    """
    try:
        status = get_arms_race_status(now)

        # If currently Soldier Training, return 0
        if status['current'] == 'Soldier Training':
            return timedelta(0)

        # Search forward through schedule to find next Soldier Training
        current_idx = status['event_index']

        for offset in range(1, 43):  # Check all 42 events
            check_idx = (current_idx + offset) % 42
            _, _, activity = SCHEDULE[check_idx]

            if activity == 'Soldier Training':
                # Found it! Calculate time until it starts
                events_away = offset

                # Time = remaining in current event + (events_away - 1) * EVENT_HOURS
                return status['time_remaining'] + timedelta(hours=(events_away - 1) * EVENT_HOURS)

        return None  # Should never happen

    except Exception:
        return None


if __name__ == "__main__":
    print_status()

    # Also show time until Soldier Training
    time_until = get_time_until_soldier_training()
    if time_until is not None:
        if time_until.total_seconds() == 0:
            print("\nSoldier Training is ACTIVE NOW!")
        else:
            hours = int(time_until.total_seconds() // 3600)
            mins = int((time_until.total_seconds() % 3600) // 60)
            print(f"\nSoldier Training starts in: {hours}h {mins}m")
