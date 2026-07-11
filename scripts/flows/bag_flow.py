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
from typing import TYPE_CHECKING, Any

import numpy.typing as npt

from utils.windows_screenshot_helper import WindowsScreenshotHelper

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

logger = logging.getLogger(__name__)

_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import cv2
import numpy as np
from datetime import datetime

from utils.template_matcher import match_template

DEBUG_DIR = Path(__file__).resolve().parent.parent.parent / "screenshots" / "debug"

def _save_debug(frame: npt.NDArray[Any], step: str) -> None:
    """Save debug screenshot with timestamp and step name."""
    from config import DEBUG_SCREENSHOTS_ENABLED
    if not DEBUG_SCREENSHOTS_ENABLED:  # action-capture is the sole screenshot system now
        return
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S_%f")[:-3]
    path = DEBUG_DIR / f"bag_{ts}_{step}.png"
    cv2.imwrite(str(path), frame)
    logger.info(f"[BAG DEBUG] Saved: {path.name}")
from scripts.flows.bag_special_flow import bag_special_flow
from scripts.flows.bag_hero_flow import bag_hero_flow
from scripts.flows.bag_resources_flow import bag_resources_flow
from utils.return_to_base_view import return_to_base_view
from utils.view_state_detector import go_to_town

# Fixed positions (4K resolution)
# Template excludes notification badge area (top-right corner)
BAG_BUTTON_REGION = (3659, 1556, 132, 127)
BAG_BUTTON_CLICK = (3725, 1624)
BAG_TAB_REGION = (1352, 32, 1127, 90)

from utils.ui_helpers import click_back

# Thresholds: all SQDIFF (lower=better)
BAG_BUTTON_THRESHOLD = 0.10  # CCORR masked template - higher threshold for notification badge
BAG_TAB_THRESHOLD = 0.05     # SQDIFF_NORMED - no mask

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "ground_truth"

# Active tab templates at FIXED positions (no searching - exact location match)
# Regions must be LARGER than templates for matching to work
ACTIVE_TAB_TEMPLATES = {
    "special": ("bag_special_tab_active_4k.png", (1487, 2000, 230, 150)),   # template 211x134, center X=1497
    "resources": ("bag_resources_tab_active_4k.png", (1750, 2000, 200, 140)),  # template 179x111, center X=1760
    "hero": ("bag_hero_tab_active_4k.png", (2160, 2000, 220, 145)),  # pixel-measured center (2268,2065)
}

# Tab click positions (4K) - ALL VERIFIED via sweep test
# Tab order: Special | Resource | Speed Up | Hero | Gift
TAB_CLICK_POSITIONS = {
    "special": (1605, 2065),   # VERIFIED - use template center
    "resources": (1828, 2075),  # re-measured 2026-07-10: tab center (1800 still worked, was off-center)
    "hero": (2268, 2065),  # pixel-measured 2026-07-10: tabs evenly spaced 221px from Special@1605
}


def detect_active_tab(frame: npt.NDArray[Any], debug: bool = False) -> str | None:
    """
    Detect which bag tab is currently active by matching all active templates.

    Uses fixed search regions for each tab (~1ms each vs ~750ms full-frame).
    Returns the tab name with lowest score that passes threshold, or None.
    """
    best_tab = None
    best_score = 1.0

    for tab_name, (template_name, search_region) in ACTIVE_TAB_TEMPLATES.items():
        found, min_val, _ = match_template(
            frame, template_name,
            search_region=search_region,
            threshold=0.1
        )

        if debug:
            print(f"    {tab_name}: {min_val:.4f}")

        if min_val < best_score and found:
            best_score = min_val
            best_tab = tab_name

    return best_tab


def switch_to_tab(adb: ADBHelper, win: WindowsScreenshotHelper, target_tab: str, debug: bool = False) -> bool:
    """
    Switch to the specified tab if not already there.

    Returns True if successfully on target tab.
    """
    frame = win.get_screenshot_cv2()
    _save_debug(frame, f"tab_before_{target_tab}")
    current_tab = detect_active_tab(frame, debug=debug)

    if current_tab == target_tab:
        logger.info(f"[BAG] Already on {target_tab} tab")
        return True

    if target_tab not in TAB_CLICK_POSITIONS:
        logger.warning(f"[BAG] Unknown tab: {target_tab}")
        return False

    click_pos = TAB_CLICK_POSITIONS[target_tab]
    logger.info(f"[BAG] Current tab: {current_tab}, switching to {target_tab} at {click_pos}...")

    adb.tap(*click_pos, source=f"flow:bag:switch_to_{target_tab}_tab")
    time.sleep(0.5)

    # Verify switch
    frame = win.get_screenshot_cv2()
    _save_debug(frame, f"tab_after_{target_tab}")
    new_tab = detect_active_tab(frame, debug=debug)

    if new_tab == target_tab:
        logger.info(f"[BAG] Switched to {target_tab} tab")
        return True
    else:
        logger.warning(f"[BAG] Failed to switch, still on {new_tab}")
        return False


def bag_flow(adb: ADBHelper, win: WindowsScreenshotHelper | None = None, debug: bool = False) -> dict[str, int]:
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
            win = WindowsScreenshotHelper()

    results = {"special": 0, "hero": 0, "resources": 0}

    # Step 0: Navigate to TOWN (bag button only visible in TOWN view)
    logger.info("[BAG] Step 0: Navigating to TOWN...")
    go_to_town(adb, debug=debug)
    time.sleep(0.5)

    # DEBUG: Screenshot after go_to_town
    frame = win.get_screenshot_cv2()
    _save_debug(frame, "01_after_go_to_town")

    # Step 1: Verify bag button visible (confirms we're in TOWN)
    is_present, score, location = match_template(
        frame, "bag_button_4k.png",
        search_region=BAG_BUTTON_REGION,
        threshold=BAG_BUTTON_THRESHOLD
    )
    logger.info(f"[BAG] Bag button check: present={is_present}, score={score:.4f}, location={location}, region={BAG_BUTTON_REGION}")

    if not is_present:
        logger.warning(f"[BAG] Bag button not found (score={score:.4f}), aborting")
        _save_debug(frame, "01b_bag_button_NOT_FOUND")
        return results

    logger.info(f"[BAG] Bag button verified (score={score:.4f})")

    # Step 2: Click bag button
    logger.info(f"[BAG] Step 2: Opening bag at {BAG_BUTTON_CLICK}...")
    adb.tap(*BAG_BUTTON_CLICK, source="flow:bag:open_bag_button")
    time.sleep(1.5)

    # DEBUG: Screenshot after bag click
    frame = win.get_screenshot_cv2()
    _save_debug(frame, "02_after_bag_click")

    # Verify bag opened
    is_present, score, _ = match_template(
        frame, "bag_tab_4k.png",
        search_region=BAG_TAB_REGION,
        threshold=BAG_TAB_THRESHOLD
    )
    if not is_present:
        logger.warning(f"[BAG] Bag didn't open (tab score={score:.4f}), running recovery")
        _save_debug(frame, "02b_bag_NOT_OPENED")
        return_to_base_view(adb, win, debug=debug)
        return results

    logger.info(f"[BAG] Bag opened successfully (score={score:.4f})")

    # Step 3: Run Special tab flow
    logger.info("[BAG] Step 3: Special tab...")
    if switch_to_tab(adb, win, "special", debug=debug):
        results["special"] = bag_special_flow(adb, win, debug=debug, open_bag=False)
        logger.info(f"[BAG] Special tab claimed: {results['special']}")
        frame = win.get_screenshot_cv2()
        _save_debug(frame, "03_after_special")
    else:
        logger.warning("[BAG] Failed to switch to Special tab")

    # Step 4: Run Hero tab flow
    logger.info("[BAG] Step 4: Hero tab...")
    if switch_to_tab(adb, win, "hero", debug=debug):
        results["hero"] = bag_hero_flow(adb, win, debug=debug, open_bag=False)
        logger.info(f"[BAG] Hero tab claimed: {results['hero']}")
        frame = win.get_screenshot_cv2()
        _save_debug(frame, "04_after_hero")
    else:
        logger.warning("[BAG] Failed to switch to Hero tab")

    # Step 5: Run Resources tab flow
    logger.info("[BAG] Step 5: Resources tab...")
    if switch_to_tab(adb, win, "resources", debug=debug):
        results["resources"] = bag_resources_flow(adb, win, debug=debug, open_bag=False)
        logger.info(f"[BAG] Resources tab claimed: {results['resources']}")
        frame = win.get_screenshot_cv2()
        _save_debug(frame, "05_after_resources")
    else:
        logger.warning("[BAG] Failed to switch to Resources tab")

    # Step 6: Close bag and return to base view
    logger.info("[BAG] Step 6: Closing bag...")
    frame = win.get_screenshot_cv2()
    _save_debug(frame, "06_before_close")
    click_back(adb)
    time.sleep(0.5)

    frame = win.get_screenshot_cv2()
    _save_debug(frame, "07_after_close")
    return_to_base_view(adb, win, debug=debug)

    logger.info(f"[BAG] Complete: Special={results['special']}, Hero={results['hero']}, Resources={results['resources']}")

    return results


if __name__ == "__main__":
    import argparse
    from utils.adb_helper import ADBHelper

    parser = argparse.ArgumentParser(description="Bag Flow - Claim from all bag tabs")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    results = bag_flow(adb, win, debug=args.debug)
    print(f"\nResults: Special={results['special']}, Hero={results['hero']}, Resources={results['resources']}")
