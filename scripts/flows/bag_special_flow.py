"""
Bag Special Tab Flow - Chest claiming from Special tab.

Opens the bag (defaults to Special tab), finds chest tiles using multi-template
COLOR matching, and uses them one at a time. Rescans after each use since items shift.

All matching uses template_matcher with COLOR images (no grayscale).
"""
from __future__ import annotations

import logging
logger = logging.getLogger("bag")

import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import numpy.typing as npt

from scripts.flows.bag_use_item_subflow import use_item_subflow
from utils.arms_race import get_arms_race_status
from config import VS_LEVEL_CHEST_DAYS

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.template_matcher import match_template
from utils.ui_helpers import click_back

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

# Fixed positions (4K resolution)
BAG_BUTTON_REGION = (3659, 1556, 132, 127)
BAG_BUTTON_CLICK = (3725, 1624)

BAG_TAB_REGION = (1352, 32, 1127, 90)

# Bag content region - ONLY search for items within this area (not full screen)
BAG_CONTENT_REGION = (1337, 137, 1161, 1871)  # x, y, w, h - the white item grid

SPECIAL_TAB_REGION = (1480, 2000, 230, 150)  # Must be larger than template (211x134)
SPECIAL_TAB_CLICK = (1589, 2080)  # Exact center from full-screen match (active)

# Thresholds - SQDIFF (lower is better)
CHEST_THRESHOLD = 0.02  # Strict matching for chests
VERIFICATION_THRESHOLD = 0.02

# Regular chest templates for Special tab (opened every day)
CHEST_TEMPLATES = [
    "bag_chest_special_4k.png",      # Open chest with blue gems
    "bag_golden_chest_4k.png",       # Golden wooden chest
    "bag_green_chest_4k.png",        # Green crystal chest
    "bag_purple_gold_chest_4k.png",  # Purple crystal chest
    "bag_chest_blue_4k.png",         # Blue/cyan crystal chest
    "bag_chest_purple_4k.png",       # Purple chest with gold trim
    "bag_chest_question_4k.png",     # Mystery chest with question mark
    "bag_chest_wooden_4k.png",       # Wooden chest with question mark medallion
    # "bag_chest_blue_striped_4k.png", # Disabled: false-positive/undesired trigger
    "bag_chest_gold_ornate_4k.png",  # Blue striped chest on blue background
    "bag_chest_purple_striped_4k.png",  # Gold/teal chest with blue gem
    "bag_giftbox_4k.png",            # Gift box (has quantity number below)
    "bag_chest_gems_orange_4k.png",  # Chest with blue gems on orange background
    "bag_chest_gems_purple_4k.png",  # Chest with blue gems on purple background
    "bag_chest_gold_purple_4k.png",  # Gold ornate chest on purple background
]

# Level chest templates (VS Wednesday only - Day 3)
LEVEL_CHEST_TEMPLATES = [
    "bag_chest_lv4_4k.png",  # Lv4 chest (purple striped)
    "bag_chest_lv3_4k.png",  # Lv3 chest (blue striped)
    "bag_chest_lv2_4k.png",  # Lv2 chest (gold ornate)
    "bag_chest_lv1_4k.png",  # Lv1 chest
]


def _find_first_chest(
    frame: npt.NDArray[Any],
    template_names: list[str],
    debug: bool = False,
) -> tuple[tuple[int, int] | None, float, str | None]:
    """
    Find the first (best matching) chest in the bag content region using COLOR matching.

    Returns:
        ((center_x, center_y), score, template_name) or (None, best_score, None) if not found
    """
    best_match: tuple[int, int] | None = None
    best_score = 1.0
    best_template_name: str | None = None

    for name in template_names:
        found, score, location = match_template(
            frame, name,
            search_region=BAG_CONTENT_REGION,
            threshold=CHEST_THRESHOLD
        )

        if debug:
            logger.info(f"    {name}: score={score:.4f}")

        if score < best_score:
            best_score = score
            if found and location:
                best_match = location
                best_template_name = name

    return best_match, best_score, best_template_name


def bag_special_flow(
    adb: ADBHelper,
    win: WindowsScreenshotHelper | None = None,
    debug: bool = False,
    open_bag: bool = True,
) -> int:
    """
    Execute the bag special flow to claim all chests from Special tab.

    Rescans after each chest since items shift position when used.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (optional)
        debug: Enable debug output
        open_bag: If True, click bag button first. If False, assume bag is already open.

    Returns:
        Number of chests claimed
    """
    if win is None:
        win = WindowsScreenshotHelper()

    # Check if VS level chest day AND in last 10 minutes (surprise strategy)
    arms_race = get_arms_race_status()
    is_level_chest_day = arms_race['day'] in VS_LEVEL_CHEST_DAYS
    minutes_remaining = arms_race.get('minutes_remaining', 999)

    # Only include level chests in last 10 minutes of VS day (surprise competitors)
    include_level_chests = is_level_chest_day and minutes_remaining <= 10

    # Build template list - always include regular chests, add level chests only in last 10 min
    template_names = CHEST_TEMPLATES.copy()
    if include_level_chests:
        template_names.extend(LEVEL_CHEST_TEMPLATES)
        if debug:
            logger.info(f"VS Day {arms_race['day']}, {minutes_remaining:.1f} min left - including level chest templates")

    if debug:
        logger.info(f"Using {len(template_names)} chest templates")

    # Step 1: Open bag if requested
    if open_bag:
        if debug:
            logger.info("Step 1: Opening bag...")

        frame = win.get_screenshot_cv2()

        # Use centralized template_matcher (COLOR matching)
        is_present, score, _ = match_template(frame, "bag_button_4k.png", search_region=BAG_BUTTON_REGION, threshold=0.1)
        if not is_present:
            if debug:
                logger.info(f"  Bag button not found (score={score:.4f})")
            return 0

        if debug:
            logger.info(f"  Bag button verified (score={score:.4f}), clicking...")

        adb.tap(*BAG_BUTTON_CLICK, source="flow:bag_special:open_bag_button")
        time.sleep(1.5)  # Wait for bag to fully load

        # Verify bag opened
        frame = win.get_screenshot_cv2()
        is_present, score, _ = match_template(frame, "bag_tab_4k.png", search_region=BAG_TAB_REGION, threshold=VERIFICATION_THRESHOLD)
        if not is_present:
            if debug:
                logger.info(f"  Bag tab not found - bag didn't open (score={score:.4f})")
            return 0

        if debug:
            logger.info(f"  Bag tab verified - bag is open (score={score:.4f})")

    # Step 2: Check Special tab state and activate if needed
    if debug:
        logger.info("Step 2: Checking Special tab...")

    frame = win.get_screenshot_cv2()

    # Check BOTH active and inactive - lower score wins
    _, active_score, _ = match_template(frame, "bag_special_tab_active_4k.png", search_region=SPECIAL_TAB_REGION, threshold=1.0)
    _, inactive_score, tab_center = match_template(frame, "bag_special_tab_4k.png", search_region=SPECIAL_TAB_REGION, threshold=1.0)

    if debug:
        logger.info(f"  Special tab scores: active={active_score:.4f}, inactive={inactive_score:.4f}")

    # Lower score = better match (SQDIFF)
    is_active = active_score < inactive_score

    if is_active:
        if debug:
            logger.info(f"  Special tab already ACTIVE (active_score < inactive_score)")
    else:
        if tab_center is None:
            if debug:
                logger.info(f"  Special tab not found")
            return 0

        # Click inactive tab to activate it (use detected center)
        if debug:
            logger.info(f"  Clicking Special tab at {tab_center} to activate...")
        adb.tap(*tab_center, source="flow:bag_special:activate_special_tab")
        time.sleep(0.5)

        # Verify it's now ACTIVE
        frame = win.get_screenshot_cv2()
        _, active_score, _ = match_template(frame, "bag_special_tab_active_4k.png", search_region=SPECIAL_TAB_REGION, threshold=1.0)
        _, inactive_score, _ = match_template(frame, "bag_special_tab_4k.png", search_region=SPECIAL_TAB_REGION, threshold=1.0)
        if active_score >= inactive_score:
            if debug:
                logger.info(f"  Special tab still not active after click (active={active_score:.4f}, inactive={inactive_score:.4f})")
            return 0

        if debug:
            logger.info(f"  Special tab is now ACTIVE")

    # Step 3: Loop - find and process chests one at a time, rescan after each
    chest_count = 0
    max_chests = 50

    while chest_count < max_chests:
        if debug:
            logger.info(f"\nScan #{chest_count + 1}: Looking for chests...")

        frame = win.get_screenshot_cv2()
        chest_pos, score, matched_template = _find_first_chest(frame, template_names, debug=debug)

        if chest_pos is None:
            if debug:
                logger.info(f"  No chest found (best score={score:.4f}), done!")
            break

        cx, cy = chest_pos
        if debug:
            logger.info(f"  Found chest at ({cx}, {cy}), score={score:.4f}, template={matched_template}")

        # Click chest
        if debug:
            logger.info("  Clicking chest...")
        adb.tap(cx, cy, source="flow:bag_special:click_chest")
        time.sleep(0.5)

        # Use the shared subflow for drag/use/back
        success = use_item_subflow(adb, win, debug=debug)
        if not success:
            logger.warning("  ERROR: use_item_subflow failed")
            break

        chest_count += 1
        if debug:
            logger.info(f"  Chest #{chest_count} processed!")

    if debug:
        logger.info(f"\nCompleted! Processed {chest_count} chest(s)")

    # Only close bag if we opened it
    if open_bag:
        if debug:
            logger.info("Closing bag...")
        click_back(adb)
        time.sleep(0.3)

    return chest_count


if __name__ == "__main__":
    import argparse
    from utils.adb_helper import ADBHelper

    parser = argparse.ArgumentParser(description="Bag Special Flow - Claim chests from Special tab")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--no-open-bag", action="store_true", help="Don't click bag button (assume already open)")
    args = parser.parse_args()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    count = bag_special_flow(adb, win, debug=args.debug, open_bag=not args.no_open_bag)
    logger.info(f"\nClaimed {count} chest(s)")
