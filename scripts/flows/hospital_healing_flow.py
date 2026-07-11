"""
Hospital Healing Flow - Heal soldiers in 1-hour batches.

After hospital panel is opened, this flow:
1. Finds all soldier rows (by detecting plus buttons)
2. Resets all sliders to zero
3. Fills from bottom row (highest level) until healing time reaches ~1 hour
4. Clicks Healing button
5. Returns to base view

All matching uses template_matcher with COLOR images (no grayscale).

Usage:
    python scripts/flows/hospital_healing_flow.py [--max-seconds 3600]
"""

from __future__ import annotations

import logging
logger = logging.getLogger("hospital_healing_flow")

import sys
import time
import argparse
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.template_matcher import match_template
from config import (
    HOSPITAL_HEAL_TARGET_SECONDS,
    HOSPITAL_HEAL_TARGET_TOLERANCE_RATIO,
)

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

from utils.ocr_client import OCRClient
from utils.return_to_base_view import return_to_base_view
from utils.hospital_panel_helper import (
    find_plus_buttons,
    reset_all_sliders,
    drag_slider_to_max,
    drag_slider_to_min,
    drag_slider_to_position,
    get_healing_time_seconds,
    click_healing_button,
    calculate_slider_x,
    scroll_panel_down,
    MAX_SAFE_HEAL_SECONDS,
    get_slider_y,
)

# Hospital header region for verification
HOSPITAL_HEADER_REGION = (1770, 305, 300, 90)  # x, y, w, h - header center ~(1916, 346); old region was ~15px too low -> Step 0 falsely failed (0.136), aborting every heal
HOSPITAL_HEADER_THRESHOLD = 0.1


def hospital_healing_flow(
    adb: ADBHelper | None = None,
    win: WindowsScreenshotHelper | None = None,
    max_heal_seconds: int = HOSPITAL_HEAL_TARGET_SECONDS,
    debug: bool = True,
) -> bool:
    """
    Heal soldiers in batches of up to max_heal_seconds.

    Assumes hospital panel is already open.
    Processes rows from BOTTOM to TOP (highest level soldiers first).
    Includes 90-minute safety check to prevent accidental long heals.

    Args:
        adb: ADBHelper (created if None)
        win: WindowsScreenshotHelper (created if None)
        max_heal_seconds: Maximum healing time per batch (default from config)
        debug: Enable debug output

    Returns:
        bool: True if healing was initiated
    """
    # Import here to avoid circular imports at runtime
    from utils.adb_helper import ADBHelper

    if adb is None:
        adb = ADBHelper()
    if win is None:
        win = WindowsScreenshotHelper()

    ocr = OCRClient()

    logger.info("Hospital Healing Flow")
    logger.info("=" * 50)

    # Step 0: Verify hospital panel is open by checking header (COLOR matching)
    logger.info("\nStep 0: Verifying hospital panel is open...")
    is_open, score = False, 1.0
    _deadline = time.time() + 5.0
    while time.time() < _deadline:
        frame = win.get_screenshot_cv2()
        is_open, score, _ = match_template(
            frame, "hospital_header_4k.png",
            search_region=HOSPITAL_HEADER_REGION,
            threshold=HOSPITAL_HEADER_THRESHOLD
        )
        if is_open:
            break
        time.sleep(0.4)
    if not is_open:
        logger.warning(f"[HEAL] Hospital panel NOT open after 5s poll (header score={score:.4f}) - tap missed or header template stale")
        return False
    logger.info(f"  OK - Hospital panel verified (header score={score:.4f})")

    # Step 1: Find soldier rows (detects plus buttons)
    logger.info("\nStep 1: Finding soldier rows...")
    frame = win.get_screenshot_cv2()
    buttons = find_plus_buttons(frame, debug=debug)

    if not buttons:
        logger.info("  ERROR: No soldier rows found - is hospital panel open?")
        return False

    logger.info(f"  Found {len(buttons)} soldier rows")

    # Step 2: Reset ALL sliders to zero
    # Only scroll if 3+ rows visible (indicates more rows may be below)
    logger.info("\nStep 2: Resetting all sliders to zero...")

    rows_reset = 0
    if len(buttons) >= 3:
        # Multiple rows visible - need to scroll through panel to find all
        logger.info(f"  {len(buttons)} rows visible - scrolling to find all rows")
        for scroll_num in range(5):  # Max 5 scrolls to cover all rows
            frame = win.get_screenshot_cv2()
            visible_buttons = find_plus_buttons(frame, debug=False)

            if not visible_buttons:
                break

            for plus_x, plus_y, _ in visible_buttons:
                drag_slider_to_min(adb, frame, plus_x, plus_y, debug=False)
                rows_reset += 1
                time.sleep(0.3)
                frame = win.get_screenshot_cv2()  # Refresh after each drag

            # Scroll down to find more rows
            scroll_panel_down(adb, debug=False)
            time.sleep(0.5)
    else:
        # Few rows (1-2) - all content visible, just reset directly
        logger.info(f"  {len(buttons)} rows visible - all content on screen, no scrolling needed")
        for plus_x, plus_y, _ in buttons:
            drag_slider_to_min(adb, frame, plus_x, plus_y, debug=False)
            rows_reset += 1
            time.sleep(0.3)
            frame = win.get_screenshot_cv2()  # Refresh after each drag

    logger.info(f"  Reset {rows_reset} slider positions")

    # Refresh to get current visible buttons
    time.sleep(0.3)

    # Step 3: Check initial healing time (should be 0 or very small)
    frame = win.get_screenshot_cv2()
    initial_time = get_healing_time_seconds(frame, ocr, debug=debug)
    logger.info(f"  Initial healing time: {initial_time}s")

    # Step 4: Fill ONLY the bottom row (highest level soldiers)
    # Other rows stay at minimum - we only heal one soldier type at a time
    logger.info(f"\nStep 3: Filling ONLY bottom row (highest level soldiers)...")
    logger.info(f"  Other rows stay at minimum")

    # Get current visible buttons (we're at bottom after reset loop)
    frame = win.get_screenshot_cv2()
    buttons = find_plus_buttons(frame, debug=debug)

    if not buttons:
        logger.info("  ERROR: No rows found after scrolling")
        return False

    # Bottom row is the last one (highest Y position = highest level)
    bottom_row = buttons[-1]
    plus_x, plus_y, score = bottom_row
    slider_y = get_slider_y(plus_y)
    logger.info(f"  Processing ONLY bottom row (Y={slider_y}, highest level soldiers)")
    logger.info(f"  Other rows stay at minimum")

    current_time = initial_time

    # Drag bottom row's slider to max
    frame = win.get_screenshot_cv2()
    if not drag_slider_to_max(adb, frame, plus_x, plus_y, debug=debug):
        logger.info(f"    Could not find slider, aborting")
        return False

    time.sleep(0.5)

    # Check new healing time
    frame = win.get_screenshot_cv2()
    new_time = get_healing_time_seconds(frame, ocr, debug=debug)
    logger.info(f"    After max: {new_time}s ({new_time//3600}h {(new_time%3600)//60}m)")

    upper_target = int(max_heal_seconds * (1 + HOSPITAL_HEAL_TARGET_TOLERANCE_RATIO))

    if new_time <= upper_target:
        # Under limit, keep at max
        logger.info(f"    Under limit, keeping at max")
        current_time = new_time
    else:
        # Over limit - binary search for right position
        logger.info(f"    Over limit ({new_time}s > {upper_target}s), adjusting...")

        low_ratio = 0.0
        high_ratio = 1.0
        best_ratio = 0.0
        best_time = current_time

        for _ in range(8):  # 8 iterations = ~1% precision
            mid_ratio = (low_ratio + high_ratio) / 2
            target_x = calculate_slider_x(plus_x, mid_ratio)

            frame = win.get_screenshot_cv2()
            drag_slider_to_position(adb, frame, plus_x, plus_y, target_x, debug=False)
            time.sleep(0.3)

            frame = win.get_screenshot_cv2()
            test_time = get_healing_time_seconds(frame, ocr, debug=False)

            if debug:
                logger.info(f"      ratio={mid_ratio:.2f} -> {test_time}s")

            if test_time <= upper_target:
                best_ratio = mid_ratio
                best_time = test_time
                low_ratio = mid_ratio
            else:
                high_ratio = mid_ratio

        # Set to best found ratio
        best_x = calculate_slider_x(plus_x, best_ratio)
        frame = win.get_screenshot_cv2()
        drag_slider_to_position(adb, frame, plus_x, plus_y, best_x, debug=debug)
        time.sleep(0.3)

        current_time = best_time
        logger.info(f"    Set to ratio={best_ratio:.2f}, time={current_time}s")

    # Step 5: Final check and click Healing
    logger.info("\nStep 4: Final verification and clicking Healing button...")
    frame = win.get_screenshot_cv2()
    final_time = get_healing_time_seconds(frame, ocr, debug=debug)
    logger.info(f"  Final healing time: {final_time}s ({final_time//3600}h {(final_time%3600)//60}m {final_time%60}s)")

    # Final safety check
    if final_time > MAX_SAFE_HEAL_SECONDS:
        logger.info(f"  ERROR: Final time {final_time}s exceeds safety limit! NOT clicking Heal.")
        return_to_base_view(adb, win, debug=debug)
        return False

    if final_time == 0:
        logger.info("  No soldiers to heal (time is 0)")
        return False

    click_healing_button(adb, debug=debug)
    time.sleep(0.5)

    # Step 5b: Check for insufficient resources prompt
    logger.info("\nStep 4b: Checking for insufficient resources...")
    from utils.replenish_all_helper import ReplenishAllHelper
    replenish_helper = ReplenishAllHelper()

    if replenish_helper.poll_and_handle_replenish(adb, win, debug=debug):
        # Resources were replenished - need to click Healing button again
        logger.info("  Resources replenished - clicking Healing button again...")
        time.sleep(0.5)
        click_healing_button(adb, debug=debug)
        time.sleep(0.5)
    else:
        logger.info("  No resource issue - healing started normally")

    # Step 6: Return to base view
    logger.info("\nStep 5: Returning to base view...")
    return_to_base_view(adb, win, debug=debug)

    logger.info("\n" + "=" * 50)
    logger.info("Hospital Healing Flow complete!")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Hospital Healing Flow")
    parser.add_argument("--max-seconds", type=int, default=3600,
                        help="Maximum healing time per batch (default: 3600 = 1 hour)")
    parser.add_argument("--debug", action="store_true", default=True,
                        help="Enable debug output")
    args = parser.parse_args()

    hospital_healing_flow(max_heal_seconds=args.max_seconds, debug=args.debug)


if __name__ == "__main__":
    main()
