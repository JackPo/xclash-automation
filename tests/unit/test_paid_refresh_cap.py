"""Tests for the daily paid-tavern-refresh counter (diamond spend cap)."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.scheduler import DaemonScheduler


@pytest.fixture
def scheduler(tmp_path: Path) -> Generator[DaemonScheduler, None, None]:
    with patch.object(DaemonScheduler, "SCHEDULE_FILE", tmp_path / "schedule.json"):
        yield DaemonScheduler()


def test_starts_at_zero(scheduler: DaemonScheduler) -> None:
    assert scheduler.get_paid_tavern_refreshes_today() == 0


def test_increments(scheduler: DaemonScheduler) -> None:
    scheduler.record_paid_tavern_refresh()
    scheduler.record_paid_tavern_refresh()
    assert scheduler.get_paid_tavern_refreshes_today() == 2


def test_separate_from_free_refresh_counter(scheduler: DaemonScheduler) -> None:
    scheduler.record_tavern_refresh()
    scheduler.record_tavern_refresh()
    scheduler.record_paid_tavern_refresh()
    assert scheduler.get_tavern_refreshes_today() == 2
    assert scheduler.get_paid_tavern_refreshes_today() == 1


def test_resets_on_new_day(scheduler: DaemonScheduler) -> None:
    scheduler.record_paid_tavern_refresh()
    scheduler.record_paid_tavern_refresh()
    # Simulate the stored date being yesterday
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    scheduler.schedule["tavern_quests"]["paid_refreshes_date"] = yesterday
    assert scheduler.get_paid_tavern_refreshes_today() == 0
    # Next record starts a fresh day at 1
    scheduler.record_paid_tavern_refresh()
    assert scheduler.get_paid_tavern_refreshes_today() == 1
