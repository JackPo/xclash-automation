"""
Bag Resources Tab Flow - Diamond claiming.

Opens the bag, goes to Resources tab, finds diamond tiles one at a time,
and uses them. Rescans after each use since items shift position.

All matching uses template_matcher with COLOR images (no grayscale).
"""
from __future__ import annotations

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

RESOURCES_TAB_REGION = (1720, 2010, 200, 130)  # Must be larger than template (179x111)
RESOURCES_TAB_CLICK = (1817, 2073)  # Exact center from full-screen match

BAG_TAB_REGION = (1352, 32, 1127, 90)

# Bag content region - ONLY search for items within this area (not full screen)
BAG_CONTENT_REGION = (1337, 137, 1161, 1871)  # x, y, w, h - the white item grid

# Thresholds - SQDIFF (lower is better)
DIAMOND_THRESHOLD = 0.02
VERIFICATION_THRESHOLD = 0.015


def _find_first_diamond(
    frame: npt.NDArray[Any],
    debug: bool = False,
) -> tuple[tuple[int, int] | None, float]:
    """
    Find the first (best matching) diamond in the bag content region using COLOR matching.

    Returns:
        ((center_x, center_y), score) or (None, score) if not found
    """
    found, score, location = match_template(
        frame, "bag_diamond_icon_4k.png",
        search_region=BAG_CONTENT_REGION,
        threshold=DIAMOND_THRESHOLD
    )

    if found and location:
        return location, score
    return None, score


def bag_resources_flow(
    adb: ADBHelper,
    win: WindowsScreenshotHelper | None = None,
    debug: bool = False,
    open_bag: bool = True,
) -> int:
    """
    Execute the bag resources flow to claim all diamonds.

    Rescans after each diamond since items shift position when used.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (optional)
        debug: Enable debug output
        open_bag: If True, click bag button first. If False, assume bag is already open.

    Returns:
        Number of diamonds claimed
    """
    if win is None:
        win = WindowsScreenshotHelper()

    # Step 1: Open bag if requested
    if open_bag:
        if debug:
            print("Step 1: Opening bag...")

        frame = win.get_screenshot_cv2()

        # Use centralized template_matcher (COLOR matching)
        is_present, score, _ = match_template(frame, "bag_button_4k.png", search_region=BAG_BUTTON_REGION, threshold=0.1)
        if not is_present:
            if debug:
                print(f"  Bag button not found (score={score:.4f})")
            return 0

        if debug:
            print(f"  Bag button verified (score={score:.4f}), clicking...")

        adb.tap(*BAG_BUTTON_CLICK, source="flow:bag_resources:open_bag_button")
        time.sleep(1.0)

        # VERIFY: Bag tab visible at top (confirms bag menu opened)
        frame = win.get_screenshot_cv2()
        is_present, score, _ = match_template(frame, "bag_tab_4k.png", search_region=BAG_TAB_REGION, threshold=VERIFICATION_THRESHOLD)
        if not is_present:
            if debug:
                print(f"  Bag tab not found - bag didn't open (score={score:.4f})")
            return 0

        if debug:
            print(f"  Bag tab verified - bag is open (score={score:.4f})")

    # Step 2: Check Resources tab state and activate if needed
    if debug:
        print("Step 2: Checking Resources tab...")

    frame = win.get_screenshot_cv2()

    # Check BOTH templates - lower score wins
    _, active_score, _ = match_template(frame, "bag_resources_tab_active_4k.png", search_region=RESOURCES_TAB_REGION, threshold=1.0)
    _, inactive_score, tab_center = match_template(frame, "bag_resources_tab_4k.png", search_region=RESOURCES_TAB_REGION, threshold=1.0)

    if debug:
        print(f"  Resources tab scores: active={active_score:.4f}, inactive={inactive_score:.4f}")

    # Lower score = better match (SQDIFF)
    is_active = active_score < inactive_score

    if is_active:
        if debug:
            print(f"  Resources tab already ACTIVE (active_score < inactive_score)")
    else:
        if tab_center is None:
            if debug:
                print(f"  Resources tab not found")
            return 0

        # Click inactive tab to activate it (use detected center)
        if debug:
            print(f"  Clicking Resources tab at {tab_center} to activate...")
        adb.tap(*tab_center, source="flow:bag_resources:activate_resources_tab")
        time.sleep(0.5)

        # Verify it's now ACTIVE
        frame = win.get_screenshot_cv2()
        _, active_score, _ = match_template(frame, "bag_resources_tab_active_4k.png", search_region=RESOURCES_TAB_REGION, threshold=1.0)
        _, inactive_score, _ = match_template(frame, "bag_resources_tab_4k.png", search_region=RESOURCES_TAB_REGION, threshold=1.0)
        if active_score >= inactive_score:
            if debug:
                print(f"  Resources tab still not active after click (active={active_score:.4f}, inactive={inactive_score:.4f})")
            return 0

        if debug:
            print(f"  Resources tab is now ACTIVE")

    # Step 3: Loop - find and process diamonds one at a time, rescan after each
    diamond_count = 0
    max_diamonds = 50  # Safety limit

    while diamond_count < max_diamonds:
        # RESCAN for diamonds (they shift after each use)
        if debug:
            print(f"\nScan #{diamond_count + 1}: Looking for diamonds...")

        frame = win.get_screenshot_cv2()
        diamond_pos, score = _find_first_diamond(frame, debug=debug)

        if diamond_pos is None:
            if debug:
                print(f"  No diamond found (best score={score:.4f}), done!")
            break

        dx, dy = diamond_pos
        if debug:
            print(f"  Found diamond at ({dx}, {dy}), score={score:.4f}")

        # Click diamond
        if debug:
            print("  Clicking diamond...")
        adb.tap(dx, dy, source="flow:bag_resources:click_diamond")
        time.sleep(0.5)

        # Use the shared subflow for drag/use/back
        success = use_item_subflow(adb, win, debug=debug)
        if not success:
            if debug:
                print("  ERROR: use_item_subflow failed")
            break

        diamond_count += 1
        if debug:
            print(f"  Diamond #{diamond_count} processed!")

    if debug:
        print(f"\nCompleted! Processed {diamond_count} diamond(s)")

    # Only close bag if we opened it
    if open_bag:
        if debug:
            print("Closing bag...")
        click_back(adb)
        time.sleep(0.3)

    return diamond_count


if __name__ == "__main__":
    import argparse
    from utils.adb_helper import ADBHelper

    parser = argparse.ArgumentParser(description="Bag Resources Flow - Claim diamonds")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--no-open-bag", action="store_true", help="Don't click bag button (assume already open)")
    args = parser.parse_args()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    count = bag_resources_flow(adb, win, debug=args.debug, open_bag=not args.no_open_bag)
    print(f"\nClaimed {count} diamond(s)")
