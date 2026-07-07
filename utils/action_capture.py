#!/usr/bin/env python3
"""
Action Capture — route every on-screen action through a before/after screenshot
recorder for visual debugging and replay.

For each action (tap / swipe / key_event / zoom / arrow) this records:
  1. a screenshot RIGHT BEFORE the command is sent,
  2. the command itself (type + params + source),
  3. a BURST of screenshots right AFTER (to catch the transition/animation).

Records go to a per-session JSONL (`actions.jsonl`) plus PNG/JPEG files under
`screenshots/action_capture/<session_id>/`. The dashboard "Captures" tab browses
them; `scripts/replay_actions.py` re-issues the command stream.

Design constraints (critical):
  * MUST be a bullet-proof no-op when there is no game window (tests / standalone
    scripts). Any failure latches capture to disabled and never breaks the caller.
  * The before-shot is grabbed synchronously (it must precede the send). Encoding
    and the entire after-burst run OFF the caller thread so clicks aren't blocked.
  * Screenshot GDI access is already serialized by WindowsScreenshotHelper's
    class-level lock; we add one background capture thread as a single consumer.

Usage (inside ADBHelper / Win32 wrappers):

    with get_action_capture().action(action_type="tap", params={"x": x, "y": y},
                                     source=source, device=self.device):
        self._run_adb(["shell", "input", "tap", str(x), str(y)])
"""
from __future__ import annotations

import heapq
import itertools
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

logger = logging.getLogger("action_capture")

PROJECT_ROOT = Path(__file__).parent.parent

# Config (defensive import so this module works even if config is partial).
try:
    from config import (
        ACTION_CAPTURE_ENABLED as _CFG_ENABLED,
        ACTION_CAPTURE_BURST_COUNT as _CFG_BURST_COUNT,
        ACTION_CAPTURE_BURST_INTERVAL_MS as _CFG_BURST_INTERVAL_MS,
        ACTION_CAPTURE_FORMAT as _CFG_FORMAT,
        ACTION_CAPTURE_JPG_QUALITY as _CFG_JPG_QUALITY,
        ACTION_CAPTURE_DOWNSCALE as _CFG_DOWNSCALE,
        ACTION_CAPTURE_DIR as _CFG_DIR,
        ACTION_CAPTURE_MAX_GB as _CFG_MAX_GB,
        ACTION_CAPTURE_MAX_AGE_HOURS as _CFG_MAX_AGE_HOURS,
        ACTION_CAPTURE_MAX_INFLIGHT_BURSTS as _CFG_MAX_INFLIGHT,
        ACTION_CAPTURE_ENCODER_WORKERS as _CFG_ENCODER_WORKERS,
    )
except Exception:  # pragma: no cover - config always present in practice
    _CFG_ENABLED = True
    _CFG_BURST_COUNT = 6
    _CFG_BURST_INTERVAL_MS = 330
    _CFG_FORMAT = "png"
    _CFG_JPG_QUALITY = 90
    _CFG_DOWNSCALE = 1.0
    _CFG_DIR = "screenshots/action_capture"
    _CFG_MAX_GB = 40.0
    _CFG_MAX_AGE_HOURS = 24
    _CFG_MAX_INFLIGHT = 16
    _CFG_ENCODER_WORKERS = 4


class _NullCtx:
    """Zero-cost context manager returned when capture is disabled/degraded."""
    __slots__ = ()

    def __enter__(self) -> "_NullCtx":
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


_NULL_CTX = _NullCtx()


class _ActionCtx:
    """Context manager for one captured action.

    __enter__ grabs the before-frame synchronously and stamps the start time.
    __exit__ stamps the send time and enqueues the async after-burst. All work
    is wrapped so an exception never propagates to the caller's action.
    """

    __slots__ = ("_cap", "seq", "action_type", "params", "source", "device",
                 "resolution", "ts", "ts_sent", "before_frame", "_active")

    def __init__(self, cap: "ActionCapture", action_type: str, params: dict[str, Any],
                 source: str, device: str | None, before_frame: Any | None) -> None:
        self._cap = cap
        self.action_type = action_type
        self.params = params
        self.source = source
        self.device = device
        self.resolution = (3840, 2160)
        self.seq = next(cap._seq_counter)
        self.ts = time.time()
        self.ts_sent: float | None = None
        self.before_frame = before_frame
        self._active = True

    def __enter__(self) -> "_ActionCtx":
        try:
            if self.before_frame is None:
                self.before_frame = self._cap._grab_frame()
        except Exception as e:  # never fail the action
            logger.debug(f"[capture] before-grab failed seq={self.seq}: {e}")
            self.before_frame = None
            self._active = False
        return self

    def __exit__(self, *exc: Any) -> bool:
        self.ts_sent = time.time()
        try:
            self._cap._on_action_exit(self)
        except Exception as e:  # never fail the action
            logger.debug(f"[capture] on_exit failed seq={self.seq}: {e}")
        return False  # do not suppress caller exceptions


class ActionCapture:
    """Singleton recorder. See module docstring."""

    def __init__(self) -> None:
        self._config_enabled = bool(_CFG_ENABLED)
        self._runtime_enabled = True
        self._helper: Any | None = None
        self._helper_tried = False
        self._degraded = False  # latched True if the screenshot helper is unavailable

        self.burst_count = int(_CFG_BURST_COUNT)
        self.burst_interval = float(_CFG_BURST_INTERVAL_MS) / 1000.0
        self.fmt = str(_CFG_FORMAT).lower()
        self.jpg_quality = int(_CFG_JPG_QUALITY)
        self.downscale = float(_CFG_DOWNSCALE)
        self.max_gb = float(_CFG_MAX_GB)
        self.max_age_hours = float(_CFG_MAX_AGE_HOURS)
        self.max_inflight = int(_CFG_MAX_INFLIGHT)

        self.base_dir = (PROJECT_ROOT / _CFG_DIR)
        self.session_id: str | None = None
        self.session_dir: Path | None = None

        self._seq_counter = itertools.count(1)
        self._prev_seq: int | None = None
        self._prev_ts_sent: float | None = None

        # Background machinery (lazy-started on first real use).
        self._lock = threading.Lock()
        self._jsonl_lock = threading.Lock()
        self._encoder: ThreadPoolExecutor | None = None
        self._sched_thread: threading.Thread | None = None
        self._sched_cv = threading.Condition()
        self._heap: list[tuple[float, int, Any]] = []  # (due_time, tiebreak, task)
        self._heap_seq = itertools.count()
        self._inflight = 0
        self._started = False
        self._shutdown = False
        self._last_prune = 0.0
        self.stats = {"actions": 0, "after_dropped": 0, "frames_written": 0}

    # ---- enable/availability -------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._config_enabled and self._runtime_enabled and not self._degraded

    @enabled.setter
    def enabled(self, value: bool) -> None:
        # Runtime toggle; does not clear a latched degradation.
        self._runtime_enabled = bool(value)

    def set_config_enabled(self, value: bool) -> None:
        self._config_enabled = bool(value)

    # ---- wiring --------------------------------------------------------------

    def attach_screenshot_helper(self, helper: Any) -> None:
        """Share the daemon's existing WindowsScreenshotHelper (avoids a 2nd GDI consumer)."""
        self._helper = helper
        self._helper_tried = True
        self._degraded = False

    def _ensure_helper(self) -> Any | None:
        if self._helper is not None:
            return self._helper
        if self._helper_tried:
            return None
        self._helper_tried = True
        try:
            from utils.windows_screenshot_helper import WindowsScreenshotHelper
            self._helper = WindowsScreenshotHelper()
        except Exception as e:
            logger.info(f"[capture] no screenshot helper ({e}); capture disabled")
            self._degraded = True
            self._helper = None
        return self._helper

    def _grab_frame(self) -> Any:
        helper = self._ensure_helper()
        if helper is None:
            raise RuntimeError("no screenshot helper")
        return helper.get_screenshot_cv2()

    # ---- session -------------------------------------------------------------

    def new_session(self, session_id: str | None = None) -> str | None:
        """Start a new capture session (one per daemon run). Returns session id or None."""
        if not self.enabled:
            # Still try to init a helper so tests that don't have a window latch cleanly.
            self._ensure_helper()
            if not self.enabled:
                return None
        with self._lock:
            self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
            self.session_dir = self.base_dir / self.session_id
            try:
                self.session_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.warning(f"[capture] cannot create session dir: {e}")
                self._degraded = True
                return None
            self._prev_seq = None
            self._prev_ts_sent = None
            self._start_workers()
        self._maybe_prune(force=True)
        logger.info(f"[capture] session {self.session_id} -> {self.session_dir}")
        return self.session_id

    def _start_workers(self) -> None:
        if self._started:
            return
        self._started = True
        self._shutdown = False
        self._encoder = ThreadPoolExecutor(
            max_workers=max(1, int(_CFG_ENCODER_WORKERS)), thread_name_prefix="capture-enc"
        )
        self._sched_thread = threading.Thread(
            target=self._scheduler_loop, name="capture-burst", daemon=True
        )
        self._sched_thread.start()

    # ---- public entry point --------------------------------------------------

    def action(self, *, action_type: str, params: dict[str, Any], source: str,
               device: str | None = None, before_frame: Any | None = None) -> Any:
        """Return a context manager wrapping one action. No-op ctx if disabled."""
        if not self.enabled:
            return _NULL_CTX
        if self.session_dir is None:
            # Auto-start a session if the daemon never called new_session().
            if self.new_session() is None:
                return _NULL_CTX
        return _ActionCtx(self, action_type, params, source, device, before_frame)

    # ---- after-burst orchestration ------------------------------------------

    def _on_action_exit(self, ctx: _ActionCtx) -> None:
        """Called from _ActionCtx.__exit__: persist before-shot + schedule after-burst."""
        if self.session_dir is None or self._encoder is None:
            return
        self.stats["actions"] += 1
        seq = ctx.seq
        prefix = f"{seq:08d}"

        delay_before_ms = None
        if self._prev_ts_sent is not None:
            delay_before_ms = int((ctx.ts - self._prev_ts_sent) * 1000)

        # Backpressure: if too many bursts are already in flight, keep the
        # before-shot but skip the after-burst (record it as dropped).
        with self._sched_cv:
            over_capacity = self._inflight >= self.max_inflight

        after_paths: list[str] = []
        after_dropped = over_capacity or ctx.before_frame is None

        # Persist the before-shot (async encode).
        before_rel = ""
        if ctx.before_frame is not None:
            before_path = self.session_dir / f"{prefix}_before.{self._ext()}"
            before_rel = self._relpath(before_path)
            self._encoder.submit(self._encode_and_write, ctx.before_frame, before_path)

        record = {
            "seq": seq,
            "session_id": self.session_id,
            "ts": round(ctx.ts, 3),
            "ts_sent": round(ctx.ts_sent or ctx.ts, 3),
            "source": ctx.source,
            "action_type": ctx.action_type,
            "params": ctx.params,
            "device": ctx.device,
            "resolution": list(ctx.resolution),
            "before_shot": before_rel,
            "after_shots": after_paths,   # filled in as frames land
            "after_dropped": after_dropped,
            "prev_seq": self._prev_seq,
            "delay_before_ms": delay_before_ms,
        }
        self._prev_seq = seq
        self._prev_ts_sent = ctx.ts_sent

        # Write a pre-record now (crash-safe) — final record rewritten when burst done.
        self._append_jsonl(record, pre=True)

        if after_dropped:
            if over_capacity:
                self.stats["after_dropped"] += 1
                logger.debug(f"[capture] after-burst dropped (inflight={self._inflight}) seq={seq}")
            self._append_jsonl(record, pre=False)
            self._maybe_prune()
            return

        # Schedule the after-burst frames on the single scheduler thread.
        with self._sched_cv:
            self._inflight += 1
            now = time.time()
            state = {"record": record, "written": 0, "expected": self.burst_count,
                     "prefix": prefix, "after_paths": after_paths}
            for k in range(self.burst_count):
                due = now + self.burst_interval * (k + 1)
                task = ("frame", state, k)
                heapq.heappush(self._heap, (due, next(self._heap_seq), task))
            self._sched_cv.notify()
        self._maybe_prune()

    def _scheduler_loop(self) -> None:
        """Single background thread: fire due after-burst captures in time order."""
        while True:
            with self._sched_cv:
                while not self._heap and not self._shutdown:
                    self._sched_cv.wait()
                if self._shutdown and not self._heap:
                    return
                due, _tb, task = self._heap[0]
                now = time.time()
                if due > now:
                    self._sched_cv.wait(timeout=min(due - now, 1.0))
                    continue
                heapq.heappop(self._heap)
            # Do the capture OUTSIDE the cv lock.
            try:
                self._run_burst_frame(task)
            except Exception as e:
                logger.debug(f"[capture] burst frame error: {e}")

    def _run_burst_frame(self, task: tuple[str, dict[str, Any], int]) -> None:
        _kind, state, k = task
        prefix = state["prefix"]
        path = self.session_dir / f"{prefix}_after_{k:02d}.{self._ext()}"  # type: ignore[union-attr]
        try:
            frame = self._grab_frame()
        except Exception as e:
            frame = None
            logger.debug(f"[capture] after-grab failed {prefix}#{k}: {e}")
        if frame is not None and self._encoder is not None:
            state["after_paths"].append(self._relpath(path))
            self._encoder.submit(self._encode_and_write, frame, path)
        # Track completion of this burst.
        state["written"] += 1
        if state["written"] >= state["expected"]:
            state["after_paths"].sort()
            state["record"]["after_shots"] = list(state["after_paths"])
            self._append_jsonl(state["record"], pre=False)
            with self._sched_cv:
                self._inflight = max(0, self._inflight - 1)

    # ---- encode / write ------------------------------------------------------

    def _ext(self) -> str:
        return "jpg" if self.fmt == "jpg" else "png"

    def _encode_and_write(self, frame: Any, path: Path) -> None:
        try:
            img = frame
            if self.downscale and self.downscale != 1.0:
                img = cv2.resize(img, None, fx=self.downscale, fy=self.downscale,
                                 interpolation=cv2.INTER_AREA)
            if self.fmt == "jpg":
                params = [cv2.IMWRITE_JPEG_QUALITY, self.jpg_quality]
            else:
                params = [cv2.IMWRITE_PNG_COMPRESSION, 1]  # fast PNG; CPU is plentiful
            ok = cv2.imwrite(str(path), img, params)
            if ok:
                self.stats["frames_written"] += 1
        except Exception as e:
            logger.debug(f"[capture] write failed {path.name}: {e}")

    # ---- jsonl ---------------------------------------------------------------

    def _append_jsonl(self, record: dict[str, Any], pre: bool) -> None:
        if self.session_dir is None:
            return
        fname = "actions.pre.jsonl" if pre else "actions.jsonl"
        line = json.dumps(record, default=str)
        try:
            with self._jsonl_lock:
                with open(self.session_dir / fname, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception as e:
            logger.debug(f"[capture] jsonl append failed: {e}")

    def _relpath(self, p: Path) -> str:
        try:
            return str(p.relative_to(PROJECT_ROOT)).replace("\\", "/")
        except Exception:
            return str(p)

    # ---- pruning -------------------------------------------------------------

    def _maybe_prune(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_prune < 300:  # throttle: every 5 min
            return
        self._last_prune = now
        try:
            self._prune()
        except Exception as e:
            logger.debug(f"[capture] prune failed: {e}")

    def _prune(self) -> None:
        """Bound the capture dir by BYTES, trimming oldest image frames first.

        Critically this trims frames INSIDE the active session too (the previous
        version protected the current session, so a long-running daemon session
        grew unbounded and blew past the cap - it filled a 953GB disk). We keep
        the small .jsonl logs (they're the record of what happened) and only ever
        delete image frames, oldest-first, until we're under the byte budget.
        """
        if not self.base_dir.exists():
            return

        # 1) Whole-session age cull for NON-current sessions past the age cap.
        current = self.session_dir.resolve() if self.session_dir else None
        age_cutoff = time.time() - self.max_age_hours * 3600
        removed_dirs = 0
        for d in list(self.base_dir.iterdir()):
            if not d.is_dir():
                continue
            try:
                if current is not None and d.resolve() == current:
                    continue
                if d.stat().st_mtime < age_cutoff:
                    if self._rm_dir(d):
                        removed_dirs += 1
            except Exception:
                continue

        # 2) Byte-budget trim across ALL sessions (incl. current): collect every
        #    image frame, oldest-first, and delete until under the cap. Never the
        #    .jsonl. In-flight burst frames are the newest, so they're safe.
        max_bytes = int(self.max_gb * (1024 ** 3))
        frames: list[tuple[float, int, Path]] = []
        total = 0
        for f in self.base_dir.rglob("*"):
            try:
                if not f.is_file():
                    continue
                st = f.stat()
                total += st.st_size
                if f.suffix.lower() in (".png", ".jpg", ".jpeg"):
                    frames.append((st.st_mtime, st.st_size, f))
            except Exception:
                continue

        removed_frames = 0
        if total > max_bytes:
            frames.sort(key=lambda x: x[0])  # oldest first
            for _mtime, size, f in frames:
                if total <= max_bytes:
                    break
                try:
                    f.unlink()
                    total -= size
                    removed_frames += 1
                except Exception:
                    continue

        # 3) Tidy up: remove now-empty non-current session dirs left behind by
        #    frame trimming (keeps the base dir clean).
        for d in list(self.base_dir.iterdir()):
            try:
                if not d.is_dir():
                    continue
                if current is not None and d.resolve() == current:
                    continue
                if not any(d.iterdir()):
                    self._rm_dir(d)
            except Exception:
                continue

        if removed_dirs or removed_frames:
            logger.info(f"[capture] pruned {removed_dirs} old session(s), "
                        f"{removed_frames} frame(s); now {total/(1024**3):.1f}GB / {self.max_gb}GB")

    def _rm_dir(self, d: Path) -> bool:
        try:
            import shutil
            shutil.rmtree(d, ignore_errors=True)
            return True
        except Exception:
            return False

    # ---- status / shutdown ---------------------------------------------------

    def disk_usage_gb(self) -> float:
        try:
            if not self.base_dir.exists():
                return 0.0
            total = sum(f.stat().st_size for f in self.base_dir.rglob("*") if f.is_file())
            return round(total / (1024 ** 3), 2)
        except Exception:
            return 0.0

    def status(self) -> dict[str, Any]:
        with self._sched_cv:
            queue = len(self._heap)
            inflight = self._inflight
        return {
            "enabled": self.enabled,
            "config_enabled": self._config_enabled,
            "runtime_enabled": self._runtime_enabled,
            "degraded": self._degraded,
            "session_id": self.session_id,
            "format": self.fmt,
            "burst_count": self.burst_count,
            "queue_depth": queue,
            "inflight_bursts": inflight,
            "disk_gb": self.disk_usage_gb(),
            "max_gb": self.max_gb,
            "stats": dict(self.stats),
        }

    def shutdown(self) -> None:
        self._shutdown = True
        with self._sched_cv:
            self._sched_cv.notify_all()
        if self._encoder is not None:
            self._encoder.shutdown(wait=False)


# ---- singleton --------------------------------------------------------------

_action_capture: ActionCapture | None = None
_singleton_lock = threading.Lock()


def get_action_capture() -> ActionCapture:
    """Get the process-wide ActionCapture singleton."""
    global _action_capture
    if _action_capture is None:
        with _singleton_lock:
            if _action_capture is None:
                _action_capture = ActionCapture()
    return _action_capture
