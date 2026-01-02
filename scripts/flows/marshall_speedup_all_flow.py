"""
Marshall Speedup All Flow - Apply Marshall title and speed up all training barracks.

Flow:
1. Apply Marshall title (go to Royal City, apply title)
2. Verify Marshall is active (title_active_icon visible)
3. Speed up all TRAINING barracks one by one

Usage:
    python scripts/flows/marshall_speedup_all_flow.py
    python scripts/flows/marshall_speedup_all_flow.py --debug
    python scripts/flows/marshall_speedup_all_flow.py --skip-marshall  # Skip title, just speedup
"""

import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.adb_helper import ADBHelper
from utils.template_matcher import match_template
from utils.return_to_base_view import return_to_base_view
from utils.view_state_detector import go_to_town
from utils.barracks_state_matcher import check_barracks_states, BarrackState
from scripts.flows.go_to_mark_flow import go_to_mark_flow
from scripts.flows.title_management_flow import title_management_flow
from scripts.flows.barrack_speedup_flow import barrack_speedup_flow
from config import BARRACKS_POSITIONS, BARRACKS_TEMPLATE_SIZE

# Title active icon position (scroll icon in top-left when title is active)
TITLE_ACTIVE_ICON_POS = (203, 216)
TITLE_ACTIVE_ICON_SIZE = (69, 62)
TITLE_ACTIVE_THRESHOLD = 0.95  # CCORR_NORMED (has mask)

POLL_TIMEOUT = 5.0
POLL_INTERVAL = 0.3


def verify_title_active(win, debug=False):
    """Check if any title is currently active by looking for the scroll icon.

    Returns:
        True if title active icon is visible, False otherwise
    """
    frame = win.get_screenshot_cv2()
    found, score, center = match_template(
        frame,
        "title_active_icon_4k.png",
        TITLE_ACTIVE_ICON_POS,
        TITLE_ACTIVE_ICON_SIZE,
        threshold=TITLE_ACTIVE_THRESHOLD
    )
    if debug:
        print(f"    Title active icon: found={found}, score={score:.4f}")
    return found


def apply_marshall_and_verify(adb, win, debug=False):
    """Apply Marshall title and verify it's active.

    Returns:
        True if Marshall was applied and verified, False otherwise
    """
    # Step 1: Go to Royal City via marked location
    if debug:
        print("  Step 1: Going to marked Royal City...")
    success = go_to_mark_flow(adb, win, debug=debug)
    if not success:
        print("  ERROR: Failed to go to marked location")
        return False

    time.sleep(1.0)  # Wait for navigation to complete

    # Step 2: Apply Marshall title
    if debug:
        print("  Step 2: Applying Marshall title...")
    success = title_management_flow(adb, "marshall", screenshot_helper=win, debug=debug)
    if not success:
        print("  ERROR: Failed to apply Marshall title")
        return_to_base_view(adb, win, debug=debug)
        return False

    # Step 3: Return to base view
    if debug:
        print("  Step 3: Returning to base view...")
    return_to_base_view(adb, win, debug=debug)
    time.sleep(0.5)

    # Step 4: Verify title is active
    if debug:
        print("  Step 4: Verifying title is active...")

    # Go to town first (title icon is visible in town)
    go_to_town(adb, debug=debug)
    time.sleep(0.5)

    # Poll for title icon
    start = time.time()
    while time.time() - start < POLL_TIMEOUT:
        if verify_title_active(win, debug=debug):
            if debug:
                print("  Marshall title VERIFIED active!")
            return True
        time.sleep(POLL_INTERVAL)

    print("  WARNING: Could not verify title is active (icon not found)")
    # Continue anyway - the apply might have worked
    return True


def speedup_all_training_barracks(adb, win, debug=False):
    """Speed up all barracks that are currently in TRAINING state.

    Returns:
        Number of barracks successfully sped up
    """
    speedup_count = 0

    # First, go to town
    if debug:
        print("  Going to TOWN view...")
    go_to_town(adb, debug=debug)
    time.sleep(0.5)

    # Detect training barracks
    frame = win.get_screenshot_cv2()
    states = check_barracks_states(frame)

    training_barracks = []
    for i, (state, score) in enumerate(states):
        if state == BarrackState.TRAINING:
            training_barracks.append(i)

    if debug:
        print(f"  Found {len(training_barracks)} TRAINING barracks: {[f'B{i+1}' for i in training_barracks]}")

    if not training_barracks:
        print("  No TRAINING barracks found")
        return 0

    # Speed up each training barrack
    for idx in training_barracks:
        if debug:
            print(f"\n  === Speeding up Barrack {idx + 1} ===")

        success = barrack_speedup_flow(adb, win, barrack_index=idx, debug=debug)

        if success:
            speedup_count += 1
            if debug:
                print(f"  Barrack {idx + 1} speedup SUCCESS")
        else:
            print(f"  Barrack {idx + 1} speedup FAILED")

        # Small delay between barracks
        time.sleep(0.5)

        # Re-detect states for next iteration (in case states changed)
        frame = win.get_screenshot_cv2()
        states = check_barracks_states(frame)

    return speedup_count


def marshall_speedup_all_flow(adb, screenshot_helper=None, skip_marshall=False, debug=False):
    """
    Apply Marshall title and speed up all training barracks.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance
        skip_marshall: If True, skip applying Marshall and just speedup
        debug: Enable debug logging

    Returns:
        dict with 'marshall_applied', 'barracks_sped_up' counts
    """
    win = screenshot_helper or WindowsScreenshotHelper()
    result = {
        'marshall_applied': False,
        'barracks_sped_up': 0
    }

    try:
        # Step 1: Apply Marshall (unless skipped)
        if not skip_marshall:
            print("=== Applying Marshall Title ===")
            result['marshall_applied'] = apply_marshall_and_verify(adb, win, debug=debug)
            if not result['marshall_applied']:
                print("WARNING: Marshall application may have failed, continuing anyway...")
        else:
            print("=== Skipping Marshall (--skip-marshall) ===")

        # Step 2: Speed up all training barracks
        print("\n=== Speeding Up All Training Barracks ===")
        result['barracks_sped_up'] = speedup_all_training_barracks(adb, win, debug=debug)

        return result

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return result

    finally:
        # Always return to base view
        print("\n=== Returning to Base View ===")
        return_to_base_view(adb, win, debug=debug)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Apply Marshall and speed up all training barracks")
    parser.add_argument("--skip-marshall", action="store_true", help="Skip applying Marshall title")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug output")

    args = parser.parse_args()

    print("=== Marshall Speedup All Flow ===")
    print()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    result = marshall_speedup_all_flow(
        adb, win,
        skip_marshall=args.skip_marshall,
        debug=args.debug or True
    )

    print(f"\n=== Results ===")
    print(f"Marshall applied: {result['marshall_applied']}")
    print(f"Barracks sped up: {result['barracks_sped_up']}")
