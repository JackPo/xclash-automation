"""
Return to Base View - THE SINGLE recovery function.

Handles ALL recovery scenarios:
1. App not running → start it (force stop first)
2. Resolution wrong → run setup_bluestacks.py
3. Stuck in popup/menu → click back buttons
4. Completely stuck → restart app and retry

This is the ONE source of truth for recovery. Use it everywhere.
"""

import time
import subprocess
from pathlib import Path

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.view_state_detector import detect_view, ViewState
from utils.back_button_matcher import BackButtonMatcher
from utils.adb_helper import ADBHelper

# Click position
BACK_BUTTON_CLICK = (1407, 2055)

# Recovery limits
MAX_BACK_CLICKS = 5
MAX_RECOVERY_ATTEMPTS = 5


def _is_xclash_in_foreground(adb: ADBHelper) -> bool:
    """Check if xclash (com.xman.na.gp) is the foreground app."""
    try:
        result = subprocess.run(
            [adb.ADB_PATH, '-s', adb.device, 'shell',
             'dumpsys window | grep mFocusedApp'],
            capture_output=True, text=True, timeout=5
        )
        return 'com.xman.na.gp' in result.stdout
    except Exception:
        return False


def _run_setup_bluestacks(debug: bool = False):
    """Run BlueStacks setup to ensure resolution is correct."""
    if debug:
        print("    [RETURN] Running BlueStacks setup...")
    try:
        subprocess.run(
            ['python', 'scripts/setup_bluestacks.py'],
            capture_output=True, timeout=30,
            cwd=str(Path(__file__).parent.parent)
        )
    except Exception as e:
        if debug:
            print(f"    [RETURN] BlueStacks setup failed: {e}")
    time.sleep(2)


def _start_app(adb: ADBHelper, debug: bool = False):
    """Force stop and start xclash, wait for load, run setup."""
    if debug:
        print("    [RETURN] Force stopping xclash...")
    subprocess.run(
        [adb.ADB_PATH, '-s', adb.device, 'shell',
         'am force-stop com.xman.na.gp'],
        capture_output=True, timeout=10
    )
    time.sleep(2)

    if debug:
        print("    [RETURN] Starting xclash...")
    subprocess.run(
        [adb.ADB_PATH, '-s', adb.device, 'shell',
         'am start -n com.xman.na.gp/com.q1.ext.Q1UnityActivity'],
        capture_output=True, timeout=10
    )

    if debug:
        print("    [RETURN] Waiting 30s for game to load...")
    time.sleep(30)

    _run_setup_bluestacks(debug)
    time.sleep(3)


def return_to_base_view(adb: ADBHelper, screenshot_helper: WindowsScreenshotHelper = None,
                        debug: bool = False) -> bool:
    """
    THE recovery function. Handles everything:
    - App not running → start it
    - Resolution wrong → setup_bluestacks
    - Stuck in menu → back button clicks
    - Totally stuck → restart and retry

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper (optional, creates one if not provided)
        debug: Print debug info

    Returns:
        True when successfully in TOWN/WORLD (keeps trying until success).
    """
    win = screenshot_helper if screenshot_helper else WindowsScreenshotHelper()
    back_matcher = BackButtonMatcher()

    # STEP 1: Ensure app is running and setup is correct
    if not _is_xclash_in_foreground(adb):
        if debug:
            print("    [RETURN] xclash not in foreground, starting app...")
        _start_app(adb, debug)
    else:
        if debug:
            print("    [RETURN] xclash is running, ensuring resolution...")
        _run_setup_bluestacks(debug)

    # STEP 2: Try to get to TOWN/WORLD (5 attempts)
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
                if debug:
                    print(f"    [RETURN] No back button visible (score={back_score:.3f})")
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

        # Phase 3: Unknown state - try clicking back button location to dismiss popup
        if debug:
            print("    [RETURN] Unknown state, clicking back button location...")
        adb.tap(*BACK_BUTTON_CLICK)
        time.sleep(0.5)

        # Check again
        frame = win.get_screenshot_cv2()
        if frame is not None:
            view_state, view_score = detect_view(frame)
            if view_state in (ViewState.TOWN, ViewState.WORLD):
                if debug:
                    print(f"    [RETURN] Reached {view_state.value} view after popup dismiss")
                return True

            # Also check for back button now - if visible, retry the loop
            back_present, _ = back_matcher.is_present(frame)
            if back_present or view_state == ViewState.CHAT:
                if debug:
                    print(f"    [RETURN] Now in known state ({view_state.value}), retrying...")
                continue  # Go back to phase 1

        if debug:
            print(f"    [RETURN] Still stuck after attempt {attempt + 1}")

    # STEP 3: All attempts failed - restart app and RETRY
    if debug:
        print(f"    [RETURN] All {MAX_RECOVERY_ATTEMPTS} attempts failed, restarting app...")
    _start_app(adb, debug)

    if debug:
        print("    [RETURN] Retrying recovery after restart...")
    return return_to_base_view(adb, win, debug)  # Recursive - keeps trying until success


if __name__ == '__main__':
    # Test
    adb = ADBHelper()
    result = return_to_base_view(adb, debug=True)
    print(f"Result: {result}")
