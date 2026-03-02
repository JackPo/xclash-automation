"""
Gold coin harvest flow - clicks the gold coin bubble.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import cv2

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.gold_coin_matcher import GoldCoinMatcher

from utils.windows_screenshot_helper import WindowsScreenshotHelper

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper


def _save_debug(frame, label: str) -> Path:
    """Save a debug screenshot for gold flow before/after click analysis."""
    debug_dir = Path(__file__).parent.parent.parent / "screenshots" / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S_%f")[:-3]
    out = debug_dir / f"gold_{ts}_{label}.png"
    cv2.imwrite(str(out), frame)
    return out


def gold_coin_flow(adb: ADBHelper, win: WindowsScreenshotHelper | None = None) -> bool:
    """Click the gold coin harvest bubble if present.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (optional, creates one if not provided)

    Returns:
        bool: True if clicked, False if not present
    """
    if win is None:
        win = WindowsScreenshotHelper()

    matcher = GoldCoinMatcher()
    frame = win.get_screenshot_cv2()

    is_present, score = matcher.is_present(frame)
    if not is_present:
        print(f"    [GOLD] Not present (score={score:.3f})")
        return False

    pre_path = _save_debug(frame, f"PRE_CLICK_score_{score:.4f}")
    matcher.click(adb)
    time.sleep(0.3)

    post_frame = win.get_screenshot_cv2()
    post_path = _save_debug(post_frame, "POST_CLICK")
    print(
        f"    [GOLD] Clicked harvest bubble (score={score:.3f}) "
        f"pre={pre_path.name} post={post_path.name}"
    )
    return True
