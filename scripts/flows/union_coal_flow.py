"""
Union Coal Collection Flow - Collect coal from Union City.

Trigger Conditions:
- Runs every hour (like union technology donation)
- User idle
- No other flows currently running

Sequence:
1. Click Union button (bottom bar)
2. Click Union City button (template match)
3. Verify Union Cities header
4. Click Coal Output tab (if not active)
5. Click Claim All button
6. Return to base view
"""
from __future__ import annotations

import sys
import time
import logging
from pathlib import Path
from typing import TYPE_CHECKING

# Add parent dirs to path for imports
_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.return_to_base_view import return_to_base_view
from utils.template_matcher import match_template

# Setup logger
logger = logging.getLogger("union_coal_flow")

# Templates directory
TEMPLATES_DIR = "union_cities"

# Fixed click coordinates (4K resolution)
UNION_BUTTON_CLICK = (3165, 2033)  # Union button on bottom bar
UNION_CITY_CLICK = (2173, 1007)    # Union City button in Union menu
COAL_OUTPUT_TAB_CLICK = (1670, 185)  # Coal Output tab
CLAIM_ALL_CLICK = (1914, 2036)     # Claim All button

# Timing constants
CLICK_DELAY = 0.5
SCREEN_TRANSITION_DELAY = 1.5

# Thresholds
THRESHOLD = 0.08


def union_coal_flow(
    adb: ADBHelper,
    debug: bool = False,
) -> bool:
    """
    Collect coal from Union City.

    Args:
        adb: ADBHelper instance
        debug: Enable debug output

    Returns:
        bool: True if successful
    """
    win = WindowsScreenshotHelper()

    if debug:
        print("Union Coal Flow")
        print("=" * 50)

    # Step 1: Click Union button
    if debug:
        print("Step 1: Clicking Union button...")
    adb.tap(*UNION_BUTTON_CLICK, source="flow:union_coal:union_button")
    time.sleep(SCREEN_TRANSITION_DELAY)

    # Step 2: Click Union City button
    if debug:
        print("Step 2: Clicking Union City...")
    frame = win.get_screenshot_cv2()

    found, score, pos = match_template(
        frame,
        f"{TEMPLATES_DIR}/union_city_button_4k.png",
        threshold=THRESHOLD
    )
    if debug:
        print(f"  Union City button: found={found}, score={score:.4f}, pos={pos}")

    if found and pos:
        adb.tap(*pos, source="flow:union_coal:union_city")
    else:
        # Fallback to fixed position
        adb.tap(*UNION_CITY_CLICK, source="flow:union_coal:union_city_fixed")
    time.sleep(SCREEN_TRANSITION_DELAY)

    # Step 3: Verify Union Cities header
    if debug:
        print("Step 3: Verifying Union Cities header...")
    frame = win.get_screenshot_cv2()

    found, score, _ = match_template(
        frame,
        f"{TEMPLATES_DIR}/union_cities_header_4k.png",
        threshold=THRESHOLD
    )
    if debug:
        print(f"  Union Cities header: found={found}, score={score:.4f}")

    if not found:
        logger.warning("Union Cities header not found")
        if debug:
            print("  WARNING: Header not found, continuing anyway...")

    # Step 4: Click Coal Output tab (check if This Kingdom is active, meaning we need to switch)
    if debug:
        print("Step 4: Checking which tab is active...")

    # Check if This Kingdom tab is active (meaning Coal Output is NOT active)
    this_kingdom_active, tk_score, _ = match_template(
        frame,
        f"{TEMPLATES_DIR}/this_kingdom_tab_active_4k.png",
        threshold=THRESHOLD
    )
    if debug:
        print(f"  This Kingdom active: found={this_kingdom_active}, score={tk_score:.4f}")

    if this_kingdom_active:
        # We're on This Kingdom, need to click Coal Output
        if debug:
            print("  Clicking Coal Output tab...")
        adb.tap(*COAL_OUTPUT_TAB_CLICK, source="flow:union_coal:coal_output_tab")
        time.sleep(SCREEN_TRANSITION_DELAY)
        frame = win.get_screenshot_cv2()
    else:
        if debug:
            print("  Already on Coal Output tab")

    # Step 5: Click Claim All button
    if debug:
        print("Step 5: Clicking Claim All...")

    found, score, pos = match_template(
        frame,
        f"{TEMPLATES_DIR}/claim_all_button_blue_4k.png",
        threshold=THRESHOLD
    )
    if debug:
        print(f"  Claim All button: found={found}, score={score:.4f}, pos={pos}")

    if found and pos:
        adb.tap(*pos, source="flow:union_coal:claim_all")
    else:
        # Fallback to fixed position
        if debug:
            print("  Using fixed position for Claim All...")
        adb.tap(*CLAIM_ALL_CLICK, source="flow:union_coal:claim_all_fixed")
    time.sleep(CLICK_DELAY)

    # Step 6: Return to base view
    if debug:
        print("Step 6: Returning to base view...")
    return_to_base_view(adb, win, debug=False)

    if debug:
        print("=" * 50)
        print("Union Coal Flow completed!")

    return True


if __name__ == "__main__":
    import argparse
    from utils.adb_helper import ADBHelper

    parser = argparse.ArgumentParser(description="Union Coal Collection Flow")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    adb = ADBHelper()
    result = union_coal_flow(adb, debug=args.debug)
    print(f"\nResult: {'SUCCESS' if result else 'FAILED'}")
