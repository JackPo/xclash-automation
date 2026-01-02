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

import cv2

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.view_state_detector import detect_view, ViewState
from utils.back_button_matcher import BackButtonMatcher
from utils.adb_helper import ADBHelper
import numpy as np

# Target resolution
TARGET_RESOLUTION = "3840x2160"

# Import from centralized config
from config import BACK_BUTTON_CLICK

# Click positions
MAP_DESELECT_CLICK = (500, 1000)  # Click on empty map area to deselect troops
CENTER_SCREEN_CLICK = (1920, 1600)  # Click center-bottom for "Tap to Close" popups

# Template paths for state detection
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"
FORM_TEAM_TEMPLATE = TEMPLATE_DIR / "form_team_button_4k.png"
RESOURCE_BAR_TEMPLATE = TEMPLATE_DIR / "resource_bar_4k.png"

# Recovery limits
MAX_BACK_CLICKS = 5
MAX_RECOVERY_ATTEMPTS = 30  # Attempts before restarting game

# Track consecutive restarts (module-level state, for logging only - never gives up)
_consecutive_restarts = 0

# Cached templates
_form_team_template = None
_resource_bar_template = None


def _load_templates():
    """Load detection templates once."""
    global _form_team_template, _resource_bar_template
    if _form_team_template is None and FORM_TEAM_TEMPLATE.exists():
        _form_team_template = cv2.imread(str(FORM_TEAM_TEMPLATE))
    if _resource_bar_template is None and RESOURCE_BAR_TEMPLATE.exists():
        _resource_bar_template = cv2.imread(str(RESOURCE_BAR_TEMPLATE))


def _detect_troop_selected(frame) -> tuple[bool, float]:
    """Detect if a troop is selected (Form Team button visible)."""
    _load_templates()
    if _form_team_template is None or frame is None:
        return False, 1.0

    # Search in bottom portion of screen
    search_region = frame[1900:2160, 1000:1700]
    result = cv2.matchTemplate(search_region, _form_team_template, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)
    return min_val < 0.1, min_val


def _detect_resource_bar(frame) -> tuple[bool, float]:
    """Detect resource bar at top (indicates TOWN/WORLD view even if button hidden)."""
    _load_templates()
    if _resource_bar_template is None or frame is None:
        return False, 1.0

    # Search in top portion of screen
    search_region = frame[0:100, 0:600]
    result = cv2.matchTemplate(search_region, _resource_bar_template, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)
    return min_val < 0.1, min_val


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


def _get_current_resolution(adb: ADBHelper) -> str:
    """Get current screen resolution from ADB."""
    try:
        result = subprocess.run(
            [adb.ADB_PATH, '-s', adb.device, 'shell', 'wm', 'size'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            # Parse "Physical size: 1920x1080" or "Override size: 3840x2160"
            for line in result.stdout.split('\n'):
                if 'size:' in line.lower():
                    parts = line.split(':')
                    if len(parts) > 1:
                        res = parts[-1].strip()
                        if 'x' in res:
                            return res
    except Exception:
        pass
    return None


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
    """Force stop and start xclash, poll for UI load, dismiss startup popups."""
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

    # Poll for game UI to load (detect shaded or normal button)
    from utils.shaded_button_helper import is_button_shaded, dismiss_popups, BUTTON_X, BUTTON_Y, BUTTON_W, BUTTON_H
    from utils.windows_screenshot_helper import WindowsScreenshotHelper
    win = WindowsScreenshotHelper()

    if debug:
        print("    [RETURN] Polling for game UI to load...")

    max_wait = 120  # Max 2 minutes
    poll_interval = 3
    waited = 0

    while waited < max_wait:
        time.sleep(poll_interval)
        waited += poll_interval

        frame = win.get_screenshot_cv2()
        if frame is None:
            continue

        # Check if shaded button is visible (game loaded with popups)
        shaded, shaded_score = is_button_shaded(frame)
        if shaded:
            if debug:
                print(f"    [RETURN] Game loaded (shaded button detected, score={shaded_score:.4f}) after {waited}s")
            break

        # Check if normal world/town button is visible (game loaded, no popups)
        view_state, view_score = detect_view(frame)
        if view_state in (ViewState.TOWN, ViewState.WORLD):
            if debug:
                print(f"    [RETURN] Game loaded ({view_state.value} detected) after {waited}s")
            _run_setup_bluestacks(debug)
            return  # Already at base view, no popups

        if debug and waited % 15 == 0:
            print(f"    [RETURN] Still waiting for game UI... ({waited}s)")

    # Run setup after game loaded
    _run_setup_bluestacks(debug)
    time.sleep(2)

    # Dismiss startup popups by clicking shaded button until clear
    if debug:
        print("    [RETURN] Dismissing startup popups...")
    dismiss_popups(adb, win, debug=debug)


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
    global _consecutive_restarts  # Track restart count across recursive calls

    win = screenshot_helper if screenshot_helper else WindowsScreenshotHelper()
    back_matcher = BackButtonMatcher()

    # STEP 1: Ensure app is running and setup is correct
    if not _is_xclash_in_foreground(adb):
        if debug:
            print("    [RETURN] xclash not in foreground, starting app...")
        _start_app(adb, debug)
    else:
        # Only run setup if resolution is not already correct
        current_res = _get_current_resolution(adb)
        if current_res != TARGET_RESOLUTION:
            if debug:
                print(f"    [RETURN] Resolution is {current_res}, expected {TARGET_RESOLUTION}, running setup...")
            _run_setup_bluestacks(debug)
        else:
            if debug:
                print(f"    [RETURN] xclash is running, resolution is {current_res} (correct)")

    # STEP 1b: Check for shaded button (indicates popups blocking)
    from utils.shaded_button_helper import is_button_shaded, dismiss_popups, BUTTON_CLICK

    frame = win.get_screenshot_cv2()
    if frame is not None:
        shaded, shaded_score = is_button_shaded(frame)
        if shaded:
            if debug:
                print(f"    [RETURN] Shaded button detected (score={shaded_score:.4f}) - dismissing popups...")
            dismiss_popups(adb, win, max_clicks=10, debug=debug)

    # STEP 2: Try to get to TOWN/WORLD (5 attempts)
    for attempt in range(MAX_RECOVERY_ATTEMPTS):
        if debug:
            print(f"    [RETURN] Attempt {attempt + 1}/{MAX_RECOVERY_ATTEMPTS}")

        # Phase 1: Click back button while visible
        back_clicks = 0
        while back_clicks < MAX_BACK_CLICKS:
            time.sleep(0.5)  # Give UI time to settle before checking
            frame = win.get_screenshot_cv2()
            if frame is None:
                if debug:
                    print("    [RETURN] Failed to get screenshot")
                break

            # Check if we're already in a good state
            view_state, view_score = detect_view(frame)
            if view_state in (ViewState.TOWN, ViewState.WORLD):
                _consecutive_restarts = 0  # Reset on success
                if debug:
                    print(f"    [RETURN] Reached {view_state.value} view (score={view_score:.3f})")
                return True

            # Check for back button using search
            back_present, back_score, back_pos = back_matcher.find(frame)
            if back_present and back_pos:
                if debug:
                    print(f"    [RETURN] Back button found at {back_pos} (score={back_score:.3f}), clicking...")
                adb.tap(*back_pos)
                back_clicks += 1
            else:
                if debug:
                    print(f"    [RETURN] No back button visible (score={back_score:.3f})")
                break

        # Phase 2: Check view state again
        time.sleep(0.5)  # Give UI time to settle
        frame = win.get_screenshot_cv2()
        if frame is not None:
            view_state, view_score = detect_view(frame)
            if view_state in (ViewState.TOWN, ViewState.WORLD):
                _consecutive_restarts = 0  # Reset on success
                if debug:
                    print(f"    [RETURN] Reached {view_state.value} view")
                return True

        # Phase 3: Smart state detection - figure out what state we're in
        frame = win.get_screenshot_cv2()
        if frame is not None:
            # If we can match ground/grass with high confidence, we KNOW which view we're in
            # Ground = TOWN, Grass = WORLD - just return True, we're already there!
            from utils.safe_grass_matcher import find_safe_grass
            from utils.safe_ground_matcher import find_safe_ground

            # Quick ground check (TOWN indicator)
            ground_pos = find_safe_ground(frame, debug=debug)
            if ground_pos:
                _consecutive_restarts = 0
                if debug:
                    print(f"    [RETURN] SUCCESS: GROUND detected = we're in TOWN view")
                return True

            # Quick grass check (WORLD indicator)
            grass_pos = find_safe_grass(frame, debug=debug)
            if grass_pos:
                _consecutive_restarts = 0
                if debug:
                    print(f"    [RETURN] SUCCESS: GRASS detected = we're in WORLD view")
                return True

            # Detect other states
            troop_selected, troop_score = _detect_troop_selected(frame)
            resource_bar, resource_score = _detect_resource_bar(frame)
            back_present, back_score, back_pos = back_matcher.find(frame)

            # Save debug screenshot with state info
            debug_dir = Path(__file__).parent.parent / "screenshots" / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            debug_path = debug_dir / f"return_unknown_state_a{attempt+1}_{timestamp}.png"
            cv2.imwrite(str(debug_path), frame)

            if debug:
                print(f"    [RETURN] State detection results:")
                print(f"      - View: UNKNOWN (score={view_score:.3f})")
                print(f"      - Troop selected: {troop_selected} (score={troop_score:.3f})")
                print(f"      - Resource bar: {resource_bar} (score={resource_score:.3f})")
                print(f"      - Back button: {back_present} (score={back_score:.3f})")
                print(f"    [RETURN] Saved debug screenshot: {debug_path.name}")

            # Decision logic based on detected state
            if troop_selected:
                # Troop is selected - click map to deselect
                if debug:
                    print("    [RETURN] TROOP SELECTED state detected - clicking map to deselect...")
                adb.tap(*MAP_DESELECT_CLICK)
                time.sleep(1.5)

                # Check if we're now in TOWN/WORLD
                frame = win.get_screenshot_cv2()
                if frame is not None:
                    view_state, view_score = detect_view(frame)
                    if view_state in (ViewState.TOWN, ViewState.WORLD):
                        _consecutive_restarts = 0
                        if debug:
                            print(f"    [RETURN] SUCCESS: Reached {view_state.value} after troop deselect")
                        return True
                continue  # Retry detection

            elif resource_bar and not back_present:
                # Resource bar visible but no World button - might be popup or panned view
                if debug:
                    print("    [RETURN] RESOURCE BAR visible but World button hidden - trying center click...")
                adb.tap(*CENTER_SCREEN_CLICK)
                time.sleep(1.5)

                frame = win.get_screenshot_cv2()
                if frame is not None:
                    view_state, view_score = detect_view(frame)
                    if view_state in (ViewState.TOWN, ViewState.WORLD):
                        _consecutive_restarts = 0
                        if debug:
                            print(f"    [RETURN] SUCCESS: Reached {view_state.value} after center click")
                        return True
                continue

            elif back_present and back_pos:
                # Back button visible - we're in some menu/dialog
                if debug:
                    print(f"    [RETURN] BACK BUTTON at {back_pos} - clicking to exit dialog...")
                adb.tap(*back_pos)
                time.sleep(1.0)
                continue

            else:
                # Unknown state - try grass/ground click first (dismisses floating panels)
                # Uses find_safe_grass/find_safe_ground which call match_template internally
                from utils.safe_grass_matcher import find_safe_grass
                from utils.safe_ground_matcher import find_safe_ground

                if debug:
                    print(f"    [RETURN] UNKNOWN state - checking grass/ground...")

                # Try grass first (WORLD indicator)
                grass_pos = find_safe_grass(frame, debug=debug)
                if grass_pos:
                    if debug:
                        print(f"    [RETURN] Grass detected (WORLD view) - clicking at {grass_pos}")
                    adb.tap(*grass_pos)
                    time.sleep(1.5)
                    # Check if we're now in TOWN/WORLD
                    frame = win.get_screenshot_cv2()
                    if frame is not None:
                        view_state, view_score = detect_view(frame)
                        if view_state in (ViewState.TOWN, ViewState.WORLD):
                            _consecutive_restarts = 0
                            if debug:
                                print(f"    [RETURN] SUCCESS: Reached {view_state.value} after grass click")
                            return True
                    continue  # Retry from top

                # Try ground (TOWN indicator)
                ground_pos = find_safe_ground(frame, debug=debug)
                if ground_pos:
                    if debug:
                        print(f"    [RETURN] Ground detected (TOWN view) - clicking at {ground_pos}")
                    adb.tap(*ground_pos)
                    time.sleep(1.5)
                    # Check if we're now in TOWN/WORLD
                    frame = win.get_screenshot_cv2()
                    if frame is not None:
                        view_state, view_score = detect_view(frame)
                        if view_state in (ViewState.TOWN, ViewState.WORLD):
                            _consecutive_restarts = 0
                            if debug:
                                print(f"    [RETURN] SUCCESS: Reached {view_state.value} after ground click")
                            return True
                    continue  # Retry from top

                # Neither grass nor ground found - search for back button again
                back_found, back_score2, back_pos2 = back_matcher.find(frame)
                if back_found and back_pos2:
                    if debug:
                        print(f"    [RETURN] Found back button at {back_pos2} (score={back_score2:.3f})")
                    adb.tap(*back_pos2)
                    time.sleep(1.0)
                else:
                    if debug:
                        print("    [RETURN] No back button found, skipping...")
                    time.sleep(0.5)

                # Check again
                frame = win.get_screenshot_cv2()
                if frame is not None:
                    view_state, view_score = detect_view(frame)
                    if view_state in (ViewState.TOWN, ViewState.WORLD):
                        _consecutive_restarts = 0
                        if debug:
                            print(f"    [RETURN] SUCCESS: Reached {view_state.value} after back click")
                        return True

                # Try center click for "Tap to Close" popups
                if debug:
                    print("    [RETURN] Trying center screen click...")
                adb.tap(*CENTER_SCREEN_CLICK)
                time.sleep(1.5)

                frame = win.get_screenshot_cv2()
                if frame is not None:
                    view_state, view_score = detect_view(frame)
                    if view_state in (ViewState.TOWN, ViewState.WORLD):
                        _consecutive_restarts = 0
                        if debug:
                            print(f"    [RETURN] SUCCESS: Reached {view_state.value} after center click")
                        return True

        if debug:
            print(f"    [RETURN] Still stuck after attempt {attempt + 1}")

    # STEP 3: All attempts failed - restart app and RETRY (never give up)
    _consecutive_restarts += 1

    # CRITICAL: Save debug screenshot with detailed marker BEFORE restart
    frame = win.get_screenshot_cv2()
    if frame is not None:
        debug_dir = Path(__file__).parent.parent / "screenshots" / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        debug_path = debug_dir / f"RESTART_TRIGGER_{timestamp}.png"
        cv2.imwrite(str(debug_path), frame)
        # Also detect view state for the marker
        view_state, view_score = detect_view(frame)
        back_present, back_score, _ = back_matcher.find(frame)
        print(f"    [RETURN] *** RESTART #{_consecutive_restarts} - will keep trying ***")
        print(f"    [RETURN] Screenshot saved: {debug_path.name}")
        print(f"    [RETURN] View state at restart: {view_state.value} (score={view_score:.3f})")
        print(f"    [RETURN] Back button present: {back_present} (score={back_score:.3f})")
        print(f"    [RETURN] All {MAX_RECOVERY_ATTEMPTS} attempts exhausted")
    else:
        print(f"    [RETURN] *** RESTART #{_consecutive_restarts} - will keep trying (no screenshot) ***")
        print(f"    [RETURN] All {MAX_RECOVERY_ATTEMPTS} attempts exhausted")

    if debug:
        print(f"    [RETURN] Restarting app...")
    _start_app(adb, debug)

    if debug:
        print("    [RETURN] Retrying recovery after restart...")
    return return_to_base_view(adb, win, debug)  # Recursive - keeps trying until success


if __name__ == '__main__':
    # Test
    adb = ADBHelper()
    result = return_to_base_view(adb, debug=True)
    print(f"Result: {result}")
