"""
Zombie Level Helper - OCR-based level reading and targeting for zombie/elite flows.

Uses slider dragging + OCR to set the zombie level, with plus/minus fine-tuning.

Usage:
    from utils.zombie_level_helper import read_zombie_level, set_zombie_level

    # Read current level
    level = read_zombie_level(frame)

    # Set to target level (uses slider + fine-tune)
    success = set_zombie_level(adb, win, target_level=25)
"""
from __future__ import annotations

import re
import time
import logging
from typing import TYPE_CHECKING, Any

import numpy.typing as npt

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

from utils.ocr_client import OCRClient, get_ocr_client
from utils.template_matcher import match_template

logger = logging.getLogger("zombie_level_helper")

# Level text region on search panel (4K resolution)
# Located to the right of the plus button, showing "Level XX"
LEVEL_TEXT_REGION = (2260, 1830, 200, 80)  # x, y, w, h

# Plus/Minus button positions (4K) - verified via template matching
PLUS_BUTTON_CLICK = (2230, 1869)
MINUS_BUTTON_CLICK = (1540, 1869)

# Slider parameters (4K) - verified via template matching
SLIDER_Y = 1874  # Slider circle Y
SLIDER_LEFT_X = 1580   # Left end (level 1) - just right of minus button
SLIDER_RIGHT_X = 2190  # Right end (max level) - just left of plus button
SLIDER_WIDTH = SLIDER_RIGHT_X - SLIDER_LEFT_X  # 610 pixels

# Level range - elite zombies can go to 60+
MIN_LEVEL = 1
MAX_LEVEL = 70

# Timing
CLICK_DELAY = 0.12  # Delay between fine-tune clicks
SETTLE_DELAY = 0.4  # Delay after slider drag before reading

# Fine-tune limits
MAX_FINE_TUNE_CLICKS = 10  # Max clicks for fine-tuning after slider


def _log(msg: str) -> None:
    """Log to both logger and stdout."""
    logger.info(msg)
    print(f"    [ZOMBIE_LEVEL] {msg}")


def read_zombie_level(
    frame: npt.NDArray[Any],
    ocr: OCRClient | None = None,
    debug: bool = False
) -> int | None:
    """
    Read the current zombie level from the search panel using OCR.

    Args:
        frame: BGR screenshot of the search panel
        ocr: Optional OCRClient instance (will create one if not provided)
        debug: Enable debug output

    Returns:
        The level as an integer, or None if OCR failed
    """
    if ocr is None:
        ocr = get_ocr_client()

    # Extract text from level region
    text = ocr.extract_text(frame, region=LEVEL_TEXT_REGION)

    if debug:
        _log(f"OCR raw text: '{text}'")

    if not text:
        if debug:
            _log("OCR returned empty text")
        return None

    # Parse level from text like "Level 39" or just "39"
    text = text.strip()

    # Try to find a number in the text
    match = re.search(r'\d+', text)
    if match:
        level = int(match.group())
        if MIN_LEVEL <= level <= MAX_LEVEL:
            if debug:
                _log(f"Parsed level: {level}")
            return level
        elif debug:
            _log(f"Level {level} out of range [{MIN_LEVEL}, {MAX_LEVEL}]")
    elif debug:
        _log(f"Could not parse level from: '{text}'")

    return None


def read_zombie_level_with_retry(
    win: WindowsScreenshotHelper,
    ocr: OCRClient | None = None,
    max_attempts: int = 3,
    debug: bool = False
) -> int | None:
    """
    Read zombie level with multiple attempts for reliability.
    """
    if ocr is None:
        ocr = get_ocr_client()

    for attempt in range(max_attempts):
        frame = win.get_screenshot_cv2()
        level = read_zombie_level(frame, ocr, debug=debug)
        if level is not None:
            return level
        if debug:
            _log(f"OCR attempt {attempt + 1}/{max_attempts} failed")
        time.sleep(0.2)

    return None


def _calculate_slider_x(target_level: int, max_level: int) -> int:
    """
    Calculate the X position on the slider for a target level.

    Args:
        target_level: Desired level
        max_level: Maximum level (determines right end of slider)

    Returns:
        X coordinate to drag slider to
    """
    # Clamp to valid range
    target_level = max(MIN_LEVEL, min(target_level, max_level))

    # Calculate ratio (0.0 = min level, 1.0 = max level)
    ratio = (target_level - MIN_LEVEL) / (max_level - MIN_LEVEL)

    # Calculate X position
    target_x = SLIDER_LEFT_X + int(ratio * SLIDER_WIDTH)

    return target_x


def _find_slider_position(frame: npt.NDArray[Any], debug: bool = False) -> int | None:
    """
    Find current slider handle position via template matching.

    Returns:
        X coordinate of slider handle, or None if not found
    """
    # Search for slider circle in the slider area
    found, score, center = match_template(
        frame, "slider_circle_4k.png",
        search_region=(1500, 1800, 800, 150),
        threshold=0.15
    )

    if found and center:
        if debug:
            _log(f"Found slider circle at {center} (score={score:.4f})")
        return center[0]  # Return X coordinate

    if debug:
        _log(f"Slider circle not found (score={score:.4f}), using estimate")
    return None


def set_zombie_level(
    adb: ADBHelper,
    win: WindowsScreenshotHelper,
    target_level: int,
    debug: bool = False
) -> bool:
    """
    Set the zombie level using slider drag + fine-tuning.

    This function:
    1. Reads current level via OCR
    2. Finds slider position via template matching
    3. Drags slider to approximate target position
    4. Reads level again, fine-tunes with plus/minus until exact

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        target_level: Desired level (1-70)
        debug: Enable debug output

    Returns:
        True if target level reached, False otherwise
    """
    if not (MIN_LEVEL <= target_level <= MAX_LEVEL):
        _log(f"ERROR: target_level {target_level} out of range [{MIN_LEVEL}, {MAX_LEVEL}]")
        return False

    ocr = get_ocr_client()

    # Step 1: Read current level
    if debug:
        _log(f"Step 1: Reading current level (target={target_level})...")

    frame = win.get_screenshot_cv2()
    current_level = read_zombie_level(frame, ocr, debug=debug)

    if current_level is None:
        _log("ERROR: Could not read current level via OCR")
        return False

    if debug:
        _log(f"Current level: {current_level}, target: {target_level}")

    if current_level == target_level:
        if debug:
            _log("Already at target level!")
        return True

    # Estimate max level (elite zombies go to 60)
    estimated_max = max(current_level, 60)

    # Step 2: Calculate target X position and TAP on slider track
    target_x = _calculate_slider_x(target_level, estimated_max)

    if debug:
        _log(f"Step 2: Tapping slider at X={target_x}, Y={SLIDER_Y} for level {target_level}")

    adb.tap(target_x, SLIDER_Y, source="util:zombie_level:slider_tap")
    time.sleep(SETTLE_DELAY)

    # Step 4: Read level and fine-tune in a loop until we hit target
    max_iterations = 5
    for iteration in range(max_iterations):
        frame = win.get_screenshot_cv2()
        current_level = read_zombie_level(frame, ocr, debug=debug)

        if current_level is None:
            _log("WARNING: Could not read level, retrying...")
            time.sleep(0.3)
            continue

        if debug:
            _log(f"Step 3 (iter {iteration+1}): Current level = {current_level}")

        if current_level == target_level:
            _log(f"SUCCESS: Reached target level {target_level}")
            return True

        # Calculate clicks needed
        diff = target_level - current_level
        clicks_needed = abs(diff)

        if clicks_needed == 0:
            break

        # Click plus or minus
        is_plus = diff > 0
        button_pos = PLUS_BUTTON_CLICK if is_plus else MINUS_BUTTON_CLICK
        button_name = "plus" if is_plus else "minus"

        # Do up to 10 clicks per iteration
        clicks_this_round = min(clicks_needed, 10)

        if debug:
            _log(f"  Clicking {button_name} {clicks_this_round} times (need {clicks_needed} total)")

        for _ in range(clicks_this_round):
            adb.tap(*button_pos, source=f"util:zombie_level:{button_name}_finetune")
            time.sleep(CLICK_DELAY)

        time.sleep(SETTLE_DELAY)

    # Final verification
    frame = win.get_screenshot_cv2()
    final_level = read_zombie_level(frame, ocr, debug=debug)

    if final_level == target_level:
        _log(f"SUCCESS: Reached target level {target_level}")
        return True

    _log(f"FAILED: Final level {final_level} != target {target_level}")
    return False


def get_level_adjustment(
    win: WindowsScreenshotHelper,
    target_level: int,
    debug: bool = False
) -> int | None:
    """
    Calculate the number of plus/minus clicks needed to reach target level.

    This is useful if you want to use level_clicks instead of set_zombie_level.

    Returns:
        Signed integer: positive for plus clicks, negative for minus clicks.
        None if OCR failed.
    """
    ocr = get_ocr_client()
    current_level = read_zombie_level_with_retry(win, ocr, debug=debug)

    if current_level is None:
        return None

    diff = target_level - current_level
    if debug:
        _log(f"Current: {current_level}, Target: {target_level}, Diff: {diff:+d}")

    return diff


if __name__ == "__main__":
    # Test the helper
    import sys
    from utils.windows_screenshot_helper import WindowsScreenshotHelper
    from utils.adb_helper import ADBHelper

    print("Zombie Level Helper Test")
    print("=" * 50)

    win = WindowsScreenshotHelper()

    # Test 1: Read current level
    print("\nTest 1: Reading current level...")
    frame = win.get_screenshot_cv2()
    level = read_zombie_level(frame, debug=True)

    if level is not None:
        print(f"Current level: {level}")
    else:
        print("Could not read level (is search panel open?)")
        sys.exit(1)

    # Test 2: If target provided, set level
    if len(sys.argv) > 1:
        target = int(sys.argv[1])
        print(f"\nTest 2: Setting level to {target}...")
        adb = ADBHelper()
        success = set_zombie_level(adb, win, target, debug=True)
        print(f"Result: {'SUCCESS' if success else 'FAILED'}")
    else:
        print("\nTo test level setting, run: python utils/zombie_level_helper.py <target_level>")
