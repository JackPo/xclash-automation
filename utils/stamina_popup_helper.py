"""
Stamina popup helper for parsing and claiming stamina items.

Coordinates verified from screenshot (4K resolution).
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

logger = logging.getLogger(__name__)

# Coordinates (4K resolution)
STAMINA_DISPLAY_CLICK = (117, 233)  # Click stamina number to open popup

# Row 1: Free 50 Stamina
ROW1_CLAIM_BUTTON_CLICK = (2284, 741)  # Claim/timer button
ROW1_COOLDOWN_REGION = (2161, 691, 246, 101)  # OCR timer "00:50:27"

# Row 3: 10 Stamina items
ROW3_OWNED_REGION = (1605, 1211, 249, 50)  # "Owned: 19"
ROW3_USE_BUTTON_CLICK = (2284, 1212)

# Row 4: 50 Stamina items
ROW4_OWNED_REGION = (1605, 1440, 249, 50)  # "Owned: 10"
ROW4_USE_BUTTON_CLICK = (2282, 1442)

# Popup close - tap blank space
POPUP_CLOSE_CLICK = (500, 500)


def open_stamina_popup(adb: ADBHelper) -> None:
    """Click stamina display to open recovery popup."""
    logger.info(f"Opening stamina popup at {STAMINA_DISPLAY_CLICK}")
    adb.tap(*STAMINA_DISPLAY_CLICK)
    time.sleep(1.0)


def close_stamina_popup(adb: ADBHelper) -> None:
    """Close the popup by tapping blank space."""
    logger.info("Closing stamina popup")
    adb.tap(*POPUP_CLOSE_CLICK)
    time.sleep(0.5)


def get_cooldown_seconds(frame: npt.NDArray[Any]) -> int:
    """
    OCR the cooldown timer and return seconds remaining.

    Returns 0 if ready to claim, or seconds remaining.
    """
    from utils.ocr_client import OCRClient

    x, y, w, h = ROW1_COOLDOWN_REGION
    roi = frame[y:y+h, x:x+w]

    ocr = OCRClient()
    text = ocr.extract_text(roi)

    if not text:
        return 0

    # Parse "00:50:27" or "03:50:27" format
    text = text.strip()
    logger.debug(f"Cooldown timer OCR raw: {text!r}")

    try:
        parts = text.split(":")
        if len(parts) == 3:
            hours, mins, secs = int(parts[0]), int(parts[1]), int(parts[2])
            return hours * 3600 + mins * 60 + secs
        elif len(parts) == 2:
            mins, secs = int(parts[0]), int(parts[1])
            return mins * 60 + secs
    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse cooldown timer '{text}': {e}")

    return 0  # Assume ready if can't parse


def get_owned_counts(frame: npt.NDArray[Any]) -> dict[str, int]:
    """
    OCR owned counts for 10 and 50 stamina items.

    Returns: {"owned_10": int, "owned_50": int}
    """
    from utils.ocr_client import OCRClient

    ocr = OCRClient()
    result = {"owned_10": 0, "owned_50": 0}

    # OCR Row 3 (10 stamina)
    x, y, w, h = ROW3_OWNED_REGION
    roi_10 = frame[y:y+h, x:x+w]
    text_10 = ocr.extract_text(roi_10)
    logger.debug(f"Row 3 OCR raw: {text_10!r}")

    if text_10:
        # Try to extract number from "Owned: 19" or just "19"
        text_10 = text_10.strip()
        if ":" in text_10:
            try:
                result["owned_10"] = int(text_10.split(":")[-1].strip())
            except ValueError:
                pass
        else:
            # Try to parse the whole thing as a number
            try:
                result["owned_10"] = int(text_10)
            except ValueError:
                # Try to extract digits only
                import re
                digits = re.findall(r'\d+', text_10)
                if digits:
                    result["owned_10"] = int(digits[0])

    # OCR Row 4 (50 stamina)
    x, y, w, h = ROW4_OWNED_REGION
    roi_50 = frame[y:y+h, x:x+w]
    text_50 = ocr.extract_text(roi_50)
    logger.debug(f"Row 4 OCR raw: {text_50!r}")

    if text_50:
        text_50 = text_50.strip()
        if ":" in text_50:
            try:
                result["owned_50"] = int(text_50.split(":")[-1].strip())
            except ValueError:
                pass
        else:
            try:
                result["owned_50"] = int(text_50)
            except ValueError:
                import re
                digits = re.findall(r'\d+', text_50)
                if digits:
                    result["owned_50"] = int(digits[0])

    logger.info(f"Owned counts: 10sta={result['owned_10']}, 50sta={result['owned_50']}")
    return result


def claim_free_50(adb: ADBHelper) -> None:
    """Click the free 50 stamina claim button."""
    logger.info(f"Claiming free 50 stamina at {ROW1_CLAIM_BUTTON_CLICK}")
    adb.tap(*ROW1_CLAIM_BUTTON_CLICK)
    time.sleep(0.5)


def use_10_stamina(adb: ADBHelper, count: int = 1) -> None:
    """Click Use button for 10 stamina item N times."""
    for i in range(count):
        logger.info(f"Using 10 stamina item ({i+1}/{count})")
        adb.tap(*ROW3_USE_BUTTON_CLICK)
        time.sleep(0.3)


def use_50_stamina(adb: ADBHelper, count: int = 1) -> None:
    """Click Use button for 50 stamina item N times."""
    for i in range(count):
        logger.info(f"Using 50 stamina item ({i+1}/{count})")
        adb.tap(*ROW4_USE_BUTTON_CLICK)
        time.sleep(0.3)


def get_inventory_snapshot(adb: ADBHelper, win: WindowsScreenshotHelper) -> dict[str, int]:
    """
    Open popup, capture inventory state, close popup.

    Returns:
        {
            "owned_10": int,
            "owned_50": int,
            "cooldown_secs": int
        }
    """
    open_stamina_popup(adb)
    time.sleep(0.5)

    frame = win.get_screenshot_cv2()

    owned = get_owned_counts(frame)
    cooldown = get_cooldown_seconds(frame)

    close_stamina_popup(adb)

    return {
        "owned_10": owned["owned_10"],
        "owned_50": owned["owned_50"],
        "cooldown_secs": cooldown
    }


def execute_claim_decision(adb: ADBHelper, decision: dict[str, Any]) -> None:
    """
    Execute the claim decision from the stamina rule engine.

    Args:
        decision: {claim_free_50: bool, use_10_count: int, use_50_count: int}
    """
    if decision.get("claim_free_50"):
        claim_free_50(adb)

    use_10_count = decision.get("use_10_count", 0)
    if use_10_count > 0:
        use_10_stamina(adb, use_10_count)

    use_50_count = decision.get("use_50_count", 0)
    if use_50_count > 0:
        use_50_stamina(adb, use_50_count)


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    print("=== Stamina Popup Helper Test ===\n")

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    if len(sys.argv) > 1 and sys.argv[1] == "--snapshot":
        # Full inventory snapshot test
        print("Running full inventory snapshot...")
        inventory = get_inventory_snapshot(adb, win)
        print(f"\nResult: {inventory}")
    else:
        # Quick test - just OCR current screenshot (assumes popup is open)
        print("Taking screenshot (assumes popup is already open)...")
        frame = win.get_screenshot_cv2()

        print("\nOCR cooldown timer...")
        cooldown = get_cooldown_seconds(frame)
        print(f"  Cooldown: {cooldown} seconds")

        print("\nOCR owned counts...")
        owned = get_owned_counts(frame)
        print(f"  Owned 10: {owned['owned_10']}")
        print(f"  Owned 50: {owned['owned_50']}")
