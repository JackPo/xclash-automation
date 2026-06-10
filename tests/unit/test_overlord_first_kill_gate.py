"""Tests for the Zombie Overlord first-kill gate.

Rule: after server reset (02:00 UTC), no Zombie Overlord rally may be joined
until one team has been successfully sent to a Lv190+ overlord. The
qualifying join bypasses the normal max_level cap; a dashboard override
(RALLY_OVERLORD_GATE_OVERRIDE) unlocks lower overlords early.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.rally_monster_validator import RallyMonsterValidator
from utils.scheduler import DaemonScheduler

MONSTERS = [
    {"name": "Zombie Overlord", "auto_join": True, "max_level": 130,
     "has_level": True, "track_daily_limit": False},
    {"name": "Elite Zombie", "auto_join": True, "max_level": 60,
     "has_level": True, "track_daily_limit": False},
]


@pytest.fixture
def scheduler(tmp_path: Path) -> Generator[DaemonScheduler, None, None]:
    with patch.object(DaemonScheduler, "SCHEDULE_FILE", tmp_path / "schedule.json"):
        yield DaemonScheduler()


def _validator() -> RallyMonsterValidator:
    return RallyMonsterValidator(ocr_client=MagicMock(), monsters_config=MONSTERS)


def _should_join(
    level: int,
    done: bool,
    gate_enabled: bool = True,
    override: bool = False,
    monster: str = "zombie overlord",
) -> bool:
    mgr = MagicMock()
    mgr.get_effective.side_effect = lambda key, default: {
        "RALLY_OVERLORD_GATE_ENABLED": (gate_enabled, False),
        "RALLY_OVERLORD_GATE_OVERRIDE": (override, False),
    }.get(key, (default, False))

    sched = MagicMock()
    sched.is_overlord_first_kill_done.return_value = done

    with patch("utils.config_overrides.get_override_manager", return_value=mgr), \
         patch("utils.scheduler.get_scheduler", return_value=sched):
        should, _is_known = _validator()._should_join_rally(monster, level)
    return should


class TestGateBeforeFirstKill:
    def test_low_overlord_blocked(self) -> None:
        assert _should_join(level=130, done=False) is False

    def test_190_overlord_joins_despite_max_level_cap(self) -> None:
        # max_level is 130, but the qualifying first kill bypasses it
        assert _should_join(level=190, done=False) is True

    def test_higher_than_190_joins(self) -> None:
        assert _should_join(level=250, done=False) is True

    def test_189_blocked(self) -> None:
        assert _should_join(level=189, done=False) is False


class TestGateAfterFirstKill:
    def test_low_overlord_joins_normally(self) -> None:
        assert _should_join(level=120, done=True) is True

    def test_max_level_cap_applies_again(self) -> None:
        # Once the gate is satisfied, the normal <=130 rule is back
        assert _should_join(level=200, done=True) is False


class TestOverrideAndToggle:
    def test_override_unlocks_low_overlords(self) -> None:
        assert _should_join(level=120, done=False, override=True) is True

    def test_gate_disabled_uses_normal_rules(self) -> None:
        assert _should_join(level=120, done=False, gate_enabled=False) is True
        assert _should_join(level=200, done=False, gate_enabled=False) is False

    def test_other_monsters_unaffected(self) -> None:
        assert _should_join(level=50, done=False, monster="elite zombie") is True


class TestSchedulerState:
    def test_not_done_initially(self, scheduler: DaemonScheduler) -> None:
        assert scheduler.is_overlord_first_kill_done() is False

    def test_done_after_marking(self, scheduler: DaemonScheduler) -> None:
        scheduler.mark_overlord_first_kill_done(level=190)
        assert scheduler.is_overlord_first_kill_done() is True

    def test_stale_entry_from_before_reset_not_done(self, scheduler: DaemonScheduler) -> None:
        # Entry timestamped 25h ago is before the last 02:00 UTC reset
        old = datetime.now(timezone.utc) - timedelta(hours=25)
        scheduler.schedule["overlord_first_kill"] = {
            "done_at": old.isoformat(), "level": 200,
        }
        assert scheduler.is_overlord_first_kill_done() is False

    def test_garbage_timestamp_not_done(self, scheduler: DaemonScheduler) -> None:
        scheduler.schedule["overlord_first_kill"] = {"done_at": "not-a-date", "level": 200}
        assert scheduler.is_overlord_first_kill_done() is False
