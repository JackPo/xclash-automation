"""
Back from Chat Flow

Generic action to close chat dialogs by clicking the back button.
Searches for both dark and light back button variants and clicks until neither is detected.

Templates:
- back_button_4k.png (dark teal, gray arrow)
- back_button_light_4k.png (bright cyan, white arrow)

Click position: (1407, 2055) - center of back button
"""

import time
from pathlib import Path

import cv2
import numpy as np


# Import from centralized config
from config import BACK_BUTTON_CLICK
from utils.ui_helpers import click_back

# Extract X, Y for logging purposes
BACK_BUTTON_X = BACK_BUTTON_CLICK[0]
BACK_BUTTON_Y = BACK_BUTTON_CLICK[1]

# Search region around the back button (with some margin)
SEARCH_X = 1300
SEARCH_Y = 1950
SEARCH_W = 220
SEARCH_H = 220

# Templates
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATE_DARK = BASE_DIR / "templates" / "ground_truth" / "back_button_4k.png"
TEMPLATE_LIGHT = BASE_DIR / "templates" / "ground_truth" / "back_button_light_4k.png"

# Matching threshold
THRESHOLD = 0.7  # TM_CCOEFF_NORMED - higher is better


def _load_templates():
    """Load both back button templates."""
    dark = cv2.imread(str(TEMPLATE_DARK), cv2.IMREAD_GRAYSCALE)
    light = cv2.imread(str(TEMPLATE_LIGHT), cv2.IMREAD_GRAYSCALE)
    return dark, light


def _find_back_button(frame, template_dark, template_light):
    """
    Search for either back button variant in the frame.

    Returns:
        Tuple of (found, variant, score) where variant is 'dark', 'light', or None
    """
    # Extract search region
    roi = frame[SEARCH_Y:SEARCH_Y + SEARCH_H, SEARCH_X:SEARCH_X + SEARCH_W]

    if len(roi.shape) == 3:
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    else:
        roi_gray = roi

    best_score = 0
    best_variant = None

    # Try dark template
    if template_dark is not None:
        result = cv2.matchTemplate(roi_gray, template_dark, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        if max_val > best_score:
            best_score = max_val
            best_variant = 'dark'

    # Try light template
    if template_light is not None:
        result = cv2.matchTemplate(roi_gray, template_light, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        if max_val > best_score:
            best_score = max_val
            best_variant = 'light'

    found = best_score >= THRESHOLD
    return found, best_variant, best_score


def back_from_chat_flow(adb, screenshot_helper=None, max_clicks=5):
    """
    Close chat dialogs by clicking back button until it's gone.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance (optional, will create if not provided)
        max_clicks: Maximum number of back button clicks (default 5)

    Returns:
        Number of back buttons clicked
    """
    # Load templates
    template_dark, template_light = _load_templates()

    if template_dark is None and template_light is None:
        print("    [BACK] ERROR: No back button templates found")
        return 0

    # Get screenshot helper
    if screenshot_helper is None:
        from utils.windows_screenshot_helper import WindowsScreenshotHelper
        screenshot_helper = WindowsScreenshotHelper()

    clicks = 0

    for i in range(max_clicks):
        # Take screenshot
        frame = screenshot_helper.get_screenshot_cv2()

        # Search for back button
        found, variant, score = _find_back_button(frame, template_dark, template_light)

        if not found:
            print(f"    [BACK] No back button detected (score={score:.3f}), done after {clicks} clicks")
            break

        # Click the back button
        print(f"    [BACK] Clicking back button ({variant}, score={score:.3f})")
        click_back(adb)
        clicks += 1

        # Wait for UI to update
        time.sleep(0.3)

    return clicks


# For standalone testing
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(BASE_DIR))

    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    adb = ADBHelper()
    helper = WindowsScreenshotHelper()

    print("Testing back_from_chat_flow...")
    clicks = back_from_chat_flow(adb, helper)
    print(f"Done. Clicked {clicks} times.")
