"""Tests that DaemonScheduler state survives concurrent access from multiple threads."""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.scheduler import DaemonScheduler


@pytest.fixture
def scheduler_with_temp_file(tmp_path: Path) -> Generator[DaemonScheduler, None, None]:
    """Scheduler backed by a throwaway schedule file."""
    with patch.object(DaemonScheduler, "SCHEDULE_FILE", tmp_path / "daemon_schedule.json"):
        yield DaemonScheduler()


def test_concurrent_mutation_no_lost_updates(
    scheduler_with_temp_file: DaemonScheduler,
) -> None:
    """Daemon flow threads and the WebSocket server thread mutate the
    scheduler concurrently; every recorded run must survive."""
    scheduler = scheduler_with_temp_file
    runs_per_thread = 50
    errors: list[Exception] = []

    def record_runs(flow_name: str) -> None:
        try:
            for _ in range(runs_per_thread):
                scheduler.record_flow_run(flow_name)
        except Exception as e:  # pragma: no cover - surfaced via errors list
            errors.append(e)

    def churn_other_state() -> None:
        try:
            for i in range(runs_per_thread):
                scheduler.record_event(
                    flow_name="churn_flow",
                    status="completed",
                    duration=0.1,
                    result={"i": i},
                    category="test",
                    is_critical=False,
                )
                scheduler.get_recent_events(hours=1)
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [
        threading.Thread(target=record_runs, args=("flow_a",)),
        threading.Thread(target=record_runs, args=("flow_b",)),
        threading.Thread(target=churn_other_state),
        threading.Thread(target=churn_other_state),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert not errors, f"concurrent access raised: {errors}"
    assert len(scheduler.get_flow_history("flow_a")) == runs_per_thread
    assert len(scheduler.get_flow_history("flow_b")) == runs_per_thread
