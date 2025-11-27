"""
Harvest Box flow - complete harvest sequence.

Step 1: Click the harvest box icon at fixed position (2177, 1618)
Step 2: Wait briefly for dialog to appear
Step 3: Find harvest_surprise_box_4k.png vertically (it moves) and click it
Step 4: Click Open button at fixed position (1918, 1254)
Step 5: Click Back button at fixed position (1407, 2055)

Templates:
- Trigger icon: templates/ground_truth/harvest_box_4k.png (154x157 at 2100,1540)
- Dialog box: templates/ground_truth/harvest_surprise_box_4k.png (791x253, moves vertically)
- Open button: templates/ground_truth/open_button_4k.png (242x99 at 1797,1205)
- Back button: templates/ground_truth/back_button_4k.png (142x136 at 1336,1987)
"""

from pathlib import Path
import time
import cv2

# Template for the dialog box (moves vertically)
SURPRISE_BOX_TEMPLATE = Path(__file__).parent.parent.parent / "templates" / "ground_truth" / "harvest_surprise_box_4k.png"

# Matching threshold for dialog - looser because text inside changes
MATCH_THRESHOLD = 0.7

# Fixed click positions
HARVEST_ICON_CLICK_X = 2177
HARVEST_ICON_CLICK_Y = 1618

OPEN_BUTTON_X = 1918
OPEN_BUTTON_Y = 1254

BACK_BUTTON_X = 1407
BACK_BUTTON_Y = 2055


def harvest_box_flow(adb, screenshot_helper=None):
    """
    Complete harvest box flow: icon -> surprise box -> open -> back.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance (optional)

    Returns:
        True if successful, False otherwise
    """
    # Step 1: Click the harvest box icon
    print(f"    [HARVEST] Step 1: Clicking icon at ({HARVEST_ICON_CLICK_X}, {HARVEST_ICON_CLICK_Y})")
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

    print(f"    [HARVEST] Step 2: Dialog match score: {max_val:.3f} (threshold: {MATCH_THRESHOLD})")

    if max_val < MATCH_THRESHOLD:
        print(f"    [HARVEST] Dialog not found (score {max_val:.3f} < {MATCH_THRESHOLD})")
        return False

    # Found! Calculate click position (center of template)
    template_h, template_w = template_gray.shape
    top_left = max_loc
    center_x = top_left[0] + template_w // 2
    center_y = top_left[1] + template_h // 2

    print(f"    [HARVEST] Step 3: Clicking surprise box at ({center_x}, {center_y})")
    adb.tap(center_x, center_y)

    # Step 4: Click Open button
    time.sleep(0.5)
    print(f"    [HARVEST] Step 4: Clicking Open at ({OPEN_BUTTON_X}, {OPEN_BUTTON_Y})")
    adb.tap(OPEN_BUTTON_X, OPEN_BUTTON_Y)

    # Step 5: Click Back button
    time.sleep(0.5)
    print(f"    [HARVEST] Step 5: Clicking Back at ({BACK_BUTTON_X}, {BACK_BUTTON_Y})")
    adb.tap(BACK_BUTTON_X, BACK_BUTTON_Y)

    print("    [HARVEST] Flow complete")
    return True
