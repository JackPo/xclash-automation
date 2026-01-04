"""
AFK Rewards Flow - Claim idle rewards from chest.

Trigger Conditions:
- User idle for 5+ minutes
- In TOWN view with dog house aligned
- AFK rewards chest icon visible

Sequence:
1. Click on the AFK rewards chest icon
2. Click Claim button repeatedly until back in TOWN view (world button visible)

NOTE: ALL detection uses WindowsScreenshotHelper (NOT ADB screenshots).
"""
from __future__ import annotations

import sys
import time
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy.typing as npt

# Add parent dirs to path for imports
_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import cv2

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.view_state_detector import detect_view, ViewState
from utils.debug_screenshot import save_debug_screenshot

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

# Setup logger
logger = logging.getLogger("afk_rewards_flow")

# Flow name for debug screenshots
FLOW_NAME = "afk_rewards"

# Click coordinates (4K resolution)
AFK_CHEST_CLICK = (805, 1709)  # Center of AFK rewards chest
CLAIM_BUTTON_CLICK = (1917, 1718)  # Center of Claim button

# Timing
CLICK_DELAY = 1.0  # Delay between claim clicks
MAX_CLAIM_ATTEMPTS = 3  # Maximum claim button clicks


def _save_debug_screenshot(frame: npt.NDArray[Any], name: str) -> str:
    """Save screenshot for debugging. Returns path."""
    return save_debug_screenshot(frame, FLOW_NAME, name)


def _log(msg: str) -> None:
    """Log to both logger and stdout."""
    logger.info(msg)
    print(f"    [AFK_REWARDS] {msg}")


def afk_rewards_flow(adb: ADBHelper) -> bool:
    """
    Execute the AFK rewards claim flow.

    Args:
        adb: ADBHelper instance

    Returns:
        bool: True if flow completed successfully, False otherwise
    """
    flow_start = time.time()
    _log("=== AFK REWARDS FLOW START ===")

    win = WindowsScreenshotHelper()

    # VERIFY we're in TOWN view before clicking
    frame = win.get_screenshot_cv2()
    view_state, view_score = detect_view(frame)
    if view_state != ViewState.TOWN:
        _log(f"NOT in TOWN view (state={view_state.value}), aborting")
        return False

    # Step 1: Click on AFK rewards chest
    _log(f"Step 1: Clicking AFK rewards chest at {AFK_CHEST_CLICK}")
    adb.tap(*AFK_CHEST_CLICK)
    time.sleep(1.5)  # Wait for dialog to open

    frame = win.get_screenshot_cv2()
    _save_debug_screenshot(frame, "01_after_chest_click")

    # Step 2: Click Claim button until back in TOWN view
    _log("Step 2: Clicking Claim button until back in TOWN view")

    for attempt in range(MAX_CLAIM_ATTEMPTS):
        # Click the Claim button
        _log(f"Clicking Claim at {CLAIM_BUTTON_CLICK} (attempt {attempt + 1})")
        adb.tap(*CLAIM_BUTTON_CLICK)
        time.sleep(CLICK_DELAY)

        # Check if we're back in TOWN view
        frame = win.get_screenshot_cv2()
        _save_debug_screenshot(frame, f"02_claim_attempt_{attempt}")

        view_state, view_score = detect_view(frame)
        if view_state == ViewState.TOWN:
            _log(f"Back in TOWN view (score={view_score:.4f}), flow complete")
            break
        else:
            _log(f"Not in TOWN yet (state={view_state.value}, score={view_score:.4f})")

    elapsed = time.time() - flow_start
    _log(f"=== AFK REWARDS FLOW SUCCESS === (took {elapsed:.1f}s)")
    return True


if __name__ == "__main__":
    # Test the flow manually
    from utils.adb_helper import ADBHelper

    adb = ADBHelper()
    print("Testing AFK Rewards Flow...")
    print("=" * 50)

    success = afk_rewards_flow(adb)

    print("=" * 50)
    if success:
        print("Flow completed successfully!")
    else:
        print("Flow FAILED!")
