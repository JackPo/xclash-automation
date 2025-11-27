"""
Harvest Box flow - clicks the harvest box icon, then finds and clicks the surprise box dialog.

Step 1: Click the harvest box icon at fixed position (2177, 1618)
Step 2: Wait briefly for dialog to appear
Step 3: Find harvest_surprise_box_4k.png vertically (it moves) and click it

Templates:
- Trigger icon: templates/ground_truth/harvest_box_4k.png (154x157 at 2100,1540)
- Dialog box: templates/ground_truth/harvest_surprise_box_4k.png (791x253, moves vertically)
"""

from pathlib import Path
import time
import cv2

# Template for the dialog box (moves vertically)
SURPRISE_BOX_TEMPLATE = Path(__file__).parent.parent.parent / "templates" / "ground_truth" / "harvest_surprise_box_4k.png"

# Matching threshold for dialog - looser because text inside changes
MATCH_THRESHOLD = 0.7

# Fixed click position for the harvest box icon
HARVEST_ICON_CLICK_X = 2177
HARVEST_ICON_CLICK_Y = 1618


def harvest_box_flow(adb, screenshot_helper=None):
    """
    Click harvest box icon, then find and click the Harvest Surprise Box dialog.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance (optional)

    Returns:
        True if successful, False otherwise
    """
    # Step 1: Click the harvest box icon
    print(f"    [HARVEST] Clicking icon at ({HARVEST_ICON_CLICK_X}, {HARVEST_ICON_CLICK_Y})")
    adb.tap(HARVEST_ICON_CLICK_X, HARVEST_ICON_CLICK_Y)

    # Step 2: Wait for dialog to appear
    time.sleep(1.0)

    # Step 3: Find and click the surprise box dialog
    if screenshot_helper:
        frame = screenshot_helper.get_screenshot_cv2()
    else:
        import tempfile
        import os
        tmp_path = os.path.join(tempfile.gettempdir(), "harvest_check.png")
        adb.take_screenshot(tmp_path)
        frame = cv2.imread(tmp_path)

    if frame is None:
        print("    [HARVEST] Failed to get screenshot")
        return False

    # Load template
    template = cv2.imread(str(SURPRISE_BOX_TEMPLATE))
    if template is None:
        print(f"    [HARVEST] Template not found: {SURPRISE_BOX_TEMPLATE}")
        return False

    # Convert both to grayscale for matching
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

    # Template matching with correlation (tolerates text changes)
    result = cv2.matchTemplate(frame_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    print(f"    [HARVEST] Dialog match score: {max_val:.3f} (threshold: {MATCH_THRESHOLD})")

    if max_val < MATCH_THRESHOLD:
        print(f"    [HARVEST] Dialog not found (score {max_val:.3f} < {MATCH_THRESHOLD})")
        return False

    # Found! Calculate click position (center of template)
    template_h, template_w = template_gray.shape
    top_left = max_loc
    center_x = top_left[0] + template_w // 2
    center_y = top_left[1] + template_h // 2

    print(f"    [HARVEST] Dialog found at ({top_left[0]}, {top_left[1]}), clicking ({center_x}, {center_y})")
    adb.tap(center_x, center_y)

    return True
