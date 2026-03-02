"""
Cabbage harvest flow - clicks the cabbage bubble.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.cabbage_matcher import CabbageMatcher

from utils.windows_screenshot_helper import WindowsScreenshotHelper

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper


def cabbage_flow(adb: ADBHelper, win: WindowsScreenshotHelper | None = None) -> bool | dict[str, object]:
    """Click the cabbage bubble if present.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (optional, creates one if not provided)

    Returns:
        bool: True if clicked, False if not present
    """
    if win is None:
        win = WindowsScreenshotHelper()

    matcher = CabbageMatcher()
    frame = win.get_screenshot_cv2()

    is_present, score = matcher.is_present(frame)
    if not is_present:
        print(f"    [CABBAGE] Not present (score={score:.3f})")
        return False

    matcher.click(adb)
    time.sleep(0.3)

    # Verify the click actually changed state; if not, back off instead of repeating spam clicks.
    after = win.get_screenshot_cv2()
    still_present, after_score = matcher.is_present(after)
    if still_present:
        print(
            f"    [CABBAGE] No visible change after click "
            f"(before={score:.3f}, after={after_score:.3f}) - backing off"
        )
        return {
            "skipped": True,
            "reason": "cabbage_no_effect_after_click",
            "before_score": float(score),
            "after_score": float(after_score),
        }

    print(f"    [CABBAGE] Clicked harvest bubble (score={score:.3f} -> {after_score:.3f})")
    return True
