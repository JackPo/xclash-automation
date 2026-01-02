"""
Bag Flow - Main orchestrator for all bag tab flows.

Opens the bag and runs all 3 subflows:
1. Special tab - chests
2. Hero tab - chests
3. Resources tab - diamonds

Then closes bag and returns to base view.
Triggered by 5-minute idle (same as union gifts/donation).
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import cv2
import numpy as np

from utils.template_matcher import match_template
from scripts.flows.bag_special_flow import bag_special_flow
from scripts.flows.bag_hero_flow import bag_hero_flow
from scripts.flows.bag_resources_flow import bag_resources_flow
from utils.return_to_base_view import return_to_base_view
from utils.view_state_detector import go_to_town

# Fixed positions (4K resolution)
# Template excludes notification badge area (top-right corner)
BAG_BUTTON_REGION = (3679, 1596, 72, 77)
BAG_BUTTON_CLICK = (3725, 1624)
BAG_TAB_REGION = (1352, 32, 1127, 90)

from utils.ui_helpers import click_back

# Thresholds: bag_button has mask (CCORR, higher=better), bag_tab no mask (SQDIFF, lower=better)
BAG_BUTTON_THRESHOLD = 0.97  # CCORR - masked template
BAG_TAB_THRESHOLD = 0.05     # SQDIFF - no mask

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "ground_truth"

# Active tab templates - match all, lowest score = current tab
ACTIVE_TAB_TEMPLATES = {
    "special": "bag_special_tab_active_4k.png",
    "resources": "bag_resources_tab_active_4k.png",
    "hero": "bag_hero_tab_active_4k.png",
}

# Tab click positions (4K)
TAB_CLICK_POSITIONS = {
    "special": (1602, 2080),
    "resources": (1827, 2076),
    "hero": (2257, 2078),
}


def detect_active_tab(frame: np.ndarray, debug: bool = False) -> str | None:
    """
    Detect which bag tab is currently active by matching all active templates.

    Returns the tab name with lowest score that passes threshold, or None.
    """
    best_tab = None
    best_score = 1.0

    for tab_name, template_name in ACTIVE_TAB_TEMPLATES.items():
        found, min_val, _ = match_template(frame, template_name, threshold=0.1)

        if debug:
            print(f"    {tab_name}: {min_val:.4f}")

        if min_val < best_score and found:
            best_score = min_val
            best_tab = tab_name

    return best_tab


def switch_to_tab(adb, win, target_tab: str, debug: bool = False) -> bool:
    """
    Switch to the specified tab if not already there.

    Returns True if successfully on target tab.
    """
    frame = win.get_screenshot_cv2()
    current_tab = detect_active_tab(frame, debug=debug)

    if current_tab == target_tab:
        if debug:
            print(f"  Already on {target_tab} tab")
        return True

    if target_tab not in TAB_CLICK_POSITIONS:
        if debug:
            print(f"  Unknown tab: {target_tab}")
        return False

    if debug:
        print(f"  Current tab: {current_tab}, switching to {target_tab}...")

    adb.tap(*TAB_CLICK_POSITIONS[target_tab])
    time.sleep(0.5)

    # Verify switch
    frame = win.get_screenshot_cv2()
    new_tab = detect_active_tab(frame, debug=debug)

    if new_tab == target_tab:
        if debug:
            print(f"  Switched to {target_tab} tab")
        return True
    else:
        if debug:
            print(f"  Failed to switch, still on {new_tab}")
        return False


def bag_flow(adb, win=None, debug: bool = False) -> dict:
    """
    Execute the main bag flow - opens bag and runs all 3 subflows.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (optional)
        debug: Enable debug output

    Returns:
        dict with counts: {"special": N, "hero": N, "resources": N}
    """
    if win is None:
        from utils.windows_screenshot_helper import WindowsScreenshotHelper
        win = WindowsScreenshotHelper()

    results = {"special": 0, "hero": 0, "resources": 0}

    # Step 0: Navigate to TOWN (bag button only visible in TOWN view)
    logger.info("[BAG] Step 0: Navigating to TOWN...")
    go_to_town(adb, debug=debug)
    time.sleep(0.5)

    # Step 1: Verify bag button visible (confirms we're in TOWN)
    frame = win.get_screenshot_cv2()
    is_present, score, _ = match_template(
        frame, "bag_button_4k.png",
        search_region=BAG_BUTTON_REGION,
        threshold=BAG_BUTTON_THRESHOLD
    )
    if not is_present:
        logger.warning(f"[BAG] Bag button not found (score={score:.4f}), aborting")
        return results

    logger.info(f"[BAG] Bag button verified (score={score:.4f})")

    # Step 2: Click bag button
    logger.info(f"[BAG] Step 2: Opening bag at {BAG_BUTTON_CLICK}...")
    adb.tap(*BAG_BUTTON_CLICK)
    time.sleep(1.5)

    # Verify bag opened
    frame = win.get_screenshot_cv2()
    is_present, score, _ = match_template(
        frame, "bag_tab_4k.png",
        search_region=BAG_TAB_REGION,
        threshold=BAG_TAB_THRESHOLD
    )
    if not is_present:
        logger.warning(f"[BAG] Bag didn't open (tab score={score:.4f}), running recovery")
        return_to_base_view(adb, win, debug=debug)
        return results

    logger.info(f"[BAG] Bag opened successfully (score={score:.4f})")

    # Step 3: Run Special tab flow
    logger.info("[BAG] Step 3: Special tab...")
    if switch_to_tab(adb, win, "special", debug=debug):
        results["special"] = bag_special_flow(adb, win, debug=debug, open_bag=False)
        logger.info(f"[BAG] Special tab claimed: {results['special']}")
    else:
        logger.warning("[BAG] Failed to switch to Special tab")

    # Step 4: Run Hero tab flow
    logger.info("[BAG] Step 4: Hero tab...")
    if switch_to_tab(adb, win, "hero", debug=debug):
        results["hero"] = bag_hero_flow(adb, win, debug=debug, open_bag=False)
        logger.info(f"[BAG] Hero tab claimed: {results['hero']}")
    else:
        logger.warning("[BAG] Failed to switch to Hero tab")

    # Step 5: Run Resources tab flow
    logger.info("[BAG] Step 5: Resources tab...")
    if switch_to_tab(adb, win, "resources", debug=debug):
        results["resources"] = bag_resources_flow(adb, win, debug=debug, open_bag=False)
        logger.info(f"[BAG] Resources tab claimed: {results['resources']}")
    else:
        logger.warning("[BAG] Failed to switch to Resources tab")

    # Step 6: Close bag and return to base view
    logger.info("[BAG] Step 6: Closing bag...")
    click_back(adb)
    time.sleep(0.5)

    return_to_base_view(adb, win, debug=debug)

    logger.info(f"[BAG] Complete: Special={results['special']}, Hero={results['hero']}, Resources={results['resources']}")

    return results


if __name__ == "__main__":
    import argparse
    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    parser = argparse.ArgumentParser(description="Bag Flow - Claim from all bag tabs")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    results = bag_flow(adb, win, debug=args.debug)
    print(f"\nResults: Special={results['special']}, Hero={results['hero']}, Resources={results['resources']}")
