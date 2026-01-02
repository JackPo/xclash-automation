"""
Cabbage harvest flow - clicks the cabbage bubble.
"""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.cabbage_matcher import CabbageMatcher
from utils.windows_screenshot_helper import WindowsScreenshotHelper


def cabbage_flow(adb, win=None):
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
    print(f"    [CABBAGE] Clicked harvest bubble (score={score:.3f})")
    return True
