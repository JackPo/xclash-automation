"""
Special Events Helper - Utilities for checking active special events.

Events are defined in config.py SPECIAL_EVENTS registry.
Each event has: name, start, end, and optional properties like ignore_rally_limit.

Server resets at 02:00 UTC - end date means active until next day 02:00 UTC.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

# Import SPECIAL_EVENTS from config (may be empty list)
from config import SPECIAL_EVENTS as _SPECIAL_EVENTS

# Re-export for type checking - this is the actual list used
SPECIAL_EVENTS: list[dict[str, Any]] = _SPECIAL_EVENTS


def get_active_events(now: datetime | None = None) -> list[dict[str, Any]]:
    """
    Get list of currently active special events.

    Args:
        now: Optional datetime to check (defaults to current UTC time)

    Returns:
        List of active event dicts from SPECIAL_EVENTS
    """
    if now is None:
        now = datetime.now(timezone.utc)

    active: list[dict[str, Any]] = []
    for event in SPECIAL_EVENTS:
        start_str: str = str(event["start"])
        end_str: str = str(event["end"])
        start_date = datetime.strptime(start_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_date = datetime.strptime(end_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        # Event starts at 02:00 UTC on start date
        event_start = start_date.replace(hour=2, minute=0, second=0)
        # Event ends at 02:00 UTC on the day AFTER end date
        event_end = (end_date + timedelta(days=1)).replace(hour=2, minute=0, second=0)

        if event_start <= now < event_end:
            active.append(event)

    return active


def is_event_active(event_name: str, now: datetime | None = None) -> bool:
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


def get_active_event_names(now: datetime | None = None) -> list[str]:
    """
    Get list of active event names (for logging).

    Args:
        now: Optional datetime to check (defaults to current UTC time)

    Returns:
        List of active event names
    """
    return [e["name"] for e in get_active_events(now)]


def get_active_events_short(now: datetime | None = None) -> str:
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
