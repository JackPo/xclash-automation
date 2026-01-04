"""
Hero Upgrade Arms Race flow - Check progress and upgrade heroes if needed.

Triggered during Arms Race "Enhance Hero" event in the last 10 minutes.
NO idle requirement - we check real-time points data instead of guessing.

Flow sequence:
1. Click Events button to open Arms Race panel
2. OCR current points
3. If points >= chest3 (12000): close panel, return to town, DONE
4. If points < chest3: close panel, proceed with upgrades:
   a. Click Fing Hero button
   b. Scan hero grid for red notification dots
   c. For each tile with red dot: check and upgrade if available
5. Return to base view

Templates:
- Events button: templates/ground_truth/events_icon_4k.png (click: 3718, 642)
- Fing Hero button: templates/ground_truth/heroes_button_4k.png (click: 2272, 2038)
- Upgrade available: templates/ground_truth/upgrade_button_available_4k.png
- Upgrade unavailable: templates/ground_truth/upgrade_button_unavailable_4k.png
"""

from __future__ import annotations

import time
import logging
from typing import TYPE_CHECKING, TypedDict

from config import ARMS_RACE_ENHANCE_HERO_MAX_UPGRADES
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.hero_tile_detector import detect_tiles_with_red_dots
from utils.upgrade_button_matcher import UpgradeButtonMatcher
from utils.return_to_base_view import return_to_base_view
from utils.ocr_client import OCRClient
from utils.arms_race import get_event_metadata

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper


class EnhanceHeroProgress(TypedDict):
    """Return type for check_enhance_hero_progress."""
    success: bool
    current_points: int | None
    chest3_reached: bool

logger = logging.getLogger(__name__)

# Events button position (right side of screen, opens Arms Race panel)
EVENTS_BUTTON_CLICK = (3718, 632)

# Arms Race current points OCR region (same for all events)
CURRENT_POINTS_REGION = (1466, 693, 135, 50)

# Fing Hero button position
FING_HERO_BUTTON_CLICK = (2272, 2038)

from utils.ui_helpers import click_back
from config import BACK_BUTTON_CLICK

# Get chest3 threshold from metadata JSON
def _get_chest3_threshold() -> int:
    """Get chest3 threshold from Arms Race metadata JSON."""
    meta = get_event_metadata("Enhance Hero")
    chest3 = meta.get("chest3")
    if chest3 is None:
        return 12000  # Default fallback if metadata not collected
    return int(chest3)


def _press_hardware_back(adb: ADBHelper) -> None:
    """Press Android hardware back button to close panels that don't have visible back buttons."""
    try:
        adb._run_adb(['shell', 'input', 'keyevent', 'KEYCODE_BACK'])
        time.sleep(0.5)
    except Exception as e:
        logger.warning(f"Hardware back failed: {e}")


def check_enhance_hero_progress(
    adb: ADBHelper, win: WindowsScreenshotHelper
) -> EnhanceHeroProgress:
    """
    Open Events panel and check current Enhance Hero points.

    Returns:
        EnhanceHeroProgress dict with success, current_points, chest3_reached
    """
    result: EnhanceHeroProgress = {
        "success": False,
        "current_points": None,
        "chest3_reached": False,
    }

    try:
        # Click Events button
        logger.info(f"Opening Events panel at {EVENTS_BUTTON_CLICK}")
        adb.tap(*EVENTS_BUTTON_CLICK)
        time.sleep(1.5)

        # OCR current points with triple verification
        from collections import Counter
        ocr = OCRClient()
        results = []

        for i in range(3):
            frame = win.get_screenshot_cv2()
            if frame is None:
                continue  # type: ignore[unreachable]

            x, y, w, h = CURRENT_POINTS_REGION
            roi = frame[y:y+h, x:x+w]
            points_text = ocr.extract_text(roi)

            if points_text:
                points_text = points_text.strip().replace(",", "").replace(" ", "")
                try:
                    results.append(int(points_text))
                except ValueError:
                    pass
            if i < 2:
                time.sleep(0.1)

        if results:
            counter = Counter(results)
            most_common, count = counter.most_common(1)[0]
            if count >= 2:
                current_points = most_common
                result["current_points"] = current_points
                chest3 = _get_chest3_threshold()
                result["chest3_reached"] = current_points >= chest3
                result["success"] = True
                logger.info(f"Current points: {current_points}/{chest3}, chest3_reached: {result['chest3_reached']}")
            else:
                logger.warning(f"OCR inconsistent: {results}")
        else:
            logger.warning("OCR returned no valid results")

        # Close Events panel (click back or tap outside)
        click_back(adb)
        time.sleep(0.5)

    except Exception as e:
        logger.error(f"Error checking progress: {e}")
        # Try to close panel
        try:
            click_back(adb)
        except:
            pass

    return result


def hero_upgrade_arms_race_flow(
    adb: ADBHelper, screenshot_helper: WindowsScreenshotHelper | None = None
) -> bool:
    """
    Smart Hero Upgrade Arms Race flow:
    1. Check current points from Events panel
    2. If chest3 reached: exit early
    3. If not: proceed with hero upgrades

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance (optional)

    Returns:
        True if successful, False otherwise
    """
    win = screenshot_helper if screenshot_helper else WindowsScreenshotHelper()
    upgrade_matcher = UpgradeButtonMatcher()

    # Step 1: Check current progress
    logger.info("Step 1: Checking Enhance Hero progress...")
    progress = check_enhance_hero_progress(adb, win)

    chest3 = _get_chest3_threshold()

    if progress["success"] and progress["chest3_reached"]:
        logger.info(f"Chest3 already reached ({progress['current_points']}/{chest3}). Skipping upgrades.")
        _press_hardware_back(adb)  # Close any open panel
        return_to_base_view(adb, win, debug=False)
        return True

    if progress["success"]:
        logger.info(f"Progress: {progress['current_points']}/{chest3}. Proceeding with upgrades...")
    else:
        logger.warning("Failed to check progress, proceeding with upgrades anyway...")

    # Step 2: Click Fing Hero button
    logger.info(f"Step 2: Clicking Fing Hero button at {FING_HERO_BUTTON_CLICK}")
    adb.tap(*FING_HERO_BUTTON_CLICK)

    # Step 3: Wait for hero grid to load
    time.sleep(1.5)

    # Step 4: Take screenshot and detect tiles with red dots
    logger.info("Step 3: Scanning hero grid for red dots...")
    frame = win.get_screenshot_cv2()
    if frame is None:
        logger.error("Failed to get screenshot")  # type: ignore[unreachable]
        return False

    tiles_with_dots = detect_tiles_with_red_dots(frame, debug=True)

    if not tiles_with_dots:
        logger.info("No tiles with red dots found")
        # Close hero panel with hardware back (no visible close button)
        _press_hardware_back(adb)
        return_to_base_view(adb, win, debug=False)
        return True

    logger.info(f"Found {len(tiles_with_dots)} tiles with red dots")

    upgrades_done = 0

    # Step 5: Process each tile with red dot
    for i, tile in enumerate(tiles_with_dots):
        tile_name = tile['name']
        click_pos = tile['click']

        logger.info(f"Step 4.{i+1}: Processing tile {tile_name}")

        # Click the tile
        logger.debug(f"Clicking tile at {click_pos}")
        adb.tap(*click_pos)
        time.sleep(1.0)

        # Take screenshot and check upgrade button
        frame = win.get_screenshot_cv2()
        if frame is None:
            logger.error("Failed to get screenshot")  # type: ignore[unreachable]
            click_back(adb)
            time.sleep(0.5)
            continue

        is_available, avail_score, unavail_score = upgrade_matcher.check_upgrade_available(frame, debug=True)

        if is_available:
            # Click upgrade button
            upgrade_click = upgrade_matcher.get_click_position()
            logger.info(f"Upgrade AVAILABLE! Clicking at {upgrade_click}")
            adb.tap(*upgrade_click)
            time.sleep(0.5)
            upgrades_done += 1

            # Check if we've hit the max upgrades
            if upgrades_done >= ARMS_RACE_ENHANCE_HERO_MAX_UPGRADES:
                logger.info(f"Reached max upgrades ({ARMS_RACE_ENHANCE_HERO_MAX_UPGRADES})")
                _press_hardware_back(adb)  # Close hero panel
                return_to_base_view(adb, win, debug=False)
                logger.info(f"Flow complete - {upgrades_done} upgrade(s) performed")
                return True

            # More upgrades allowed, click back to continue
            logger.info(f"Upgrade {upgrades_done}/{ARMS_RACE_ENHANCE_HERO_MAX_UPGRADES} done, continuing...")
            click_back(adb)
            time.sleep(0.5)
        else:
            logger.debug(f"Upgrade not available (avail={avail_score:.3f}, unavail={unavail_score:.3f})")

        # Click back to return to hero grid
        logger.debug("Clicking back to return to grid")
        click_back(adb)
        time.sleep(0.5)

        # Re-take screenshot for next iteration (grid may have changed)
        frame = win.get_screenshot_cv2()

    # Step 6: Exit hero grid and return to base view
    logger.info("Step 5: Returning to base view...")
    _press_hardware_back(adb)  # Close hero panel (no visible close button)
    return_to_base_view(adb, win, debug=False)

    logger.info(f"Flow complete - {upgrades_done} upgrades performed")
    return True
