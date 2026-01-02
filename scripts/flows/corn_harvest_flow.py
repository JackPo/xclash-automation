"""
Corn harvest flow - clicks the corn bubble.
"""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.corn_harvest_matcher import CornHarvestMatcher
from utils.windows_screenshot_helper import WindowsScreenshotHelper


def corn_harvest_flow(adb, win=None):
    """Click the corn harvest bubble if present.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (optional, creates one if not provided)

    Returns:
        bool: True if clicked, False if not present
    """
    if win is None:
        win = WindowsScreenshotHelper()

    matcher = CornHarvestMatcher()
    frame = win.get_screenshot_cv2()

    is_present, score = matcher.is_present(frame)
    if not is_present:
        print(f"    [CORN] Not present (score={score:.3f})")
        return False

    matcher.click(adb)
    time.sleep(0.3)
    print(f"    [CORN] Clicked harvest bubble (score={score:.3f})")
    return True
