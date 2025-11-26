"""
Harvest Surprise Box flow - finds and clicks the harvest box dialog.

The box moves vertically on screen, so we use template matching with
a looser threshold to find it. Text like "X/10" may change but the
overall box structure stays the same.

Template: templates/ground_truth/harvest_surprise_box_4k.png
Size: 791x253 pixels
"""

from pathlib import Path
import cv2
import numpy as np

# Template path
TEMPLATE_PATH = Path(__file__).parent.parent.parent / "templates" / "ground_truth" / "harvest_surprise_box_4k.png"

# Matching threshold - looser because text inside changes
# TM_CCOEFF_NORMED: 1.0 = perfect match, lower = worse
MATCH_THRESHOLD = 0.7


def harvest_box_flow(adb, screenshot_helper=None):
    """
    Find and click the Harvest Surprise Box.

    Uses template matching to locate the box (which moves vertically).
    Clicks at center of found location.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance (optional, will create if needed)

    Returns:
        True if box found and clicked, False otherwise
    """
    # Get screenshot
    if screenshot_helper:
        frame = screenshot_helper.get_screenshot_cv2()
    else:
        # Fallback to ADB screenshot
        from utils.adb_helper import ADBHelper
        import tempfile
        import os

        tmp_path = os.path.join(tempfile.gettempdir(), "harvest_check.png")
        adb.take_screenshot(tmp_path)
        frame = cv2.imread(tmp_path)

    if frame is None:
        print("    [HARVEST] Failed to get screenshot")
        return False

    # Load template
    template = cv2.imread(str(TEMPLATE_PATH))
    if template is None:
        print(f"    [HARVEST] Template not found: {TEMPLATE_PATH}")
        return False

    # Convert both to grayscale for matching
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

    # Template matching with correlation (tolerates small differences)
    result = cv2.matchTemplate(frame_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    print(f"    [HARVEST] Match score: {max_val:.3f} (threshold: {MATCH_THRESHOLD})")

    if max_val < MATCH_THRESHOLD:
        print(f"    [HARVEST] Box not found (score {max_val:.3f} < {MATCH_THRESHOLD})")
        return False

    # Found! Calculate click position (center of template)
    template_h, template_w = template_gray.shape
    top_left = max_loc
    center_x = top_left[0] + template_w // 2
    center_y = top_left[1] + template_h // 2

    print(f"    [HARVEST] Found at ({top_left[0]}, {top_left[1]}), clicking ({center_x}, {center_y})")
    adb.tap(center_x, center_y)

    return True
