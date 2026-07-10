"""
Return to Base View - THE SINGLE recovery function.

Handles ALL recovery scenarios:
1. App not running → start it (force stop first)
2. Resolution wrong → run setup_bluestacks.py
3. Stuck in popup/menu → click back buttons
4. Completely stuck → restart app and retry

This is the ONE source of truth for recovery. Use it everywhere.
"""

from __future__ import annotations

import logging
import time
import subprocess
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import numpy.typing as npt

from utils.view_state_detector import detect_view, ViewState
from utils.back_button_matcher import BackButtonMatcher
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.adb_helper import ADBHelper
from utils.send_zoom import send_zoom
from utils.template_matcher import match_template

# Import from centralized config
from config import (
    BACK_BUTTON_CLICK,
    EXPECTED_RESOLUTION,
    FORM_TEAM_THRESHOLD,
    RESOURCE_BAR_THRESHOLD,
)

# Click positions
MAP_DESELECT_CLICK = (500, 1000)  # Click on empty map area to deselect troops
CENTER_SCREEN_CLICK = (1920, 1950)  # Click center-bottom for "Tap to Close" popups (below popup area)
UNION_DONATE_DIALOG_REGION = (1973, 1470, 369, 130)
UNION_DONATE_DIALOG_THRESHOLD = 0.05

# Template paths for state detection
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"
FORM_TEAM_TEMPLATE = TEMPLATE_DIR / "form_team_button_4k.png"
RESOURCE_BAR_TEMPLATE = TEMPLATE_DIR / "resource_bar_4k.png"

# Recovery limits
MAX_BACK_CLICKS = 5
MAX_RECOVERY_ATTEMPTS = 30  # Attempts before restarting game
MAX_ZOOM_OUT_ATTEMPTS = 3   # Max zoom-outs when grass visible but town button not (was 15 - a blind 7.5s burst that spammed the user's map; zoom can't close a modal panel anyway)

# Track consecutive restarts (module-level state, for logging only - never gives up)
_consecutive_restarts = 0

# Cached templates
_form_team_template: npt.NDArray[Any] | None = None
_resource_bar_template: npt.NDArray[Any] | None = None


def _load_templates() -> None:
    global _form_team_template, _resource_bar_template
    if _form_team_template is None and FORM_TEAM_TEMPLATE.exists():
        _form_team_template = cv2.imread(str(FORM_TEAM_TEMPLATE))
    if _resource_bar_template is None and RESOURCE_BAR_TEMPLATE.exists():
        _resource_bar_template = cv2.imread(str(RESOURCE_BAR_TEMPLATE))


def _detect_troop_selected(frame: npt.NDArray[Any] | None) -> tuple[bool, float]:
    _load_templates()
    if _form_team_template is None or frame is None:
        return False, 1.0

    search_region = frame[1900:2160, 1000:1700]
    result = cv2.matchTemplate(search_region, _form_team_template, cv2.TM_SQDIFF_NORMED)
    min_val: float
    min_val, _, _, _ = cv2.minMaxLoc(result)
    return min_val < FORM_TEAM_THRESHOLD, min_val


def _detect_resource_bar(frame: npt.NDArray[Any] | None) -> tuple[bool, float]:
    _load_templates()
    if _resource_bar_template is None or frame is None:
        return False, 1.0

    search_region = frame[0:100, 0:600]
    result = cv2.matchTemplate(search_region, _resource_bar_template, cv2.TM_SQDIFF_NORMED)
    min_val: float
    min_val, _, _, _ = cv2.minMaxLoc(result)
    return min_val < RESOURCE_BAR_THRESHOLD, min_val


def _detect_union_donate_dialog(frame: npt.NDArray[Any] | None) -> tuple[bool, float]:
    """
    Detect Union Technology donate modal by matching active/inactive donate button states.

    This modal can hide/disable normal back button detection and trap recovery in UNKNOWN.
    """
    if frame is None:
        return False, 1.0

    active_found, active_score, _ = match_template(
        frame,
        "tech_donate_200_button_active_4k.png",
        search_region=UNION_DONATE_DIALOG_REGION,
        threshold=UNION_DONATE_DIALOG_THRESHOLD,
    )
    inactive_found, inactive_score, _ = match_template(
        frame,
        "tech_donate_200_button_inactive_4k.png",
        search_region=UNION_DONATE_DIALOG_REGION,
        threshold=UNION_DONATE_DIALOG_THRESHOLD,
    )

    if active_found or inactive_found:
        return True, min(active_score, inactive_score)
    return False, 1.0


def _is_xclash_in_foreground(adb: ADBHelper) -> bool:
    try:
        device = adb.device
        if device is None:
            return False
        result = subprocess.run(
            [adb.ADB_PATH, '-s', device, 'shell',
             'dumpsys window | grep mFocusedApp'],
            capture_output=True, text=True, timeout=5
        )
        return 'com.xman.na.gp' in result.stdout
    except Exception:
        return False


def _get_current_resolution(adb: ADBHelper) -> str | None:
    try:
        device = adb.device
        if device is None:
            return None
        result = subprocess.run(
            [adb.ADB_PATH, '-s', device, 'shell', 'wm', 'size'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
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


def _run_setup_bluestacks(debug: bool = False) -> None:
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


def _start_app(adb: ADBHelper, debug: bool = False) -> None:
    device = adb.device
    if device is None:
        if debug:
            print("    [RETURN] No device found, cannot start app")
        return
    if debug:
        print("    [RETURN] Force stopping xclash...")
    subprocess.run(
        [adb.ADB_PATH, '-s', device, 'shell',
         'am force-stop com.xman.na.gp'],
        capture_output=True, timeout=10
    )
    time.sleep(2)

    # Kill other apps (Play Store, Game Center, etc.)
    if debug:
        print("    [RETURN] Killing other apps...")
    killed = adb.kill_other_apps()
    if debug and killed:
        print(f"    [RETURN] Killed: {', '.join(killed)}")

    if debug:
        print("    [RETURN] Starting xclash...")
    subprocess.run(
        [adb.ADB_PATH, '-s', device, 'shell',
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
    poll_interval = 0.75  # Fast polling - screenshot is only ~9ms now
    waited = 0.0

    while waited < max_wait:
        time.sleep(poll_interval)
        waited += poll_interval

        frame = win.get_screenshot_cv2()
        if frame is None:
            continue  # type: ignore[unreachable]

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


def _save_rtb_debug(frame: npt.NDArray[Any] | None, step: str, extra: str = "") -> None:
    """Save debug screenshot for return_to_base diagnostics."""
    if frame is None:
        return
    try:
        from config import DEBUG_RETURN_TO_BASE
        if not DEBUG_RETURN_TO_BASE:
            return
        from datetime import datetime
        debug_dir = Path(__file__).parent.parent / "screenshots" / "debug" / "return_to_base"
        debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        label = f"{step}_{extra}" if extra else step
        filepath = debug_dir / f"{timestamp}_{label}.png"
        cv2.imwrite(str(filepath), frame)
    except Exception:
        pass  # Never fail the main flow due to screenshot issues


def _try_zoom_out_recovery(win: WindowsScreenshotHelper, debug: bool = False) -> bool:
    """
    Zoom out until TOWN/WORLD button becomes visible.

    Used when grass/ground is visible but town button is not (zoomed in too much).
    Returns True if recovery succeeded, False if max attempts reached.
    """
    for i in range(MAX_ZOOM_OUT_ATTEMPTS):
        # Yield to the user BEFORE every zoom (not just once at entry). Without
        # this, a recovery that started while idle would keep zooming the user's
        # map the instant they start playing again.
        try:
            from config import RETURN_ACTIVE_ABORT_SECONDS
            from utils.user_idle_tracker import get_user_idle_seconds
            if get_user_idle_seconds() < RETURN_ACTIVE_ABORT_SECONDS:
                if debug:
                    print("    [RETURN] Zoom-out recovery aborted - user active")
                return False
        except Exception:
            pass

        if debug:
            print(f"    [RETURN] Zoom out attempt {i+1}/{MAX_ZOOM_OUT_ATTEMPTS}")

        send_zoom('out')
        time.sleep(0.5)  # Wait for zoom animation

        frame = win.get_screenshot_cv2()
        _save_rtb_debug(frame, f"ZOOM_OUT_attempt{i+1}")

        if frame is not None:
            state, score = detect_view(frame)
            if state in (ViewState.TOWN, ViewState.WORLD):
                _save_rtb_debug(frame, f"ZOOM_OUT_SUCCESS_{state.value}")
                if debug:
                    print(f"    [RETURN] Zoom out recovery succeeded: {state.value} (score={score:.3f})")
                return True

    if debug:
        print(f"    [RETURN] Zoom out recovery FAILED after {MAX_ZOOM_OUT_ATTEMPTS} attempts")
    return False


def _ensure_target_view(adb: ADBHelper, win: WindowsScreenshotHelper, current: ViewState,
                        target: ViewState | None, debug: bool = False) -> bool:
    """
    Ensure we're at the target view. If current != target, toggle.

    Args:
        current: Current ViewState (must be TOWN or WORLD)
        target: Target ViewState (TOWN, WORLD, or None for any)

    Returns:
        True if at target (or target is None), False if toggle failed
    """
    if target is None:
        return True

    if current == target:
        return True

    # Need to toggle
    if debug:
        print(f"    [RETURN] At {current.value}, need {target.value} - toggling")

    from config import TOGGLE_BUTTON_CLICK
    adb.tap(*TOGGLE_BUTTON_CLICK, source="rtb:toggle_to_target")

    # Poll until view changes (max 1.5s)
    for poll in range(5):
        time.sleep(0.3)
        frame = win.get_screenshot_cv2()
        if frame is None:
            continue
        poll_state, _ = detect_view(frame)
        if poll_state == target:
            if debug:
                print(f"    [RETURN] Toggled to {target.value}")
            return True

    if debug:
        print(f"    [RETURN] Failed to toggle to {target.value}")
    return False


def return_to_base_view(adb: ADBHelper, screenshot_helper: WindowsScreenshotHelper | None = None,
                        debug: bool = False, respect_idle: bool = True,
                        target: ViewState | None = None,
                        deadline: float | None = None) -> bool:
    """
    Return to TOWN or WORLD view. THE unified navigation/recovery function.

    Args:
        adb: ADBHelper instance
        screenshot_helper: Optional WindowsScreenshotHelper (created if not provided)
        debug: Print debug info
        respect_idle: If True (default), skip recovery if user is active (idle < threshold).
                     Set to False for startup recovery or critical situations.
        target: Optional specific view to navigate to (ViewState.TOWN or ViewState.WORLD).
                If None, returns True when reaching either TOWN or WORLD.
                If specified, will toggle to that view after reaching base view.
        deadline: Optional time.time() wall-clock cutoff. When set and exceeded, the
                slow recovery path bails out (returns False) instead of force-restarting
                the app and recursing forever. Used by callers (e.g. soldier_upgrade_flow)
                to bound cleanup time so a single flow can't freeze the daemon loop when
                the emulator window is occluded and recovery is futile. The next daemon
                cycle retries recovery once the window is capturable again.

    Returns:
        True if successfully reached target view (or any base view if target=None)
    """
    global _consecutive_restarts  # Track restart count across recursive calls

    win = screenshot_helper if screenshot_helper else WindowsScreenshotHelper()
    back_matcher = BackButtonMatcher()

    _fight_strikes = [0]  # calls that saw RECENT user activity (cumulative)

    def _should_abort_for_user_activity(context: str) -> bool:
        """
        Return True when manual user activity should preempt automation.

        Two detectors:
        - Instant: input within RETURN_ACTIVE_ABORT_SECONDS (respect_idle only).
        - Cumulative FIGHT detection: if the user showed activity (<8s idle)
          during 3+ separate checks in this call, they OWN the screen - abort
          even for respect_idle=False callers (yielding beats a tug-of-war;
          observed 130s of toggle/center taps against an active user whose
          click cadence kept instant-idle jittering above the threshold).
        """
        try:
            from utils.user_idle_tracker import get_user_idle_seconds
            from config import RETURN_ACTIVE_ABORT_SECONDS
            idle_secs = get_user_idle_seconds()
            if idle_secs < 8.0:
                _fight_strikes[0] += 1
                if _fight_strikes[0] >= 3:
                    if debug:
                        print(f"    [RETURN] FIGHT DETECTED during {context} ({_fight_strikes[0]} strikes) - yielding to user")
                    logging.getLogger("return_to_base").info(
                        "RECOVERY YIELDED during %s: user active across %d checks - they own the screen",
                        context, _fight_strikes[0])
                    return True
            if respect_idle and idle_secs < RETURN_ACTIVE_ABORT_SECONDS:
                if debug:
                    print(
                        f"    [RETURN] User is active during {context} "
                        f"(idle={idle_secs:.1f}s < {RETURN_ACTIVE_ABORT_SECONDS}s), stopping recovery"
                    )
                return True  # Assume user is handling it
        except Exception:
            pass  # If idle check fails, proceed with recovery
        return False

    # Check idle FIRST - if user is active, don't interfere with clicking
    if _should_abort_for_user_activity("initial check"):
        return True

    # =========================================================================
    # FAST PATH: Try simple navigation FIRST (no subprocess calls)
    # This handles the common case: we're in a menu, just need to click back
    # =========================================================================
    from utils.ui_helpers import click_back

    # Per-call tracking of back buttons that don't dismiss when tapped, so we
    # escalate instead of ping-ponging fast_back <-> toggle-escape forever
    # (observed ~10s of flailing on the Marshal title panel, whose bottom-left
    # arrow matches a back template but the panel wants "Tap to close").
    _stuck_back_fails: dict[tuple[str, int, int], int] = {}
    _ignored_backs: set[tuple[str, int, int]] = set()

    for fast_attempt in range(5):
        if _should_abort_for_user_activity("fast path"):
            return True

        frame = win.get_screenshot_cv2()
        if frame is None:
            break

        # Check if already at TOWN/WORLD
        view_state, view_score = detect_view(frame)
        if view_state in (ViewState.TOWN, ViewState.WORLD):
            _consecutive_restarts = 0
            if debug:
                print(f"    [RETURN] Fast path: At {view_state.value} (attempt {fast_attempt + 1})")
            if _ensure_target_view(adb, win, view_state, target, debug):
                return True
            continue  # Toggle failed, retry

        # Check for known modal that needs blank-space dismissal before back buttons are visible
        donate_popup, donate_score = _detect_union_donate_dialog(frame)
        if donate_popup:
            if debug:
                print(
                    f"    [RETURN] Fast path: Union donate popup detected "
                    f"(score={donate_score:.3f}), clicking center to close"
                )
            if _should_abort_for_user_activity("fast path donate popup close"):
                return True
            adb.tap(*CENTER_SCREEN_CLICK, source="rtb:center_screen_donate_popup")
            time.sleep(0.4)
            continue

        # Check for back button
        back_present, back_score, back_pos, matched_template = back_matcher.find(frame)
        if back_present and back_pos:
            _back_key = (str(matched_template), back_pos[0] // 50, back_pos[1] // 50)
            if _back_key in _ignored_backs:
                # This exact button already failed twice (tap + toggle + tap-to-
                # close). Stop treating it as a back button this call - fall
                # through to the other fast-path handlers / full recovery.
                back_present = False
        if back_present and back_pos:
            if debug:
                print(f"    [RETURN] Fast path: Back button at {back_pos}, clicking (attempt {fast_attempt + 1})")
            if _should_abort_for_user_activity("fast path before back tap"):
                return True
            adb.tap(*back_pos, source="rtb:fast_back")

            # Poll until back button gone or view changed (max 1.5s)
            progressed = False
            for poll in range(5):
                time.sleep(0.3)
                poll_frame = win.get_screenshot_cv2()
                if poll_frame is None:
                    continue

                # Check if reached TOWN/WORLD
                poll_state, _ = detect_view(poll_frame)
                if poll_state in (ViewState.TOWN, ViewState.WORLD):
                    _consecutive_restarts = 0
                    if debug:
                        print(f"    [RETURN] Fast path: Reached {poll_state.value} after {(poll+1)*0.3:.1f}s")
                    if _ensure_target_view(adb, win, poll_state, target, debug):
                        return True
                    progressed = True
                    break  # At base view but wrong target, continue outer loop

                # Check if that specific back button is gone
                if matched_template and not back_matcher.is_template_present(poll_frame, matched_template, near_pos=back_pos, tolerance=30):
                    if debug:
                        print(f"    [RETURN] Fast path: Back button dismissed after {(poll+1)*0.3:.1f}s")
                    progressed = True
                    break

            # The back button never dismissed -> tapping it isn't closing anything
            # (false match on a panel's title area, or a panel that dismisses via
            # "Tap to close" like the Marshal title panel). Escalation ladder,
            # tracked per button so we NEVER ping-pong on the same dead button:
            #   fail 1: toggle-escape (closes most panels)
            #   fail 2: "Tap to close" - tap the dim background above the panel
            #   fail 3: ignore this button for the rest of this call
            if not progressed:
                fails = _stuck_back_fails.get(_back_key, 0) + 1
                _stuck_back_fails[_back_key] = fails
                if fails == 1:
                    from config import TOGGLE_BUTTON_CLICK
                    if debug:
                        print(f"    [RETURN] Back '{matched_template}' at {back_pos} won't dismiss - toggle-escape")
                    adb.tap(*TOGGLE_BUTTON_CLICK, source="rtb:toggle_escape_stuck_back")
                    time.sleep(0.6)
                elif fails == 2:
                    if debug:
                        print(f"    [RETURN] Back '{matched_template}' still stuck - trying tap-to-close (dim top)")
                    adb.tap(1920, 140, source="rtb:tap_to_close_stuck_back")
                    time.sleep(0.8)
                else:
                    _ignored_backs.add(_back_key)
                    if debug:
                        print(f"    [RETURN] Back '{matched_template}' at {back_pos} is dead - ignoring it this call")
            continue

        # Check for CHAT state
        if view_state == ViewState.CHAT:
            if debug:
                print(f"    [RETURN] Fast path: In CHAT, clicking back (attempt {fast_attempt + 1})")
            if _should_abort_for_user_activity("fast path before chat back"):
                return True
            click_back(adb)

            # Poll until view changes (max 1.5s)
            for poll in range(5):
                time.sleep(0.3)
                poll_frame = win.get_screenshot_cv2()
                if poll_frame is None:
                    continue
                poll_state, _ = detect_view(poll_frame)
                if poll_state in (ViewState.TOWN, ViewState.WORLD):
                    _consecutive_restarts = 0
                    if debug:
                        print(f"    [RETURN] Fast path: Exited CHAT to {poll_state.value} after {(poll+1)*0.3:.1f}s")
                    if _ensure_target_view(adb, win, poll_state, target, debug):
                        return True
                    break  # At base view but wrong target, continue outer loop
                if poll_state != ViewState.CHAT:
                    break  # State changed, continue outer loop
            continue

        # UNKNOWN state with no back button - fast path can't handle, break to full recovery
        if debug:
            print(f"    [RETURN] Fast path: UNKNOWN state, no back button - escalating to full recovery")
        break

    # Check one more time after fast path
    frame = win.get_screenshot_cv2()
    if frame is not None:
        view_state, _ = detect_view(frame)
        if view_state in (ViewState.TOWN, ViewState.WORLD):
            _consecutive_restarts = 0
            if debug:
                print(f"    [RETURN] Fast path succeeded: {view_state.value}")
            if _ensure_target_view(adb, win, view_state, target, debug):
                return True

    # =========================================================================
    # SLOW PATH: Full recovery with subprocess checks (app/resolution/restart)
    # Only runs if fast path failed
    # =========================================================================
    if debug:
        print("    [RETURN] Fast path failed, starting full recovery...")

    # ALWAYS capture entry screenshot for debugging
    entry_frame = win.get_screenshot_cv2()
    _save_rtb_debug(entry_frame, "STEP0_ENTRY")

    # STEP 1: Ensure app is running and setup is correct
    if not _is_xclash_in_foreground(adb):
        if debug:
            print("    [RETURN] xclash not in foreground, starting app...")
        _start_app(adb, debug)
    else:
        # Only run setup if resolution is not already correct
        current_res = _get_current_resolution(adb)
        if current_res != EXPECTED_RESOLUTION:
            if debug:
                print(f"    [RETURN] Resolution is {current_res}, expected {EXPECTED_RESOLUTION}, running setup...")
            _run_setup_bluestacks(debug)
        else:
            if debug:
                print(f"    [RETURN] xclash is running, resolution is {current_res} (correct)")

    # STEP 1b: Check for shaded button (indicates popups blocking)
    from utils.shaded_button_helper import is_button_shaded, dismiss_popups, BUTTON_CLICK

    frame = win.get_screenshot_cv2()
    _save_rtb_debug(frame, "STEP1_after_foreground_check")
    if frame is not None:
        shaded, shaded_score = is_button_shaded(frame)
        if shaded:
            _save_rtb_debug(frame, "STEP1_shaded_detected", f"score{shaded_score:.3f}")
            if debug:
                print(f"    [RETURN] Shaded button detected (score={shaded_score:.4f}) - dismissing popups...")
            dismiss_popups(adb, win, max_clicks=10, debug=debug)
            frame = win.get_screenshot_cv2()
            _save_rtb_debug(frame, "STEP1_after_dismiss_popups")

    # STEP 2: Try to get to TOWN/WORLD (full recovery attempts)
    for attempt in range(MAX_RECOVERY_ATTEMPTS):

        if _should_abort_for_user_activity("full recovery attempt"):
            return True

        if deadline is not None and time.time() > deadline:
            print(f"    [RETURN] Deadline exceeded during recovery (attempt {attempt + 1}) - "
                  f"aborting, will retry next cycle")
            return False

        if debug:
            print(f"    [RETURN] Attempt {attempt + 1}/{MAX_RECOVERY_ATTEMPTS}")

        # Phase 0: Modal escape via the bottom Town/World toggle button.
        # A building/tile info panel (e.g. an ally's Union Center) leaves
        # detect_view=UNKNOWN and is NOT closed by the back-button / grass / zoom
        # steps below - recovery used to flail on it for up to 30 attempts, clicking
        # the castle and the union center over and over. The toggle button reliably
        # navigates home AND dismisses such panels, so try it FIRST every attempt.
        frame = win.get_screenshot_cv2()
        if frame is not None:
            vs0, _vs0_score = detect_view(frame)
            if vs0 not in (ViewState.TOWN, ViewState.WORLD):
                from config import TOGGLE_BUTTON_CLICK
                if _should_abort_for_user_activity("modal toggle escape"):
                    return True
                adb.tap(*TOGGLE_BUTTON_CLICK, source="rtb:toggle_escape")
                time.sleep(0.8)
                frame = win.get_screenshot_cv2()
                if frame is not None:
                    vs0b, _vs0b_score = detect_view(frame)
                    if vs0b in (ViewState.TOWN, ViewState.WORLD):
                        _consecutive_restarts = 0
                        _save_rtb_debug(frame, f"SUCCESS_toggle_escape_{vs0b.value}")
                        if debug:
                            print(f"    [RETURN] Phase 0: toggle-button escape -> {vs0b.value}")
                        return True

        # Phase 1: Click back button while visible
        back_clicks = 0
        while back_clicks < MAX_BACK_CLICKS:
            if _should_abort_for_user_activity("full recovery back loop"):
                return True

            frame = win.get_screenshot_cv2()
            if frame is None:
                if debug:  # type: ignore[unreachable]
                    print("    [RETURN] Failed to get screenshot")
                break

            _save_rtb_debug(frame, f"STEP2_attempt{attempt+1}_backclick{back_clicks}")

            # Check if we're already in a good state
            view_state, view_score = detect_view(frame)
            if view_state in (ViewState.TOWN, ViewState.WORLD):
                _consecutive_restarts = 0  # Reset on success
                _save_rtb_debug(frame, f"SUCCESS_view_{view_state.value}", f"score{view_score:.3f}")
                if debug:
                    print(f"    [RETURN] Reached {view_state.value} view (score={view_score:.3f})")
                return True

            # Check for back button using search
            back_present, back_score, back_pos, matched_template = back_matcher.find(frame)
            if back_present and back_pos and matched_template:
                _save_rtb_debug(frame, f"STEP2_back_found_a{attempt+1}", f"pos{back_pos[0]}_{back_pos[1]}")
                if debug:
                    print(f"    [RETURN] Back button found at {back_pos} (score={back_score:.3f}, template={matched_template}), clicking...")
                if _should_abort_for_user_activity("full recovery before back tap"):
                    return True
                adb.tap(*back_pos, source="rtb:back_button")
                back_clicks += 1

                # Poll for THAT SPECIFIC template at THAT position to be gone
                for poll in range(5):  # Up to 1.5s (5 x 0.3s)
                    time.sleep(0.3)
                    poll_frame = win.get_screenshot_cv2()
                    if poll_frame is None:
                        continue  # type: ignore[unreachable]

                    # Check if view changed to TOWN/WORLD
                    poll_state, poll_score = detect_view(poll_frame)
                    if poll_state in (ViewState.TOWN, ViewState.WORLD):
                        _consecutive_restarts = 0
                        _save_rtb_debug(poll_frame, f"SUCCESS_after_back_{poll_state.value}")
                        if debug:
                            print(f"    [RETURN] Reached {poll_state.value} view (score={poll_score:.3f})")
                        return True

                    # Check if THAT SPECIFIC template at THAT position is gone
                    if not back_matcher.is_template_present(poll_frame, matched_template,
                                                            near_pos=back_pos, tolerance=30):
                        _save_rtb_debug(poll_frame, f"STEP2_back_dismissed_a{attempt+1}")
                        if debug:
                            print(f"    [RETURN] Back button ({matched_template}) dismissed after {(poll+1)*0.1:.2f}s")
                        break  # Original button dismissed, continue to check for more
            else:
                _save_rtb_debug(frame, f"STEP2_no_back_a{attempt+1}", f"score{back_score:.3f}")
                if debug:
                    print(f"    [RETURN] No back button visible (score={back_score:.3f})")
                break

        # Phase 2: Check view state again
        time.sleep(0.3)  # Give UI time to settle (reduced - fast screenshots)
        frame = win.get_screenshot_cv2()
        _save_rtb_debug(frame, f"STEP2_phase2_a{attempt+1}")
        if frame is not None:
            view_state, view_score = detect_view(frame)
            if view_state in (ViewState.TOWN, ViewState.WORLD):
                _consecutive_restarts = 0  # Reset on success
                _save_rtb_debug(frame, f"SUCCESS_phase2_{view_state.value}")
                if debug:
                    print(f"    [RETURN] Reached {view_state.value} view")
                return True

        # Phase 3: Smart state detection - figure out what state we're in
        frame = win.get_screenshot_cv2()
        _save_rtb_debug(frame, f"STEP3_smart_detect_a{attempt+1}")
        if frame is not None:
            # If we can match ground/grass with high confidence, we KNOW which view we're in
            # Ground = TOWN, Grass = WORLD - just return True, we're already there!
            from utils.safe_grass_matcher import find_safe_grass
            from utils.safe_ground_matcher import find_safe_ground

            # Quick ground check (TOWN indicator)
            ground_pos = find_safe_ground(frame, debug=debug)
            if ground_pos:
                # Ground found - click it first to dismiss any floating panels
                if debug:
                    print(f"    [RETURN] GROUND detected at {ground_pos} - clicking to dismiss panels")
                if _should_abort_for_user_activity("ground dismiss"):
                    return True
                adb.tap(*ground_pos, source="rtb:ground_click")
                time.sleep(0.5)

                # Now check if world button is visible
                frame = win.get_screenshot_cv2()
                view_state, view_score = detect_view(frame)
                if view_state in (ViewState.TOWN, ViewState.WORLD):
                    _consecutive_restarts = 0
                    _save_rtb_debug(frame, "SUCCESS_ground_TOWN")
                    if debug:
                        print(f"    [RETURN] SUCCESS: GROUND click + world button visible = TOWN view")
                    return True
                else:
                    # Ground clicked but world button NOT visible - likely zoomed in
                    _save_rtb_debug(frame, "GROUND_BUT_NO_WORLD_BUTTON")
                    if debug:
                        print(f"    [RETURN] GROUND clicked but world button NOT visible - trying zoom out...")
                    if _try_zoom_out_recovery(win, debug):
                        _consecutive_restarts = 0
                        return True
                    # Zoom out failed - continue to other recovery attempts

            # Quick grass check (WORLD indicator)
            grass_pos = find_safe_grass(frame, debug=debug)
            if grass_pos:
                # Grass found - click it first to dismiss any floating panels
                if debug:
                    print(f"    [RETURN] GRASS detected at {grass_pos} - clicking to dismiss panels")
                if _should_abort_for_user_activity("grass dismiss"):
                    return True
                adb.tap(*grass_pos, source="rtb:grass_click")
                time.sleep(0.5)

                # Now check if town button is visible
                frame = win.get_screenshot_cv2()
                view_state, view_score = detect_view(frame)
                if view_state in (ViewState.TOWN, ViewState.WORLD):
                    _consecutive_restarts = 0
                    _save_rtb_debug(frame, "SUCCESS_grass_WORLD")
                    if debug:
                        print(f"    [RETURN] SUCCESS: GRASS click + town button visible = WORLD view")
                    return True
                else:
                    # Grass clicked but town button NOT visible - likely zoomed in
                    _save_rtb_debug(frame, "GRASS_BUT_NO_TOWN_BUTTON")
                    if debug:
                        print(f"    [RETURN] GRASS clicked but town button NOT visible - trying zoom out...")
                    if _try_zoom_out_recovery(win, debug):
                        _consecutive_restarts = 0
                        return True
                    # Zoom out failed - continue to other recovery attempts

            # Detect other states
            troop_selected, troop_score = _detect_troop_selected(frame)
            resource_bar, resource_score = _detect_resource_bar(frame)
            donate_popup, donate_score = _detect_union_donate_dialog(frame)
            back_present, back_score, back_pos, _ = back_matcher.find(frame)

            if debug:
                # Save debug screenshot with state info
                debug_dir = Path(__file__).parent.parent / "screenshots" / "debug"
                debug_dir.mkdir(parents=True, exist_ok=True)
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                debug_path = debug_dir / f"return_unknown_state_a{attempt+1}_{timestamp}.png"
                cv2.imwrite(str(debug_path), frame)

                print(f"    [RETURN] State detection results:")
                print(f"      - View: UNKNOWN (score={view_score:.3f})")
                print(f"      - Troop selected: {troop_selected} (score={troop_score:.3f})")
                print(f"      - Resource bar: {resource_bar} (score={resource_score:.3f})")
                print(f"      - Union donate popup: {donate_popup} (score={donate_score:.3f})")
                print(f"      - Back button: {back_present} (score={back_score:.3f})")
                print(f"    [RETURN] Saved debug screenshot: {debug_path.name}")

            # Decision logic based on detected state
            if donate_popup:
                _save_rtb_debug(frame, f"STEP3_union_donate_popup_a{attempt+1}")
                if debug:
                    print("    [RETURN] UNION DONATE POPUP detected - clicking center to dismiss...")
                if _should_abort_for_user_activity("union donate popup dismiss"):
                    return True
                adb.tap(*CENTER_SCREEN_CLICK, source="rtb:center_screen_donate_popup")
                time.sleep(0.5)
                continue  # Retry detection

            elif troop_selected:
                # Troop is selected - click map to deselect
                _save_rtb_debug(frame, f"STEP3_troop_selected_a{attempt+1}")
                if debug:
                    print("    [RETURN] TROOP SELECTED state detected - clicking map to deselect...")
                if _should_abort_for_user_activity("troop deselect"):
                    return True
                adb.tap(*MAP_DESELECT_CLICK, source="rtb:map_deselect")
                time.sleep(0.5)

                # Check if we're now in TOWN/WORLD
                frame = win.get_screenshot_cv2()
                _save_rtb_debug(frame, f"STEP3_after_troop_deselect_a{attempt+1}")
                if frame is not None:
                    view_state, view_score = detect_view(frame)
                    if view_state in (ViewState.TOWN, ViewState.WORLD):
                        _consecutive_restarts = 0
                        _save_rtb_debug(frame, f"SUCCESS_troop_deselect_{view_state.value}")
                        if debug:
                            print(f"    [RETURN] SUCCESS: Reached {view_state.value} after troop deselect")
                        return True
                continue  # Retry detection

            elif resource_bar and not back_present:
                # Resource bar visible but no World button - might be popup or panned view
                _save_rtb_debug(frame, f"STEP3_resource_bar_a{attempt+1}")
                if debug:
                    print("    [RETURN] RESOURCE BAR visible but World button hidden - trying center click...")
                if _should_abort_for_user_activity("resource bar center click"):
                    return True
                adb.tap(*CENTER_SCREEN_CLICK, source="rtb:center_screen")
                time.sleep(0.5)

                frame = win.get_screenshot_cv2()
                _save_rtb_debug(frame, f"STEP3_after_center_click_a{attempt+1}")
                if frame is not None:
                    view_state, view_score = detect_view(frame)
                    if view_state in (ViewState.TOWN, ViewState.WORLD):
                        _consecutive_restarts = 0
                        _save_rtb_debug(frame, f"SUCCESS_center_click_{view_state.value}")
                        if debug:
                            print(f"    [RETURN] SUCCESS: Reached {view_state.value} after center click")
                        return True
                continue

            elif back_present and back_pos:
                # Back button visible - we're in some menu/dialog
                _save_rtb_debug(frame, f"STEP3_back_in_menu_a{attempt+1}")
                if debug:
                    print(f"    [RETURN] BACK BUTTON at {back_pos} - clicking to exit dialog...")
                if _should_abort_for_user_activity("step3 back button"):
                    return True
                adb.tap(*back_pos, source="rtb:back_button")
                # Poll for back button to disappear (same as Phase 1)
                for poll in range(5):
                    time.sleep(0.3)
                    poll_frame = win.get_screenshot_cv2()
                    if poll_frame is not None:
                        poll_state, _ = detect_view(poll_frame)
                        if poll_state in (ViewState.TOWN, ViewState.WORLD):
                            _consecutive_restarts = 0
                            if debug:
                                print(f"    [RETURN] SUCCESS after back click ({(poll+1)*0.3:.1f}s)")
                            return True
                continue

            else:
                # Unknown state - try grass/ground click first (dismisses floating panels)
                # Uses find_safe_grass/find_safe_ground which call match_template internally
                from utils.safe_grass_matcher import find_safe_grass
                from utils.safe_ground_matcher import find_safe_ground

                _save_rtb_debug(frame, f"STEP3_unknown_state_a{attempt+1}")
                if debug:
                    print(f"    [RETURN] UNKNOWN state - checking grass/ground...")

                # Try grass first (WORLD indicator)
                grass_pos = find_safe_grass(frame, debug=debug)
                if grass_pos:
                    _save_rtb_debug(frame, f"STEP3_grass_found_a{attempt+1}", f"pos{grass_pos[0]}_{grass_pos[1]}")
                    if debug:
                        print(f"    [RETURN] Grass detected (WORLD view) - clicking at {grass_pos}")
                    if _should_abort_for_user_activity("unknown grass click"):
                        return True
                    adb.tap(*grass_pos, source="rtb:grass_click")
                    time.sleep(0.5)
                    # Check if we're now in TOWN/WORLD
                    frame = win.get_screenshot_cv2()
                    _save_rtb_debug(frame, f"STEP3_after_grass_click_a{attempt+1}")
                    if frame is not None:
                        view_state, view_score = detect_view(frame)
                        if view_state in (ViewState.TOWN, ViewState.WORLD):
                            _consecutive_restarts = 0
                            _save_rtb_debug(frame, f"SUCCESS_grass_click_{view_state.value}")
                            if debug:
                                print(f"    [RETURN] SUCCESS: Reached {view_state.value} after grass click")
                            return True
                        else:
                            # Grass clicked but town button still not visible - try zoom out
                            if debug:
                                print(f"    [RETURN] Grass clicked but town button NOT visible - trying zoom out...")
                            if _try_zoom_out_recovery(win, debug):
                                _consecutive_restarts = 0
                                return True
                    continue  # Retry from top

                # Try ground (TOWN indicator)
                ground_pos = find_safe_ground(frame, debug=debug)
                if ground_pos:
                    _save_rtb_debug(frame, f"STEP3_ground_found_a{attempt+1}", f"pos{ground_pos[0]}_{ground_pos[1]}")
                    if debug:
                        print(f"    [RETURN] Ground detected (TOWN view) - clicking at {ground_pos}")
                    if _should_abort_for_user_activity("unknown ground click"):
                        return True
                    adb.tap(*ground_pos, source="rtb:ground_click")
                    time.sleep(0.5)
                    # Check if we're now in TOWN/WORLD
                    frame = win.get_screenshot_cv2()
                    _save_rtb_debug(frame, f"STEP3_after_ground_click_a{attempt+1}")
                    if frame is not None:
                        view_state, view_score = detect_view(frame)
                        if view_state in (ViewState.TOWN, ViewState.WORLD):
                            _consecutive_restarts = 0
                            _save_rtb_debug(frame, f"SUCCESS_ground_click_{view_state.value}")
                            if debug:
                                print(f"    [RETURN] SUCCESS: Reached {view_state.value} after ground click")
                            return True
                        else:
                            # Ground clicked but world button still not visible - try zoom out
                            if debug:
                                print(f"    [RETURN] Ground clicked but world button NOT visible - trying zoom out...")
                            if _try_zoom_out_recovery(win, debug):
                                _consecutive_restarts = 0
                                return True
                    continue  # Retry from top

                # Neither grass nor ground found - search for back button again
                _save_rtb_debug(frame, f"STEP3_no_grass_ground_a{attempt+1}")
                back_found, back_score2, back_pos2, _ = back_matcher.find(frame)
                if back_found and back_pos2:
                    _save_rtb_debug(frame, f"STEP3_fallback_back_a{attempt+1}", f"pos{back_pos2[0]}_{back_pos2[1]}")
                    if debug:
                        print(f"    [RETURN] Found back button at {back_pos2} (score={back_score2:.3f})")
                    if _should_abort_for_user_activity("fallback back click"):
                        return True
                    adb.tap(*back_pos2, source="rtb:back_button")
                    time.sleep(0.5)
                else:
                    if debug:
                        print("    [RETURN] No back button found, skipping...")
                    time.sleep(0.5)

                # Check again
                frame = win.get_screenshot_cv2()
                _save_rtb_debug(frame, f"STEP3_after_fallback_a{attempt+1}")
                if frame is not None:
                    view_state, view_score = detect_view(frame)
                    if view_state in (ViewState.TOWN, ViewState.WORLD):
                        _consecutive_restarts = 0
                        _save_rtb_debug(frame, f"SUCCESS_fallback_{view_state.value}")
                        if debug:
                            print(f"    [RETURN] SUCCESS: Reached {view_state.value} after back click")
                        return True

                # Try center click for "Tap to Close" popups
                _save_rtb_debug(frame, f"STEP3_trying_center_a{attempt+1}")
                if debug:
                    print("    [RETURN] Trying center screen click...")
                if _should_abort_for_user_activity("fallback center click"):
                    return True
                adb.tap(*CENTER_SCREEN_CLICK, source="rtb:center_screen")
                time.sleep(0.5)

                frame = win.get_screenshot_cv2()
                _save_rtb_debug(frame, f"STEP3_after_center_a{attempt+1}")
                if frame is not None:
                    view_state, view_score = detect_view(frame)
                    if view_state in (ViewState.TOWN, ViewState.WORLD):
                        _consecutive_restarts = 0
                        _save_rtb_debug(frame, f"SUCCESS_center_{view_state.value}")
                        if debug:
                            print(f"    [RETURN] SUCCESS: Reached {view_state.value} after center click")
                        return True

        _save_rtb_debug(frame, f"STEP2_still_stuck_a{attempt+1}")
        if debug:
            print(f"    [RETURN] Still stuck after attempt {attempt + 1}")

    # Deadline guard: an app restart + recursion is the pathological path that can
    # freeze the daemon for ~11 min when the window is merely occluded (restarting
    # the app cannot fix occlusion). Bail before paying that cost.
    if deadline is not None and time.time() > deadline:
        print("    [RETURN] Deadline exceeded before app restart - aborting recovery "
              "(will retry next cycle)")
        return False

    # STEP 3: All attempts failed - restart app and RETRY (never give up)
    _consecutive_restarts += 1

    # Save debug screenshot with detailed marker BEFORE restart (only if debug mode)
    if debug:
        frame = win.get_screenshot_cv2()
        if frame is not None:
            debug_dir = Path(__file__).parent.parent / "screenshots" / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            debug_path = debug_dir / f"RESTART_TRIGGER_{timestamp}.png"
            cv2.imwrite(str(debug_path), frame)
            # Also detect view state for the marker
            view_state, view_score = detect_view(frame)
            back_present, back_score, _, _ = back_matcher.find(frame)
            print(f"    [RETURN] *** RESTART #{_consecutive_restarts} - will keep trying ***")
            print(f"    [RETURN] Screenshot saved: {debug_path.name}")
            print(f"    [RETURN] View state at restart: {view_state.value} (score={view_score:.3f})")
            print(f"    [RETURN] Back button present: {back_present} (score={back_score:.3f})")
            print(f"    [RETURN] All {MAX_RECOVERY_ATTEMPTS} attempts exhausted")
        else:
            print(f"    [RETURN] *** RESTART #{_consecutive_restarts} - will keep trying (no screenshot) ***")  # type: ignore[unreachable]
            print(f"    [RETURN] All {MAX_RECOVERY_ATTEMPTS} attempts exhausted")
    else:
        print(f"    [RETURN] *** RESTART #{_consecutive_restarts} - will keep trying ***")
        print(f"    [RETURN] All {MAX_RECOVERY_ATTEMPTS} attempts exhausted")

    if debug:
        print(f"    [RETURN] Restarting app...")
    _start_app(adb, debug)

    if debug:
        print("    [RETURN] Retrying recovery after restart...")
    return return_to_base_view(adb, win, debug, deadline=deadline)  # Recursive - keeps trying until success (or deadline)


if __name__ == '__main__':
    # Test
    adb = ADBHelper()
    result = return_to_base_view(adb, debug=True)
    print(f"Result: {result}")
