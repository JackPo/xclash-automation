"""Unit tests for scripts/replay_actions.py."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import scripts.replay_actions as replay


def _write_session(base: Path, name: str, records: list[dict]) -> Path:
    d = base / name
    d.mkdir(parents=True)
    with open(d / "actions.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return d


def test_dispatch_routes_to_adb_methods() -> None:
    adb = MagicMock()
    replay._dispatch(adb, {"action_type": "tap", "params": {"x": 5, "y": 6}, "source": "s"})
    adb.tap.assert_called_once()
    assert adb.tap.call_args.args == (5, 6)

    replay._dispatch(adb, {"action_type": "swipe",
                           "params": {"x1": 1, "y1": 2, "x2": 3, "y2": 4, "duration": 200}, "source": "s"})
    adb.swipe.assert_called_once()
    assert adb.swipe.call_args.args == (1, 2, 3, 4)
    assert adb.swipe.call_args.kwargs["duration"] == 200

    replay._dispatch(adb, {"action_type": "key_event", "params": {"keycode": 4}, "source": "s"})
    adb.key_event.assert_called_once()
    assert adb.key_event.call_args.args == (4,)


def test_dispatch_unknown_raises() -> None:
    with pytest.raises(ValueError):
        replay._dispatch(MagicMock(), {"action_type": "bogus", "params": {}, "source": "s"})


def test_resolve_latest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    base = tmp_path / "ac"
    older = _write_session(base, "20260101_000000", [])
    newer = _write_session(base, "20260202_000000", [])
    # Force distinct mtimes (same-instant creation ties on Windows' coarse mtime).
    os.utime(older, (1_000_000, 1_000_000))
    os.utime(newer, (2_000_000, 2_000_000))
    monkeypatch.setattr(replay, "_capture_dir", lambda: base)
    assert replay._resolve_session("latest") == newer


def test_load_records_merges_pre_and_final(tmp_path: Path) -> None:
    d = tmp_path / "s"
    d.mkdir()
    (d / "actions.pre.jsonl").write_text(json.dumps({"seq": 1, "action_type": "tap", "params": {"x": 1, "y": 1}}) + "\n")
    (d / "actions.jsonl").write_text(json.dumps({"seq": 1, "action_type": "tap", "params": {"x": 1, "y": 1}, "after_shots": ["a.png"]}) + "\n")
    recs = replay._load_records(d)
    assert len(recs) == 1
    assert recs[0]["after_shots"] == ["a.png"]  # final overrides pre


def test_dry_run_sends_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    base = tmp_path / "ac"
    _write_session(base, "sess", [
        {"seq": 1, "ts": 1000.0, "action_type": "tap", "params": {"x": 1, "y": 2},
         "source": "flow:a", "delay_before_ms": None},
        {"seq": 2, "ts": 1001.0, "action_type": "tap", "params": {"x": 3, "y": 4},
         "source": "flow:b", "delay_before_ms": 1000},
    ])
    monkeypatch.setattr(replay, "_capture_dir", lambda: base)

    # If ADBHelper were constructed, this would fail loudly — ensure dry-run never does.
    def _boom(*a, **k):
        raise AssertionError("ADBHelper must not be built in --dry-run")
    monkeypatch.setattr("utils.adb_helper.ADBHelper", _boom)

    rc = replay.main.__wrapped__ if hasattr(replay.main, "__wrapped__") else replay.main
    monkeypatch.setattr("sys.argv", ["replay_actions", "--session", "sess", "--dry-run"])
    assert replay.main() == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "#1" in out and "#2" in out


def test_source_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    base = tmp_path / "ac"
    _write_session(base, "sess", [
        {"seq": 1, "ts": 1000.0, "action_type": "tap", "params": {"x": 1, "y": 2}, "source": "flow:keep"},
        {"seq": 2, "ts": 1001.0, "action_type": "tap", "params": {"x": 3, "y": 4}, "source": "flow:skip"},
    ])
    monkeypatch.setattr(replay, "_capture_dir", lambda: base)
    monkeypatch.setattr("sys.argv", ["replay_actions", "--session", "sess",
                                     "--source-filter", "keep", "--dry-run"])
    assert replay.main() == 0
    out = capsys.readouterr().out
    assert "flow:keep" in out
    assert "flow:skip" not in out
