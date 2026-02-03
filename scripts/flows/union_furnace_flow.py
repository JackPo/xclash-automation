"""
Union Furnace Donation Flow - Donate to Union Furnace upgrade.

Trigger Conditions:
- Runs every 2 hours
- User idle
- No other flows currently running

Sequence:
1. Click Union button (bottom bar)
2. Scroll up to reveal Union Furnace button
3. Click Union Furnace button (template match)
4. Verify Union Furnace header
5. Check if Upgrade tab is active
6. If not, click on Upgrade tab
7. Long press Donation button (3 seconds)
8. Return to base view
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
logger = logging.getLogger("union_furnace_flow")

# Templates directory
TEMPLATES_DIR = "union_furnace"

# Fixed click coordinates (4K resolution)
UNION_BUTTON_CLICK = (3165, 2033)  # Union button on bottom bar
UPGRADE_TAB_CLICK = (1913, 1077)   # Upgrade tab center
DONATION_BUTTON_CLICK = (2259, 1316)  # Donation button center

# Scroll parameters (swipe up to reveal Union Furnace)
SCROLL_START = (1920, 1700)
SCROLL_END = (1920, 1200)
SCROLL_DURATION = 500

# Timing constants
CLICK_DELAY = 0.5
SCREEN_TRANSITION_DELAY = 1.5
LONG_PRESS_DURATION = 3000  # 3 seconds in milliseconds

# Thresholds
THRESHOLD = 0.08


def union_furnace_flow(
    adb: ADBHelper,
    debug: bool = False,
) -> bool:
    """
    Donate to Union Furnace upgrade.

    Args:
        adb: ADBHelper instance
        debug: Enable debug output

    Returns:
        bool: True if successful
    """
    win = WindowsScreenshotHelper()

    if debug:
        print("Union Furnace Flow")
        print("=" * 50)

    # Step 1: Click Union button
    if debug:
        print("Step 1: Clicking Union button...")
    adb.tap(*UNION_BUTTON_CLICK, source="flow:union_furnace:union_button")
    time.sleep(SCREEN_TRANSITION_DELAY)

    # Step 2: Scroll up to reveal Union Furnace
    if debug:
        print("Step 2: Scrolling up...")
    adb.swipe(*SCROLL_START, *SCROLL_END, duration=SCROLL_DURATION)
    time.sleep(1.0)

    # Step 3: Click Union Furnace button
    if debug:
        print("Step 3: Clicking Union Furnace...")
    frame = win.get_screenshot_cv2()

    found, score, pos = match_template(
        frame,
        f"{TEMPLATES_DIR}/union_furnace_button_4k.png",
        threshold=THRESHOLD
    )
    if debug:
        print(f"  Union Furnace button: found={found}, score={score:.4f}, pos={pos}")

    if found and pos:
        adb.tap(*pos, source="flow:union_furnace:furnace_button")
    else:
        # Fallback to fixed position (approximate)
        if debug:
            print("  Using fallback position...")
        adb.tap(1652, 1761, source="flow:union_furnace:furnace_button_fixed")
    time.sleep(SCREEN_TRANSITION_DELAY)

    # Step 4: Verify Union Furnace header
    if debug:
        print("Step 4: Verifying Union Furnace header...")
    frame = win.get_screenshot_cv2()

    found, score, _ = match_template(
        frame,
        f"{TEMPLATES_DIR}/union_furnace_header_4k.png",
        threshold=THRESHOLD
    )
    if debug:
        print(f"  Union Furnace header: found={found}, score={score:.4f}")

    if not found:
        logger.warning("Union Furnace header not found")
        if debug:
            print("  WARNING: Header not found, continuing anyway...")

    # Step 5: Check if Console tab is active (meaning we need to switch to Upgrade)
    if debug:
        print("Step 5: Checking if Console tab is active...")

    console_active, ca_score, _ = match_template(
        frame,
        f"{TEMPLATES_DIR}/console_tab_active_4k.png",
        threshold=THRESHOLD
    )
    if debug:
        print(f"  Console tab active: found={console_active}, score={ca_score:.4f}")

    # Step 6: If Console is active, click on Upgrade tab
    if console_active:
        if debug:
            print("Step 6: Clicking Upgrade tab...")
        adb.tap(*UPGRADE_TAB_CLICK, source="flow:union_furnace:upgrade_tab")
        time.sleep(SCREEN_TRANSITION_DELAY)
        frame = win.get_screenshot_cv2()
    else:
        if debug:
            print("Step 6: Already on Upgrade tab, skipping...")

    # Step 7: Long press Donation button (3 seconds)
    if debug:
        print("Step 7: Long pressing Donation button for 3 seconds...")

    # Find donation button position
    found, score, pos = match_template(
        frame,
        f"{TEMPLATES_DIR}/donation_button_green_4k.png",
        threshold=THRESHOLD
    )
    if debug:
        print(f"  Donation button: found={found}, score={score:.4f}, pos={pos}")

    if found and pos:
        x, y = pos
    else:
        # Fallback to fixed position
        x, y = DONATION_BUTTON_CLICK
        if debug:
            print(f"  Using fallback position: ({x}, {y})")

    # Long press by swiping from same point to same point
    adb.swipe(x, y, x, y, duration=LONG_PRESS_DURATION)
    time.sleep(CLICK_DELAY)

    # Step 8: Return to base view
    if debug:
        print("Step 8: Returning to base view...")
    return_to_base_view(adb, win, debug=False)

    if debug:
        print("=" * 50)
        print("Union Furnace Flow completed!")

    return True


if __name__ == "__main__":
    import argparse
    from utils.adb_helper import ADBHelper

    parser = argparse.ArgumentParser(description="Union Furnace Donation Flow")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    adb = ADBHelper()
    result = union_furnace_flow(adb, debug=args.debug)
    print(f"\nResult: {'SUCCESS' if result else 'FAILED'}")
