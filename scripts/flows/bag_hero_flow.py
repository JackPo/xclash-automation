"""
Bag Hero Tab Flow - Treasure chest claiming.

Opens the bag, goes to Hero tab, finds treasure chest tiles one at a time,
and uses them. Rescans after each use since items shift position.

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

HERO_TAB_REGION = (2150, 2008, 230, 145)  # Must be larger than template (207x127)
HERO_TAB_CLICK = (2261, 2078)  # Exact center from full-screen match

# Thresholds - SQDIFF (lower is better)
CHEST_THRESHOLD = 0.02
VERIFICATION_THRESHOLD = 0.015

# Chest templates for Hero tab
# bag_hero_chest_4k.png has a mask that ignores background color,
# so it matches all color variants (blue, purple, orange backgrounds)
CHEST_TEMPLATES = [
    "bag_hero_chest_4k.png",
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


def bag_hero_flow(
    adb: ADBHelper,
    win: WindowsScreenshotHelper | None = None,
    debug: bool = False,
    open_bag: bool = True,
) -> int:
    """
    Execute the bag hero flow to claim all treasure chests.

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

    if debug:
        logger.info(f"Loaded {len(CHEST_TEMPLATES)} chest templates: {CHEST_TEMPLATES}")

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

        adb.tap(*BAG_BUTTON_CLICK, source="flow:bag_hero:open_bag_button")
        time.sleep(1.0)

        # Verify bag opened
        frame = win.get_screenshot_cv2()
        is_present, score, _ = match_template(frame, "bag_tab_4k.png", search_region=BAG_TAB_REGION, threshold=VERIFICATION_THRESHOLD)
        if not is_present:
            if debug:
                logger.info(f"  Bag tab not found - bag didn't open (score={score:.4f})")
            return 0

        if debug:
            logger.info(f"  Bag tab verified - bag is open (score={score:.4f})")

    # Step 2: Check Hero tab state and activate if needed
    if debug:
        logger.info("Step 2: Checking Hero tab...")

    frame = win.get_screenshot_cv2()

    # Check BOTH active and inactive - lower score wins
    _, active_score, _ = match_template(frame, "bag_hero_tab_active_4k.png", search_region=HERO_TAB_REGION, threshold=1.0)
    _, inactive_score, tab_center = match_template(frame, "bag_hero_tab_4k.png", search_region=HERO_TAB_REGION, threshold=1.0)

    if debug:
        logger.info(f"  Hero tab scores: active={active_score:.4f}, inactive={inactive_score:.4f}")

    # Lower score = better match (SQDIFF)
    is_active = active_score < inactive_score

    if is_active:
        if debug:
            logger.info(f"  Hero tab already ACTIVE (active_score < inactive_score)")
    else:
        if tab_center is None:
            if debug:
                logger.info(f"  Hero tab not found")
            return 0

        # Click inactive tab to activate it (use detected center)
        if debug:
            logger.info(f"  Clicking Hero tab at {tab_center} to activate...")
        adb.tap(*tab_center, source="flow:bag_hero:activate_hero_tab")
        time.sleep(0.5)

        # Verify it's now ACTIVE
        frame = win.get_screenshot_cv2()
        _, active_score, _ = match_template(frame, "bag_hero_tab_active_4k.png", search_region=HERO_TAB_REGION, threshold=1.0)
        _, inactive_score, _ = match_template(frame, "bag_hero_tab_4k.png", search_region=HERO_TAB_REGION, threshold=1.0)
        if active_score >= inactive_score:
            if debug:
                logger.info(f"  Hero tab still not active after click (active={active_score:.4f}, inactive={inactive_score:.4f})")
            return 0

        if debug:
            logger.info(f"  Hero tab is now ACTIVE")

    # Step 3: Loop - find and process chests one at a time, rescan after each
    chest_count = 0
    max_chests = 50

    while chest_count < max_chests:
        if debug:
            logger.info(f"\nScan #{chest_count + 1}: Looking for chests...")

        frame = win.get_screenshot_cv2()
        chest_pos, score, matched_template = _find_first_chest(frame, CHEST_TEMPLATES, debug=debug)

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
        adb.tap(cx, cy, source="flow:bag_hero:click_chest")
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

    parser = argparse.ArgumentParser(description="Bag Hero Flow - Claim treasure chests")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--no-open-bag", action="store_true", help="Don't click bag button (assume already open)")
    args = parser.parse_args()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    count = bag_hero_flow(adb, win, debug=args.debug, open_bag=not args.no_open_bag)
    logger.info(f"\nClaimed {count} chest(s)")
