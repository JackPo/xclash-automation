"""
FrameBus - a latest-frame pub/sub for continuous detection.

Every frame captured ANYWHERE in the process (main loop, flow polls, action
capture) is published here by a hook inside WindowsScreenshotHelper, so a
background detector can consume fresh frames with ZERO additional GDI load.
Crucially, flows capture frames constantly while they run - which is exactly
when the old serial design was blind - so the bus is freshest during flows.

Consumers call latest(max_age) and get (frame, ts) or None. Frames are BGR
numpy arrays at 4K; the bus stores only a reference (no copies) - consumers
must treat frames as read-only (all matchers do).
"""
from __future__ import annotations

import threading
import time
from typing import Any


class FrameBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._frame: Any = None
        self._ts: float = 0.0

    def publish(self, frame: Any) -> None:
        """Store the newest frame. Called from get_screenshot_cv2 on every
        capture - must be effectively free (reference swap under a lock)."""
        if frame is None:
            return
        with self._cond:
            self._frame = frame
            self._ts = time.time()
            self._cond.notify_all()

    def latest(self, max_age: float | None = None) -> tuple[Any, float] | None:
        """Newest (frame, ts), or None if empty / older than max_age."""
        with self._lock:
            if self._frame is None:
                return None
            if max_age is not None and (time.time() - self._ts) > max_age:
                return None
            return self._frame, self._ts

    def wait_for_frame(self, newer_than: float, timeout: float) -> tuple[Any, float] | None:
        """Block until a frame newer than `newer_than` arrives (or timeout)."""
        deadline = time.time() + timeout
        with self._cond:
            while self._ts <= newer_than:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                self._cond.wait(remaining)
            return self._frame, self._ts

    @property
    def age(self) -> float:
        with self._lock:
            return (time.time() - self._ts) if self._frame is not None else float("inf")


_bus: FrameBus | None = None
_bus_lock = threading.Lock()


def get_frame_bus() -> FrameBus:
    global _bus
    with _bus_lock:
        if _bus is None:
            _bus = FrameBus()
        return _bus
