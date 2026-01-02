"""
Gift Box Flow - Claim rewards from gift box in WORLD view.

Trigger Conditions:
- User idle for 5+ minutes
- In WORLD view (town button visible)
- Gift box icon visible at fixed position

Sequence:
1. Verify gift box icon present at (410, 378)
2. Click gift box center (462, 428)
3. Wait for rewards dialog
4. Click Claim All button
5. Return to base view

NOTE: ALL detection uses WindowsScreenshotHelper (NOT ADB screenshots).
"""
import sys
import time
import logging
from pathlib import Path

# Add parent dirs to path for imports
_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import numpy as np

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.return_to_base_view import return_to_base_view
from utils.template_matcher import match_template

# Setup logger
logger = logging.getLogger("gift_box_flow")

# Gift box icon position (4K resolution)
GIFT_BOX_REGION = (410, 400, 70, 70)  # x, y, w, h - just the gift box without badge
GIFT_BOX_CLICK = (445, 435)  # Center of icon

# Claim All button in Loot dialog
CLAIM_ALL_CLICK = (1913, 1699)  # Center of Claim All button

from utils.ui_helpers import click_back
from config import BACK_BUTTON_CLICK

# Threshold
GIFT_BOX_THRESHOLD = 0.06


def _log(msg: str):
    """Log to both logger and stdout."""
    logger.info(msg)
    print(f"    [GIFT_BOX] {msg}")


def gift_box_flow(adb, win=None, debug: bool = False) -> bool:
    """
    Execute the gift box claim flow.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (optional)
        debug: Enable debug output

    Returns:
        bool: True if flow completed successfully, False otherwise
    """
    if win is None:
        win = WindowsScreenshotHelper()

    # Step 1: Verify gift box present
    if debug:
        _log("Step 1: Checking for gift box...")

    frame = win.get_screenshot_cv2()
    is_present, score, _ = match_template(
        frame, "gift_box_4k.png",
        search_region=GIFT_BOX_REGION,
        threshold=GIFT_BOX_THRESHOLD
    )
    if not is_present:
        if debug:
            _log(f"Gift box not found (score={score:.4f})")
        return False

    if debug:
        _log(f"Gift box found (score={score:.4f})")

    # Step 2: Click gift box
    if debug:
        _log(f"Step 2: Clicking gift box at {GIFT_BOX_CLICK}")
    adb.tap(*GIFT_BOX_CLICK)
    time.sleep(1.5)  # Wait for dialog

    # Step 3: Click Claim All
    if debug:
        _log(f"Step 3: Clicking Claim All at {CLAIM_ALL_CLICK}")
    adb.tap(*CLAIM_ALL_CLICK)
    time.sleep(1.0)

    # Step 4: Click back button to close rewards popup
    if debug:
        _log(f"Step 4: Clicking back button at {BACK_BUTTON_CLICK}")
    click_back(adb)
    time.sleep(0.5)

    # Step 5: Return to base view
    if debug:
        _log("Step 5: Returning to base view")
    return_to_base_view(adb, win, debug=debug)

    if debug:
        _log("=== GIFT BOX FLOW COMPLETE ===")
    return True


if __name__ == "__main__":
    import argparse
    from utils.adb_helper import ADBHelper

    parser = argparse.ArgumentParser(description="Gift Box Flow - Claim world view rewards")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    success = gift_box_flow(adb, win, debug=args.debug)
    print(f"\nResult: {'SUCCESS' if success else 'FAILED'}")
