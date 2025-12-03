"""
Soldier Upgrade Flow - Upgrades soldiers during Arms Race event.

Flow:
1. Open barracks panel (click on pending barracks bubble)
2. Find highest unlocked soldier level using template matching
3. Select soldier level = (highest unlocked - 1)
4. Drag slider all the way to the right (max quantity)
5. Click Upgrade button
6. Verify Promote screen appears
7. Click Promote button

Uses:
- soldier_tile_matcher: Find visible soldier levels and detect locked status
- promote_button_matcher: Verify and click Promote button
- upgrade_button template: Click upgrade button in panel
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import time
import cv2

from config import BARRACKS_POSITIONS
from utils.soldier_tile_matcher import find_visible_soldiers, find_soldier_level
from utils.promote_button_matcher import is_promote_visible, get_promote_click
from utils.windows_screenshot_helper import WindowsScreenshotHelper

# UI positions (4K resolution)
UPGRADE_BUTTON_CLICK = (2351, 1301)  # Center of upgrade button
SLIDER_LEFT = (1490, 1465)   # Left end of slider
SLIDER_RIGHT = (2832, 1465)  # Right end of slider

# Barracks bubble click positions
BARRACKS_CLICK_OFFSETS = (40, 43)

# Soldier levels range
MIN_LEVEL = 3
MAX_LEVEL = 8

# Template matching threshold
MATCH_THRESHOLD = 0.1


def get_barrack_click_position(barrack_index):
    """Get the click position for a barrack's bubble."""
    x, y = BARRACKS_POSITIONS[barrack_index]
    return (x + BARRACKS_CLICK_OFFSETS[0], y + BARRACKS_CLICK_OFFSETS[1])


def find_highest_unlocked_level(frame, debug=False):
    """
    Find the highest unlocked soldier level in the barracks panel.

    Unlocked levels have templates that match well (score < threshold).
    Locked levels have high scores (poor match).

    Args:
        frame: BGR screenshot
        debug: Enable debug output

    Returns:
        int: Highest unlocked level (3-8), or None if none found
    """
    highest = None

    for level in range(MIN_LEVEL, MAX_LEVEL + 1):
        info = find_soldier_level(frame, level)
        if info is not None:
            if debug:
                print(f"  Lv{level}: score={info['score']:.4f} - UNLOCKED")
            highest = level
        else:
            if debug:
                print(f"  Lv{level}: NOT FOUND or locked")

    return highest


def drag_slider_to_max(adb, debug=False):
    """
    Drag the quantity slider all the way to the right (max).

    Args:
        adb: ADBHelper instance
        debug: Enable debug logging
    """
    start_x, start_y = SLIDER_LEFT
    end_x, end_y = SLIDER_RIGHT

    if debug:
        print(f"  Dragging slider from ({start_x}, {start_y}) to ({end_x}, {end_y})")

    adb.swipe(start_x, start_y, end_x, end_y, duration=500)
    time.sleep(0.5)


def soldier_upgrade_flow(adb, barrack_index=0, debug=False):
    """
    Upgrade soldiers at a specific barracks.

    Flow:
    1. Assumes barracks panel is already open
    2. Find highest unlocked level
    3. Select level = highest - 1
    4. Drag slider to max
    5. Click Upgrade
    6. Verify Promote screen and click Promote

    Args:
        adb: ADBHelper instance
        barrack_index: Which barracks (0-3), only used if panel needs to be opened
        debug: Enable debug logging

    Returns:
        bool: True if upgrade succeeded
    """
    win = WindowsScreenshotHelper()

    if debug:
        print("Soldier Upgrade Flow")
        print("=" * 50)

    # Step 1: Take screenshot and find highest unlocked level
    if debug:
        print("Step 1: Finding highest unlocked soldier level...")

    frame = win.get_screenshot_cv2()
    highest = find_highest_unlocked_level(frame, debug=debug)

    if highest is None:
        if debug:
            print("  ERROR: No unlocked soldier levels found")
        return False

    # Step 2: Calculate target level (highest - 1)
    target_level = highest - 1
    if target_level < MIN_LEVEL:
        if debug:
            print(f"  ERROR: Cannot upgrade below Lv{MIN_LEVEL} (highest={highest})")
        return False

    if debug:
        print(f"  Highest unlocked: Lv{highest}")
        print(f"  Target level: Lv{target_level}")

    # Step 3: Click on target level tile
    if debug:
        print(f"Step 2: Clicking Lv{target_level} tile...")

    target_info = find_soldier_level(frame, target_level)
    if target_info is None:
        if debug:
            print(f"  ERROR: Could not find Lv{target_level} tile")
        return False

    click_x, click_y = target_info['center']
    if debug:
        print(f"  Clicking at ({click_x}, {click_y})")

    adb.tap(click_x, click_y)
    time.sleep(0.8)

    # Step 4: Drag slider to max
    if debug:
        print("Step 3: Dragging slider to maximum...")

    drag_slider_to_max(adb, debug=debug)
    time.sleep(0.5)

    # Step 5: Click Upgrade button
    if debug:
        print("Step 4: Clicking Upgrade button...")

    adb.tap(*UPGRADE_BUTTON_CLICK)
    time.sleep(1.0)

    # Step 6: Verify Promote screen appeared
    if debug:
        print("Step 5: Verifying Promote screen...")

    frame = win.get_screenshot_cv2()
    is_promote, score = is_promote_visible(frame, debug=debug)

    if not is_promote:
        if debug:
            print(f"  WARNING: Promote button not detected (score={score:.4f})")
            print("  Attempting to click anyway...")

    # Step 7: Click Promote button
    if debug:
        print("Step 6: Clicking Promote button...")

    promote_click = get_promote_click()
    adb.tap(*promote_click)
    time.sleep(0.5)

    if debug:
        print("=" * 50)
        print("Soldier upgrade flow complete!")

    return True


def upgrade_all_pending_barracks(adb, debug=False):
    """
    Upgrade soldiers at all PENDING barracks.

    Args:
        adb: ADBHelper instance
        debug: Enable debug logging

    Returns:
        int: Number of successful upgrades
    """
    from utils.barracks_state_matcher import BarrackState, get_matcher as get_barracks_matcher

    win = WindowsScreenshotHelper()
    upgrades = 0

    if debug:
        print("Checking all barracks for pending upgrades...")

    frame = win.get_screenshot_cv2()
    matcher = get_barracks_matcher()
    states = matcher.get_all_states(frame)

    for i, (state, score) in enumerate(states):
        if state == BarrackState.PENDING:
            if debug:
                print(f"\nBarracks {i+1}: PENDING - opening panel...")

            # Click to open panel
            click_x, click_y = get_barrack_click_position(i)
            adb.tap(click_x, click_y)
            time.sleep(1.0)

            # Run upgrade flow
            success = soldier_upgrade_flow(adb, barrack_index=i, debug=debug)
            if success:
                upgrades += 1

            # Close panel by tapping outside
            time.sleep(0.5)
            adb.tap(100, 100)
            time.sleep(0.5)

    if debug:
        print(f"\nTotal upgrades completed: {upgrades}")

    return upgrades


# For testing
if __name__ == "__main__":
    from utils.adb_helper import ADBHelper

    adb = ADBHelper()

    print("Testing soldier_upgrade_flow (panel should already be open)...")
    print()

    success = soldier_upgrade_flow(adb, debug=True)
    print(f"\nResult: {'SUCCESS' if success else 'FAILED'}")
