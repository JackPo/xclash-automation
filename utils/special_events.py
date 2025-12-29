"""
Special Events Helper - Utilities for checking active special events.

Events are defined in config.py SPECIAL_EVENTS registry.
Each event has: name, start, end, and optional properties like ignore_rally_limit.

Server resets at 02:00 UTC - end date means active until next day 02:00 UTC.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

try:
    from config import SPECIAL_EVENTS
except ImportError:
    SPECIAL_EVENTS = []


def get_active_events(now: Optional[datetime] = None) -> list[dict]:
    """
    Get list of currently active special events.

    Args:
        now: Optional datetime to check (defaults to current UTC time)

    Returns:
        List of active event dicts from SPECIAL_EVENTS
    """
    if now is None:
        now = datetime.now(timezone.utc)

    active = []
    for event in SPECIAL_EVENTS:
        start_date = datetime.strptime(event["start"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_date = datetime.strptime(event["end"], "%Y-%m-%d").replace(tzinfo=timezone.utc)

        # Event starts at 02:00 UTC on start date
        event_start = start_date.replace(hour=2, minute=0, second=0)
        # Event ends at 02:00 UTC on the day AFTER end date
        event_end = (end_date + timedelta(days=1)).replace(hour=2, minute=0, second=0)

        if event_start <= now < event_end:
            active.append(event)

    return active


def is_event_active(event_name: str, now: Optional[datetime] = None) -> bool:
    """
    Check if a specific event is currently active.

    Args:
        event_name: Name of the event to check (case-insensitive)
        now: Optional datetime to check (defaults to current UTC time)

    Returns:
        True if the event is currently active
    """
    active = get_active_events(now)
    return any(e["name"].lower() == event_name.lower() for e in active)


def get_active_event_names(now: Optional[datetime] = None) -> list[str]:
    """
    Get list of active event names (for logging).

    Args:
        now: Optional datetime to check (defaults to current UTC time)

    Returns:
        List of active event names
    """
    return [e["name"] for e in get_active_events(now)]


def get_active_events_short(now: Optional[datetime] = None) -> str:
    """
    Get short string of active events for daemon log.

    Examples:
        "[WinFest]"
        "[NYFeast]"
        "[WinFest][NYFeast]"
        "" (empty if no events)

    Args:
        now: Optional datetime to check (defaults to current UTC time)

    Returns:
        Short string for logging
    """
    active = get_active_events(now)
    if not active:
        return ""

    # Short names for common events
    short_names = {
        "Winter Fest": "WinFest",
        "New Year's Feast": "NYFeast",
    }

    parts = []
    for event in active:
        name = event["name"]
        short = short_names.get(name, name[:7])  # Fallback: first 7 chars
        parts.append(f"[{short}]")

    return "".join(parts)
