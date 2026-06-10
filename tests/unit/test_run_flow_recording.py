"""Tests for IconDaemon._run_flow scheduler recording (failure vs success cooldowns)."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.icon_daemon import IconDaemon


def _make_daemon() -> IconDaemon:
    """Build a minimal IconDaemon without running __init__ (no ADB/window deps)."""
    d = IconDaemon.__new__(IconDaemon)
    d.logger = MagicMock()
    d.flow_lock = threading.Lock()
    d.active_flows = set()
    d.critical_flow_active = False
    d.critical_flow_name = None
    d.critical_flow_start_time = None
    d.critical_flow_thread = None
    d.scheduler = MagicMock()
    d.scheduler.get_tavern_completions.return_value = []
    d.TAVERN_BLOCKING_FLOW_GUARD_SECONDS = 60
    d.adb = MagicMock()
    return d


def _wait_for_flow_end(d: IconDaemon, flow_name: str, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with d.flow_lock:
            if flow_name not in d.active_flows:
                return
        time.sleep(0.02)
    raise AssertionError(f"flow {flow_name} did not finish within {timeout}s")


def test_exception_records_failure_cooldown() -> None:
    """A flow that raises must get the 15-min retry cooldown, not full cooldown."""
    d = _make_daemon()

    def boom(adb: Any) -> None:
        raise RuntimeError("boom")

    assert d._run_flow("test_flow", boom, critical=False, record_to_scheduler=True)
    _wait_for_flow_end(d, "test_flow")

    d.scheduler.record_flow_run.assert_called_once_with("test_flow", cooldown_override=900)


def test_false_result_records_failure_cooldown() -> None:
    """A flow returning False gets the 15-min retry cooldown."""
    d = _make_daemon()

    assert d._run_flow("test_flow", lambda adb: False, critical=False, record_to_scheduler=True)
    _wait_for_flow_end(d, "test_flow")

    d.scheduler.record_flow_run.assert_called_once_with("test_flow", cooldown_override=900)


def test_success_records_full_cooldown() -> None:
    """A successful flow gets the full cooldown (no override)."""
    d = _make_daemon()

    assert d._run_flow("test_flow", lambda adb: {"ok": True}, critical=False, record_to_scheduler=True)
    _wait_for_flow_end(d, "test_flow")

    d.scheduler.record_flow_run.assert_called_once_with("test_flow")


def test_critical_flow_tracks_thread() -> None:
    """Critical flows must expose their thread so the daemon's timeout
    handler can tell a live (still-running) flow from stuck-stale flags."""
    d = _make_daemon()
    release = threading.Event()
    started = threading.Event()

    def slow_flow(adb: Any) -> bool:
        started.set()
        release.wait(timeout=5)
        return True

    assert d._run_flow("critical_flow", slow_flow, critical=True)
    assert started.wait(timeout=5)

    assert d.critical_flow_thread is not None
    assert d.critical_flow_thread.is_alive()

    release.set()
    _wait_for_flow_end(d, "critical_flow")
    deadline = time.time() + 5
    while d.critical_flow_thread is not None and time.time() < deadline:
        time.sleep(0.02)

    assert d.critical_flow_thread is None
    assert d.critical_flow_active is False
    assert d.critical_flow_start_time is None


def test_skipped_records_short_retry() -> None:
    """A skipped flow gets the 5-min retry cooldown."""
    d = _make_daemon()

    assert d._run_flow("test_flow", lambda adb: {"skipped": True}, critical=False, record_to_scheduler=True)
    _wait_for_flow_end(d, "test_flow")

    d.scheduler.record_flow_run.assert_called_once_with("test_flow", cooldown_override=300)
