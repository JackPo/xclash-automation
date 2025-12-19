"""
Arms Race schedule calculator.

Uses the exact schedule table provided by the user.
Day 1 starts Wednesday Dec 3, 2025 at 6PM PT (Dec 4, 2025 02:00 UTC).
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any

# Exact schedule from user (42 events total)
# Format: (day, utc_hour, activity_name)
SCHEDULE = [
    # Day 1 - Wednesday
    (1, 2, "Enhance Hero"),           # 18:00 system time (6PM PT Wed = 2AM UTC Thu)
    (1, 6, "City Construction"),      # 22:00
    (1, 10, "Soldier Training"),      # 02:00
    (1, 14, "Technology Research"),   # 06:00
    (1, 18, "Mystic Beast Training"), # 10:00
    (1, 22, "Enhance Hero"),          # 14:00

    # Day 2 - Thursday
    (2, 2, "City Construction"),      # 18:00
    (2, 6, "Soldier Training"),       # 22:00
    (2, 10, "Technology Research"),   # 02:00
    (2, 14, "Mystic Beast Training"), # 06:00
    (2, 18, "Enhance Hero"),          # 10:00
    (2, 22, "City Construction"),     # 14:00

    # Day 3 - Friday
    (3, 2, "Soldier Training"),       # 18:00
    (3, 6, "Technology Research"),    # 22:00
    (3, 10, "Mystic Beast Training"), # 02:00
    (3, 14, "Enhance Hero"),          # 06:00
    (3, 18, "City Construction"),     # 10:00
    (3, 22, "Soldier Training"),      # 14:00

    # Day 4 - Saturday
    (4, 2, "Technology Research"),    # 18:00
    (4, 6, "Mystic Beast Training"),  # 22:00
    (4, 10, "Enhance Hero"),          # 02:00
    (4, 14, "City Construction"),     # 06:00
    (4, 18, "Soldier Training"),      # 10:00
    (4, 22, "Technology Research"),   # 14:00

    # Day 5 - Sunday
    (5, 2, "Mystic Beast Training"),  # 18:00
    (5, 6, "Enhance Hero"),           # 22:00
    (5, 10, "City Construction"),     # 02:00
    (5, 14, "Soldier Training"),      # 06:00
    (5, 18, "Technology Research"),   # 10:00
    (5, 22, "Mystic Beast Training"), # 14:00

    # Day 6 - Monday
    (6, 2, "Enhance Hero"),           # 18:00
    (6, 6, "City Construction"),      # 22:00
    (6, 10, "Soldier Training"),      # 02:00
    (6, 14, "Technology Research"),   # 06:00
    (6, 18, "Mystic Beast Training"), # 10:00
    (6, 22, "Enhance Hero"),          # 14:00

    # Day 7 - Tuesday
    (7, 2, "City Construction"),      # 18:00
    (7, 6, "Soldier Training"),       # 22:00
    (7, 10, "Technology Research"),   # 02:00
    (7, 14, "Mystic Beast Training"), # 06:00
    (7, 18, "Enhance Hero"),          # 10:00
    (7, 22, "City Construction"),     # 14:00
]

# Reference: Day 1 starts Dec 3, 2025 6PM PT = Dec 4, 2025 02:00 UTC
REFERENCE_TIME = datetime(2025, 12, 4, 2, 0, 0, tzinfo=timezone.utc)

EVENT_HOURS = 4


def get_arms_race_status(now: datetime = None) -> Dict[str, Any]:
    """Get the current Arms Race status using the exact lookup table."""
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Calculate hours since reference
    delta = now - REFERENCE_TIME
    hours_since_ref = delta.total_seconds() / 3600

    # Calculate which event (0-41, wraps after 168 hours)
    cycle_hours = 42 * EVENT_HOURS  # 168 hours
    hours_in_cycle = hours_since_ref % cycle_hours
    event_index = int(hours_in_cycle // EVENT_HOURS)

    # Look up in table
    day, hour, current_activity = SCHEDULE[event_index]

    # Get previous and next
    prev_index = (event_index - 1) % 42
    next_index = (event_index + 1) % 42
    _, _, previous_activity = SCHEDULE[prev_index]
    _, _, next_activity = SCHEDULE[next_index]

    # Calculate timing
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


# Valid event names for get_time_until_event()
VALID_EVENTS = [
    "Enhance Hero",
    "City Construction",
    "Soldier Training",
    "Technology Research",
    "Mystic Beast Training",
]


def get_time_until_event(event_name: str, now: datetime = None) -> timedelta | None:
    """
    Get time until next occurrence of specified Arms Race event.

    Args:
        event_name: One of "Enhance Hero", "City Construction", "Soldier Training",
                    "Technology Research", "Mystic Beast Training"
        now: Optional datetime (defaults to current UTC time)

    Returns:
        timedelta(0) if currently in the specified event
        timedelta with positive value if event is upcoming
        None on error or invalid event name
    """
    if event_name not in VALID_EVENTS:
        return None

    try:
        status = get_arms_race_status(now)

        # If currently in the specified event, return 0
        if status['current'] == event_name:
            return timedelta(0)

        # Search forward in table
        current_idx = status['event_index']

        for offset in range(1, 43):
            check_idx = (current_idx + offset) % 42
            _, _, activity = SCHEDULE[check_idx]

            if activity == event_name:
                # Found it
                events_away = offset
                return status['time_remaining'] + timedelta(hours=(events_away - 1) * EVENT_HOURS)

        return None

    except Exception:
        return None


def get_time_until_soldier_training(now: datetime = None) -> timedelta | None:
    """Get time until next Soldier Training event. Alias for get_time_until_event()."""
    return get_time_until_event("Soldier Training", now)


def get_time_until_beast_training(now: datetime = None) -> timedelta | None:
    """Get time until next Mystic Beast Training event. Alias for get_time_until_event()."""
    return get_time_until_event("Mystic Beast Training", now)


def get_time_until_vs_promotion_day(vs_days: list[int], now: datetime = None) -> timedelta | None:
    """
    Get time until next VS Soldier Promotion Day starts.

    Args:
        vs_days: List of days (1-7) when VS soldier promotions run all day
        now: Optional datetime (defaults to current UTC time)

    Returns:
        timedelta(0) if currently on a VS promotion day
        timedelta to next VS day start if approaching
        None if vs_days is empty or error
    """
    if not vs_days:
        return None

    try:
        status = get_arms_race_status(now)
        current_day = status['day']

        # If currently on a VS promotion day, return 0
        if current_day in vs_days:
            return timedelta(0)

        # Find next VS day
        # Days go 1->2->3->4->5->6->7->1->2...
        for days_ahead in range(1, 8):
            check_day = ((current_day - 1 + days_ahead) % 7) + 1
            if check_day in vs_days:
                # Calculate time until that day starts
                # Day N starts when the first event of Day N begins
                # That's at block_start of Day N's first event

                # Current position in cycle
                hours_until_day_end = status['time_remaining'].total_seconds() / 3600

                # How many 4-hour blocks until end of current day?
                # Current event is at some block in current day
                # Each day has 6 events (24 hours)
                current_event_in_day = status['event_index'] % 6  # 0-5 within day
                blocks_left_in_day = 5 - current_event_in_day

                # Hours until current day ends = time remaining in current event + remaining blocks
                hours_until_current_day_ends = hours_until_day_end + (blocks_left_in_day * EVENT_HOURS)

                # Then add full days until the target day
                full_days_between = days_ahead - 1
                hours_of_full_days = full_days_between * 24

                total_hours = hours_until_current_day_ends + hours_of_full_days
                return timedelta(hours=total_hours)

        return None

    except Exception:
        return None


def get_time_until_soldier_promotion_opportunity(vs_days: list[int] = None, now: datetime = None) -> timedelta | None:
    """
    Get time until next opportunity to promote soldiers.

    Returns the MINIMUM of:
    - Time until next Arms Race "Soldier Training" event
    - Time until next VS Promotion Day starts

    This ensures training completes before the earliest promotion opportunity.

    Args:
        vs_days: List of days (1-7) when VS soldier promotions run all day.
                 If None or empty, only considers Arms Race schedule.
        now: Optional datetime (defaults to current UTC time)

    Returns:
        timedelta(0) if currently in a promotion opportunity
        timedelta to next opportunity
        None if unable to determine
    """
    time_until_arms_race = get_time_until_soldier_training(now)
    time_until_vs_day = get_time_until_vs_promotion_day(vs_days, now) if vs_days else None

    # If both are None, return None
    if time_until_arms_race is None and time_until_vs_day is None:
        return None

    # If only one is available, return that
    if time_until_arms_race is None:
        return time_until_vs_day
    if time_until_vs_day is None:
        return time_until_arms_race

    # Return the minimum (earliest opportunity)
    return min(time_until_arms_race, time_until_vs_day)


if __name__ == "__main__":
    print_status()

    # Show time until each event type using the generalized function
    print("\n=== Time Until Each Event ===")
    for event in VALID_EVENTS:
        time_until = get_time_until_event(event)
        if time_until is not None:
            if time_until.total_seconds() == 0:
                print(f"{event}: ACTIVE NOW!")
            else:
                hours = int(time_until.total_seconds() // 3600)
                mins = int((time_until.total_seconds() % 3600) // 60)
                print(f"{event}: {hours}h {mins}m")
