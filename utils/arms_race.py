"""
Arms Race schedule calculator.

The Arms Race rotates through 5 activities every 4 hours:
1. City Construction
2. Soldier Training
3. Tech Research
4. Mystic Beast
5. Enhance Hero

Each activity runs for 4 hours, then rotates to the next.
The full cycle is 20 hours (5 activities x 4 hours each).

Note: The game's "day" terminology shifts weekly because the 5-activity
cycle doesn't align with 7-day weeks. We track by activity name instead.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any

# Activity names in order
ACTIVITIES = [
    "City Construction",
    "Soldier Training",
    "Tech Research",
    "Mystic Beast",
    "Enhance Hero",
]

# Block duration in hours
BLOCK_HOURS = 4

# Total activities in cycle
TOTAL_ACTIVITIES = 5

# Reference point: 2025-12-02 02:00 UTC = start of Enhance Hero block (Day 6)
# Currently (before that time) = Day 5, Mystic Beast
# Days are a 7-day week rotation (1-7), separate from the 5-activity rotation
REFERENCE_TIME = datetime(2025, 12, 2, 2, 0, 0, tzinfo=timezone.utc)
REFERENCE_ACTIVITY = 4  # Enhance Hero index at reference time
REFERENCE_DAY = 6  # Day 6 at reference time (when Enhance Hero starts)


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
            - day: Current day in game's Arms Race (1-5, then resets)
            - time_remaining: Time until next activity (timedelta)
            - time_elapsed: Time since activity started (timedelta)
            - block_start: When current activity started (datetime)
            - block_end: When current activity ends (datetime)
            - activity_index: Index in ACTIVITIES list (0-4)
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Calculate hours since reference
    delta = now - REFERENCE_TIME
    hours_since_ref = delta.total_seconds() / 3600

    # Calculate which block we're in (relative to reference)
    blocks_since_ref = int(hours_since_ref // BLOCK_HOURS)

    # Calculate activity index (0-4)
    activity_index = (REFERENCE_ACTIVITY + blocks_since_ref) % TOTAL_ACTIVITIES

    # Calculate day (1-7, 7-day week cycle)
    # Day increments with each 4-hour activity block
    day = ((REFERENCE_DAY - 1 + blocks_since_ref) % 7) + 1

    # Calculate block timing
    hours_into_block = hours_since_ref % BLOCK_HOURS
    block_start = now - timedelta(hours=hours_into_block)
    block_end = block_start + timedelta(hours=BLOCK_HOURS)
    time_remaining = block_end - now
    time_elapsed = now - block_start

    # Get activity names
    current_activity = ACTIVITIES[activity_index]
    previous_activity = ACTIVITIES[(activity_index - 1) % TOTAL_ACTIVITIES]
    next_activity = ACTIVITIES[(activity_index + 1) % TOTAL_ACTIVITIES]

    return {
        "current": current_activity,
        "previous": previous_activity,
        "next": next_activity,
        "day": day,
        "time_remaining": time_remaining,
        "time_elapsed": time_elapsed,
        "block_start": block_start,
        "block_end": block_end,
        "activity_index": activity_index,
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
        None: If unable to determine (should not happen with calendar-based calc)
    """
    try:
        status = get_arms_race_status(now)

        # If currently Soldier Training, return 0
        if status['current'] == 'Soldier Training':
            return timedelta(0)

        # If Soldier Training is next, return time remaining in current block
        if status['next'] == 'Soldier Training':
            return status['time_remaining']

        # Calculate blocks until Soldier Training
        current_idx = status['activity_index']
        soldier_idx = ACTIVITIES.index('Soldier Training')

        if soldier_idx > current_idx:
            blocks_away = soldier_idx - current_idx
        else:
            blocks_away = (TOTAL_ACTIVITIES - current_idx) + soldier_idx

        # Time = remaining in current block + (blocks_away - 1) * BLOCK_HOURS
        return status['time_remaining'] + timedelta(hours=(blocks_away - 1) * BLOCK_HOURS)

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
