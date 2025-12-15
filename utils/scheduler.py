"""
Unified Scheduling System for Daemon Flows

Provides persistent tracking of:
- Flow cooldowns and run history
- Tavern quest completion times
- Daily limits (rally exhaustion)
- Arms Race block state

All state is persisted to data/daemon_schedule.json and survives daemon restarts.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Flow configurations: cooldown (seconds), idle required (seconds)
# These are defaults; can be overridden by config.py values
FLOW_CONFIGS = {
    "afk_rewards": {"cooldown": 3600, "idle_required": 300},
    "union_gifts": {"cooldown": 3600, "idle_required": 1200},
    "union_technology": {"cooldown": 3600, "idle_required": 1200},
    "bag_flow": {"cooldown": 3600, "idle_required": 300},
    "gift_box": {"cooldown": 3600, "idle_required": 300},
    "tavern_scan": {"cooldown": 1800, "idle_required": 300},
    "soldier_training": {"cooldown": 300, "idle_required": 300},
}


class DaemonScheduler:
    """
    Unified scheduling system for daemon flows.

    Persists all state to data/daemon_schedule.json:
    - Flow last_run times and daily history
    - Tavern quest completion times
    - Daily limits (rally exhaustion)
    - Arms Race block state
    """

    SCHEDULE_FILE = Path(__file__).parent.parent / "data" / "daemon_schedule.json"

    def __init__(self, config_overrides: dict = None):
        """
        Initialize scheduler, loading state from file.

        Args:
            config_overrides: Optional dict of flow_name -> {"cooldown": int, "idle_required": int}
                              to override default FLOW_CONFIGS
        """
        self.config_overrides = config_overrides or {}
        self.schedule = self._load_or_create()
        self._check_daily_reset()
        self._clear_expired_limits()

    # =========================================================================
    # Core Flow Operations
    # =========================================================================

    def is_flow_ready(self, flow_name: str, idle_seconds: float = 0) -> bool:
        """
        Check if a flow can run (cooldown passed + idle requirement met).

        Args:
            flow_name: Name of the flow (e.g., "bag_flow", "union_gifts")
            idle_seconds: Current idle time in seconds

        Returns:
            True if flow is ready to run
        """
        config = self._get_flow_config(flow_name)
        if config is None:
            logger.warning(f"[SCHEDULER] Unknown flow '{flow_name}', allowing by default")
            return True

        # Check idle requirement
        if idle_seconds < config["idle_required"]:
            logger.debug(f"[SCHEDULER] {flow_name}: idle {idle_seconds:.0f}s < required {config['idle_required']}s")
            return False

        # Check cooldown
        flow_data = self.schedule.get("flows", {}).get(flow_name, {})
        last_run_str = flow_data.get("last_run")

        if not last_run_str:
            logger.debug(f"[SCHEDULER] {flow_name}: never run, READY")
            return True  # Never run, ready to go

        try:
            last_run = datetime.fromisoformat(last_run_str)
            elapsed = (datetime.now() - last_run).total_seconds()
            cooldown = config["cooldown"]
            if elapsed >= cooldown:
                logger.debug(f"[SCHEDULER] {flow_name}: elapsed {elapsed:.0f}s >= cooldown {cooldown}s, READY")
                return True
            else:
                remaining = cooldown - elapsed
                logger.debug(f"[SCHEDULER] {flow_name}: {remaining:.0f}s remaining until ready")
                return False
        except (ValueError, TypeError):
            logger.warning(f"[SCHEDULER] {flow_name}: invalid last_run data, allowing")
            return True  # Invalid data, allow run

    def record_flow_run(self, flow_name: str) -> None:
        """
        Record that a flow ran now. Updates last_run and appends to history.

        Args:
            flow_name: Name of the flow
        """
        now = datetime.now()
        now_str = now.isoformat()

        if "flows" not in self.schedule:
            self.schedule["flows"] = {}

        if flow_name not in self.schedule["flows"]:
            config = self._get_flow_config(flow_name)
            self.schedule["flows"][flow_name] = {
                "last_run": None,
                "cooldown_seconds": config["cooldown"] if config else 3600,
                "idle_required": config["idle_required"] if config else 300,
                "history": [],
            }

        flow_data = self.schedule["flows"][flow_name]
        flow_data["last_run"] = now_str
        flow_data["history"].append(now_str)
        run_count = len(flow_data["history"])

        self.save()
        logger.info(f"[SCHEDULER] Recorded {flow_name} run #{run_count} at {now.strftime('%H:%M:%S')}")

    def get_next_eligible(self, flow_name: str) -> datetime | None:
        """
        Get when a flow will next be eligible (last_run + cooldown).

        Args:
            flow_name: Name of the flow

        Returns:
            datetime when flow becomes eligible, or None if ready now
        """
        config = self._get_flow_config(flow_name)
        if config is None:
            return None

        flow_data = self.schedule.get("flows", {}).get(flow_name, {})
        last_run_str = flow_data.get("last_run")

        if not last_run_str:
            return None  # Ready now

        try:
            last_run = datetime.fromisoformat(last_run_str)
            next_eligible = last_run + timedelta(seconds=config["cooldown"])
            if next_eligible <= datetime.now():
                return None  # Ready now
            return next_eligible
        except (ValueError, TypeError):
            return None

    def get_missed_flows(self) -> list[str]:
        """
        Get flows that are past due (for catchup on restart).

        Returns:
            List of flow names that are past their next_eligible time
        """
        missed = []
        for flow_name in FLOW_CONFIGS:
            if flow_name in self.config_overrides or flow_name in FLOW_CONFIGS:
                next_eligible = self.get_next_eligible(flow_name)
                if next_eligible is None:
                    # Check if it has ever run - if not and we have config, it's "missed"
                    flow_data = self.schedule.get("flows", {}).get(flow_name, {})
                    if not flow_data.get("last_run"):
                        missed.append(flow_name)
        return missed

    def get_flow_history(self, flow_name: str) -> list[datetime]:
        """
        Get today's run history for a flow.

        Args:
            flow_name: Name of the flow

        Returns:
            List of datetime objects for runs today
        """
        flow_data = self.schedule.get("flows", {}).get(flow_name, {})
        history = flow_data.get("history", [])

        result = []
        for dt_str in history:
            try:
                result.append(datetime.fromisoformat(dt_str))
            except (ValueError, TypeError):
                pass
        return result

    def get_flow_config(self, flow_name: str) -> dict | None:
        """Get the configuration for a flow (public accessor)."""
        return self._get_flow_config(flow_name)

    # =========================================================================
    # Tavern Quest Completions
    # =========================================================================

    def get_tavern_completions(self) -> list[datetime]:
        """
        Get scheduled tavern quest completion times.

        Returns:
            List of datetime objects for upcoming completions
        """
        tavern_data = self.schedule.get("tavern_quests", {})
        completions = tavern_data.get("completions", [])

        result = []
        for dt_str in completions:
            try:
                result.append(datetime.fromisoformat(dt_str))
            except (ValueError, TypeError):
                pass
        return result

    def set_tavern_completions(self, completions: list[datetime], dedup_threshold: int = 15) -> None:
        """
        Set tavern quest completion times, deduplicating within threshold.

        Args:
            completions: List of datetime objects
            dedup_threshold: Seconds within which to merge duplicates (default 15)
        """
        # Deduplicate
        sorted_completions = sorted(completions)
        deduped = []

        for dt in sorted_completions:
            is_duplicate = False
            for i, existing in enumerate(deduped):
                if abs((dt - existing).total_seconds()) <= dedup_threshold:
                    if dt < existing:
                        deduped[i] = dt
                    is_duplicate = True
                    break
            if not is_duplicate:
                deduped.append(dt)

        if "tavern_quests" not in self.schedule:
            self.schedule["tavern_quests"] = {}

        self.schedule["tavern_quests"]["last_scan"] = datetime.now().isoformat()
        self.schedule["tavern_quests"]["completions"] = [dt.isoformat() for dt in deduped]

        self.save()

        # Log each completion time
        if deduped:
            completion_strs = [dt.strftime('%H:%M:%S') for dt in deduped]
            logger.info(f"[SCHEDULER] Tavern completions updated: {completion_strs} (deduped {len(completions)} -> {len(deduped)})")
        else:
            logger.info(f"[SCHEDULER] Tavern completions cleared (no active quests)")

    def is_tavern_completion_imminent(self, buffer_seconds: int = 15) -> bool:
        """
        Check if any tavern quest completion is within buffer_seconds.

        Args:
            buffer_seconds: How many seconds before completion to trigger

        Returns:
            True if a quest is about to complete
        """
        completions = self.get_tavern_completions()
        now = datetime.now()

        for completion in completions:
            time_until = (completion - now).total_seconds()
            if 0 < time_until <= buffer_seconds:
                logger.info(f"[SCHEDULER] Tavern quest completing in {time_until:.0f}s! (at {completion.strftime('%H:%M:%S')})")
                return True
        return False

    def get_next_tavern_completion(self) -> datetime | None:
        """Get the next upcoming tavern quest completion time."""
        completions = self.get_tavern_completions()
        now = datetime.now()

        future = [dt for dt in completions if dt > now]
        if not future:
            return None
        return min(future)

    # =========================================================================
    # Daily Limits (Rally Exhaustion)
    # =========================================================================

    def is_exhausted(self, limit_name: str) -> bool:
        """
        Check if a daily limit is exhausted.

        Args:
            limit_name: Name of the limit (e.g., "rally_elite_zombie")

        Returns:
            True if limit is exhausted and not yet reset
        """
        limit_data = self.schedule.get("daily_limits", {}).get(limit_name)
        if not limit_data:
            return False

        resets_at_str = limit_data.get("resets_at")
        if not resets_at_str:
            return False

        try:
            resets_at = datetime.fromisoformat(resets_at_str)
            return datetime.now() < resets_at
        except (ValueError, TypeError):
            return False

    def mark_exhausted(self, limit_name: str, reset_time: datetime) -> None:
        """
        Mark a daily limit as exhausted.

        Args:
            limit_name: Name of the limit
            reset_time: When the limit resets (e.g., 02:00 UTC next day)
        """
        if "daily_limits" not in self.schedule:
            self.schedule["daily_limits"] = {}

        self.schedule["daily_limits"][limit_name] = {
            "exhausted_at": datetime.now().isoformat(),
            "resets_at": reset_time.isoformat(),
        }

        self.save()
        logger.info(f"[SCHEDULER] Daily limit '{limit_name}' EXHAUSTED until {reset_time.strftime('%Y-%m-%d %H:%M:%S')}")

    def _clear_expired_limits(self) -> None:
        """Clear daily limits that have expired (called on load)."""
        limits = self.schedule.get("daily_limits", {})
        now = datetime.now()
        expired = []

        for limit_name, limit_data in limits.items():
            resets_at_str = limit_data.get("resets_at")
            if resets_at_str:
                try:
                    resets_at = datetime.fromisoformat(resets_at_str)
                    if now >= resets_at:
                        expired.append(limit_name)
                except (ValueError, TypeError):
                    expired.append(limit_name)

        for limit_name in expired:
            del self.schedule["daily_limits"][limit_name]
            logger.info(f"Cleared expired daily limit: {limit_name}")

        if expired:
            self.save()

    @staticmethod
    def get_next_server_reset() -> datetime:
        """
        Get the next server day reset time (02:00 UTC).

        Returns:
            datetime of next server reset
        """
        import pytz
        utc = pytz.UTC
        now = datetime.now(utc)
        reset_hour = 2  # 02:00 UTC

        # Calculate next reset
        next_reset = now.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
        if now.hour >= reset_hour:
            next_reset += timedelta(days=1)

        # Return as naive datetime (local time equivalent)
        return next_reset.replace(tzinfo=None)

    # =========================================================================
    # Arms Race Tracking
    # =========================================================================

    def get_arms_race_state(self) -> dict:
        """
        Get current Arms Race block state.

        Returns:
            Dict with keys: current_block_start, beast_training_rallies,
            beast_training_uses, enhance_hero_done, union_boss_mode_until
        """
        return self.schedule.get("arms_race", {}).copy()

    def update_arms_race_state(self, **kwargs) -> None:
        """
        Update Arms Race block state.

        Args:
            **kwargs: Key-value pairs to update (e.g., beast_training_rallies=5)
        """
        if "arms_race" not in self.schedule:
            self.schedule["arms_race"] = {}

        for key, value in kwargs.items():
            if isinstance(value, datetime):
                self.schedule["arms_race"][key] = value.isoformat()
            else:
                self.schedule["arms_race"][key] = value

        self.save()

    def reset_arms_race_block(self, block_start: datetime) -> None:
        """
        Reset Arms Race state for a new 4-hour block.

        Args:
            block_start: Start time of the new block
        """
        self.schedule["arms_race"] = {
            "current_block_start": block_start.isoformat(),
            "beast_training_rallies": 0,
            "beast_training_uses": 0,
            "enhance_hero_done": False,
            "union_boss_mode_until": None,
        }
        self.save()
        logger.info(f"Reset Arms Race state for block starting {block_start}")

    # =========================================================================
    # Persistence
    # =========================================================================

    def save(self) -> None:
        """Save schedule to file with atomic write."""
        self.schedule["last_updated"] = datetime.now().isoformat()

        # Ensure directory exists
        self.SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to temp file, then rename
        fd, temp_path = tempfile.mkstemp(
            dir=self.SCHEDULE_FILE.parent,
            prefix="daemon_schedule_",
            suffix=".tmp"
        )
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(self.schedule, f, indent=2)

            # Atomic rename (works on same filesystem)
            os.replace(temp_path, self.SCHEDULE_FILE)
        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def _load_or_create(self) -> dict:
        """Load schedule from file or create new."""
        if self.SCHEDULE_FILE.exists():
            try:
                with open(self.SCHEDULE_FILE, 'r') as f:
                    data = json.load(f)
                logger.info(f"Loaded schedule from {self.SCHEDULE_FILE}")
                return data
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load schedule: {e}, creating new")

        return self._create_empty_schedule()

    def _create_empty_schedule(self) -> dict:
        """Create empty schedule structure."""
        return {
            "version": 1,
            "last_updated": datetime.now().isoformat(),
            "history_date": date.today().isoformat(),
            "flows": {},
            "tavern_quests": {
                "last_scan": None,
                "completions": [],
            },
            "daily_limits": {},
            "arms_race": {},
        }

    def _check_daily_reset(self) -> None:
        """Reset daily history if it's a new day."""
        history_date_str = self.schedule.get("history_date")
        today = date.today().isoformat()

        if history_date_str != today:
            logger.info(f"New day detected ({history_date_str} -> {today}), clearing history")

            # Clear history arrays for all flows
            for flow_name, flow_data in self.schedule.get("flows", {}).items():
                flow_data["history"] = []

            self.schedule["history_date"] = today
            self.save()

    def _get_flow_config(self, flow_name: str) -> dict | None:
        """Get flow configuration (overrides take precedence)."""
        if flow_name in self.config_overrides:
            return self.config_overrides[flow_name]
        if flow_name in FLOW_CONFIGS:
            return FLOW_CONFIGS[flow_name]
        return None

    # =========================================================================
    # Logging / Visibility
    # =========================================================================

    def log_status(self) -> None:
        """Log summary of all flows: last run, next eligible, run count today."""
        logger.info("=== SCHEDULER STATUS ===")

        # Flows
        for flow_name in sorted(FLOW_CONFIGS.keys()):
            flow_data = self.schedule.get("flows", {}).get(flow_name, {})
            last_run_str = flow_data.get("last_run", "never")
            history = flow_data.get("history", [])
            next_eligible = self.get_next_eligible(flow_name)

            if last_run_str != "never":
                try:
                    last_run = datetime.fromisoformat(last_run_str)
                    last_run_str = last_run.strftime("%H:%M:%S")
                except (ValueError, TypeError):
                    pass

            next_str = "ready" if next_eligible is None else next_eligible.strftime("%H:%M:%S")
            logger.info(f"  {flow_name}: last={last_run_str}, next={next_str}, today={len(history)}")

        # Tavern quests
        next_tavern = self.get_next_tavern_completion()
        if next_tavern:
            logger.info(f"  tavern_quest: next completion at {next_tavern.strftime('%H:%M:%S')}")

        # Daily limits
        for limit_name, limit_data in self.schedule.get("daily_limits", {}).items():
            resets_at_str = limit_data.get("resets_at", "?")
            logger.info(f"  limit/{limit_name}: exhausted until {resets_at_str}")

        # Arms Race
        arms_race = self.schedule.get("arms_race", {})
        if arms_race:
            block_start = arms_race.get("current_block_start", "?")
            rallies = arms_race.get("beast_training_rallies", 0)
            uses = arms_race.get("beast_training_uses", 0)
            hero_done = arms_race.get("enhance_hero_done", False)
            logger.info(f"  arms_race: block={block_start}, rallies={rallies}, uses={uses}, hero_done={hero_done}")

        logger.info("========================")


# Singleton instance for easy access
_scheduler_instance: DaemonScheduler | None = None


def get_scheduler(config_overrides: dict = None) -> DaemonScheduler:
    """Get or create the singleton scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = DaemonScheduler(config_overrides)
    return _scheduler_instance


def reset_scheduler() -> None:
    """Reset the singleton instance (for testing)."""
    global _scheduler_instance
    _scheduler_instance = None
