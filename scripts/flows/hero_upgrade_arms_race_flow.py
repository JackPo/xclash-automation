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
from utils.hero_tile_detector import detect_sub_max_tiles, MAX_HERO_LEVEL
from utils.upgrade_button_matcher import UpgradeButtonMatcher
from utils.return_to_base_view import return_to_base_view
from utils.ocr_client import OCRClient
from utils.arms_race import get_event_metadata, get_exp_per_arms_race_point

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
        adb.tap(*EVENTS_BUTTON_CLICK, source="flow:hero_upgrade_arms_race:events_button")
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
    adb.tap(*FING_HERO_BUTTON_CLICK, source="flow:hero_upgrade_arms_race:fing_hero_button")

    # Step 3: Wait for hero grid to load
    time.sleep(1.5)

    # Step 4: Scan + scroll loop. Most heroes are now Lv 150 (maxed), so the
    # red-dot signal is unreliable -- some maxed heroes still show transient
    # dots while genuinely-upgradable lower-level heroes don't. Instead we OCR
    # the "Lv. NNN" banner under each visible tile and treat any tile under
    # MAX_HERO_LEVEL as a candidate. Sub-max heroes tend to live at the BOTTOM
    # of the grid (maxed ones cluster at the top), so we scan the current page,
    # process candidates, then swipe to scroll down and repeat.
    #
    # Budget control: Arms Race scoring for Enhance Hero is 1 point per
    # exp_per_arms_race_point (=2000) hero EXP spent. After each upgrade we
    # read the required EXP off the hero detail panel, accumulate it, and
    # stop once we project we've hit chest3.

    upgrades_done = 0
    MAX_SCROLL_PAGES = 6  # 31 heroes / 12 per page -> 3 pages; pad to 6 for slack
    # Page 1 (top of the grid) is consistently all maxed heroes -- sub-Lv150
    # heroes live at the BOTTOM. So we MUST scroll past at least one all-max
    # page before believing there are no upgradable heroes. Requiring 2
    # consecutive empty pages also tolerates a transient OCR misread.
    # Top of the grid is sometimes 2+ pages of maxed heroes; sub-Lv150 heroes
    # live at the bottom. Set high enough to traverse all 31 heroes (~3 pages
    # of 12 visible), with margin in case the panel layout varies. The MAX
    # safety cap above stops infinite scroll.
    EMPTY_PAGES_TO_STOP = 4

    chest3_target = chest3  # already fetched above
    exp_per_point = get_exp_per_arms_race_point("Enhance Hero") or 2000
    current_points = progress["current_points"] if progress["success"] else 0
    if current_points is None:
        current_points = 0
    points_needed = max(0, chest3_target - current_points)
    exp_budget = points_needed * exp_per_point
    exp_spent = 0
    logger.info(
        f"Budget: need {points_needed} pts to hit chest3 ({current_points}/{chest3_target}); "
        f"= {exp_budget:,} hero EXP at {exp_per_point} EXP/pt"
    )

    empty_pages = 0
    for page in range(MAX_SCROLL_PAGES):
        logger.info(f"Step 3.{page+1}: Scanning hero grid page {page+1}...")
        frame = win.get_screenshot_cv2()
        if frame is None:
            logger.error("Failed to get screenshot")  # type: ignore[unreachable]
            return False

        sub_max_tiles = detect_sub_max_tiles(frame, max_level=MAX_HERO_LEVEL, debug=True)
        logger.info(f"  Found {len(sub_max_tiles)} tiles below Lv{MAX_HERO_LEVEL} on this page")

        if not sub_max_tiles:
            empty_pages += 1
            if empty_pages >= EMPTY_PAGES_TO_STOP:
                logger.info("No sub-max tiles found; assuming we've scrolled past upgradable heroes")
                break
        else:
            empty_pages = 0

        # Process each sub-max tile on this page.
        for i, tile in enumerate(sub_max_tiles):
            tile_name = tile['name']
            click_pos = tile['click']
            level = tile['level']

            logger.info(f"Step 4.{page+1}.{i+1}: Processing tile {tile_name} (Lv{level})")

            adb.tap(*click_pos, source="flow:hero_upgrade_arms_race:hero_tile")
            time.sleep(1.0)

            frame = win.get_screenshot_cv2()
            if frame is None:
                logger.error("Failed to get screenshot")  # type: ignore[unreachable]
                click_back(adb)
                time.sleep(0.5)
                continue

            # Per-tile click loop: click Upgrade repeatedly on this hero,
            # measuring the actual EXP spent each click as A_before - A_after.
            # This is correct even if the per-click cost shifts as the hero
            # levels up. Stop when the button grays out, OCR fails, the click
            # has no effect, or cumulative EXP crosses the budget.
            upgrade_click = upgrade_matcher.get_click_position()
            while True:
                is_available, avail_score, unavail_score = upgrade_matcher.check_upgrade_available(frame, debug=True)
                if not is_available:
                    logger.info(
                        f"Lv{level} hero -- upgrade button not available "
                        f"(avail={avail_score:.3f}, unavail={unavail_score:.3f}); "
                        f"moving on"
                    )
                    break

                owned_before, required, _ = upgrade_matcher.read_resource_cost(frame, debug=True)
                if owned_before is None:
                    logger.info(f"Lv{level} hero -- couldn't OCR owned EXP; bailing on this hero")
                    break

                adb.tap(*upgrade_click, source="flow:hero_upgrade_arms_race:upgrade_button")
                time.sleep(0.6)
                frame = win.get_screenshot_cv2()

                owned_after, _, _ = upgrade_matcher.read_resource_cost(frame, debug=False)
                if owned_after is None:
                    # Re-OCR failed -- count `required` (next-click cost is the
                    # closest proxy we have) and bail this hero rather than
                    # double-clicking on unknown state.
                    spent_this = required or 0
                    exp_spent += spent_this
                    upgrades_done += 1
                    logger.info(
                        f"Lv{level}: clicked Upgrade but post-OCR failed; "
                        f"assumed spent={spent_this:,} EXP. Total {exp_spent:,} EXP "
                        f"(~{exp_spent // exp_per_point} pts). Bailing this hero."
                    )
                    break

                spent_this = max(0, owned_before - owned_after)
                if spent_this == 0:
                    logger.info(f"Lv{level}: Upgrade click had no effect (A unchanged); moving on")
                    break

                exp_spent += spent_this
                upgrades_done += 1
                pts_est = exp_spent // exp_per_point
                logger.info(
                    f"Lv{level}: click #{upgrades_done} spent {spent_this:,} EXP "
                    f"(A {owned_before:,} -> {owned_after:,}); "
                    f"cumulative {exp_spent:,} EXP ~ {pts_est} pts (target {points_needed})"
                )

                if exp_spent >= exp_budget:
                    logger.info("Budget crossed; projected chest3 reached. Stopping.")
                    _press_hardware_back(adb)
                    return_to_base_view(adb, win, debug=False)
                    return True

                if upgrades_done >= ARMS_RACE_ENHANCE_HERO_MAX_UPGRADES:
                    logger.warning(
                        f"Hit ARMS_RACE_ENHANCE_HERO_MAX_UPGRADES safety cap "
                        f"({ARMS_RACE_ENHANCE_HERO_MAX_UPGRADES}) before reaching budget "
                        f"({exp_spent:,}/{exp_budget:,} EXP). OCR or budget metadata may be off."
                    )
                    _press_hardware_back(adb)
                    return_to_base_view(adb, win, debug=False)
                    return True

                time.sleep(0.3)  # brief pause before next iteration

            # Click back to return to hero grid for the next tile.
            click_back(adb)
            time.sleep(0.5)

        # Swipe to scroll the grid down before next page (unless we're done).
        if page < MAX_SCROLL_PAGES - 1:
            logger.info("Scrolling hero grid down...")
            # Swipe upward within the grid area; covers ~one full page of rows.
            # Grid rows are at y=211/639/1067 -> ~430px spacing, so a ~900px
            # swipe scrolls roughly two rows worth (one fresh row + buffer).
            adb.swipe(1900, 1400, 1900, 500, duration=500)
            time.sleep(1.0)

    # Step 5: Exit hero grid and return to base view
    logger.info("Step 5: Returning to base view...")
    _press_hardware_back(adb)  # Close hero panel (no visible close button)
    return_to_base_view(adb, win, debug=False)

    logger.info(f"Flow complete - {upgrades_done} upgrades performed")
    return True
