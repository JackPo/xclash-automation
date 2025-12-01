"""
Return to Base View - Robust recovery to get back to TOWN or WORLD view.

Strategy:
1. Click back button repeatedly while it's visible
2. Check if we're in TOWN or WORLD view
3. If stuck in unknown state, click corn harvest location to dismiss popups
4. After 3 failed attempts, kill and restart xclash
"""

import time
import subprocess
from pathlib import Path

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.view_state_detector import detect_view, go_to_town, ViewState
from utils.back_button_matcher import BackButtonMatcher
from utils.adb_helper import ADBHelper

# Click positions
BACK_BUTTON_CLICK = (1407, 2055)
CORN_HARVEST_CLICK = (1932, 1297)  # Center of screen, dismisses most popups

MAX_BACK_CLICKS = 5
MAX_RECOVERY_ATTEMPTS = 5


def return_to_base_view(adb: ADBHelper, screenshot_helper: WindowsScreenshotHelper = None,
                        debug: bool = False) -> bool:
    """
    Return to TOWN or WORLD view from any state.

    Strategy:
    1. Click back button while visible (max 5 clicks)
    2. Check if in known view (TOWN/WORLD)
    3. If stuck, click corn harvest location to dismiss popups
    4. After 5 failed recovery attempts, kill and restart app

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper (optional, creates one if not provided)
        debug: Print debug info

    Returns:
        True if successfully returned to TOWN/WORLD, False if had to restart app
    """
    win = screenshot_helper if screenshot_helper else WindowsScreenshotHelper()
    back_matcher = BackButtonMatcher()

    for attempt in range(MAX_RECOVERY_ATTEMPTS):
        if debug:
            print(f"    [RETURN] Attempt {attempt + 1}/{MAX_RECOVERY_ATTEMPTS}")

        # Phase 1: Click back button while visible
        back_clicks = 0
        while back_clicks < MAX_BACK_CLICKS:
            time.sleep(0.5)
            frame = win.get_screenshot_cv2()
            if frame is None:
                if debug:
                    print("    [RETURN] Failed to get screenshot")
                break

            # Check if we're already in a good state
            view_state, view_score = detect_view(frame)
            if view_state in (ViewState.TOWN, ViewState.WORLD):
                if debug:
                    print(f"    [RETURN] Reached {view_state.value} view (score={view_score:.3f})")
                return True

            # Check for back button
            back_present, back_score = back_matcher.is_present(frame)
            if back_present:
                if debug:
                    print(f"    [RETURN] Back button visible (score={back_score:.3f}), clicking...")
                adb.tap(*BACK_BUTTON_CLICK)
                back_clicks += 1
            else:
                # No back button visible, break to next phase
                if debug:
                    print(f"    [RETURN] No back button (score={back_score:.3f})")
                break

        # Phase 2: Check view state again
        time.sleep(0.5)
        frame = win.get_screenshot_cv2()
        if frame is not None:
            view_state, view_score = detect_view(frame)
            if view_state in (ViewState.TOWN, ViewState.WORLD):
                if debug:
                    print(f"    [RETURN] Reached {view_state.value} view")
                return True

        # Phase 3: Unknown state - try clicking corn harvest location to dismiss popup
        if debug:
            print(f"    [RETURN] Unknown state, clicking center to dismiss popup...")
        adb.tap(*CORN_HARVEST_CLICK)
        time.sleep(0.5)

        # Check again
        frame = win.get_screenshot_cv2()
        if frame is not None:
            view_state, view_score = detect_view(frame)
            if view_state in (ViewState.TOWN, ViewState.WORLD):
                if debug:
                    print(f"    [RETURN] Reached {view_state.value} view after popup dismiss")
                return True

            # Also check for back button now
            back_present, _ = back_matcher.is_present(frame)
            if back_present or view_state == ViewState.CHAT:
                if debug:
                    print(f"    [RETURN] Now in known state ({view_state.value}), retrying...")
                continue  # Go back to phase 1

        if debug:
            print(f"    [RETURN] Still stuck after attempt {attempt + 1}")

    # All attempts failed - kill and restart app
    if debug:
        print(f"    [RETURN] All {MAX_RECOVERY_ATTEMPTS} attempts failed, restarting app...")

    _restart_xclash(adb, win, debug)
    return False


def _restart_xclash(adb: ADBHelper, win: WindowsScreenshotHelper, debug: bool = False):
    """Kill xclash and restart it."""
    if debug:
        print("    [RETURN] Killing xclash...")

    # Force stop the app
    subprocess.run(
        [adb.ADB_PATH, '-s', adb.device, 'shell',
         'am force-stop com.xman.na.gp'],
        capture_output=True, timeout=10
    )

    time.sleep(2)

    if debug:
        print("    [RETURN] Starting xclash...")

    # Start the app
    subprocess.run(
        [adb.ADB_PATH, '-s', adb.device, 'shell',
         'am start -n com.xman.na.gp/com.q1.ext.Q1UnityActivity'],
        capture_output=True, timeout=10
    )

    # Wait for app to load
    if debug:
        print("    [RETURN] Waiting 30s for game to load...")
    time.sleep(30)

    # Run BlueStacks setup
    if debug:
        print("    [RETURN] Running BlueStacks setup...")
    try:
        subprocess.run(
            ['python', 'setup_bluestacks.py'],
            capture_output=True, timeout=30,
            cwd=str(Path(__file__).parent.parent)
        )
    except Exception as e:
        if debug:
            print(f"    [RETURN] BlueStacks setup failed: {e}")

    time.sleep(5)

    # Navigate to town
    if debug:
        print("    [RETURN] Navigating to TOWN view...")
    go_to_town(adb, debug=False)

    if debug:
        print("    [RETURN] App restart complete")


if __name__ == '__main__':
    # Test
    adb = ADBHelper()
    result = return_to_base_view(adb, debug=True)
    print(f"Result: {result}")
