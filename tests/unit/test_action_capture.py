"""Unit tests for utils/action_capture.py."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pytest

from utils.action_capture import ActionCapture, _NULL_CTX


def _frame() -> np.ndarray:
    return np.zeros((2160, 3840, 3), dtype=np.uint8)


class _FakeHelper:
    """Screenshot helper stub that returns a small frame quickly."""
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def get_screenshot_cv2(self) -> np.ndarray:
        self.calls += 1
        if self.fail:
            raise RuntimeError("no window")
        return _frame()


def _make(tmp_path: Path, **over) -> ActionCapture:
    cap = ActionCapture()
    cap.base_dir = tmp_path / "action_capture"
    cap.burst_count = over.get("burst_count", 2)
    cap.burst_interval = over.get("burst_interval", 0.02)
    cap.max_gb = over.get("max_gb", 100.0)
    cap.max_age_hours = over.get("max_age_hours", 24)
    cap.max_inflight = over.get("max_inflight", 16)
    cap.fmt = "png"
    return cap


def _drain(cap: ActionCapture, timeout: float = 3.0) -> None:
    """Wait until the burst scheduler + encoder have flushed."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with cap._sched_cv:
            idle = not cap._heap and cap._inflight == 0
        if idle:
            break
        time.sleep(0.02)
    # give the encoder pool a beat to finish writes
    time.sleep(0.1)


def test_disabled_returns_null_ctx(tmp_path: Path) -> None:
    cap = _make(tmp_path)
    cap.enabled = False
    ctx = cap.action(action_type="tap", params={"x": 1, "y": 2}, source="t")
    assert ctx is _NULL_CTX
    with ctx:
        pass  # no exception, no disk


def test_records_before_and_after(tmp_path: Path) -> None:
    cap = _make(tmp_path, burst_count=3)
    cap.attach_screenshot_helper(_FakeHelper())
    assert cap.new_session("sess1") == "sess1"

    with cap.action(action_type="tap", params={"x": 10, "y": 20}, source="flow:test:x", device="dev"):
        pass
    _drain(cap)

    jsonl = cap.session_dir / "actions.jsonl"
    assert jsonl.exists()
    lines = [json.loads(l) for l in jsonl.read_text().splitlines() if l.strip()]
    assert len(lines) == 1
    rec = lines[0]
    # schema fields
    for key in ("seq", "session_id", "ts", "ts_sent", "source", "action_type",
                "params", "device", "resolution", "before_shot", "after_shots",
                "after_dropped", "prev_seq", "delay_before_ms"):
        assert key in rec
    assert rec["action_type"] == "tap"
    assert rec["params"] == {"x": 10, "y": 20}
    assert rec["after_dropped"] is False
    assert len(rec["after_shots"]) == 3
    # before-shot file exists on disk (path is absolute since base_dir is outside project root)
    assert Path(rec["before_shot"]).exists()
    cap.shutdown()


def test_before_grab_failure_degrades(tmp_path: Path) -> None:
    cap = _make(tmp_path)
    cap.attach_screenshot_helper(_FakeHelper(fail=True))
    cap.new_session("sessfail")
    # Should not raise even though the grab fails.
    with cap.action(action_type="tap", params={"x": 1, "y": 1}, source="t"):
        pass
    _drain(cap)
    # A record is still written, flagged after_dropped (no before frame).
    jsonl = cap.session_dir / "actions.jsonl"
    lines = [json.loads(l) for l in jsonl.read_text().splitlines() if l.strip()]
    assert len(lines) == 1
    assert lines[0]["after_dropped"] is True
    cap.shutdown()


def test_backpressure_marks_dropped(tmp_path: Path) -> None:
    cap = _make(tmp_path, burst_count=2, max_inflight=0)  # 0 => always over capacity
    cap.attach_screenshot_helper(_FakeHelper())
    cap.new_session("sesspb")
    with cap.action(action_type="tap", params={"x": 1, "y": 1}, source="t"):
        pass
    _drain(cap)
    lines = [json.loads(l) for l in (cap.session_dir / "actions.jsonl").read_text().splitlines() if l.strip()]
    assert lines[0]["after_dropped"] is True
    assert lines[0]["after_shots"] == []
    cap.stats["after_dropped"] >= 1
    cap.shutdown()


def test_prune_removes_oldest_over_gb(tmp_path: Path) -> None:
    cap = _make(tmp_path)
    cap.attach_screenshot_helper(_FakeHelper())
    base = cap.base_dir
    base.mkdir(parents=True, exist_ok=True)
    # Two old session dirs with fake data.
    for name in ("old1", "old2"):
        d = base / name
        d.mkdir()
        (d / "blob.png").write_bytes(b"x" * (2 * 1024 * 1024))  # 2 MB each
    # Set a tiny cap so both are over budget, then start current session.
    cap.max_gb = 0.000001
    cap.new_session("current")  # triggers a forced prune
    # Old dirs pruned; current session preserved.
    assert not (base / "old1").exists()
    assert not (base / "old2").exists()
    assert (base / "current").exists()
    cap.shutdown()


def test_prune_trims_current_session_over_cap(tmp_path: Path) -> None:
    """Regression: a single long-running (current) session must be trimmed to the
    byte cap. The original bug protected the active session, so it grew unbounded
    and filled the disk (591GB)."""
    cap = _make(tmp_path)
    cap.attach_screenshot_helper(_FakeHelper())
    cap.new_session("current")
    sd = cap.session_dir
    # Write frames into the CURRENT session totalling ~10MB.
    for i in range(10):
        (sd / f"{i:08d}_before.png").write_bytes(b"x" * (1024 * 1024))
    (sd / "actions.jsonl").write_text('{"seq":1}\n')
    # Cap below current usage -> must trim frames from the ACTIVE session.
    cap.max_gb = 4 / 1024  # 4 MB
    cap._last_prune = 0.0
    cap._prune()
    pngs = list(sd.glob("*.png"))
    total_mb = sum(p.stat().st_size for p in pngs) / (1024 * 1024)
    assert total_mb <= 4.5, f"active session not trimmed: {total_mb:.1f}MB of pngs remain"
    # The jsonl log is preserved (it's the record of what happened).
    assert (sd / "actions.jsonl").exists()
    cap.shutdown()


def test_jsonl_roundtrip_multiple(tmp_path: Path) -> None:
    cap = _make(tmp_path, burst_count=1)
    cap.attach_screenshot_helper(_FakeHelper())
    cap.new_session("multi")
    for i in range(3):
        with cap.action(action_type="tap", params={"x": i, "y": i}, source=f"s{i}"):
            pass
    _drain(cap)
    lines = [json.loads(l) for l in (cap.session_dir / "actions.jsonl").read_text().splitlines() if l.strip()]
    seqs = sorted(r["seq"] for r in lines)
    assert len(seqs) == 3
    # prev_seq chain is set on later records
    by_seq = {r["seq"]: r for r in lines}
    assert by_seq[seqs[1]]["prev_seq"] == seqs[0]
    cap.shutdown()
