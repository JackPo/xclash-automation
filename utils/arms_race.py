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

    # Day 5 - Sunday (SPECIAL: Soldier Training at both 06:00 and 10:00)
    (5, 2, "Mystic Beast Training"),  # 18:00
    (5, 6, "Enhance Hero"),           # 22:00
    (5, 10, "City Construction"),     # 02:00
    (5, 14, "Soldier Training"),      # 06:00
    (5, 18, "Soldier Training"),      # 10:00 - PATTERN BREAK (duplicate ST)
    (5, 22, "Technology Research"),   # 14:00

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


def get_time_until_soldier_training(now: datetime = None) -> timedelta | None:
    """Get time until next Soldier Training event."""
    try:
        status = get_arms_race_status(now)

        # If currently Soldier Training, return 0
        if status['current'] == 'Soldier Training':
            return timedelta(0)

        # Search forward in table
        current_idx = status['event_index']

        for offset in range(1, 43):
            check_idx = (current_idx + offset) % 42
            _, _, activity = SCHEDULE[check_idx]

            if activity == 'Soldier Training':
                # Found it
                events_away = offset
                return status['time_remaining'] + timedelta(hours=(events_away - 1) * EVENT_HOURS)

        return None

    except Exception:
        return None


if __name__ == "__main__":
    print_status()

    # Show time until Soldier Training
    time_until = get_time_until_soldier_training()
    if time_until is not None:
        if time_until.total_seconds() == 0:
            print("\nSoldier Training is ACTIVE NOW!")
        else:
            hours = int(time_until.total_seconds() // 3600)
            mins = int((time_until.total_seconds() % 3600) // 60)
            print(f"\nSoldier Training starts in: {hours}h {mins}m")
