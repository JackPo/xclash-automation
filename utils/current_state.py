"""
Current State Manager - Persistent state file for daemon/dashboard communication.

Provides a simple JSON file that the daemon writes to and the dashboard reads from.
This decouples the dashboard from needing a live WebSocket connection for basic state.

State file: data/daemon_current_state.json
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Server reset time (02:00 UTC)
SERVER_RESET_HOUR_UTC = 2


def _get_server_day(dt: datetime) -> datetime:
    """
    Get the server day for a given datetime.
    Server resets at 02:00 UTC, so times before 02:00 belong to the previous day.
    Returns the date at 02:00 UTC for that server day.
    """
    # Convert to UTC if needed
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    # If before 02:00 UTC, it's still the previous server day
    if dt.hour < SERVER_RESET_HOUR_UTC:
        dt = dt - timedelta(days=1)

    return dt.replace(hour=SERVER_RESET_HOUR_UTC, minute=0, second=0, microsecond=0)


def _is_same_server_day(ts: datetime, now: datetime) -> bool:
    """Check if two datetimes are on the same server day (reset at 02:00 UTC)."""
    return _get_server_day(ts) == _get_server_day(now)

# State file location
STATE_FILE = Path(__file__).parent.parent / "data" / "daemon_current_state.json"

# Thread lock for safe writes
_lock = threading.Lock()


def _get_default_state() -> dict[str, Any]:
    """Return default empty state structure."""
    return {
        "stamina": {
            "value": None,
            "timestamp": None,
            "view": None,
        },
        "arms_race_score": {
            "current_points": None,
            "chest3_target": 30000,
            "points_to_chest3": None,
            "event": None,
            "timestamp": None,
        },
        "view_state": {
            "state": None,
            "timestamp": None,
        },
        "zombie_mode": {
            "mode": "elite",
            "expires": None,
        },
        "rally_status": {
            "rally_count": 0,
            "target_rallies": None,
            "timestamp": None,
        },
        "last_rally_join": {
            "success": None,
            "monster_name": None,
            "level": None,
            "abort_reason": None,
            "timestamp": None,
        },
        "stamina_claim_timer": {
            "seconds_remaining": None,  # Seconds until free claim available
            "claim_available": None,    # True if Claim button was visible
            "checked_at": None,         # When we checked (ISO timestamp)
            "block_start": None,        # Which Beast Training block this is for
        },
        "daemon_status": {
            "paused": False,
            "active_flows": [],
            "critical_flow": None,
            "idle_seconds": 0,
        },
        "tavern_quests": {
            "assist_allies": {"current": None, "max": 5},
            "plunder_others": {"current": None, "max": 5},
            "timestamp": None,
        },
        "shield_inventory": {
            "8hr": None,
            "12hr": None,
            "24hr": None,
            "timestamp": None,
        },
        "under_attack": {
            "is_under_attack": False,
            "last_detected": None,
            "attack_count_today": 0,
        },
        "bloodlust": {
            "is_active": False,
            "started_at": None,
            "expected_end": None,
        },
        "last_update": None,
    }


def load_state() -> dict[str, Any]:
    """
    Load current state from file.

    Returns default state if file doesn't exist or is invalid.
    """
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                # Merge with defaults to ensure all keys exist
                default = _get_default_state()
                for key in default:
                    if key not in state:
                        state[key] = default[key]
                return state
    except Exception as e:
        logger.warning(f"Failed to load state file: {e}")

    return _get_default_state()


def save_state(state: dict[str, Any]) -> bool:
    """
    Save state to file atomically.

    Returns True on success, False on failure.
    """
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Update timestamp
        state["last_update"] = datetime.now(timezone.utc).isoformat()

        with _lock:
            # Write to temp file first, then rename (atomic)
            temp_file = STATE_FILE.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            temp_file.replace(STATE_FILE)

        return True
    except Exception as e:
        logger.error(f"Failed to save state file: {e}")
        return False


def update_stamina(value: int | None, view: str | None = None) -> None:
    """Update stamina value in state file."""
    state = load_state()
    state["stamina"] = {
        "value": value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "view": view,
    }
    save_state(state)


def update_arms_race_score(
    current_points: int | None,
    chest3_target: int = 30000,
    event: str | None = None,
) -> None:
    """Update Arms Race score in state file."""
    state = load_state()
    points_to_chest3 = None
    if current_points is not None:
        points_to_chest3 = max(0, chest3_target - current_points)

    state["arms_race_score"] = {
        "current_points": current_points,
        "chest3_target": chest3_target,
        "points_to_chest3": points_to_chest3,
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    save_state(state)


def update_view_state(view: str) -> None:
    """Update view state in state file."""
    state = load_state()
    state["view_state"] = {
        "state": view,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    save_state(state)


def update_zombie_mode(mode: str, expires: str | None = None) -> None:
    """Update zombie mode in state file."""
    state = load_state()
    state["zombie_mode"] = {
        "mode": mode,
        "expires": expires,
    }
    save_state(state)


def update_rally_status(
    rally_count: int,
    target_rallies: int | None = None,
) -> None:
    """Update rally status in state file."""
    state = load_state()
    state["rally_status"] = {
        "rally_count": rally_count,
        "target_rallies": target_rallies,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    save_state(state)


def update_rally_join_result(
    success: bool,
    monster_name: str | None = None,
    level: int | None = None,
    abort_reason: str | None = None,
) -> None:
    """
    Update last rally join result in state file.

    Args:
        success: Whether the rally join succeeded
        monster_name: Name of the monster (if identified)
        level: Monster level (if identified)
        abort_reason: Why the flow was aborted (if not successful)
            Examples: "no_rallies", "no_idle_heroes", "daily_limit",
                      "panel_invalid", "no_matching_monster"
    """
    state = load_state()
    state["last_rally_join"] = {
        "success": success,
        "monster_name": monster_name,
        "level": level,
        "abort_reason": abort_reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    save_state(state)


def update_stamina_claim_timer(
    seconds_remaining: int | None,
    claim_available: bool,
    block_start: str | None = None,
) -> None:
    """
    Update stamina claim timer in state file.

    Called once at Beast Training block start to record when free claim
    will be available. Dashboard can calculate countdown from this.

    Args:
        seconds_remaining: Seconds until free claim (None if claim_available=True)
        claim_available: True if Claim button was visible (can claim now)
        block_start: ISO timestamp of the Beast Training block this is for
    """
    state = load_state()
    state["stamina_claim_timer"] = {
        "seconds_remaining": seconds_remaining,
        "claim_available": claim_available,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "block_start": block_start,
    }
    save_state(state)


def update_daemon_status(
    paused: bool = False,
    active_flows: list[str] | None = None,
    critical_flow: str | None = None,
    idle_seconds: float = 0,
) -> None:
    """Update daemon status in state file."""
    state = load_state()
    state["daemon_status"] = {
        "paused": paused,
        "active_flows": active_flows or [],
        "critical_flow": critical_flow,
        "idle_seconds": idle_seconds,
    }
    save_state(state)


def get_stamina() -> dict[str, Any]:
    """Get stamina from state file."""
    return load_state().get("stamina", {})


def get_arms_race_score() -> dict[str, Any]:
    """Get Arms Race score from state file."""
    return load_state().get("arms_race_score", {})


def update_tavern_quests(
    assist_current: int | None,
    assist_max: int = 5,
    plunder_current: int | None = None,
    plunder_max: int = 5,
) -> None:
    """
    Update tavern quest counters (Assist Allies, Plunder Others).

    Args:
        assist_current: Current assist count (e.g., 3 of 5)
        assist_max: Max assists per day (default 5)
        plunder_current: Current plunder count (e.g., 0 of 5)
        plunder_max: Max plunders per day (default 5)
    """
    state = load_state()
    state["tavern_quests"] = {
        "assist_allies": {"current": assist_current, "max": assist_max},
        "plunder_others": {"current": plunder_current, "max": plunder_max},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    save_state(state)


def get_tavern_quests() -> dict[str, Any]:
    """Get tavern quest counters from state file."""
    return load_state().get("tavern_quests", {})


def is_tavern_assists_maxed() -> bool:
    """
    Check if assist allies is maxed for today.

    Returns True if current >= max AND timestamp is from same server day (reset at 02:00 UTC).
    """
    state = load_state().get("tavern_quests", {})
    assist = state.get("assist_allies", {})
    current = assist.get("current")
    maximum = assist.get("max", 5)
    timestamp = state.get("timestamp")

    if current is None or timestamp is None:
        return False

    # Check if from same server day (resets at 02:00 UTC)
    try:
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if not _is_same_server_day(ts, now):
            return False  # Old data, from previous server day
    except Exception:
        return False

    return current >= maximum


def is_tavern_plunder_maxed() -> bool:
    """
    Check if plunder others is maxed for today.

    Returns True if current >= max AND timestamp is from same server day (reset at 02:00 UTC).
    """
    state = load_state().get("tavern_quests", {})
    plunder = state.get("plunder_others", {})
    current = plunder.get("current")
    maximum = plunder.get("max", 5)
    timestamp = state.get("timestamp")

    if current is None or timestamp is None:
        return False

    # Check if from same server day (resets at 02:00 UTC)
    try:
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if not _is_same_server_day(ts, now):
            return False  # Old data, from previous server day
    except Exception:
        return False

    return current >= maximum


def get_full_state() -> dict[str, Any]:
    """Get complete current state."""
    return load_state()


def update_shield_inventory(
    shields_8hr: int | None,
    shields_12hr: int | None,
    shields_24hr: int | None,
) -> None:
    """
    Update shield inventory counts in state file.

    Args:
        shields_8hr: Count of 8-hour shields (green)
        shields_12hr: Count of 12-hour shields (blue)
        shields_24hr: Count of 24-hour shields (purple)
    """
    state = load_state()
    state["shield_inventory"] = {
        "8hr": shields_8hr,
        "12hr": shields_12hr,
        "24hr": shields_24hr,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    save_state(state)


def get_shield_inventory() -> dict[str, Any]:
    """Get shield inventory from state file."""
    return load_state().get("shield_inventory", {})


def update_under_attack(is_under_attack: bool) -> None:
    """
    Update under attack status in state file.

    Args:
        is_under_attack: True if currently under attack
    """
    state = load_state()
    now = datetime.now(timezone.utc)

    # Get existing state
    attack_state = state.get("under_attack", {})
    attack_count = attack_state.get("attack_count_today", 0)
    last_detected = attack_state.get("last_detected")

    # Reset count if from previous server day
    if last_detected:
        try:
            last_ts = datetime.fromisoformat(last_detected.replace("Z", "+00:00"))
            if not _is_same_server_day(last_ts, now):
                attack_count = 0
        except Exception:
            pass

    # Increment count if newly detected
    was_under_attack = attack_state.get("is_under_attack", False)
    if is_under_attack and not was_under_attack:
        attack_count += 1

    state["under_attack"] = {
        "is_under_attack": is_under_attack,
        "last_detected": now.isoformat() if is_under_attack else last_detected,
        "attack_count_today": attack_count,
    }
    save_state(state)


def get_under_attack() -> dict[str, Any]:
    """Get under attack status from state file."""
    return load_state().get("under_attack", {})


def update_bloodlust(is_active: bool) -> None:
    """
    Update bloodlust status in state file.

    When bloodlust becomes active, sets expected_end to 15 minutes from now.
    When bloodlust ends, clears the timestamps.

    Args:
        is_active: True if bloodlust is currently active
    """
    from utils.bloodlust_matcher import BLOODLUST_DURATION_SECONDS

    state = load_state()
    now = datetime.now(timezone.utc)

    bloodlust_state = state.get("bloodlust", {})
    was_active = bloodlust_state.get("is_active", False)

    if is_active and not was_active:
        # Bloodlust just started
        expected_end = now + timedelta(seconds=BLOODLUST_DURATION_SECONDS)
        state["bloodlust"] = {
            "is_active": True,
            "started_at": now.isoformat(),
            "expected_end": expected_end.isoformat(),
        }
    elif not is_active and was_active:
        # Bloodlust just ended
        state["bloodlust"] = {
            "is_active": False,
            "started_at": bloodlust_state.get("started_at"),
            "expected_end": None,
        }
    elif is_active:
        # Still active - don't update timestamps
        pass
    else:
        # Still inactive - ensure state is clean
        if bloodlust_state.get("is_active"):
            state["bloodlust"] = {
                "is_active": False,
                "started_at": None,
                "expected_end": None,
            }

    save_state(state)


def get_bloodlust() -> dict[str, Any]:
    """Get bloodlust status from state file."""
    return load_state().get("bloodlust", {})
