"""
Stamina Claim flow - open stamina popup and click Claim button.

This flow:
1. Clicks on stamina display to open the stamina popup
2. Waits for popup to appear
3. Detects if Claim button is present (free stamina every 4 hours)
4. Clicks Claim if found
5. Closes the popup

Templates:
- Trigger: templates/ground_truth/claim_button_4k.png (256x107 at ~2161,690)
- Click position: center (2284, 743)
"""

from pathlib import Path
import time
import cv2

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from .back_from_chat_flow import back_from_chat_flow

# Template for Claim button detection
CLAIM_BUTTON_TEMPLATE = Path(__file__).parent.parent.parent / "templates" / "ground_truth" / "claim_button_4k.png"

# Fixed click position (center of Claim button)
CLAIM_BUTTON_X = 2284
CLAIM_BUTTON_Y = 743

# Stamina display click position (to open popup)
# Based on STAMINA_REGION from config: (69, 203, 96, 60)
STAMINA_DISPLAY_X = 117  # center of region
STAMINA_DISPLAY_Y = 233

# Matching threshold using TM_SQDIFF_NORMED (lower is better, 0 = perfect)
MATCH_THRESHOLD = 0.05

# Search region for Claim button (to avoid false positives elsewhere)
# Based on stamina popup location - upper half of center screen
SEARCH_REGION = (1800, 400, 800, 500)  # x, y, w, h


def stamina_claim_flow(adb, screenshot_helper=None):
    """
    Open stamina popup and click the Claim button if present.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance (optional)

    Returns:
        True if Claim button was found and clicked, False otherwise
    """
    win = screenshot_helper if screenshot_helper else WindowsScreenshotHelper()

    # Step 1: Click on stamina display to open popup
    print(f"    [STAMINA-CLAIM] Step 1: Opening stamina popup (clicking {STAMINA_DISPLAY_X}, {STAMINA_DISPLAY_Y})")
    adb.tap(STAMINA_DISPLAY_X, STAMINA_DISPLAY_Y)

    # Step 2: Wait for popup to appear
    time.sleep(0.5)

    # Step 3: Take screenshot and check for Claim button
    print("    [STAMINA-CLAIM] Step 2: Checking for Claim button...")
    frame = win.get_screenshot_cv2()

    if frame is None:
        print("    [STAMINA-CLAIM] Failed to get screenshot")
        back_from_chat_flow(adb, win)
        return False

    # Load template
    template = cv2.imread(str(CLAIM_BUTTON_TEMPLATE))
    if template is None:
        print(f"    [STAMINA-CLAIM] Template not found: {CLAIM_BUTTON_TEMPLATE}")
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

    print(f"    [STAMINA-CLAIM] Match score: {min_val:.4f} (threshold: {MATCH_THRESHOLD})")

    if min_val > MATCH_THRESHOLD:
        print("    [STAMINA-CLAIM] Claim button not found (no free stamina available)")
        # Close popup
        back_from_chat_flow(adb, win)
        return False

    # Step 4: Click the Claim button
    print(f"    [STAMINA-CLAIM] Step 3: Clicking Claim at ({CLAIM_BUTTON_X}, {CLAIM_BUTTON_Y})")
    adb.tap(CLAIM_BUTTON_X, CLAIM_BUTTON_Y)

    # Step 5: Wait and close popup
    time.sleep(0.5)
    print("    [STAMINA-CLAIM] Step 4: Closing popup")
    back_from_chat_flow(adb, win)

    print("    [STAMINA-CLAIM] Flow complete - claimed free stamina!")
    return True


def check_claim_button(frame):
    """
    Check if Claim button is present in the given frame.

    Args:
        frame: BGR numpy array screenshot

    Returns:
        (is_present, score) tuple
    """
    template = cv2.imread(str(CLAIM_BUTTON_TEMPLATE))
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
