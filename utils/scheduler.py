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

import functools
import json
import logging
import os
import tempfile
import threading
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from config import IDLE_THRESHOLD

logger = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable[..., Any])


def _locked(method: _F) -> _F:
    """Serialize access to scheduler state.

    The daemon thread, flow worker threads, and the WebSocket server thread
    all mutate self.schedule and save() concurrently; without a lock the
    interleaved read-modify-write sequences lose updates and json.dump can
    crash on a dict mutated mid-serialization.
    """
    @functools.wraps(method)
    def wrapper(self: "DaemonScheduler", *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper  # type: ignore[return-value]

# Flow configurations: cooldown (seconds), idle required (seconds)
# All flows use IDLE_THRESHOLD from config.py as the default idle requirement
# Exception: pre_beast_stamina_claim ignores idle (time-critical, must run in 6-min window)
FLOW_CONFIGS = {
    "afk_rewards": {"cooldown": 3600, "idle_required": IDLE_THRESHOLD},
    "union_gifts": {"cooldown": 3600, "idle_required": IDLE_THRESHOLD},
    "union_technology": {"cooldown": 3600, "idle_required": IDLE_THRESHOLD},
    "bag_flow": {"cooldown": 3600, "idle_required": IDLE_THRESHOLD},
    "gift_box": {"cooldown": 3600, "idle_required": IDLE_THRESHOLD},
    "tavern_quest": {"cooldown": 1800, "idle_required": IDLE_THRESHOLD},
    "pre_beast_stamina_claim": {"cooldown": 14400, "idle_required": 0},  # 4hr cooldown, NO idle (time-critical)
    "end_of_day_stamina_claim": {"cooldown": 86400, "idle_required": 0},  # 24hr cooldown, NO idle (time-critical)
    # Harvest flows - 10s cooldown to prevent spam-clicking same bubble
    "corn_harvest": {"cooldown": 10, "idle_required": 0},
    "gold_coin": {"cooldown": 10, "idle_required": 0},
    "iron_bar": {"cooldown": 10, "idle_required": 0},
    "gem": {"cooldown": 10, "idle_required": 0},
    "cabbage": {"cooldown": 10, "idle_required": 0},
    "equipment_enhancement": {"cooldown": 10, "idle_required": 0},
    # Beast Training phases - no cooldown (block-based tracking in arms_race_state)
    "beast_training_hour_mark": {"cooldown": 0, "idle_required": IDLE_THRESHOLD},  # 5 min idle
    "beast_training_last_hour": {"cooldown": 0, "idle_required": IDLE_THRESHOLD},    # 5 min idle
    "beast_training_mid_check": {"cooldown": 0, "idle_required": IDLE_THRESHOLD},    # 5 min idle (30 min mark)
    # Class Skills - 24 hour cooldown (matches in-game cooldown)
    "quick_production": {"cooldown": 86400, "idle_required": IDLE_THRESHOLD},  # 24hr cooldown
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
    MAX_FLOW_HISTORY_SIZE = 5000      # Per-flow cap to prevent unbounded growth
    FLOW_HISTORY_MAX_AGE_DAYS = 2     # Keep a small recent buffer only

    def __init__(self, config_overrides: dict[str, Any] | None = None) -> None:
        """
        Initialize scheduler, loading state from file.

        Args:
            config_overrides: Optional dict of flow_name -> {"cooldown": int, "idle_required": int}
                              to override default FLOW_CONFIGS
        """
        self._lock = threading.RLock()  # Must exist before any @_locked method runs
        self.config_overrides = config_overrides or {}
        self.schedule = self._load_or_create()
        self._check_daily_reset()
        self._clear_expired_limits()

    # =========================================================================
    # Core Flow Operations
    # =========================================================================

    @_locked
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

    @_locked
    def record_flow_run(self, flow_name: str, cooldown_override: int | None = None) -> None:
        """
        Record that a flow ran now. Updates last_run and appends to history.

        Args:
            flow_name: Name of the flow
            cooldown_override: If set, use this cooldown instead of normal.
                              Used for skipped flows to set a short retry cooldown.
        """
        now = datetime.now()

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

        # If cooldown_override, backdate last_run so next ready = now + override
        if cooldown_override is not None:
            normal_cooldown = flow_data.get("cooldown_seconds", 3600)
            adjusted = now - timedelta(seconds=(normal_cooldown - cooldown_override))
            flow_data["last_run"] = adjusted.isoformat()
        else:
            flow_data["last_run"] = now.isoformat()
        flow_data["history"].append(now.isoformat())
        run_count = len(flow_data["history"])

        self.save()
        logger.info(f"[SCHEDULER] Recorded {flow_name} run #{run_count} at {now.strftime('%H:%M:%S')}")

    @_locked
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

    @_locked
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

    @_locked
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

    def get_flow_config(self, flow_name: str) -> dict[str, Any] | None:
        """Get the configuration for a flow (public accessor)."""
        return self._get_flow_config(flow_name)

    # =========================================================================
    # Tavern Quest Completions
    # =========================================================================

    @_locked
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

    @_locked
    def set_tavern_completions(self, completions: list[datetime], dedup_threshold: int = 2) -> None:
        """
        Set tavern quest completion times, deduplicating within threshold.

        Args:
            completions: List of datetime objects
            dedup_threshold: Seconds within which to merge duplicates (default 15)
        """
        # Deduplicate
        sorted_completions = sorted(completions)
        deduped: list[datetime] = []

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

    @_locked
    def is_tavern_completion_imminent(self, buffer_seconds: int = 5, overdue_grace_seconds: int = 600) -> bool:
        """
        Check if any tavern quest completion is imminent or recently overdue.

        Args:
            buffer_seconds: How many seconds before completion to trigger
            overdue_grace_seconds: How many seconds after completion to still trigger (for missed claims)

        Returns:
            True if a quest is about to complete OR recently overdue (needs claiming)
        """
        completions = self.get_tavern_completions()
        now = datetime.now()

        for completion in completions:
            time_until = (completion - now).total_seconds()
            # Trigger if: imminent (within buffer_seconds) OR overdue (within grace period)
            if -overdue_grace_seconds <= time_until <= buffer_seconds:
                if time_until > 0:
                    logger.info(f"[SCHEDULER] Tavern quest completing in {time_until:.0f}s! (at {completion.strftime('%H:%M:%S')})")
                else:
                    logger.info(f"[SCHEDULER] Tavern quest OVERDUE by {-time_until:.0f}s! (was {completion.strftime('%H:%M:%S')})")
                return True
        return False

    @_locked
    def get_next_tavern_completion(self) -> datetime | None:
        """Get the next upcoming tavern quest completion time."""
        completions = self.get_tavern_completions()
        now = datetime.now()

        future = [dt for dt in completions if dt > now]
        if not future:
            return None
        return min(future)

    @_locked
    def get_last_tavern_dispatch(self) -> datetime | None:
        """Get last tavern quest dispatch time."""
        ts = self.schedule.get("tavern_quests", {}).get("last_dispatch")
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            return None

    @_locked
    def record_tavern_dispatch(self) -> None:
        """Record that a tavern quest was dispatched now."""
        if "tavern_quests" not in self.schedule:
            self.schedule["tavern_quests"] = {}
        self.schedule["tavern_quests"]["last_dispatch"] = datetime.now().isoformat()
        self.save()
        logger.info("[SCHEDULER] Recorded tavern dispatch")

    @_locked
    def record_tavern_claims(self, count: int) -> None:
        """Record tavern quest claims. Adds to today's total."""
        if "tavern_quests" not in self.schedule:
            self.schedule["tavern_quests"] = {}

        # Check if we need to reset (new day)
        claims_date = self.schedule["tavern_quests"].get("claims_date")
        today = date.today().isoformat()

        if claims_date != today:
            # New day - reset counter
            self.schedule["tavern_quests"]["claims_today"] = 0
            self.schedule["tavern_quests"]["claims_date"] = today

        # Add to today's count
        current = self.schedule["tavern_quests"].get("claims_today", 0)
        self.schedule["tavern_quests"]["claims_today"] = current + count
        self.save()
        logger.info(f"[SCHEDULER] Recorded {count} tavern claim(s), today total: {current + count}")

    @_locked
    def get_tavern_claims_today(self) -> int:
        """Get number of tavern quests claimed today."""
        tavern_data = self.schedule.get("tavern_quests", {})
        claims_date = tavern_data.get("claims_date")

        # Check if it's still today
        if claims_date != date.today().isoformat():
            return 0

        return tavern_data.get("claims_today", 0)

    @_locked
    def set_tavern_claims_today(self, count: int) -> None:
        """Force-set today's tavern claims counter to an exact value."""
        if count < 0:
            raise ValueError("count must be >= 0")

        if "tavern_quests" not in self.schedule:
            self.schedule["tavern_quests"] = {}

        today = date.today().isoformat()
        self.schedule["tavern_quests"]["claims_date"] = today
        self.schedule["tavern_quests"]["claims_today"] = int(count)
        self.save()
        logger.info(f"[SCHEDULER] Force-set tavern claims for {today} to {count}")

    @_locked
    def is_tavern_dispatch_exhausted_today(self) -> bool:
        """True if a dispatch attempt today found zero Go buttons.

        Auto-resets at midnight via date comparison: if the stored date isn't
        today, the flag is treated as cleared. Dispatch attempts (both
        standalone and the scan follow-up) skip when this is True. Claim
        and ally flows are unaffected.
        """
        stored_date = self.schedule.get("tavern_quests", {}).get("dispatch_exhausted_date")
        return stored_date == date.today().isoformat()

    @_locked
    def mark_tavern_dispatch_exhausted_today(self) -> None:
        """Record that today's dispatch search came up empty."""
        if "tavern_quests" not in self.schedule:
            self.schedule["tavern_quests"] = {}
        today = date.today().isoformat()
        self.schedule["tavern_quests"]["dispatch_exhausted_date"] = today
        self.save()
        logger.info(f"[SCHEDULER] Marked tavern dispatch exhausted for {today}")

    @_locked
    def clear_tavern_dispatch_exhausted_today(self) -> None:
        """Manually clear today's exhaustion flag (e.g. from dashboard)."""
        tq = self.schedule.get("tavern_quests")
        if not tq or "dispatch_exhausted_date" not in tq:
            return
        del tq["dispatch_exhausted_date"]
        self.save()
        logger.info("[SCHEDULER] Cleared tavern dispatch exhaustion flag")

    @_locked
    def record_tavern_refresh(self) -> None:
        """Increment today's tavern-refresh counter (auto-reset at midnight).

        Mirrors the claims_today pattern. Used by the auto-refresh loop in
        _dispatch_in_open_tavern() to track how many Refresh clicks the bot
        made today across all dispatch runs. Useful for the dashboard and
        for future per-day rate-limiting.
        """
        if "tavern_quests" not in self.schedule:
            self.schedule["tavern_quests"] = {}
        today = date.today().isoformat()
        if self.schedule["tavern_quests"].get("refreshes_date") != today:
            self.schedule["tavern_quests"]["refreshes_date"] = today
            self.schedule["tavern_quests"]["refreshes_today"] = 0
        self.schedule["tavern_quests"]["refreshes_today"] = (
            self.schedule["tavern_quests"].get("refreshes_today", 0) + 1
        )
        self.save()

    @_locked
    def get_tavern_refreshes_today(self) -> int:
        tq = self.schedule.get("tavern_quests", {})
        if tq.get("refreshes_date") != date.today().isoformat():
            return 0
        return int(tq.get("refreshes_today", 0))

    @_locked
    def record_paid_tavern_refresh(self) -> None:
        """Increment today's PAID (diamond) tavern-refresh counter.

        Separate from record_tavern_refresh (which counts all refresh clicks):
        this tracks only refreshes that cost diamonds via the 'Spend 100
        Diamonds?' confirmation, so the daily spend can be capped. Auto-resets
        at midnight.
        """
        if "tavern_quests" not in self.schedule:
            self.schedule["tavern_quests"] = {}
        today = date.today().isoformat()
        if self.schedule["tavern_quests"].get("paid_refreshes_date") != today:
            self.schedule["tavern_quests"]["paid_refreshes_date"] = today
            self.schedule["tavern_quests"]["paid_refreshes_today"] = 0
        self.schedule["tavern_quests"]["paid_refreshes_today"] = (
            self.schedule["tavern_quests"].get("paid_refreshes_today", 0) + 1
        )
        self.save()

    @_locked
    def get_paid_tavern_refreshes_today(self) -> int:
        tq = self.schedule.get("tavern_quests", {})
        if tq.get("paid_refreshes_date") != date.today().isoformat():
            return 0
        return int(tq.get("paid_refreshes_today", 0))

    @_locked
    def record_tavern_visible_counts(
        self,
        gold_visible: int,
        question_visible: int,
        dispatchable_visible: int,
        directly_startable_visible: int,
        refreshes_this_attempt: int = 0,
    ) -> None:
        """Record the first-frame counts captured during a dispatch attempt.

        Three-tier model (see docs/tavern_quests.md):
        - dispatchable: total Go buttons visible, regardless of quest type.
          This is the universe of quest slots. Tier 1.
        - directly_startable: gold-scroll + (question-mark if not a VS skip
          day) -- the subset our code currently knows how to click Go on
          right now. Tier 2.
        - The difference (dispatchable - directly_startable) is the count
          of "refresh candidates" -- visible Gos of unsupported types that
          the player could in-game-refresh to potentially roll into a
          supported type. The dashboard computes this; we don't store it.

        gold_visible / question_visible are sub-components for debugging /
        UI subtitles.
        """
        if "tavern_quests" not in self.schedule:
            self.schedule["tavern_quests"] = {}
        self.schedule["tavern_quests"]["visible_counts"] = {
            "gold": int(gold_visible),
            "question": int(question_visible),
            "dispatchable": int(dispatchable_visible),
            "directly_startable": int(directly_startable_visible),
            "refreshes_this_attempt": int(refreshes_this_attempt),
            "checked_at": datetime.now().isoformat(),
        }
        self.save()

    @_locked
    def get_tavern_visible_counts(self) -> dict[str, Any] | None:
        """Return the most recent visible-Go counts, or None if never set."""
        return self.schedule.get("tavern_quests", {}).get("visible_counts")

    # =========================================================================
    # Daily Limits (Rally Exhaustion)
    # =========================================================================

    @_locked
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
            # Compare using UTC time (resets_at is stored in UTC)
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            return now_utc < resets_at
        except (ValueError, TypeError):
            return False

    @_locked
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

    @_locked
    def _clear_expired_limits(self) -> None:
        """Clear daily limits that have expired (called on load)."""
        limits = self.schedule.get("daily_limits", {})
        # Use UTC time for comparison (resets_at is stored in UTC)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
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
        now = datetime.now(timezone.utc)
        reset_hour = 2  # 02:00 UTC

        # Calculate next reset
        next_reset = now.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
        if now.hour >= reset_hour:
            next_reset += timedelta(days=1)

        # Return as naive datetime (local time equivalent)
        return next_reset.replace(tzinfo=None)

    # =========================================================================
    # Overlord First-Kill Gate
    # =========================================================================

    @_locked
    def mark_overlord_first_kill_done(self, level: int) -> None:
        """Record that a team was successfully sent to a qualifying (Lv190+) Zombie Overlord."""
        self.schedule["overlord_first_kill"] = {
            "done_at": datetime.now(timezone.utc).isoformat(),
            "level": level,
        }
        self.save()
        logger.info(f"Overlord first-kill gate satisfied (Lv.{level})")

    @_locked
    def is_overlord_first_kill_done(self) -> bool:
        """True if a qualifying overlord join happened since the last server reset (02:00 UTC)."""
        entry = self.schedule.get("overlord_first_kill")
        if not entry or not entry.get("done_at"):
            return False
        try:
            done_at = datetime.fromisoformat(entry["done_at"])
        except (ValueError, TypeError):
            return False
        if done_at.tzinfo is None:
            done_at = done_at.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        reset_hour = 2  # Must match get_next_server_reset
        last_reset = now.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
        if now.hour < reset_hour:
            last_reset -= timedelta(days=1)
        return done_at >= last_reset

    # =========================================================================
    # Arms Race Tracking
    # =========================================================================

    @_locked
    def get_arms_race_state(self) -> dict[str, Any]:
        """
        Get current Arms Race block state.

        Returns:
            Dict with keys: current_block_start, beast_training_rallies,
            beast_training_uses, enhance_hero_done, union_boss_mode_until
        """
        result = self.schedule.get("arms_race", {})
        return dict(result) if result else {}

    @_locked
    def update_arms_race_state(self, **kwargs: Any) -> None:
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

    @_locked
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
    # Zombie Mode (for Beast Training)
    # =========================================================================

    @_locked
    def get_zombie_mode(self) -> tuple[str, datetime | None]:
        """
        Get current zombie mode and expiry.

        Returns:
            (mode, expires) tuple. mode is "elite"|"gold"|"food"|"iron_mine".
            expires is None if permanent or not set.
        """
        state = self.schedule.get("zombie_mode", {})
        mode = state.get("mode", "elite")
        expires_str = state.get("expires")

        if expires_str:
            try:
                expires = datetime.fromisoformat(expires_str)
                # Handle timezone-aware comparison
                now = datetime.now(timezone.utc)
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if now > expires:
                    # Expired, revert to elite
                    self.clear_zombie_mode()
                    logger.info("Zombie mode expired, reverting to elite")
                    return "elite", None
                return mode, expires
            except (ValueError, TypeError):
                return "elite", None
        return mode, None

    @_locked
    def set_zombie_mode(self, mode: str, hours: float) -> datetime:
        """
        Set zombie mode for N hours.

        Args:
            mode: "elite"|"gold"|"food"|"iron_mine"
            hours: Duration in hours

        Returns:
            Expiry datetime
        """
        expires = datetime.now(timezone.utc) + timedelta(hours=hours)
        self.schedule["zombie_mode"] = {
            "mode": mode,
            "expires": expires.isoformat(),
            "set_at": datetime.now(timezone.utc).isoformat(),
        }
        self.save()
        logger.info(f"Zombie mode set to '{mode}' for {hours}h (expires {expires})")
        return expires

    @_locked
    def clear_zombie_mode(self) -> None:
        """Clear zombie mode, revert to elite."""
        self.schedule.pop("zombie_mode", None)
        self.save()
        logger.info("Zombie mode cleared, reverted to elite")

    # =========================================================================
    # REINFORCE MODE - Loop reinforce camp, block other flows except handshake
    # =========================================================================

    @_locked
    def get_reinforce_mode(self) -> tuple[bool, datetime | None]:
        """
        Get current reinforce mode status.

        Returns:
            (active, expires) tuple. active=True if looping reinforce.
            expires is None if not set or permanent.
        """
        state = self.schedule.get("reinforce_mode", {})
        active = state.get("active", False)
        expires_str = state.get("expires")

        if not active:
            return False, None

        if expires_str:
            try:
                expires = datetime.fromisoformat(expires_str)
                now = datetime.now(timezone.utc)
                if now > expires:
                    # Expired, clear mode
                    self.clear_reinforce_mode()
                    logger.info("Reinforce mode expired")
                    return False, None
                return True, expires
            except (ValueError, TypeError):
                return False, None
        return active, None

    @_locked
    def set_reinforce_mode(self, hours: float | None = None) -> datetime | None:
        """
        Enable reinforce mode for N hours.

        Args:
            hours: Duration in hours. None = until manually stopped.

        Returns:
            Expiry datetime, or None if permanent.
        """
        expires = None
        if hours:
            expires = datetime.now(timezone.utc) + timedelta(hours=hours)
            self.schedule["reinforce_mode"] = {
                "active": True,
                "expires": expires.isoformat(),
                "set_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            self.schedule["reinforce_mode"] = {
                "active": True,
                "set_at": datetime.now(timezone.utc).isoformat(),
            }
        self.save()
        logger.info(f"Reinforce mode enabled (expires: {expires})")
        return expires

    @_locked
    def clear_reinforce_mode(self) -> None:
        """Clear reinforce mode, stop looping."""
        self.schedule.pop("reinforce_mode", None)
        self.save()
        logger.info("Reinforce mode cleared")

    # =========================================================================
    # TAVERN STEAL SNIPER MODE - watch for Steal button, spam-click at timer end
    # Blocks all other flows except tavern quest claims (mode exits for those).
    # =========================================================================

    @_locked
    def get_sniper_mode(self) -> tuple[bool, datetime | None]:
        """
        Get current steal sniper mode status.

        Returns:
            (active, expires) tuple. expires is None if not set or permanent.
        """
        state = self.schedule.get("sniper_mode", {})
        active = state.get("active", False)
        expires_str = state.get("expires")

        if not active:
            return False, None

        if expires_str:
            try:
                expires = datetime.fromisoformat(expires_str)
                now = datetime.now(timezone.utc)
                if now > expires:
                    self.clear_sniper_mode()
                    logger.info("Sniper mode expired")
                    return False, None
                return True, expires
            except (ValueError, TypeError):
                return False, None
        return active, None

    @_locked
    def set_sniper_mode(self, hours: float | None = None) -> datetime | None:
        """
        Enable steal sniper mode for N hours.

        Args:
            hours: Duration in hours. None = until manually stopped.

        Returns:
            Expiry datetime, or None if permanent.
        """
        expires = None
        if hours:
            expires = datetime.now(timezone.utc) + timedelta(hours=hours)
            self.schedule["sniper_mode"] = {
                "active": True,
                "expires": expires.isoformat(),
                "set_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            self.schedule["sniper_mode"] = {
                "active": True,
                "set_at": datetime.now(timezone.utc).isoformat(),
            }
        self.save()
        logger.info(f"Sniper mode enabled (expires: {expires})")
        return expires

    @_locked
    def clear_sniper_mode(self) -> None:
        """Clear steal sniper mode."""
        self.schedule.pop("sniper_mode", None)
        self.save()
        logger.info("Sniper mode cleared")

    @_locked
    def record_arms_race_progress(self, event: str, points: int, chest3_target: int | None, block_start: str) -> None:
        """
        Record Arms Race progress for data collection.

        Stores progress in a history array for all events, useful for:
        - Tracking which events we hit chest3 on
        - Learning chest3 thresholds for events we haven't documented
        - Debugging automation issues

        Args:
            event: Event name (e.g., "Mystic Beast Training", "City Construction")
            points: Current points OCR'd from panel
            chest3_target: Chest3 threshold (None if unknown)
            block_start: Block start time as ISO string
        """
        if "arms_race_progress" not in self.schedule:
            self.schedule["arms_race_progress"] = []

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "points": points,
            "chest3_target": chest3_target,
            "block_start": block_start,
        }

        # Add to history (keep last 100 entries)
        self.schedule["arms_race_progress"].append(entry)
        if len(self.schedule["arms_race_progress"]) > 100:
            self.schedule["arms_race_progress"] = self.schedule["arms_race_progress"][-100:]

        self.save()
        logger.info(f"[SCHEDULER] Recorded {event} progress: {points} pts (chest3={chest3_target})")

    # =========================================================================
    # Event Log (for Timeline)
    # =========================================================================

    MAX_EVENT_LOG_SIZE = 500  # Keep last 500 events

    @_locked
    def record_event(
        self,
        flow_name: str,
        status: str,
        duration: float | None = None,
        result: dict[str, Any] | None = None,
        category: str = "maintenance",
        is_critical: bool = False,
    ) -> None:
        """
        Record a flow execution to the persistent event log.

        Used by the timeline feature to show past automation events.

        Args:
            flow_name: Name of the flow (e.g., "elite_zombie", "tavern_quest")
            status: "completed" | "failed" | "skipped"
            duration: Execution time in seconds (optional)
            result: Flow-specific result data (optional)
            category: "arms_race" | "combat" | "quest" | "maintenance"
            is_critical: Whether this was a critical flow
        """
        if "event_log" not in self.schedule:
            self.schedule["event_log"] = []

        now = datetime.now()
        event_id = f"{now.isoformat()}_{flow_name}"

        entry = {
            "id": event_id,
            "flow_name": flow_name,
            "timestamp": now.isoformat(),
            "status": status,
            "duration_seconds": duration,
            "result": result,
            "category": category,
            "is_critical": is_critical,
        }

        self.schedule["event_log"].append(entry)

        # Prune if over limit
        if len(self.schedule["event_log"]) > self.MAX_EVENT_LOG_SIZE:
            self.schedule["event_log"] = self.schedule["event_log"][-self.MAX_EVENT_LOG_SIZE:]

        self.save()
        duration_str = f" ({duration:.1f}s)" if duration else ""
        logger.debug(f"[SCHEDULER] Event logged: {flow_name} [{status}]{duration_str}")

    @_locked
    def get_events_in_range(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        """
        Get all events within a time range.

        Args:
            start: Start of range (inclusive)
            end: End of range (inclusive)

        Returns:
            List of event dicts sorted by timestamp
        """
        events = self.schedule.get("event_log", [])
        result = []

        for event in events:
            try:
                timestamp = datetime.fromisoformat(event["timestamp"])
                if start <= timestamp <= end:
                    result.append(event)
            except (ValueError, TypeError, KeyError):
                continue

        return sorted(result, key=lambda e: e["timestamp"])

    @_locked
    def get_recent_events(self, hours: int = 12) -> list[dict[str, Any]]:
        """
        Get events from the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            List of event dicts sorted by timestamp
        """
        end = datetime.now()
        start = end - timedelta(hours=hours)
        return self.get_events_in_range(start, end)

    # =========================================================================
    # Daemon Runtime State
    # =========================================================================

    @_locked
    def get_daemon_state(self) -> dict[str, Any]:
        """
        Get all daemon runtime state.

        Returns:
            Dict with all persisted daemon state (stamina_history, barracks_state, etc.)
        """
        result = self.schedule.get("daemon_state", {})
        return dict(result) if result else {}

    @_locked
    def update_daemon_state(self, **kwargs: Any) -> None:
        """
        Update daemon runtime state.

        Args:
            **kwargs: Key-value pairs to update (e.g., stamina_history=[120, 118])
        """
        if "daemon_state" not in self.schedule:
            self.schedule["daemon_state"] = {}

        for key, value in kwargs.items():
            if isinstance(value, datetime):
                self.schedule["daemon_state"][key] = value.isoformat()
            elif isinstance(value, set):
                self.schedule["daemon_state"][key] = list(value)
            else:
                self.schedule["daemon_state"][key] = value

        self.save()

    @_locked
    def clear_daemon_state(self) -> None:
        """Clear all daemon runtime state (for clean restart)."""
        self.schedule["daemon_state"] = {}
        self.save()
        logger.info("Cleared daemon runtime state")

    # =========================================================================
    # Persistence
    # =========================================================================

    @_locked
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
                # Use custom encoder to handle enums
                json.dump(self.schedule, f, indent=2, default=self._json_serialize)

            # Atomic rename (works on same filesystem)
            os.replace(temp_path, self.SCHEDULE_FILE)
        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    @staticmethod
    def _json_serialize(obj: Any) -> str:
        """Custom JSON serializer for objects not serializable by default."""
        from enum import Enum
        if isinstance(obj, Enum):
            return obj.name
        if hasattr(obj, 'isoformat'):  # datetime
            return obj.isoformat()  # type: ignore[no-any-return]
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    def _load_or_create(self) -> dict[str, Any]:
        """Load schedule from file or create new."""
        if self.SCHEDULE_FILE.exists():
            try:
                with open(self.SCHEDULE_FILE, 'r') as f:
                    data: dict[str, Any] = json.load(f)
                logger.info(f"Loaded schedule from {self.SCHEDULE_FILE}")
                return data
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load schedule: {e}, creating new")

        return self._create_empty_schedule()

    def _create_empty_schedule(self) -> dict[str, Any]:
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
            "daemon_state": {},
            "event_log": [],
        }

    @_locked
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

    @_locked
    def _prune_flow_histories(self) -> int:
        """
        Prune invalid/stale/oversized per-flow history arrays.

        Returns:
            Number of history entries removed across all flows.
        """
        flows = self.schedule.get("flows", {})
        if not isinstance(flows, dict):
            return 0

        cutoff = datetime.now() - timedelta(days=self.FLOW_HISTORY_MAX_AGE_DAYS)
        removed_entries = 0

        for _, flow_data in flows.items():
            if not isinstance(flow_data, dict):
                continue

            history = flow_data.get("history", [])
            if not isinstance(history, list) or not history:
                continue

            pruned_history: list[str] = []
            for dt_str in history:
                if not isinstance(dt_str, str):
                    removed_entries += 1
                    continue
                try:
                    dt = datetime.fromisoformat(dt_str)
                except (ValueError, TypeError):
                    removed_entries += 1
                    continue

                if dt < cutoff:
                    removed_entries += 1
                    continue

                pruned_history.append(dt_str)

            if len(pruned_history) > self.MAX_FLOW_HISTORY_SIZE:
                overflow = len(pruned_history) - self.MAX_FLOW_HISTORY_SIZE
                removed_entries += overflow
                pruned_history = pruned_history[-self.MAX_FLOW_HISTORY_SIZE:]

            if pruned_history != history:
                flow_data["history"] = pruned_history

        return removed_entries

    @_locked
    def run_periodic_maintenance(self) -> dict[str, int | bool]:
        """
        Run lightweight scheduler maintenance for long-lived daemon processes.

        Returns:
            {"day_reset": bool, "pruned_entries": int}
        """
        previous_history_date = self.schedule.get("history_date")
        today = date.today().isoformat()
        day_reset = previous_history_date != today

        if day_reset:
            self._check_daily_reset()

        pruned_entries = self._prune_flow_histories()
        if pruned_entries > 0:
            self.save()
            logger.info(f"[SCHEDULER] Pruned {pruned_entries} old/invalid flow history entries")

        return {
            "day_reset": day_reset,
            "pruned_entries": pruned_entries,
        }

    def _get_flow_config(self, flow_name: str) -> dict[str, Any] | None:
        """Get flow configuration (overrides take precedence)."""
        if flow_name in self.config_overrides:
            result = self.config_overrides[flow_name]
            return dict(result) if result else None
        if flow_name in FLOW_CONFIGS:
            return dict(FLOW_CONFIGS[flow_name])
        return None

    # =========================================================================
    # Logging / Visibility
    # =========================================================================

    @_locked
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


def get_scheduler(config_overrides: dict[str, Any] | None = None) -> DaemonScheduler:
    """Get or create the singleton scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = DaemonScheduler(config_overrides)
    return _scheduler_instance


def reset_scheduler() -> None:
    """Reset the singleton instance (for testing)."""
    global _scheduler_instance
    _scheduler_instance = None
