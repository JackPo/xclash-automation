"""
Stamina Use flow - open stamina popup and click Use button.

This flow:
1. Clicks on stamina display to open the stamina popup
2. Waits for popup to appear
3. Detects if Use button is present (for stamina recovery items)
4. Clicks Use if found (+50 stamina)
5. Closes the popup

Templates:
- Trigger: templates/ground_truth/use_button_4k.png (271x118 at ~2149,1381)
- Click position: center (2284, 1440)
"""

from pathlib import Path
import time
import cv2

from config import STAMINA_REGION, STAMINA_USE_BUTTON, BACK_BUTTON_CLICK
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.ui_helpers import click_back
from .back_from_chat_flow import back_from_chat_flow

# Template for Use button detection
USE_BUTTON_TEMPLATE = Path(__file__).parent.parent.parent / "templates" / "ground_truth" / "use_button_4k.png"

# Click position from config
USE_BUTTON_X = STAMINA_USE_BUTTON['click'][0]
USE_BUTTON_Y = STAMINA_USE_BUTTON['click'][1]

# Stamina display click position (center of STAMINA_REGION)
STAMINA_DISPLAY_X = STAMINA_REGION[0] + STAMINA_REGION[2] // 2
STAMINA_DISPLAY_Y = STAMINA_REGION[1] + STAMINA_REGION[3] // 2

# Matching threshold using TM_SQDIFF_NORMED (lower is better, 0 = perfect)
MATCH_THRESHOLD = 0.05

# Search region from config
SEARCH_REGION = STAMINA_USE_BUTTON['search_region']


def stamina_use_flow(adb, screenshot_helper=None):
    """
    Open stamina popup and click the Use button if present.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance (optional)

    Returns:
        True if Use button was found and clicked, False otherwise
    """
    win = screenshot_helper if screenshot_helper else WindowsScreenshotHelper()

    # Step 1: Click on stamina display to open popup
    print(f"    [STAMINA-USE] Step 1: Opening stamina popup (clicking {STAMINA_DISPLAY_X}, {STAMINA_DISPLAY_Y})")
    adb.tap(STAMINA_DISPLAY_X, STAMINA_DISPLAY_Y)

    # Step 2: Wait for popup to appear
    time.sleep(0.5)

    # Step 3: Take screenshot and check for Use button
    print("    [STAMINA-USE] Step 2: Checking for Use button...")
    frame = win.get_screenshot_cv2()

    if frame is None:
        print("    [STAMINA-USE] Failed to get screenshot")
        back_from_chat_flow(adb, win)
        return False

    # Load template
    template = cv2.imread(str(USE_BUTTON_TEMPLATE))
    if template is None:
        print(f"    [STAMINA-USE] Template not found: {USE_BUTTON_TEMPLATE}")
        back_from_chat_flow(adb, win)
        return False

    # Extract search region
    rx, ry, rw, rh = SEARCH_REGION
    roi = frame[ry:ry+rh, rx:rx+rw]

    # Convert to grayscale
    roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

    # Template match using TM_SQDIFF_NORMED (lower = better match)
    result = cv2.matchTemplate(roi_gray, template_gray, cv2.TM_SQDIFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    print(f"    [STAMINA-USE] Match score: {min_val:.4f} (threshold: {MATCH_THRESHOLD})")

    if min_val > MATCH_THRESHOLD:
        print("    [STAMINA-USE] Use button not found (no recovery items available)")
        # Close popup
        click_back(adb)  # Click back button to close stamina popup
        time.sleep(0.3)
        back_from_chat_flow(adb, win)
        return False

    # Step 4: Click the Use button
    print(f"    [STAMINA-USE] Step 3: Clicking Use at ({USE_BUTTON_X}, {USE_BUTTON_Y})")
    adb.tap(USE_BUTTON_X, USE_BUTTON_Y)

    # Step 5: Wait and close popup
    time.sleep(0.5)
    print("    [STAMINA-USE] Step 4: Closing popup with back button")
    click_back(adb)  # Click back button to close stamina popup
    time.sleep(0.3)
    back_from_chat_flow(adb, win)

    print("    [STAMINA-USE] Flow complete - used +50 stamina recovery item!")
    return True


def check_use_button(frame):
    """
    Check if Use button is present in the given frame.

    Args:
        frame: BGR numpy array screenshot

    Returns:
        (is_present, score) tuple
    """
    template = cv2.imread(str(USE_BUTTON_TEMPLATE))
    if template is None:
        return False, 1.0

    # Extract search region
    rx, ry, rw, rh = SEARCH_REGION
    roi = frame[ry:ry+rh, rx:rx+rw]

    # Convert to grayscale
    roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

    # Template match
    result = cv2.matchTemplate(roi_gray, template_gray, cv2.TM_SQDIFF_NORMED)
    min_val, _, _, _ = cv2.minMaxLoc(result)

    return min_val <= MATCH_THRESHOLD, min_val
