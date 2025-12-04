"""
Soldier Training Flow - Handles barracks soldier training automation.

Flow:
1. Yellow bubble (READY) → Click to release soldiers
2. White bubble (PENDING) → Click to open training panel, then:
   - Find target soldier level (default Lv4)
   - If visible → click it
   - If not visible → scroll right until found, then click

Scroll mechanism: Hold-drag left on leftmost visible tile to scroll right.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import time
import cv2

from config import BARRACKS_POSITIONS, SOLDIER_TRAINING_DEFAULT_LEVEL
from utils.barracks_state_matcher import BarrackState, get_matcher as get_barracks_matcher
from utils.soldier_tile_matcher import find_visible_soldiers, find_soldier_level, get_leftmost_visible, get_rightmost_visible
from utils.windows_screenshot_helper import WindowsScreenshotHelper

# Barracks bubble click positions (center of each bubble)
# Bubble is 81x87, so center offset is ~40, 43
BARRACKS_CLICK_OFFSETS = (40, 43)


def get_barrack_click_position(barrack_index):
    """Get the click position for a barrack's bubble."""
    x, y = BARRACKS_POSITIONS[barrack_index]
    return (x + BARRACKS_CLICK_OFFSETS[0], y + BARRACKS_CLICK_OFFSETS[1])


def collect_ready_soldiers(adb, win, debug=False):
    """
    Click all READY (yellow) barracks to collect soldiers.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        debug: Enable debug logging

    Returns:
        int: Number of barracks collected
    """
    frame = win.get_screenshot_cv2()
    matcher = get_barracks_matcher()
    states = matcher.get_all_states(frame)

    collected = 0
    for i, (state, score) in enumerate(states):
        if state == BarrackState.READY:
            click_x, click_y = get_barrack_click_position(i)
            if debug:
                print(f"  Collecting soldiers from barrack {i+1} at ({click_x}, {click_y})")
            adb.tap(click_x, click_y)
            time.sleep(0.5)
            collected += 1

    return collected


def scroll_soldier_panel_left(adb, rightmost_tile_center, debug=False):
    """
    Scroll the soldier panel to the LEFT (to see lower level soldiers) by dragging right.

    Args:
        adb: ADBHelper instance
        rightmost_tile_center: (x, y) center of rightmost visible tile
        debug: Enable debug logging
    """
    start_x, start_y = rightmost_tile_center
    # Drag right by ~300 pixels to scroll left (see lower levels)
    end_x = start_x + 300
    end_y = start_y

    if debug:
        print(f"  Scrolling LEFT: drag from ({start_x}, {start_y}) to ({end_x}, {end_y})")

    # Use swipe with longer duration for smooth scroll
    adb.swipe(start_x, start_y, end_x, end_y, duration=500)
    time.sleep(0.8)  # Wait for scroll animation to settle


def scroll_soldier_panel_right(adb, leftmost_tile_center, debug=False):
    """
    Scroll the soldier panel to the RIGHT (to see higher level soldiers) by dragging left.

    Args:
        adb: ADBHelper instance
        leftmost_tile_center: (x, y) center of leftmost visible tile
        debug: Enable debug logging
    """
    start_x, start_y = leftmost_tile_center
    # Drag left by ~300 pixels to scroll right (see higher levels)
    end_x = start_x - 300
    end_y = start_y

    if debug:
        print(f"  Scrolling RIGHT: drag from ({start_x}, {start_y}) to ({end_x}, {end_y})")

    # Use swipe with longer duration for smooth scroll
    adb.swipe(start_x, start_y, end_x, end_y, duration=500)
    time.sleep(0.8)  # Wait for scroll animation to settle


def find_and_click_soldier_level(adb, win, target_level, max_scrolls=10, debug=False):
    """
    Find and click a specific soldier level tile, scrolling if necessary.

    Soldier layout: Lv3 on LEFT, Lv8 on RIGHT
    - To see lower levels: scroll LEFT (drag right)
    - To see higher levels: scroll RIGHT (drag left)

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        target_level: int (3-8) - soldier level to train
        max_scrolls: Maximum scroll attempts before giving up
        debug: Enable debug logging

    Returns:
        bool: True if successfully clicked the target level
    """
    for scroll_attempt in range(max_scrolls):
        frame = win.get_screenshot_cv2()

        visible = find_visible_soldiers(frame)
        visible_levels = sorted(visible.keys()) if visible else []

        if debug:
            print(f"  Scroll {scroll_attempt}: visible levels = {visible_levels}")

        # Check if target level is visible
        target_info = find_soldier_level(frame, target_level)
        if target_info:
            click_x, click_y = target_info['center']
            if debug:
                print(f"  Found Lv{target_level} at ({click_x}, {click_y}), clicking...")
            adb.tap(click_x, click_y)
            return True

        # Target not visible, determine scroll direction
        if not visible_levels:
            if debug:
                print("  No soldier tiles visible, cannot scroll")
            return False

        min_visible = min(visible_levels)
        max_visible = max(visible_levels)

        if debug:
            print(f"  Target Lv{target_level} not visible. Visible range: Lv{min_visible}-Lv{max_visible}")

        # Determine which direction to scroll
        if target_level < min_visible:
            # Target is lower level than visible - need to scroll LEFT to see lower levels
            # Use rightmost tile to drag right
            rightmost = get_rightmost_visible(frame)
            if rightmost is None:
                if debug:
                    print("  No rightmost tile found")
                return False
            rightmost_level, rightmost_info = rightmost
            if debug:
                print(f"  Need to scroll LEFT (target {target_level} < min visible {min_visible})")
            scroll_soldier_panel_left(adb, rightmost_info['center'], debug=debug)

        elif target_level > max_visible:
            # Target is higher level than visible - need to scroll RIGHT to see higher levels
            # Use leftmost tile to drag left
            leftmost = get_leftmost_visible(frame)
            if leftmost is None:
                if debug:
                    print("  No leftmost tile found")
                return False
            leftmost_level, leftmost_info = leftmost
            if debug:
                print(f"  Need to scroll RIGHT (target {target_level} > max visible {max_visible})")
            scroll_soldier_panel_right(adb, leftmost_info['center'], debug=debug)
        else:
            # Target should be in visible range but wasn't detected
            # This shouldn't happen if templates are good, but try scrolling left as fallback
            if debug:
                print(f"  Target Lv{target_level} in range {min_visible}-{max_visible} but not detected, trying scroll LEFT")
            rightmost = get_rightmost_visible(frame)
            if rightmost:
                scroll_soldier_panel_left(adb, rightmost[1]['center'], debug=debug)
            else:
                return False

    if debug:
        print(f"  Reached max scrolls ({max_scrolls}), target Lv{target_level} not found")
    return False


def train_soldier_at_barrack(adb, win, barrack_index, target_level=None, debug=False):
    """
    Open training panel at a barrack and select a soldier level to train.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        barrack_index: 0-3 for the 4 barracks
        target_level: Soldier level to train (default from config)
        debug: Enable debug logging

    Returns:
        bool: True if successfully started training
    """
    if target_level is None:
        target_level = SOLDIER_TRAINING_DEFAULT_LEVEL

    # Click the barrack to open training panel
    click_x, click_y = get_barrack_click_position(barrack_index)
    if debug:
        print(f"  Opening training panel for barrack {barrack_index+1} at ({click_x}, {click_y})")
    adb.tap(click_x, click_y)
    time.sleep(1.0)  # Wait for panel to open

    # Find and click the target soldier level
    success = find_and_click_soldier_level(adb, win, target_level, debug=debug)

    if success:
        time.sleep(0.5)  # Wait for training to start

        # Check for resource replenishment
        from utils.replenish_all_helper import ReplenishAllHelper
        replenish_helper = ReplenishAllHelper()

        frame = win.get_screenshot_cv2()
        if replenish_helper.find_replenish_button(frame):
            if debug:
                print(f"  Replenish button detected - handling shortage...")

            replenish_helper.handle_replenish_flow(adb, win, debug=debug)

            # Re-click the soldier level after replenishing
            if debug:
                print(f"  Re-clicking Lv{target_level} after replenishment...")

            success = find_and_click_soldier_level(adb, win, target_level, debug=debug)
            if success:
                time.sleep(0.5)
            else:
                if debug:
                    print(f"  Failed to find Lv{target_level} after replenishment")
                return False

        if debug:
            print(f"  Started training Lv{target_level} soldiers at barrack {barrack_index+1}")
    else:
        if debug:
            print(f"  Failed to find Lv{target_level} in training panel")
        # Close the panel by tapping outside (top left corner)
        adb.tap(100, 100)
        time.sleep(0.5)

    return success


def soldier_training_flow(adb, target_level=None, debug=False):
    """
    Main soldier training flow - handles all barracks.

    1. Collect soldiers from all READY (yellow) barracks
    2. Start training at all PENDING (white) barracks

    Args:
        adb: ADBHelper instance
        target_level: Soldier level to train (default from config)
        debug: Enable debug logging

    Returns:
        dict: {'collected': N, 'trained': N} counts
    """
    if target_level is None:
        target_level = SOLDIER_TRAINING_DEFAULT_LEVEL

    win = WindowsScreenshotHelper()
    results = {'collected': 0, 'trained': 0}

    if debug:
        print(f"Soldier Training Flow - target level: Lv{target_level}")

    # Step 1: Collect from READY barracks
    frame = win.get_screenshot_cv2()
    matcher = get_barracks_matcher()
    states = matcher.get_all_states(frame)

    if debug:
        state_str = " ".join([f"B{i+1}:{s.value[0].upper()}" for i, (s, _) in enumerate(states)])
        print(f"  Barracks states: {state_str}")

    for i, (state, score) in enumerate(states):
        if state == BarrackState.READY:
            click_x, click_y = get_barrack_click_position(i)
            if debug:
                print(f"  Collecting from barrack {i+1} (READY)")
            adb.tap(click_x, click_y)
            time.sleep(0.5)
            results['collected'] += 1

    # Step 2: Re-check states after collecting
    if results['collected'] > 0:
        time.sleep(0.5)
        frame = win.get_screenshot_cv2()
        states = matcher.get_all_states(frame)

        if debug:
            state_str = " ".join([f"B{i+1}:{s.value[0].upper()}" for i, (s, _) in enumerate(states)])
            print(f"  States after collecting: {state_str}")

    # Step 3: Train at PENDING barracks
    for i, (state, score) in enumerate(states):
        if state == BarrackState.PENDING:
            if debug:
                print(f"  Training at barrack {i+1} (PENDING)")
            success = train_soldier_at_barrack(adb, win, i, target_level, debug=debug)
            if success:
                results['trained'] += 1

            # Re-check states for next iteration
            time.sleep(0.5)
            frame = win.get_screenshot_cv2()
            states = matcher.get_all_states(frame)

    if debug:
        print(f"  Flow complete: collected={results['collected']}, trained={results['trained']}")

    return results


# For testing
if __name__ == "__main__":
    from utils.adb_helper import ADBHelper

    adb = ADBHelper()
    results = soldier_training_flow(adb, debug=True)
    print(f"\nResults: {results}")
