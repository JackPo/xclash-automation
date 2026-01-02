"""
Barrack Speedup Flow - Speed up barrack training for Arms Race points.

Flow (VERIFY-THEN-CLICK pattern):
1. Detect TRAINING barrack (stopwatch icon)
2. Click barrack bubble
3. POLL/VERIFY soldier_training_header at FIXED position
4. VERIFY speedup_button at FIXED position
5. Click speedup button
6. POLL for speed_up_header (vertical search, fixed X)
7. FIND quick_speedup_button (vertical search, fixed X)
8. Click Quick Speedup
9. VERIFY confirm_button at FIXED position
10. Click Confirm
11. Return to base view

Usage:
    python scripts/flows/barrack_speedup_flow.py
    python scripts/flows/barrack_speedup_flow.py --barrack 2
"""

import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.adb_helper import ADBHelper
from utils.template_matcher import match_template
from utils.return_to_base_view import return_to_base_view
from utils.barracks_state_matcher import check_barracks_states, BarrackState
from config import BARRACKS_POSITIONS, BARRACKS_TEMPLATE_SIZE

# Fixed positions (top-left, size)
SOLDIER_TRAINING_HEADER_POS = (1678, 315)
SOLDIER_TRAINING_HEADER_SIZE = (480, 54)

SPEEDUP_BUTTON_POS = (1728, 1397)
SPEEDUP_BUTTON_SIZE = (372, 132)
SPEEDUP_BUTTON_CLICK = (1914, 1463)

# Vertical search regions (fixed X, search full Y)
SPEED_UP_HEADER_SEARCH_REGION = (1758, 0, 334, 400)  # x, y, w, h - top portion of screen
QUICK_SPEEDUP_SEARCH_REGION = (1728, 1700, 372, 400)  # x, y, w, h - bottom portion

CONFIRM_BUTTON_POS = (1957, 1359)
CONFIRM_BUTTON_SIZE = (368, 134)
CONFIRM_BUTTON_CLICK = (2141, 1426)

THRESHOLD = 0.1
POLL_TIMEOUT = 3.0
POLL_INTERVAL = 0.3


def _poll_for_template_fixed(win, template_name, pos, size, timeout=POLL_TIMEOUT, debug=False):
    """Poll until template matches at fixed position or timeout."""
    start = time.time()
    last_score = 1.0
    while time.time() - start < timeout:
        frame = win.get_screenshot_cv2()
        found, score, center = match_template(frame, template_name, pos, size, threshold=THRESHOLD)
        last_score = score
        if found:
            if debug:
                print(f"    VERIFIED {template_name}: score={score:.4f}")
            return True, score, center, frame
        time.sleep(POLL_INTERVAL)
    if debug:
        print(f"    TIMEOUT {template_name}: last_score={last_score:.4f}")
    return False, last_score, None, None


def _poll_for_template_region(win, template_name, search_region, timeout=POLL_TIMEOUT, debug=False):
    """Poll until template matches in search region or timeout."""
    start = time.time()
    last_score = 1.0
    while time.time() - start < timeout:
        frame = win.get_screenshot_cv2()
        found, score, pos = match_template(frame, template_name, search_region=search_region, threshold=THRESHOLD)
        last_score = score
        if found:
            if debug:
                print(f"    FOUND {template_name}: score={score:.4f}, pos={pos}")
            return True, score, pos, frame
        time.sleep(POLL_INTERVAL)
    if debug:
        print(f"    TIMEOUT {template_name}: last_score={last_score:.4f}")
    return False, last_score, None, None


def find_training_barrack(frame, debug=False):
    """Find the first barrack that is in TRAINING state.

    Returns:
        (barrack_index, click_position) or (None, None) if none found
    """
    states = check_barracks_states(frame)

    for i, (state, score) in enumerate(states):
        if state == BarrackState.TRAINING:
            # Calculate click position (center of bubble)
            pos = BARRACKS_POSITIONS[i]
            w, h = BARRACKS_TEMPLATE_SIZE
            click_pos = (pos[0] + w // 2, pos[1] + h // 2)
            if debug:
                print(f"    Found TRAINING barrack {i+1} at {click_pos}")
            return i, click_pos

    if debug:
        print("    No TRAINING barrack found")
    return None, None


def barrack_speedup_flow(adb, screenshot_helper=None, barrack_index=None, debug=False):
    """
    Speed up a barrack that is currently training.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance
        barrack_index: Specific barrack to speedup (0-3), or None to find first TRAINING
        debug: Enable debug logging

    Returns:
        True if speedup succeeded, False otherwise
    """
    win = screenshot_helper or WindowsScreenshotHelper()

    try:
        # Step 1: Find TRAINING barrack
        if debug:
            print("  Step 1: Finding TRAINING barrack...")
        frame = win.get_screenshot_cv2()

        if barrack_index is not None:
            # Use specified barrack
            pos = BARRACKS_POSITIONS[barrack_index]
            w, h = BARRACKS_TEMPLATE_SIZE
            click_pos = (pos[0] + w // 2, pos[1] + h // 2)
            if debug:
                print(f"    Using specified barrack {barrack_index + 1} at {click_pos}")
        else:
            # Find first TRAINING barrack
            idx, click_pos = find_training_barrack(frame, debug=debug)
            if idx is None:
                print("  ERROR: No TRAINING barrack found")
                return False

        # Step 2: Click barrack bubble
        if debug:
            print(f"  Step 2: Clicking barrack at {click_pos}...")
        adb.tap(*click_pos)

        # Step 3: POLL/VERIFY soldier_training_header at FIXED position
        if debug:
            print("  Step 3: Verifying Soldier Training header...")
        found, score, _, frame = _poll_for_template_fixed(
            win, "soldier_training_header_4k.png",
            SOLDIER_TRAINING_HEADER_POS, SOLDIER_TRAINING_HEADER_SIZE,
            debug=debug
        )
        if not found:
            print("  ERROR: Soldier Training header not found")
            return False

        # Step 4: POLL/VERIFY speedup_button at FIXED position (needs time to render)
        if debug:
            print("  Step 4: Polling for Speedup button...")
        found, score, _, frame = _poll_for_template_fixed(
            win, "speedup_button_4k.png",
            SPEEDUP_BUTTON_POS, SPEEDUP_BUTTON_SIZE,
            debug=debug
        )
        if not found:
            print(f"  ERROR: Speedup button not found (score={score:.4f})")
            return False

        # Step 5: Click speedup button
        if debug:
            print(f"  Step 5: Clicking Speedup button at {SPEEDUP_BUTTON_CLICK}...")
        adb.tap(*SPEEDUP_BUTTON_CLICK)

        # Step 6: POLL for speed_up_header (vertical search)
        if debug:
            print("  Step 6: Polling for Speed Up header...")
        found, score, pos, frame = _poll_for_template_region(
            win, "speed_up_header_4k.png",
            SPEED_UP_HEADER_SEARCH_REGION,
            debug=debug
        )
        if not found:
            print("  ERROR: Speed Up header not found")
            return False

        # Step 7: FIND quick_speedup_button (vertical search)
        if debug:
            print("  Step 7: Finding Quick Speedup button...")
        found, score, quick_pos = match_template(
            frame, "quick_speedup_button_4k.png",
            search_region=QUICK_SPEEDUP_SEARCH_REGION,
            threshold=THRESHOLD
        )
        if not found:
            print(f"  ERROR: Quick Speedup button not found (score={score:.4f})")
            return False
        if debug:
            print(f"    FOUND quick_speedup_button: score={score:.4f}, pos={quick_pos}")

        # Step 8: Click Quick Speedup
        if debug:
            print(f"  Step 8: Clicking Quick Speedup at {quick_pos}...")
        adb.tap(*quick_pos)
        time.sleep(0.5)

        # Step 9: VERIFY confirm_button at FIXED position
        if debug:
            print("  Step 9: Verifying Confirm button...")
        found, score, _, frame = _poll_for_template_fixed(
            win, "confirm_button_4k.png",
            CONFIRM_BUTTON_POS, CONFIRM_BUTTON_SIZE,
            debug=debug
        )
        if not found:
            print(f"  ERROR: Confirm button not found (score={score:.4f})")
            return False

        # Step 10: Click Confirm
        if debug:
            print(f"  Step 10: Clicking Confirm at {CONFIRM_BUTTON_CLICK}...")
        adb.tap(*CONFIRM_BUTTON_CLICK)
        time.sleep(1.0)

        if debug:
            print("  Speedup complete!")
        return True

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Step 11: Return to base view
        if debug:
            print("  Step 11: Returning to base view...")
        return_to_base_view(adb, win, debug=debug)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Speed up barrack training")
    parser.add_argument("--barrack", "-b", type=int, choices=[1, 2, 3, 4],
                        help="Specific barrack to speedup (1-4)")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug output")

    args = parser.parse_args()

    print("=== Barrack Speedup Flow ===")
    print()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    barrack_idx = (args.barrack - 1) if args.barrack else None

    result = barrack_speedup_flow(adb, win, barrack_index=barrack_idx, debug=args.debug or True)
    print(f"\nResult: {'SUCCESS' if result else 'FAILED'}")
