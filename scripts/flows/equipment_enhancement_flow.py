"""
Equipment enhancement flow - clicks the crossed swords bubble.
"""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.equipment_enhancement_matcher import EquipmentEnhancementMatcher
from utils.windows_screenshot_helper import WindowsScreenshotHelper


def equipment_enhancement_flow(adb, win=None):
    """Click the equipment enhancement bubble if present.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (optional, creates one if not provided)

    Returns:
        bool: True if clicked, False if not present
    """
    if win is None:
        win = WindowsScreenshotHelper()

    matcher = EquipmentEnhancementMatcher()
    frame = win.get_screenshot_cv2()

    is_present, score = matcher.is_present(frame)
    if not is_present:
        print(f"    [EQUIPMENT] Not present (score={score:.3f})")
        return False

    matcher.click(adb)
    time.sleep(0.3)
    print(f"    [EQUIPMENT] Clicked enhancement bubble (score={score:.3f})")
    return True
