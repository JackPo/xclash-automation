"""
Rally Exhaustion Tracker - Track daily rally limits per monster.

When a "daily rally rewards limit" dialog appears, we mark that monster
as exhausted for the rest of the server day.

Server day resets at 02:00 UTC (6PM PT previous day).
"""

from datetime import datetime, timezone, timedelta
from typing import Dict

# Track monster exhaustion: {monster_name_lower: exhausted_at_utc}
_exhausted_monsters: Dict[str, datetime] = {}

SERVER_RESET_HOUR_UTC = 2  # 02:00 UTC


def _get_current_day_start() -> datetime:
    """Get the start of the current server day (02:00 UTC)."""
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=SERVER_RESET_HOUR_UTC, minute=0, second=0, microsecond=0)
    if now.hour < SERVER_RESET_HOUR_UTC:
        day_start -= timedelta(days=1)
    return day_start


def mark_exhausted(monster_name: str) -> None:
    """
    Mark a monster as exhausted (daily rally limit reached).

    Args:
        monster_name: Name of the monster (case-insensitive)
    """
    key = monster_name.lower()
    _exhausted_monsters[key] = datetime.now(timezone.utc)
    print(f"[EXHAUSTION] Marked '{monster_name}' as exhausted until next server reset (02:00 UTC)")


def is_exhausted(monster_name: str) -> bool:
    """
    Check if a monster is exhausted for today.

    Automatically clears exhaustion if server day has reset.

    Args:
        monster_name: Name of the monster (case-insensitive)

    Returns:
        True if monster is exhausted and should be skipped
    """
    key = monster_name.lower()
    if key not in _exhausted_monsters:
        return False

    exhausted_at = _exhausted_monsters[key]
    day_start = _get_current_day_start()

    # If exhausted before current day started, it's been reset
    if exhausted_at < day_start:
        del _exhausted_monsters[key]
        print(f"[EXHAUSTION] '{monster_name}' exhaustion reset (new server day)")
        return False

    return True


def get_exhausted_monsters() -> list[str]:
    """Get list of currently exhausted monster names."""
    day_start = _get_current_day_start()
    return [
        name for name, exhausted_at in _exhausted_monsters.items()
        if exhausted_at >= day_start
    ]


def clear_all() -> None:
    """Clear all exhaustion tracking (for testing)."""
    _exhausted_monsters.clear()
    print("[EXHAUSTION] Cleared all exhaustion tracking")


if __name__ == '__main__':
    # Test
    print("Testing exhaustion tracker...")

    mark_exhausted("Elite Zombie")
    mark_exhausted("Nightfall Servant")

    print(f"Elite Zombie exhausted: {is_exhausted('Elite Zombie')}")
    print(f"Zombie Overlord exhausted: {is_exhausted('Zombie Overlord')}")
    print(f"Exhausted monsters: {get_exhausted_monsters()}")

    clear_all()
    print(f"After clear: {get_exhausted_monsters()}")
