"""
Bag Use Item Subflow - Shared logic for using items with slider.

Handles the common "use dialog" that appears when clicking bag items:
1. Verify Use button present
2. Verify Plus button present
3. Find slider X position
4. Drag slider to max
5. Click Use button
6. Click back to close dialog

All matching uses template_matcher with COLOR images (no grayscale).
"""
from __future__ import annotations

import logging
logger = logging.getLogger("bag")

import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy.typing as npt

_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

from utils.template_matcher import match_template
from utils.ui_helpers import click_back

# Fixed positions (4K resolution)
# Use button can be at different Y positions depending on dialog type
USE_BUTTON_REGION = (1750, 1400, 350, 300)  # x, y, w, h - search region for Use button

# Bag header region for verification (same as bag_special_flow)
BAG_TAB_REGION = (1352, 32, 1127, 90)

# Thresholds - SQDIFF (lower is better)
BAG_HEADER_THRESHOLD = 0.05
DIALOG_THRESHOLD = 0.1  # Use button/slider detection


def use_item_subflow(
    adb: ADBHelper, win: WindowsScreenshotHelper, debug: bool = False
) -> bool:
    """
    Handle the use dialog: verify, drag slider, click use, click back.

    Assumes the use dialog is already open (after clicking an item).

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        debug: Enable debug output

    Returns:
        True if successful, False if verification failed
    """
    # Take screenshot for verification
    frame = win.get_screenshot_cv2()

    # Find Use button (searches Y range to handle different dialog positions)
    use_found, use_score, use_pos = match_template(
        frame, "use_button_4k.png",
        search_region=USE_BUTTON_REGION,
        threshold=DIALOG_THRESHOLD
    )
    if debug:
        logger.info(f"  Use button: found={use_found}, score={use_score:.4f}")
    if not use_found or use_pos is None:
        logger.warning("  ERROR: Use dialog not detected")
        return False

    use_click_x, use_click_y = use_pos

    # Find plus button to get correct Y coordinate for slider
    plus_found, plus_score, plus_pos = match_template(
        frame, "plus_button_4k.png",
        threshold=DIALOG_THRESHOLD
    )
    if not plus_found or plus_pos is None:
        logger.warning(f"  ERROR: Plus button not found (score={plus_score:.4f})")
        return False

    plus_x, plus_y = plus_pos
    if debug:
        logger.info(f"  Plus button at ({plus_x}, {plus_y}), score={plus_score:.4f}")

    # Find slider position - search in a Y band around plus button
    slider_search_region = (0, plus_y - 50, frame.shape[1], 100)  # Full width, narrow Y band
    slider_found, slider_score, slider_pos = match_template(
        frame, "slider_circle_4k.png",
        search_region=slider_search_region,
        threshold=DIALOG_THRESHOLD
    )
    if not slider_found or slider_pos is None:
        logger.warning(f"  ERROR: Slider not found (score={slider_score:.4f})")
        return False

    slider_x, slider_y = slider_pos
    # Use plus_y directly since slider is at same Y as plus/minus buttons
    slider_y = plus_y
    if debug:
        logger.info(f"  Slider at ({slider_x}, {slider_y}), score={slider_score:.4f}")

    # Click at max position on slider (just before plus button)
    max_x = plus_x - 40  # Max position just before the plus button
    if debug:
        logger.info(f"  Clicking slider at max position ({max_x}, {slider_y})...")
    adb.tap(max_x, slider_y, source="flow:bag_use_item:slider_max")
    time.sleep(0.3)

    # Click Use button at found position
    if debug:
        logger.info(f"  Clicking Use button at ({use_click_x}, {use_click_y})...")
    adb.tap(use_click_x, use_click_y, source="flow:bag_use_item:use_button")
    time.sleep(1.0)  # Initial wait for use animation

    # Poll for bag screen - click back until Bag header is visible
    max_attempts = 10
    for attempt in range(max_attempts):
        if debug:
            logger.info(f"  Clicking back (attempt {attempt + 1})...")
        click_back(adb)
        time.sleep(0.5)

        # Check if we're back at the bag screen (COLOR matching)
        frame = win.get_screenshot_cv2()
        is_bag, score, _ = match_template(
            frame, "bag_tab_4k.png",
            search_region=BAG_TAB_REGION,
            threshold=BAG_HEADER_THRESHOLD
        )

        if debug:
            logger.info(f"    Bag header check: visible={is_bag}, score={score:.4f}")

        if is_bag:
            if debug:
                logger.info("  Back at bag screen!")
            return True

    logger.warning(f"  ERROR: Could not return to bag screen after {max_attempts} attempts")
    return False
