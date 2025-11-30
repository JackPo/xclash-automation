"""
Union Gifts Flow - Claim all loot chests and rare gifts.

Trigger Conditions:
- User idle for 20+ minutes
- No other flows currently running (lowest priority)
- At most once per hour (cooldown: 60 minutes)
- Must be in TOWN view with dog house aligned

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
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Add parent dirs to path for imports
_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import cv2
import numpy as np

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.view_state_detector import detect_view, ViewState

# Setup logger
logger = logging.getLogger("union_gifts_flow")

# Debug output directory
DEBUG_DIR = Path(__file__).parent.parent.parent / "templates" / "debug" / "union_gifts_flow"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

# Fixed click coordinates (4K resolution)
UNION_BUTTON_CLICK = (3165, 2033)  # Union button on bottom bar
UNION_RALLY_GIFTS_CLICK = (2175, 1193)  # Union Rally Gifts menu item
LOOT_CHEST_TAB_CLICK = (1622, 545)  # Loot Chest tab
RARE_GIFTS_TAB_CLICK = (2202, 548)  # Rare Gifts tab
LOOT_CHEST_CLAIM_ALL_CLICK = (1879, 2051)  # Claim All button for Loot Chest
RARE_GIFTS_CLAIM_ALL_CLICK = (2217, 2049)  # Claim All button for Rare Gifts
BACK_BUTTON_CLICK = (1407, 2055)  # Back button (same as chat back)

# Back button detection (fixed position)
# Template cropped: +5 left, +5 top from original, so adjust position
BACK_BUTTON_X = 1345  # 1340 + 5 (offset for left crop)
BACK_BUTTON_Y = 2002  # 1997 + 5 (offset for top crop)
BACK_BUTTON_WIDTH = 107
BACK_BUTTON_HEIGHT = 111
BACK_BUTTON_THRESHOLD = 0.06  # TM_SQDIFF_NORMED (lower = better)
BACK_BUTTON_TEMPLATE = Path(__file__).parent.parent.parent / "templates" / "ground_truth" / "back_button_union_4k.png"

# Load template once
_back_button_template = None

def _get_back_button_template():
    global _back_button_template
    if _back_button_template is None:
        _back_button_template = cv2.imread(str(BACK_BUTTON_TEMPLATE), cv2.IMREAD_GRAYSCALE)
    return _back_button_template

def _is_back_button_present(frame: np.ndarray) -> tuple[bool, float]:
    """Check if back button is present at fixed location using TM_SQDIFF_NORMED."""
    template = _get_back_button_template()
    if template is None:
        return False, 1.0

    # Extract ROI at fixed position
    roi = frame[BACK_BUTTON_Y:BACK_BUTTON_Y + BACK_BUTTON_HEIGHT,
                BACK_BUTTON_X:BACK_BUTTON_X + BACK_BUTTON_WIDTH]

    if len(roi.shape) == 3:
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    else:
        roi_gray = roi

    # Template match with TM_SQDIFF_NORMED (lower = better)
    result = cv2.matchTemplate(roi_gray, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, _, _ = cv2.minMaxLoc(result)
    score = float(min_val)

    is_present = score <= BACK_BUTTON_THRESHOLD
    return is_present, score

# Timing constants
CLICK_DELAY = 0.5  # Delay after each click
SCREEN_TRANSITION_DELAY = 1.5  # Delay for screen transitions
CLAIM_DELAY = 1.0  # Delay after claiming


def _save_debug_screenshot(frame, name: str) -> str:
    """Save screenshot for debugging. Returns path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = DEBUG_DIR / f"{timestamp}_{name}.png"
    cv2.imwrite(str(path), frame)
    return str(path)


def _log(msg: str):
    """Log to both logger and stdout."""
    logger.info(msg)
    print(f"    [UNION_GIFTS] {msg}")


def union_gifts_flow(adb) -> bool:
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

    # Step 0: Verify we're in TOWN view
    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "00_initial_state")
        state, score = detect_view(frame)
        _log(f"Current view: {state.name} (score={score:.4f})")

        if state != ViewState.TOWN:
            _log("FAILED: Not in TOWN view, aborting")
            return False

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

    # Step 7: Click Back button until no longer visible
    # Click first, then check if still there, repeat until gone
    _log("Step 7: Clicking Back button until menu closed")
    max_back_attempts = 5

    for attempt in range(max_back_attempts):
        # Click back button first (don't check before clicking)
        _log(f"Clicking Back button at {BACK_BUTTON_CLICK} (attempt {attempt + 1})")
        adb.tap(*BACK_BUTTON_CLICK)
        time.sleep(CLICK_DELAY)

        # Now check if back button is still visible
        frame = win.get_screenshot_cv2()
        if frame is None:
            break

        is_present, score = _is_back_button_present(frame)
        _save_debug_screenshot(frame, f"07_back_check_{attempt}")

        if not is_present:
            _log(f"Back button no longer visible (score={score:.4f}), menu closed")
            break

        _log(f"Back button still visible (score={score:.4f}), will click again")

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
