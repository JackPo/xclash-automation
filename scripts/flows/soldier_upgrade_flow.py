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

from config import BARRACKS_POSITIONS, BARRACKS_CLICK_OFFSETS
from utils.soldier_tile_matcher import find_visible_soldiers, find_soldier_level
from utils.promote_button_matcher import is_promote_visible, get_promote_click
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.soldier_training_header_matcher import is_panel_open
from utils.debug_screenshot import save_debug_screenshot
from utils.return_to_base_view import return_to_base_view
from utils.soldier_panel_slider import drag_slider_to_max

# UI positions (4K resolution)
UPGRADE_BUTTON_CLICK = (2351, 1301)  # Center of upgrade button

# BARRACKS_CLICK_OFFSETS imported from config

# Soldier levels range
MIN_LEVEL = 3
MAX_LEVEL = 8

# Template matching threshold
MATCH_THRESHOLD = 0.1

# Panel dismiss position (dark area outside panel)
DISMISS_TAP = (500, 500)


def get_barrack_click_position(barrack_index):
    """Get the click position for a barrack's bubble."""
    x, y = BARRACKS_POSITIONS[barrack_index]
    return (x + BARRACKS_CLICK_OFFSETS[0], y + BARRACKS_CLICK_OFFSETS[1])


def find_highest_unlocked_level(frame, adb, debug=False):
    """
    Find the highest unlocked soldier level using visible tile detection.

    Args:
        frame: BGR screenshot
        adb: ADBHelper instance (for scrolling if needed)
        debug: Enable debug output

    Returns:
        tuple: (highest_level, visible_tiles_dict) or (None, None) if none found
    """
    visible = find_visible_soldiers(frame, debug_timing=debug)

    if not visible:
        if debug:
            print("  ERROR: No soldier tiles detected")
        return None, None

    highest = max(visible.keys())

    if debug:
        levels = sorted(visible.keys())
        print(f"  Visible tiles: {levels}")
        for level in levels:
            print(f"    Lv{level}: x={visible[level]['x']}, score={visible[level]['score']:.6f}")
        print(f"  Highest unlocked: Lv{highest}")

    return highest, visible


def soldier_upgrade_flow(adb, barrack_index=0, debug=False, detect_only=False, scroll_and_select=False):
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
        detect_only: If True, only detect tiles and report highest unlocked, then exit
        scroll_and_select: If True, scroll to find target level, select it, then exit

    Returns:
        bool: True if upgrade succeeded, or highest_level (int) if detect_only=True
    """
    win = WindowsScreenshotHelper()

    if debug:
        print("Soldier Upgrade Flow")
        print("=" * 50)

    try:
        flow_start = time.time()

        # Step 0: Verify panel is open
        if debug:
            print("Step 0: Verifying soldier training panel is open...")

        step_start = time.time()
        frame = win.get_screenshot_cv2()
        if debug:
            print(f"  Screenshot took: {(time.time() - step_start)*1000:.1f}ms")

        step_start = time.time()
        panel_open, score = is_panel_open(frame, debug=debug)
        if debug:
            print(f"  Panel check took: {(time.time() - step_start)*1000:.1f}ms")

        if not panel_open:
            if debug:
                print(f"  ERROR: Soldier training panel not detected (score={score:.6f})")
            save_debug_screenshot(frame, "upgrade", "FAIL_step0_panel_not_open")
            return False

        # Wait for tiles to fully render
        time.sleep(0.5)

        # Step 1: Take fresh screenshot and find highest unlocked level
        if debug:
            print("Step 1: Finding highest unlocked soldier level...")

        step_start = time.time()
        frame = win.get_screenshot_cv2()
        if debug:
            print(f"  Screenshot took: {(time.time() - step_start)*1000:.1f}ms")

        step_start = time.time()
        highest, visible_tiles = find_highest_unlocked_level(frame, adb, debug=debug)
        if debug:
            print(f"  find_highest_unlocked_level took: {(time.time() - step_start)*1000:.1f}ms")

        if highest is None:
            if debug:
                print("  ERROR: No unlocked soldier levels found")
            save_debug_screenshot(frame, "upgrade", "FAIL_step1_no_tiles")
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

        # If detect_only mode, stop here and return highest level
        if detect_only:
            print(f"\n=== DETECTION RESULT ===")
            print(f"Highest unlocked level: Lv{highest}")
            return highest

        # Get the center position of the highest level tile for scrolling
        # Reuse visible_tiles from find_highest_unlocked_level (no second scan needed)
        highest_tile_center = visible_tiles[highest]['center']
        scroll_start_x, scroll_start_y = highest_tile_center

        if debug:
            print(f"  Using Lv{highest} tile center ({scroll_start_x}, {scroll_start_y}) as scroll anchor")

        # Step 3: Find target level tile (scroll if needed)
        if debug:
            print(f"Step 2: Finding Lv{target_level} tile...")

        step_start = time.time()
        target_info = find_soldier_level(frame, target_level)
        if debug:
            print(f"  find_soldier_level took: {(time.time() - step_start)*1000:.1f}ms")

        # If not visible, swipe from the highest tile center to the right
        max_scrolls = 3
        scroll_count = 0
        while target_info is None and scroll_count < max_scrolls:
            if debug:
                print(f"  Lv{target_level} not visible, swiping right from tile center... (attempt {scroll_count + 1}/{max_scrolls})")

            # Swipe FROM the detected tile TO THE RIGHT to reveal left content
            scroll_end_x = scroll_start_x + 233  # Swipe 233 pixels to the right (reduced by 2/3 from original 700)
            adb.swipe(scroll_start_x, scroll_start_y, scroll_end_x, scroll_start_y, duration=500)
            time.sleep(0.5)

            # Re-check
            frame = win.get_screenshot_cv2()
            target_info = find_soldier_level(frame, target_level)
            scroll_count += 1

        if target_info is None:
            if debug:
                print(f"  ERROR: Could not find Lv{target_level} tile after {scroll_count} scrolls")
            save_debug_screenshot(frame, "upgrade", f"FAIL_step2_no_lv{target_level}")
            return False

        if debug:
            print(f"  Found Lv{target_level} at ({target_info['x']}, {target_info['y']}) score={target_info['score']:.6f}")

        # Step 4: Click on target level tile
        if debug:
            print(f"Step 3: Clicking Lv{target_level} tile...")

        click_x, click_y = target_info['center']
        if debug:
            print(f"  Clicking at ({click_x}, {click_y})")

        adb.tap(click_x, click_y)
        time.sleep(0.8)

        # If scroll_and_select mode, stop here
        if scroll_and_select:
            print(f"\n=== SCROLL AND SELECT RESULT ===")
            print(f"Selected Lv{target_level} tile at ({click_x}, {click_y})")
            return True

        # Step 5: Drag slider to max
        if debug:
            print("Step 3: Dragging slider to maximum...")

        frame = win.get_screenshot_cv2()
        if not drag_slider_to_max(adb, frame, debug=debug):
            if debug:
                print("  WARNING: Could not find slider, continuing anyway...")
        time.sleep(0.5)

        # Step 5: Click Upgrade button
        if debug:
            print("Step 4: Clicking Upgrade button...")

        adb.tap(*UPGRADE_BUTTON_CLICK)
        time.sleep(1.0)

        # Step 5a: Check for resource replenishment
        if debug:
            print("Step 4a: Checking for resource replenishment...")

        from utils.replenish_all_helper import ReplenishAllHelper
        replenish_helper = ReplenishAllHelper()

        frame = win.get_screenshot_cv2()
        if replenish_helper.find_replenish_button(frame):
            if debug:
                print("  Replenish button detected - handling shortage...")

            replenish_helper.handle_replenish_flow(adb, win, debug=debug)

            # Re-click Upgrade button after replenishing
            if debug:
                print("  Re-clicking Upgrade button after replenishment...")

            adb.tap(*UPGRADE_BUTTON_CLICK)
            time.sleep(1.0)
        else:
            if debug:
                print("  No replenish needed - continuing...")

        # Step 6: Verify Promote screen appeared
        if debug:
            print("Step 5: Verifying Promote screen...")

        frame = win.get_screenshot_cv2()
        is_promote, score = is_promote_visible(frame, debug=debug)

        if not is_promote:
            if debug:
                print(f"  WARNING: Promote button not detected (score={score:.4f})")
                print("  Attempting to click anyway...")
            save_debug_screenshot(frame, "upgrade", "WARN_no_promote_button")

        # Step 7: Click Promote button
        if debug:
            print("Step 6: Clicking Promote button...")

        promote_click = get_promote_click()
        adb.tap(*promote_click)
        time.sleep(0.5)

        if debug:
            total_time = (time.time() - flow_start) * 1000
            print("=" * 50)
            print(f"Soldier upgrade flow complete! Total time: {total_time:.1f}ms")

        return True

    except Exception as e:
        if debug:
            print(f"EXCEPTION: {type(e).__name__}: {e}")
        return False

    finally:
        # ALWAYS return to base view (unless detect_only mode where we didn't open it)
        if not detect_only:
            if debug:
                print("Returning to base view...")
            return_to_base_view(adb, win, debug=debug)


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

            # Panel closes automatically after upgrade - no need to click

    if debug:
        print(f"\nTotal upgrades completed: {upgrades}")

    return upgrades


# For testing
if __name__ == "__main__":
    import argparse
    from utils.adb_helper import ADBHelper

    parser = argparse.ArgumentParser(description="Soldier upgrade flow")
    parser.add_argument('--detect-only', action='store_true', help='Only detect tiles, do not click anything')
    parser.add_argument('--scroll-and-select', action='store_true', help='Scroll to find target level and select it, then stop')
    args = parser.parse_args()

    adb = ADBHelper()

    if args.detect_only:
        print("Detection-only mode (panel should already be open)...")
        print()
        highest = soldier_upgrade_flow(adb, debug=True, detect_only=True)
        if highest:
            print(f"\n=== MAXIMUM UNLOCKED: Lv{highest} ===")
        else:
            print("\nFailed to detect tiles")
    elif args.scroll_and_select:
        print("Scroll-and-select mode (panel should already be open)...")
        print()
        success = soldier_upgrade_flow(adb, debug=True, scroll_and_select=True)
        print(f"\nResult: {'SUCCESS' if success else 'FAILED'}")
    else:
        print("Testing soldier_upgrade_flow (panel should already be open)...")
        print()
        success = soldier_upgrade_flow(adb, debug=True)
        print(f"\nResult: {'SUCCESS' if success else 'FAILED'}")
