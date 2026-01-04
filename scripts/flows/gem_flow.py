"""
Gem harvest flow - clicks the gem bubble.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.gem_matcher import GemMatcher

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper


def gem_flow(adb: ADBHelper, win: WindowsScreenshotHelper | None = None) -> bool:
    """Click the gem harvest bubble if present.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (optional, creates one if not provided)

    Returns:
        bool: True if clicked, False if not present
    """
    if win is None:
        win = WindowsScreenshotHelper()

    matcher = GemMatcher()
    frame = win.get_screenshot_cv2()

    is_present, score = matcher.is_present(frame)
    if not is_present:
        print(f"    [GEM] Not present (score={score:.3f})")
        return False

    matcher.click(adb)
    time.sleep(0.3)
    print(f"    [GEM] Clicked harvest bubble (score={score:.3f})")
    return True
