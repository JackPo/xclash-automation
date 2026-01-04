"""
Config Override Manager - Temporary runtime config overrides with expiry.

Allows dashboard to temporarily override config values for a specified duration,
with automatic expiry and persistence across daemon restarts.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar('T')

# Config definitions: key -> {default, type, min, max, category, description}
CONFIG_DEFINITIONS = {
    # Rally Settings
    "RALLY_JOIN_ENABLED": {
        "default": False,
        "type": "bool",
        "category": "rally",
        "description": "Auto-join rallies when handshake icon detected",
    },
    "RALLY_IGNORE_DAILY_LIMIT": {
        "default": False,
        "type": "bool",
        "category": "rally",
        "description": "Ignore daily rally reward limit warning",
    },
    # Stamina Settings
    "ELITE_ZOMBIE_STAMINA_THRESHOLD": {
        "default": 118,
        "type": "int",
        "min": 0,
        "max": 200,
        "category": "stamina",
        "description": "Minimum stamina to trigger Elite Zombie rally",
    },
    "ELITE_ZOMBIE_PLUS_CLICKS": {
        "default": 5,
        "type": "int",
        "min": 0,
        "max": 15,
        "category": "stamina",
        "description": "Times to click plus button (increases zombie level)",
    },
    # Cooldowns
    "BAG_FLOW_COOLDOWN": {
        "default": 1200,
        "type": "int",
        "min": 60,
        "max": 7200,
        "category": "cooldowns",
        "description": "Bag flow cooldown in seconds (default 20 min)",
    },
    "AFK_REWARDS_COOLDOWN": {
        "default": 3600,
        "type": "int",
        "min": 300,
        "max": 7200,
        "category": "cooldowns",
        "description": "AFK rewards cooldown in seconds (default 1 hour)",
    },
    "UNION_GIFTS_COOLDOWN": {
        "default": 3600,
        "type": "int",
        "min": 300,
        "max": 7200,
        "category": "cooldowns",
        "description": "Union gifts cooldown in seconds (default 1 hour)",
    },
    "SOLDIER_TRAINING_COOLDOWN": {
        "default": 300,
        "type": "int",
        "min": 60,
        "max": 600,
        "category": "cooldowns",
        "description": "Soldier training cooldown in seconds (default 5 min)",
    },
    # Arms Race Settings
    "ARMS_RACE_BEAST_TRAINING_ENABLED": {
        "default": True,
        "type": "bool",
        "category": "arms_race",
        "description": "Enable Beast Training automation during event",
    },
    "ARMS_RACE_SOLDIER_TRAINING_ENABLED": {
        "default": True,
        "type": "bool",
        "category": "arms_race",
        "description": "Enable Soldier Training automation during event",
    },
    "ARMS_RACE_ENHANCE_HERO_ENABLED": {
        "default": True,
        "type": "bool",
        "category": "arms_race",
        "description": "Enable Enhance Hero automation during event",
    },
    # Idle/Timing
    "IDLE_THRESHOLD": {
        "default": 300,
        "type": "int",
        "min": 60,
        "max": 3600,
        "category": "timing",
        "description": "Seconds user must be idle before flows trigger (default 5 min)",
    },
}


class ConfigOverrideManager:
    """
    Manages temporary config overrides with expiry times.

    Thread-safe for daemon access. Persists to JSON for survival across restarts.
    """

    def __init__(self, storage_path: Path | None = None):
        """
        Initialize the override manager.

        Args:
            storage_path: Path to JSON file for persistence. If None, uses data/config_overrides.json
        """
        if storage_path is None:
            storage_path = Path(__file__).parent.parent / "data" / "config_overrides.json"

        self.storage_path = storage_path
        self.overrides: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

        # Load existing overrides
        self._load()

    def _load(self) -> None:
        """Load overrides from JSON file."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    # Clean up expired entries on load
                    now = datetime.now(timezone.utc)
                    for key, override in list(data.items()):
                        if override.get("expires_at"):
                            expires_at = datetime.fromisoformat(override["expires_at"])
                            if expires_at <= now:
                                continue  # Skip expired
                        self.overrides[key] = override
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[CONFIG_OVERRIDES] Error loading: {e}")
                self.overrides = {}

    def _save(self) -> None:
        """Save overrides to JSON file."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, 'w') as f:
            json.dump(self.overrides, f, indent=2, default=str)

    def set_override(
        self,
        key: str,
        value: Any,
        duration_minutes: int | None = None,
    ) -> dict[str, Any]:
        """
        Set an override with optional expiry.

        Args:
            key: Config key to override
            value: New value
            duration_minutes: Minutes until expiry (None = permanent)

        Returns:
            Dict with expires_at (ISO string or None)
        """
        with self._lock:
            # Get default from definitions or existing override
            definition = CONFIG_DEFINITIONS.get(key, {})
            default = definition.get("default")

            now = datetime.now(timezone.utc)
            expires_at = None
            if duration_minutes is not None and duration_minutes > 0:
                expires_at = now + timedelta(minutes=duration_minutes)

            self.overrides[key] = {
                "value": value,
                "default": default,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "set_at": now.isoformat(),
            }

            self._save()

            return {
                "success": True,
                "key": key,
                "value": value,
                "expires_at": expires_at.isoformat() if expires_at else None,
            }

    def get_effective(self, key: str, default: T) -> tuple[T, bool]:
        """
        Get effective value for a config key.

        Args:
            key: Config key
            default: Default value to use if no override or expired

        Returns:
            Tuple of (effective_value, is_overridden)
        """
        with self._lock:
            override = self.overrides.get(key)
            if override is None:
                return default, False

            # Check expiry
            if override.get("expires_at"):
                expires_at = datetime.fromisoformat(override["expires_at"])
                if expires_at <= datetime.now(timezone.utc):
                    # Expired - clean up
                    del self.overrides[key]
                    self._save()
                    return default, False

            return override["value"], True

    def clear_override(self, key: str) -> dict[str, Any]:
        """
        Clear an override, reverting to default.

        Args:
            key: Config key to clear

        Returns:
            Dict with success status and current default
        """
        with self._lock:
            definition = CONFIG_DEFINITIONS.get(key, {})
            default = definition.get("default")

            if key in self.overrides:
                del self.overrides[key]
                self._save()

            return {
                "success": True,
                "key": key,
                "value": default,  # Now using default
            }

    def get_all_configs(self) -> dict[str, dict[str, Any]]:
        """
        Get all config definitions with current values and override status.

        Returns:
            Dict mapping config key to its full status
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            result = {}

            for key, definition in CONFIG_DEFINITIONS.items():
                override = self.overrides.get(key)
                is_overridden = False
                expires_in = None

                if override:
                    # Check expiry
                    if override.get("expires_at"):
                        expires_at = datetime.fromisoformat(override["expires_at"])
                        if expires_at > now:
                            is_overridden = True
                            expires_in = int((expires_at - now).total_seconds())
                        else:
                            # Expired
                            override = None
                    else:
                        # Permanent override
                        is_overridden = True

                effective_value = override["value"] if override and is_overridden else definition["default"]

                result[key] = {
                    "value": effective_value,
                    "default": definition["default"],
                    "overridden": is_overridden,
                    "expires_in": expires_in,
                    "type": definition["type"],
                    "category": definition["category"],
                    "description": definition.get("description", ""),
                }

                # Add min/max for numeric types
                if "min" in definition:
                    result[key]["min"] = definition["min"]
                if "max" in definition:
                    result[key]["max"] = definition["max"]

            return result

    def get_active_overrides(self) -> dict[str, dict[str, Any]]:
        """
        Get only currently active (non-expired) overrides.

        Returns:
            Dict of active overrides with time remaining
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            result = {}

            for key, override in list(self.overrides.items()):
                if override.get("expires_at"):
                    expires_at = datetime.fromisoformat(override["expires_at"])
                    if expires_at <= now:
                        # Expired - skip (and clean up)
                        del self.overrides[key]
                        continue
                    expires_in = int((expires_at - now).total_seconds())
                else:
                    expires_in = None  # Permanent

                result[key] = {
                    "value": override["value"],
                    "default": override.get("default"),
                    "expires_in": expires_in,
                    "set_at": override.get("set_at"),
                }

            # Save if we cleaned up any expired ones
            if len(result) < len(self.overrides):
                self._save()

            return result


# Singleton instance
_instance: ConfigOverrideManager | None = None


def get_override_manager() -> ConfigOverrideManager:
    """Get the singleton ConfigOverrideManager instance."""
    global _instance
    if _instance is None:
        _instance = ConfigOverrideManager()
    return _instance
