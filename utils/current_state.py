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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

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


def get_full_state() -> dict[str, Any]:
    """Get complete current state."""
    return load_state()
