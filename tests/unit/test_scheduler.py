"""
Unit tests for utils/scheduler.py

Tests the DaemonScheduler class and get_scheduler singleton.
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Any, Generator
from unittest.mock import patch, MagicMock

import pytest

# Import after path setup in conftest
from utils.scheduler import (
    DaemonScheduler,
    get_scheduler,
    reset_scheduler,
    FLOW_CONFIGS,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_schedule_file(tmp_path: Path) -> Path:
    """Create a temporary schedule file path."""
    return tmp_path / "daemon_schedule.json"


@pytest.fixture
def scheduler_with_temp_file(temp_schedule_file: Path) -> Generator[DaemonScheduler, None, None]:
    """Create a scheduler with a temporary file for testing."""
    with patch.object(DaemonScheduler, 'SCHEDULE_FILE', temp_schedule_file):
        scheduler = DaemonScheduler()
        yield scheduler


@pytest.fixture(autouse=True)
def reset_singleton() -> Generator[None, None, None]:
    """Reset the singleton before and after each test."""
    reset_scheduler()
    yield
    reset_scheduler()


# =============================================================================
# Test 1: Singleton Pattern
# =============================================================================

class TestSingletonPattern:
    """Test that get_scheduler returns the same instance."""

    def test_get_scheduler_returns_same_instance(
        self, temp_schedule_file: Path
    ) -> None:
        """get_scheduler should return the same instance on multiple calls."""
        with patch.object(DaemonScheduler, 'SCHEDULE_FILE', temp_schedule_file):
            scheduler1 = get_scheduler()
            scheduler2 = get_scheduler()

            assert scheduler1 is scheduler2

    def test_reset_scheduler_clears_instance(
        self, temp_schedule_file: Path
    ) -> None:
        """reset_scheduler should allow a new instance to be created."""
        with patch.object(DaemonScheduler, 'SCHEDULE_FILE', temp_schedule_file):
            scheduler1 = get_scheduler()
            reset_scheduler()
            scheduler2 = get_scheduler()

            assert scheduler1 is not scheduler2

    def test_singleton_preserves_state(
        self, temp_schedule_file: Path
    ) -> None:
        """State changes in singleton should persist across get_scheduler calls."""
        with patch.object(DaemonScheduler, 'SCHEDULE_FILE', temp_schedule_file):
            scheduler1 = get_scheduler()
            scheduler1.record_flow_run("bag_flow")

            scheduler2 = get_scheduler()
            flow_data = scheduler2.schedule.get("flows", {}).get("bag_flow", {})

            assert flow_data.get("last_run") is not None

    def test_config_overrides_applied_to_singleton(
        self, temp_schedule_file: Path
    ) -> None:
        """Config overrides should be applied when creating singleton."""
        with patch.object(DaemonScheduler, 'SCHEDULE_FILE', temp_schedule_file):
            overrides = {"custom_flow": {"cooldown": 600, "idle_required": 60}}
            scheduler = get_scheduler(config_overrides=overrides)

            config = scheduler.get_flow_config("custom_flow")
            assert config is not None
            assert config["cooldown"] == 600
            assert config["idle_required"] == 60


# =============================================================================
# Test 2: Schedule Task (record_flow_run)
# =============================================================================

class TestScheduleTask:
    """Test schedule_task/record_flow_run adds tasks correctly."""

    def test_record_flow_run_creates_flow_entry(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """record_flow_run should create flow entry if it doesn't exist."""
        scheduler = scheduler_with_temp_file

        scheduler.record_flow_run("bag_flow")

        flow_data = scheduler.schedule.get("flows", {}).get("bag_flow", {})
        assert flow_data is not None
        assert flow_data.get("last_run") is not None

    def test_record_flow_run_updates_last_run(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """record_flow_run should update last_run timestamp."""
        scheduler = scheduler_with_temp_file

        before = datetime.now()
        scheduler.record_flow_run("bag_flow")
        after = datetime.now()

        flow_data = scheduler.schedule["flows"]["bag_flow"]
        last_run = datetime.fromisoformat(flow_data["last_run"])

        assert before <= last_run <= after

    def test_record_flow_run_appends_to_history(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """record_flow_run should append to history array."""
        scheduler = scheduler_with_temp_file

        scheduler.record_flow_run("bag_flow")
        scheduler.record_flow_run("bag_flow")
        scheduler.record_flow_run("bag_flow")

        flow_data = scheduler.schedule["flows"]["bag_flow"]
        assert len(flow_data["history"]) == 3

    def test_record_flow_run_for_unknown_flow(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """record_flow_run should work for flows not in FLOW_CONFIGS."""
        scheduler = scheduler_with_temp_file

        scheduler.record_flow_run("unknown_custom_flow")

        flow_data = scheduler.schedule["flows"]["unknown_custom_flow"]
        assert flow_data["last_run"] is not None
        # Default cooldown should be 3600
        assert flow_data["cooldown_seconds"] == 3600

    def test_record_flow_run_saves_to_file(
        self, scheduler_with_temp_file: DaemonScheduler, temp_schedule_file: Path
    ) -> None:
        """record_flow_run should persist changes to file."""
        with patch.object(DaemonScheduler, 'SCHEDULE_FILE', temp_schedule_file):
            scheduler = scheduler_with_temp_file
            scheduler.record_flow_run("bag_flow")

            # Read file directly
            assert temp_schedule_file.exists()
            with open(temp_schedule_file) as f:
                data = json.load(f)

            assert "bag_flow" in data.get("flows", {})


# =============================================================================
# Test 3: Get Pending Tasks (is_flow_ready)
# =============================================================================

class TestGetPendingTasks:
    """Test get_pending_tasks/is_flow_ready returns tasks due now."""

    def test_is_flow_ready_returns_true_for_never_run_flow(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """is_flow_ready should return True for flows that have never run."""
        scheduler = scheduler_with_temp_file

        # bag_flow idle_required is 300s (from FLOW_CONFIGS), provide enough idle
        result = scheduler.is_flow_ready("bag_flow", idle_seconds=400)

        assert result is True

    def test_is_flow_ready_returns_false_when_cooldown_active(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """is_flow_ready should return False when cooldown hasn't passed."""
        scheduler = scheduler_with_temp_file

        scheduler.record_flow_run("bag_flow")

        # Check immediately (cooldown is 3600s)
        result = scheduler.is_flow_ready("bag_flow", idle_seconds=400)

        assert result is False

    def test_is_flow_ready_returns_true_when_cooldown_passed(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """is_flow_ready should return True when cooldown has passed."""
        scheduler = scheduler_with_temp_file

        # Set last_run to 2 hours ago
        two_hours_ago = datetime.now() - timedelta(hours=2)
        scheduler.schedule["flows"] = {
            "bag_flow": {
                "last_run": two_hours_ago.isoformat(),
                "cooldown_seconds": 3600,
                "idle_required": 300,
                "history": [],
            }
        }

        result = scheduler.is_flow_ready("bag_flow", idle_seconds=400)

        assert result is True

    def test_is_flow_ready_returns_false_when_idle_insufficient(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """is_flow_ready should return False when idle time is insufficient."""
        scheduler = scheduler_with_temp_file

        # bag_flow requires 300s idle
        result = scheduler.is_flow_ready("bag_flow", idle_seconds=100)

        assert result is False

    def test_is_flow_ready_returns_true_for_unknown_flow(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """is_flow_ready should return True for unknown flows (warning)."""
        scheduler = scheduler_with_temp_file

        result = scheduler.is_flow_ready("nonexistent_flow", idle_seconds=0)

        assert result is True

    def test_get_next_eligible_returns_none_when_ready(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """get_next_eligible should return None when flow is ready."""
        scheduler = scheduler_with_temp_file

        result = scheduler.get_next_eligible("bag_flow")

        assert result is None

    def test_get_next_eligible_returns_datetime_when_not_ready(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """get_next_eligible should return datetime when cooldown active."""
        scheduler = scheduler_with_temp_file

        scheduler.record_flow_run("bag_flow")
        result = scheduler.get_next_eligible("bag_flow")

        assert result is not None
        assert isinstance(result, datetime)
        assert result > datetime.now()


# =============================================================================
# Test 4: Clear Completed Tasks
# =============================================================================

class TestClearCompletedTasks:
    """Test clear_completed_tasks removes old tasks (daily reset)."""

    def test_daily_reset_clears_history(
        self, temp_schedule_file: Path
    ) -> None:
        """History should be cleared when a new day is detected."""
        # Create a schedule file with yesterday's date
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        old_schedule = {
            "version": 1,
            "last_updated": datetime.now().isoformat(),
            "history_date": yesterday,
            "flows": {
                "bag_flow": {
                    "last_run": datetime.now().isoformat(),
                    "cooldown_seconds": 3600,
                    "idle_required": 300,
                    "history": ["2024-01-01T10:00:00", "2024-01-01T11:00:00"],
                }
            },
            "tavern_quests": {"last_scan": None, "completions": []},
            "daily_limits": {},
            "arms_race": {},
            "daemon_state": {},
        }

        temp_schedule_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_schedule_file, 'w') as f:
            json.dump(old_schedule, f)

        # Load scheduler - should detect new day and clear history
        with patch.object(DaemonScheduler, 'SCHEDULE_FILE', temp_schedule_file):
            scheduler = DaemonScheduler()

            flow_data = scheduler.schedule["flows"]["bag_flow"]
            assert flow_data["history"] == []
            assert scheduler.schedule["history_date"] == date.today().isoformat()

    def test_daily_reset_preserves_last_run(
        self, temp_schedule_file: Path
    ) -> None:
        """last_run should be preserved even when history is cleared."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        last_run_time = datetime.now().isoformat()
        old_schedule = {
            "version": 1,
            "last_updated": datetime.now().isoformat(),
            "history_date": yesterday,
            "flows": {
                "bag_flow": {
                    "last_run": last_run_time,
                    "cooldown_seconds": 3600,
                    "idle_required": 300,
                    "history": ["2024-01-01T10:00:00"],
                }
            },
            "tavern_quests": {"last_scan": None, "completions": []},
            "daily_limits": {},
            "arms_race": {},
            "daemon_state": {},
        }

        temp_schedule_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_schedule_file, 'w') as f:
            json.dump(old_schedule, f)

        with patch.object(DaemonScheduler, 'SCHEDULE_FILE', temp_schedule_file):
            scheduler = DaemonScheduler()

            flow_data = scheduler.schedule["flows"]["bag_flow"]
            assert flow_data["last_run"] == last_run_time

    def test_expired_daily_limits_cleared(
        self, temp_schedule_file: Path
    ) -> None:
        """Expired daily limits should be cleared on load."""
        # Set a reset time in the past (use UTC for comparison)
        past_reset = (datetime.now(timezone.utc) - timedelta(hours=5)).replace(tzinfo=None)
        old_schedule = {
            "version": 1,
            "last_updated": datetime.now().isoformat(),
            "history_date": date.today().isoformat(),
            "flows": {},
            "tavern_quests": {"last_scan": None, "completions": []},
            "daily_limits": {
                "rally_elite_zombie": {
                    "exhausted_at": datetime.now().isoformat(),
                    "resets_at": past_reset.isoformat(),
                }
            },
            "arms_race": {},
            "daemon_state": {},
        }

        temp_schedule_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_schedule_file, 'w') as f:
            json.dump(old_schedule, f)

        with patch.object(DaemonScheduler, 'SCHEDULE_FILE', temp_schedule_file):
            scheduler = DaemonScheduler()

            assert "rally_elite_zombie" not in scheduler.schedule.get("daily_limits", {})


# =============================================================================
# Test 5: Persistence (save/load)
# =============================================================================

class TestPersistence:
    """Test persistence - save/load from file."""

    def test_save_creates_file(
        self, temp_schedule_file: Path
    ) -> None:
        """save should create the schedule file."""
        with patch.object(DaemonScheduler, 'SCHEDULE_FILE', temp_schedule_file):
            scheduler = DaemonScheduler()
            scheduler.save()

            assert temp_schedule_file.exists()

    def test_save_writes_valid_json(
        self, scheduler_with_temp_file: DaemonScheduler, temp_schedule_file: Path
    ) -> None:
        """save should write valid JSON."""
        with patch.object(DaemonScheduler, 'SCHEDULE_FILE', temp_schedule_file):
            scheduler = scheduler_with_temp_file
            scheduler.record_flow_run("bag_flow")

            with open(temp_schedule_file) as f:
                data = json.load(f)

            assert "version" in data
            assert "last_updated" in data
            assert "flows" in data

    def test_load_restores_state(
        self, temp_schedule_file: Path
    ) -> None:
        """Loading from file should restore previous state."""
        # First, create and save a scheduler
        with patch.object(DaemonScheduler, 'SCHEDULE_FILE', temp_schedule_file):
            scheduler1 = DaemonScheduler()
            scheduler1.record_flow_run("bag_flow")
            scheduler1.update_arms_race_state(beast_training_rallies=5)

            # Create a new scheduler that loads from file
            scheduler2 = DaemonScheduler()

            assert "bag_flow" in scheduler2.schedule.get("flows", {})
            arms_race = scheduler2.schedule.get("arms_race", {})
            assert arms_race.get("beast_training_rallies") == 5

    def test_load_handles_corrupted_file(
        self, temp_schedule_file: Path
    ) -> None:
        """Loading should handle corrupted JSON gracefully."""
        temp_schedule_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_schedule_file, 'w') as f:
            f.write("not valid json {{{")

        with patch.object(DaemonScheduler, 'SCHEDULE_FILE', temp_schedule_file):
            # Should not raise, should create empty schedule
            scheduler = DaemonScheduler()

            assert scheduler.schedule is not None
            assert "flows" in scheduler.schedule

    def test_load_handles_missing_file(
        self, temp_schedule_file: Path
    ) -> None:
        """Loading should create empty schedule if file doesn't exist."""
        assert not temp_schedule_file.exists()

        with patch.object(DaemonScheduler, 'SCHEDULE_FILE', temp_schedule_file):
            scheduler = DaemonScheduler()

            assert scheduler.schedule is not None
            assert scheduler.schedule.get("version") == 1

    def test_save_uses_atomic_write(
        self, scheduler_with_temp_file: DaemonScheduler, temp_schedule_file: Path
    ) -> None:
        """save should use atomic write (temp file + rename)."""
        with patch.object(DaemonScheduler, 'SCHEDULE_FILE', temp_schedule_file):
            scheduler = scheduler_with_temp_file

            with patch('os.replace') as mock_replace:
                mock_replace.side_effect = lambda src, dst: Path(dst).write_text(Path(src).read_text())
                scheduler.save()

                # os.replace should have been called
                mock_replace.assert_called_once()

    def test_updates_last_updated_on_save(
        self, scheduler_with_temp_file: DaemonScheduler, temp_schedule_file: Path
    ) -> None:
        """save should update last_updated timestamp."""
        with patch.object(DaemonScheduler, 'SCHEDULE_FILE', temp_schedule_file):
            scheduler = scheduler_with_temp_file

            before = datetime.now()
            scheduler.save()
            after = datetime.now()

            last_updated = datetime.fromisoformat(scheduler.schedule["last_updated"])
            assert before <= last_updated <= after


# =============================================================================
# Additional Feature Tests
# =============================================================================

class TestDailyLimits:
    """Test daily limit (exhaustion) tracking."""

    def test_mark_exhausted_sets_limit(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """mark_exhausted should create limit entry."""
        scheduler = scheduler_with_temp_file
        reset_time = datetime.now() + timedelta(hours=24)

        scheduler.mark_exhausted("rally_elite_zombie", reset_time)

        limit_data = scheduler.schedule["daily_limits"]["rally_elite_zombie"]
        assert limit_data["resets_at"] == reset_time.isoformat()

    def test_is_exhausted_returns_true_before_reset(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """is_exhausted should return True before reset time."""
        scheduler = scheduler_with_temp_file
        # Use UTC time since that's what is_exhausted compares against
        reset_time = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24)

        scheduler.mark_exhausted("rally_elite_zombie", reset_time)

        assert scheduler.is_exhausted("rally_elite_zombie") is True

    def test_is_exhausted_returns_false_after_reset(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """is_exhausted should return False after reset time."""
        scheduler = scheduler_with_temp_file
        # Set reset time in the past (use UTC)
        reset_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)

        scheduler.schedule["daily_limits"] = {
            "rally_elite_zombie": {
                "exhausted_at": datetime.now().isoformat(),
                "resets_at": reset_time.isoformat(),
            }
        }

        assert scheduler.is_exhausted("rally_elite_zombie") is False

    def test_get_next_server_reset(self) -> None:
        """get_next_server_reset should return 02:00 UTC."""
        reset = DaemonScheduler.get_next_server_reset()

        assert reset.hour == 2
        assert reset.minute == 0
        assert reset > datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)


class TestTavernCompletions:
    """Test tavern quest completion tracking."""

    def test_set_tavern_completions(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """set_tavern_completions should store completion times."""
        scheduler = scheduler_with_temp_file
        completions = [
            datetime.now() + timedelta(minutes=10),
            datetime.now() + timedelta(minutes=30),
        ]

        scheduler.set_tavern_completions(completions)

        stored = scheduler.get_tavern_completions()
        assert len(stored) == 2

    def test_set_tavern_completions_deduplicates(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """set_tavern_completions should deduplicate within threshold."""
        scheduler = scheduler_with_temp_file
        now = datetime.now()
        completions = [
            now + timedelta(minutes=10),
            now + timedelta(minutes=10, seconds=5),  # Within 15s threshold
            now + timedelta(minutes=30),
        ]

        scheduler.set_tavern_completions(completions)

        stored = scheduler.get_tavern_completions()
        assert len(stored) == 2  # Two distinct times after dedup

    def test_is_tavern_completion_imminent(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """is_tavern_completion_imminent should detect upcoming completions."""
        scheduler = scheduler_with_temp_file
        completions = [
            datetime.now() + timedelta(seconds=10),  # Imminent
        ]

        scheduler.set_tavern_completions(completions)

        assert scheduler.is_tavern_completion_imminent(buffer_seconds=15) is True

    def test_get_next_tavern_completion(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """get_next_tavern_completion should return earliest future completion."""
        scheduler = scheduler_with_temp_file
        now = datetime.now()
        completions = [
            now + timedelta(minutes=30),
            now + timedelta(minutes=10),  # Earliest
            now + timedelta(minutes=60),
        ]

        scheduler.set_tavern_completions(completions)

        next_completion = scheduler.get_next_tavern_completion()
        assert next_completion is not None
        # Should be closest to now + 10 minutes
        expected = now + timedelta(minutes=10)
        assert abs((next_completion - expected).total_seconds()) < 2


class TestArmsRaceState:
    """Test Arms Race state tracking."""

    def test_update_arms_race_state(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """update_arms_race_state should update state values."""
        scheduler = scheduler_with_temp_file

        scheduler.update_arms_race_state(
            beast_training_rallies=5,
            enhance_hero_done=True
        )

        state = scheduler.get_arms_race_state()
        assert state["beast_training_rallies"] == 5
        assert state["enhance_hero_done"] is True

    def test_reset_arms_race_block(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """reset_arms_race_block should reset all state."""
        scheduler = scheduler_with_temp_file
        block_start = datetime.now()

        # Set some state first
        scheduler.update_arms_race_state(beast_training_rallies=10)

        # Reset
        scheduler.reset_arms_race_block(block_start)

        state = scheduler.get_arms_race_state()
        assert state["beast_training_rallies"] == 0
        assert state["beast_training_uses"] == 0
        assert state["enhance_hero_done"] is False

    def test_record_arms_race_progress(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """record_arms_race_progress should append to history."""
        scheduler = scheduler_with_temp_file

        scheduler.record_arms_race_progress(
            event="Mystic Beast Training",
            points=15000,
            chest3_target=30000,
            block_start="2026-01-04T10:00:00"
        )

        progress = scheduler.schedule.get("arms_race_progress", [])
        assert len(progress) == 1
        assert progress[0]["event"] == "Mystic Beast Training"
        assert progress[0]["points"] == 15000


class TestZombieMode:
    """Test zombie mode tracking."""

    def test_set_zombie_mode(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """set_zombie_mode should set mode with expiry."""
        scheduler = scheduler_with_temp_file

        expires = scheduler.set_zombie_mode("gold", hours=2)

        mode, mode_expires = scheduler.get_zombie_mode()
        assert mode == "gold"
        assert mode_expires is not None

    def test_clear_zombie_mode(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """clear_zombie_mode should revert to elite."""
        scheduler = scheduler_with_temp_file

        scheduler.set_zombie_mode("food", hours=1)
        scheduler.clear_zombie_mode()

        mode, expires = scheduler.get_zombie_mode()
        assert mode == "elite"
        assert expires is None

    def test_expired_zombie_mode_reverts_to_elite(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """Expired zombie mode should revert to elite."""
        scheduler = scheduler_with_temp_file

        # Set zombie mode with past expiry
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        scheduler.schedule["zombie_mode"] = {
            "mode": "gold",
            "expires": past.isoformat(),
        }

        mode, expires = scheduler.get_zombie_mode()
        assert mode == "elite"


class TestDaemonState:
    """Test daemon runtime state tracking."""

    def test_update_daemon_state(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """update_daemon_state should store values."""
        scheduler = scheduler_with_temp_file

        scheduler.update_daemon_state(
            stamina_history=[120, 118, 115],
            last_barracks_check=datetime.now()
        )

        state = scheduler.get_daemon_state()
        assert state["stamina_history"] == [120, 118, 115]
        assert "last_barracks_check" in state

    def test_clear_daemon_state(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """clear_daemon_state should remove all daemon state."""
        scheduler = scheduler_with_temp_file

        scheduler.update_daemon_state(stamina_history=[100])
        scheduler.clear_daemon_state()

        state = scheduler.get_daemon_state()
        assert state == {}

    def test_update_daemon_state_converts_sets_to_lists(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """update_daemon_state should convert sets to lists for JSON."""
        scheduler = scheduler_with_temp_file

        scheduler.update_daemon_state(checked_barracks={1, 2, 3})

        state = scheduler.get_daemon_state()
        # Sets become lists
        assert isinstance(state["checked_barracks"], list)
        assert set(state["checked_barracks"]) == {1, 2, 3}


class TestFlowHistory:
    """Test flow run history tracking."""

    def test_get_flow_history_returns_datetimes(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """get_flow_history should return list of datetime objects."""
        scheduler = scheduler_with_temp_file

        scheduler.record_flow_run("bag_flow")
        scheduler.record_flow_run("bag_flow")

        history = scheduler.get_flow_history("bag_flow")
        assert len(history) == 2
        assert all(isinstance(dt, datetime) for dt in history)

    def test_get_flow_history_empty_for_unknown_flow(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """get_flow_history should return empty list for unknown flows."""
        scheduler = scheduler_with_temp_file

        history = scheduler.get_flow_history("never_run_flow")
        assert history == []

    def test_get_missed_flows(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """get_missed_flows should return flows that have never run."""
        scheduler = scheduler_with_temp_file

        # Run one flow, leave others
        scheduler.record_flow_run("bag_flow")

        missed = scheduler.get_missed_flows()
        # Should include flows from FLOW_CONFIGS that haven't run
        assert "bag_flow" not in missed
        # Other configured flows should be in missed
        assert len(missed) > 0


class TestConfigOverrides:
    """Test config override functionality."""

    def test_config_overrides_take_precedence(
        self, temp_schedule_file: Path
    ) -> None:
        """Config overrides should take precedence over FLOW_CONFIGS."""
        with patch.object(DaemonScheduler, 'SCHEDULE_FILE', temp_schedule_file):
            overrides = {
                "bag_flow": {"cooldown": 7200, "idle_required": 600}
            }
            scheduler = DaemonScheduler(config_overrides=overrides)

            config = scheduler.get_flow_config("bag_flow")
            assert config["cooldown"] == 7200
            assert config["idle_required"] == 600

    def test_default_config_used_without_override(
        self, scheduler_with_temp_file: DaemonScheduler
    ) -> None:
        """Default FLOW_CONFIGS should be used when no override."""
        scheduler = scheduler_with_temp_file

        config = scheduler.get_flow_config("bag_flow")
        assert config is not None
        # Should match FLOW_CONFIGS default
        assert config["cooldown"] == FLOW_CONFIGS["bag_flow"]["cooldown"]
