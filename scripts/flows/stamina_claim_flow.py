"""
Stamina Claim flow - open stamina popup and click Claim button.

This flow:
1. Clicks on stamina display to open the stamina popup
2. Waits for popup to appear
3. Detects if Claim button is present (free stamina every 4 hours)
4. If Claim found: clicks it
5. If Claim NOT found: OCRs the timer to get seconds until next claim
6. Closes the popup

Templates:
- Trigger: templates/ground_truth/claim_button_4k.png (256x107 at ~2161,690)
- Click position: center (2284, 743)

Timer OCR:
- When Claim button is not visible, a countdown timer shows in its place
- Region: (2161, 693) size 246x99
- Format: HH:MM:SS (e.g., "00:14:06" = 14 min 6 sec)
"""

from pathlib import Path
import time
import re

from config import STAMINA_REGION, STAMINA_CLAIM_BUTTON, BACK_BUTTON_CLICK
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.template_matcher import match_template
from utils.ui_helpers import click_back
from .back_from_chat_flow import back_from_chat_flow

# Click position from config
CLAIM_BUTTON_X = STAMINA_CLAIM_BUTTON['click'][0]
CLAIM_BUTTON_Y = STAMINA_CLAIM_BUTTON['click'][1]

# Stamina display click position (center of STAMINA_REGION)
STAMINA_DISPLAY_X = STAMINA_REGION[0] + STAMINA_REGION[2] // 2
STAMINA_DISPLAY_Y = STAMINA_REGION[1] + STAMINA_REGION[3] // 2

# Matching threshold using TM_SQDIFF_NORMED (lower is better, 0 = perfect)
MATCH_THRESHOLD = 0.05

# Search region from config
SEARCH_REGION = STAMINA_CLAIM_BUTTON['search_region']

# Timer region - where countdown shows when Claim is not available
# Detected via Gemini: (2161, 693) to (2407, 792), size 246x99
TIMER_REGION = (2161, 693, 246, 99)  # x, y, w, h


def _ocr_timer(frame) -> int | None:
    """
    OCR the countdown timer from the stamina popup.

    Args:
        frame: BGR screenshot with popup open

    Returns:
        Seconds until next claim, or None if OCR failed
    """
    try:
        from utils.ocr_client import OCRClient
        ocr = OCRClient()

        # Extract timer region
        tx, ty, tw, th = TIMER_REGION
        timer_roi = frame[ty:ty+th, tx:tx+tw]

        # OCR the timer
        text = ocr.extract_text(timer_roi, prompt="Read the countdown timer. Return ONLY the time in HH:MM:SS format, nothing else.")

        if not text:
            return None

        # Parse HH:MM:SS format
        # Handle various formats: "00:14:06", "0:14:06", "14:06"
        text = text.strip()

        # Try HH:MM:SS
        match = re.match(r'(\d{1,2}):(\d{2}):(\d{2})', text)
        if match:
            hours, minutes, seconds = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return hours * 3600 + minutes * 60 + seconds

        # Try MM:SS
        match = re.match(r'(\d{1,2}):(\d{2})', text)
        if match:
            minutes, seconds = int(match.group(1)), int(match.group(2))
            return minutes * 60 + seconds

        print(f"    [STAMINA-CLAIM] Timer OCR returned unparseable text: {text}")
        return None

    except Exception as e:
        print(f"    [STAMINA-CLAIM] Timer OCR error: {e}")
        return None


def stamina_claim_flow(adb, screenshot_helper=None):
    """
    Open stamina popup and click the Claim button if present.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance (optional)

    Returns:
        dict with:
            - claimed: bool - True if Claim was clicked
            - timer_seconds: int | None - Seconds until next claim (if not claimed)
    """
    win = screenshot_helper if screenshot_helper else WindowsScreenshotHelper()
    result = {"claimed": False, "timer_seconds": None}

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
        return result

    # Search for Claim button in search region
    found, min_val, click_pos = match_template(
        frame, "claim_button_4k.png",
        search_region=SEARCH_REGION,
        threshold=MATCH_THRESHOLD
    )

    print(f"    [STAMINA-CLAIM] Match score: {min_val:.4f} (threshold: {MATCH_THRESHOLD})")

    if not found:
        # Claim not available - OCR the timer
        print("    [STAMINA-CLAIM] Claim button not found, OCRing timer...")
        timer_seconds = _ocr_timer(frame)
        result["timer_seconds"] = timer_seconds

        if timer_seconds is not None:
            mins, secs = divmod(timer_seconds, 60)
            hours, mins = divmod(mins, 60)
            print(f"    [STAMINA-CLAIM] Timer: {hours:02d}:{mins:02d}:{secs:02d} ({timer_seconds} seconds)")
        else:
            print("    [STAMINA-CLAIM] Timer OCR failed")

        # Close popup
        click_back(adb)  # Click back button to close stamina popup
        time.sleep(0.3)
        back_from_chat_flow(adb, win)
        return result

    # Step 4: Click the Claim button
    print(f"    [STAMINA-CLAIM] Step 3: Clicking Claim at ({CLAIM_BUTTON_X}, {CLAIM_BUTTON_Y})")
    adb.tap(CLAIM_BUTTON_X, CLAIM_BUTTON_Y)

    # Step 5: Wait and close popup
    time.sleep(0.5)
    print("    [STAMINA-CLAIM] Step 4: Closing popup with back button")
    click_back(adb)  # Click back button to close stamina popup
    time.sleep(0.3)
    back_from_chat_flow(adb, win)

    result["claimed"] = True
    print("    [STAMINA-CLAIM] Flow complete - claimed free stamina!")
    return result


def check_claim_button(frame):
    """
    Check if Claim button is present in the given frame.

    Args:
        frame: BGR numpy array screenshot (with popup open)

    Returns:
        (is_present, score) tuple
    """
    found, score, _ = match_template(
        frame, "claim_button_4k.png",
        search_region=SEARCH_REGION,
        threshold=MATCH_THRESHOLD
    )
    return found, score


def check_claim_status(adb, screenshot_helper=None) -> dict:
    """
    Open popup, check if Claim is available, OCR timer if not, close popup.

    This is a non-claiming check - just returns status.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance (optional)

    Returns:
        dict with:
            - claim_available: bool
            - timer_seconds: int | None - seconds until next claim (if not available)
    """
    win = screenshot_helper if screenshot_helper else WindowsScreenshotHelper()
    result = {"claim_available": False, "timer_seconds": None}

    # Open popup
    adb.tap(STAMINA_DISPLAY_X, STAMINA_DISPLAY_Y)
    time.sleep(0.5)

    frame = win.get_screenshot_cv2()
    if frame is None:
        back_from_chat_flow(adb, win)
        return result

    # Check for Claim button
    is_present, score = check_claim_button(frame)
    result["claim_available"] = is_present

    if not is_present:
        # OCR timer
        result["timer_seconds"] = _ocr_timer(frame)

    # Close popup without clicking Claim
    click_back(adb)
    time.sleep(0.3)
    back_from_chat_flow(adb, win)

    return result


def get_timer_from_popup(adb, screenshot_helper=None) -> int | None:
    """
    Quick helper to just get the timer value.

    Returns:
        Seconds until next claim, or None if claim is available or OCR failed
    """
    status = check_claim_status(adb, screenshot_helper)
    return status.get("timer_seconds")
