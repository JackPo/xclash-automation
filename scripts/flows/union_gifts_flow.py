"""
Union Gifts Flow - Claim all loot chests and rare gifts.

Trigger Conditions:
- User idle for 20+ minutes
- No other flows currently running (lowest priority)
- At most once per hour (cooldown: 60 minutes)

Sequence:
1. Click Union button (bottom bar)
2. Click Union Rally Gifts button
3. Click Loot Chest tab
4. Click Claim All
5. Click Rare Gifts tab
6. Click Claim All
7. Click Back button to exit

NOTE: ALL detection uses WindowsScreenshotHelper (NOT ADB screenshots).
"""
from __future__ import annotations

import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Add parent dirs to path for imports
_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from typing import TYPE_CHECKING, Any

import cv2
import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.view_state_detector import detect_view, ViewState
from utils.template_matcher import match_template
from utils.debug_screenshot import save_debug_screenshot
from utils.return_to_base_view import return_to_base_view

# Setup logger
logger = logging.getLogger("union_gifts_flow")

# Flow name for debug screenshots
FLOW_NAME = "union_gifts"

# Fixed click coordinates (4K resolution)
UNION_BUTTON_CLICK = (3165, 2033)  # Union button on bottom bar
UNION_RALLY_GIFTS_CLICK = (2175, 1193)  # Union Rally Gifts menu item
LOOT_CHEST_TAB_CLICK = (1622, 545)  # Loot Chest tab
RARE_GIFTS_TAB_CLICK = (2202, 548)  # Rare Gifts tab
LOOT_CHEST_CLAIM_ALL_CLICK = (1879, 2051)  # Claim All button for Loot Chest
RARE_GIFTS_CLAIM_ALL_CLICK = (2217, 2049)  # Claim All button for Rare Gifts

from utils.ui_helpers import click_back
from config import BACK_BUTTON_CLICK

# Back button detection (fixed position)
BACK_BUTTON_X = 1345
BACK_BUTTON_Y = 2002
BACK_BUTTON_WIDTH = 107
BACK_BUTTON_HEIGHT = 111
BACK_BUTTON_THRESHOLD = 0.95  # CCORR (has mask) - higher is better


def _is_back_button_present(frame: npt.NDArray[Any]) -> tuple[bool, float]:
    """Check if back button is present at fixed location using template_matcher."""
    is_present, score, _ = match_template(
        frame, "back_button_union_4k.png",
        search_region=(BACK_BUTTON_X, BACK_BUTTON_Y, BACK_BUTTON_WIDTH, BACK_BUTTON_HEIGHT),
        threshold=BACK_BUTTON_THRESHOLD
    )
    return is_present, score

# Timing constants
CLICK_DELAY = 0.5  # Delay after each click
SCREEN_TRANSITION_DELAY = 1.5  # Delay for screen transitions
CLAIM_DELAY = 1.0  # Delay after claiming


def _save_debug_screenshot(frame: npt.NDArray[Any], name: str) -> str:
    """Save screenshot for debugging. Returns path."""
    return save_debug_screenshot(frame, FLOW_NAME, name)


def _log(msg: str) -> None:
    """Log to both logger and stdout."""
    logger.info(msg)
    print(f"    [UNION_GIFTS] {msg}")


def union_gifts_flow(adb: ADBHelper) -> bool:
    """
    Execute the union gifts claim flow.

    Args:
        adb: ADBHelper instance

    Returns:
        bool: True if flow completed successfully, False otherwise
    """
    flow_start = time.time()
    _log("=== UNION GIFTS FLOW START ===")

    win = WindowsScreenshotHelper()

    # Step 1: Click Union button
    _log(f"Step 1: Clicking Union button at {UNION_BUTTON_CLICK}")
    adb.tap(*UNION_BUTTON_CLICK)
    time.sleep(SCREEN_TRANSITION_DELAY)

    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "01_after_union_click")

    # Step 2: Click Union Rally Gifts
    _log(f"Step 2: Clicking Union Rally Gifts at {UNION_RALLY_GIFTS_CLICK}")
    adb.tap(*UNION_RALLY_GIFTS_CLICK)
    time.sleep(SCREEN_TRANSITION_DELAY)

    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "02_after_rally_gifts_click")

    # Step 3: Click Loot Chest tab
    _log(f"Step 3: Clicking Loot Chest tab at {LOOT_CHEST_TAB_CLICK}")
    adb.tap(*LOOT_CHEST_TAB_CLICK)
    time.sleep(CLICK_DELAY)

    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "03_after_loot_chest_tab")

    # Step 4: Click Claim All (for loot chests)
    _log(f"Step 4: Clicking Claim All at {LOOT_CHEST_CLAIM_ALL_CLICK}")
    adb.tap(*LOOT_CHEST_CLAIM_ALL_CLICK)
    time.sleep(CLAIM_DELAY)

    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "04_after_loot_claim")

    # Step 5: Click Rare Gifts tab TWICE (required to activate)
    _log(f"Step 5a: Clicking Rare Gifts tab (1st click) at {RARE_GIFTS_TAB_CLICK}")
    adb.tap(*RARE_GIFTS_TAB_CLICK)
    time.sleep(1.0)  # Longer delay between clicks
    _log(f"Step 5b: Clicking Rare Gifts tab (2nd click) at {RARE_GIFTS_TAB_CLICK}")
    adb.tap(*RARE_GIFTS_TAB_CLICK)
    time.sleep(CLICK_DELAY)

    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "05_after_rare_gifts_tab")

    # Step 6: Click Claim All ONCE (for rare gifts)
    _log(f"Step 6: Clicking Claim All at {RARE_GIFTS_CLAIM_ALL_CLICK}")
    adb.tap(*RARE_GIFTS_CLAIM_ALL_CLICK)
    time.sleep(CLAIM_DELAY)

    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "06_after_rare_claim")

    # Step 7: Return to base view (TOWN/WORLD)
    _log("Step 7: Returning to base view...")
    return_to_base_view(adb, win, debug=False)

    elapsed = time.time() - flow_start
    _log(f"=== UNION GIFTS FLOW SUCCESS === (took {elapsed:.1f}s)")
    return True


if __name__ == "__main__":
    # Test the flow manually
    from utils.adb_helper import ADBHelper

    adb = ADBHelper()
    print("Testing Union Gifts Flow...")
    print("=" * 50)

    success = union_gifts_flow(adb)

    print("=" * 50)
    if success:
        print("Flow completed successfully!")
    else:
        print("Flow FAILED!")
