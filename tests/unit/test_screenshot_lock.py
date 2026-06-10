"""Tests that WindowsScreenshotHelper serializes captures across instances."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.windows_screenshot_helper import WindowsScreenshotHelper


def _bare_helper() -> WindowsScreenshotHelper:
    h = WindowsScreenshotHelper.__new__(WindowsScreenshotHelper)
    h.window_title = "test"
    h.hwnd = 1
    return h


def test_concurrent_captures_are_serialized(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two helper instances capturing concurrently must never overlap -
    they share one HWND and concurrent GDI access crashes."""
    inside = 0
    max_inside = 0
    counter_lock = threading.Lock()

    def fake_capture(self: WindowsScreenshotHelper, max_retries: int = 3) -> Image.Image:
        nonlocal inside, max_inside
        with counter_lock:
            inside += 1
            max_inside = max(max_inside, inside)
        time.sleep(0.05)
        with counter_lock:
            inside -= 1
        return Image.new("RGB", (200, 200))

    monkeypatch.setattr(WindowsScreenshotHelper, "_find_window", lambda self: None)
    monkeypatch.setattr(WindowsScreenshotHelper, "ensure_window_size", lambda self: None)
    monkeypatch.setattr(WindowsScreenshotHelper, "capture_window", fake_capture)

    helpers = [_bare_helper() for _ in range(4)]
    errors: list[Exception] = []

    def capture(h: WindowsScreenshotHelper) -> None:
        try:
            frame = h.get_screenshot_cv2()
            assert frame.shape == (2160, 3840, 3)
        except Exception as e:  # pragma: no cover - surfaced via errors list
            errors.append(e)

    threads = [threading.Thread(target=capture, args=(h,)) for h in helpers]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors
    assert max_inside == 1, f"captures overlapped (max concurrent: {max_inside})"
