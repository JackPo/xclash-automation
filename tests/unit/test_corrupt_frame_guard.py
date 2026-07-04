"""Tests for the WindowsScreenshotHelper corrupt-frame (black-band) guard.

Root cause: PrintWindow intermittently returns a frame with a wide near-black
band across the top while the rest renders fine, silently breaking fixed-region
template detection (rally panel, tavern tabs, harvest bubbles). The guard
detects that signature and re-captures.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.windows_screenshot_helper import WindowsScreenshotHelper

REPO_ROOT = Path(__file__).parent.parent.parent
CORRUPT_FRAME = REPO_ROOT / "screenshots/debug/rally_join/162559_788_step1_panel_check.png"
CLEAN_FRAME = REPO_ROOT / "screenshots/debug/rally_march_162558_attempt3_panel_OPEN.png"

H, W = 2160, 3840


def _bare_helper() -> WindowsScreenshotHelper:
    h = WindowsScreenshotHelper.__new__(WindowsScreenshotHelper)
    h.window_title = "test"
    h.hwnd = 1
    return h


def _bright_frame() -> np.ndarray:
    return np.full((H, W, 3), 150, dtype=np.uint8)


def _bright_frame_with_band() -> np.ndarray:
    f = _bright_frame()
    f[10:120, :, :] = 0  # ~110px black band across the top (~5% of height)
    return f


# --- _frame_looks_corrupt: synthetic frames -------------------------------

def test_uniform_dark_is_not_corrupt() -> None:
    """A genuinely dark screen (loading/night) must NOT be flagged."""
    dark = np.full((H, W, 3), 15, dtype=np.uint8)
    assert _bare_helper()._frame_looks_corrupt(dark) is False


def test_clean_bright_is_not_corrupt() -> None:
    assert _bare_helper()._frame_looks_corrupt(_bright_frame()) is False


def test_bright_with_black_band_is_corrupt() -> None:
    assert _bare_helper()._frame_looks_corrupt(_bright_frame_with_band()) is True


# --- _frame_looks_corrupt: real reference frames --------------------------

@pytest.mark.skipif(not CORRUPT_FRAME.exists(), reason="reference corrupt frame not present")
def test_reference_corrupt_frame() -> None:
    import cv2
    img = cv2.imread(str(CORRUPT_FRAME))
    assert _bare_helper()._frame_looks_corrupt(img) is True


@pytest.mark.skipif(not CLEAN_FRAME.exists(), reason="reference clean frame not present")
def test_reference_clean_frame() -> None:
    import cv2
    img = cv2.imread(str(CLEAN_FRAME))
    assert _bare_helper()._frame_looks_corrupt(img) is False


@pytest.mark.skipif(not (CORRUPT_FRAME.exists() and CLEAN_FRAME.exists()),
                    reason="reference frames not present")
def test_detector_premise() -> None:
    """Pin the root cause: the heading detector fails on the corrupt frame and
    passes on the clean one."""
    import cv2
    from utils.union_war_panel_detector import UnionWarPanelDetector
    d = UnionWarPanelDetector()
    bad_found, bad_score = d.is_union_war_panel(cv2.imread(str(CORRUPT_FRAME)))
    good_found, good_score = d.is_union_war_panel(cv2.imread(str(CLEAN_FRAME)))
    assert bad_found is False and bad_score > 0.05
    assert good_found is True and good_score <= 0.05


# --- get_screenshot_cv2 retry behavior ------------------------------------

def test_retry_returns_first_clean_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("utils.windows_screenshot_helper.time.sleep", lambda *_: None)
    clean = _bright_frame()
    frames = [_bright_frame_with_band(), _bright_frame_with_band(), clean]
    calls = {"n": 0}

    def fake_once(self: WindowsScreenshotHelper) -> np.ndarray:
        f = frames[calls["n"]]
        calls["n"] += 1
        return f

    monkeypatch.setattr(WindowsScreenshotHelper, "_capture_once", fake_once)
    out = _bare_helper().get_screenshot_cv2()
    assert calls["n"] == 3
    assert np.array_equal(out, clean)


def test_retry_gives_up_returns_last(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("utils.windows_screenshot_helper.time.sleep", lambda *_: None)
    calls = {"n": 0}

    def fake_once(self: WindowsScreenshotHelper) -> np.ndarray:
        calls["n"] += 1
        return _bright_frame_with_band()  # always corrupt

    monkeypatch.setattr(WindowsScreenshotHelper, "_capture_once", fake_once)
    h = _bare_helper()
    out = h.get_screenshot_cv2()  # must not raise / hang
    assert calls["n"] == h.MAX_CORRUPT_RETRIES + 1
    assert out is not None and out.shape == (H, W, 3)


# --- Union Boss case-insensitive compare (icon_daemon.py:2683) -------------

@pytest.mark.parametrize("name,expected", [
    ("union boss", True),
    ("Union Boss", True),
    (" UNION BOSS ", True),
    ("elite zombie", False),
    (None, False),
])
def test_union_boss_predicate(name, expected) -> None:
    # Mirrors the daemon predicate; validator lowercases names, daemon must
    # compare case-insensitively and tolerate None.
    assert ((name or "").strip().lower() == "union boss") is expected
