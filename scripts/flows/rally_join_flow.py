"""
Rally Join Flow - Automatically join Union War rallies.

Assumes Union War panel is already open (trigger handled by daemon).

Flow:
1. Validate panel state (heading + Team Intelligence tab)
2. Find all plus buttons in rightmost column
3. For each plus button (top to bottom):
   - OCR monster icon
   - Validate against config rules
   - If match: Join rally
4. Select leftmost idle hero (Zz icon check)
5. Click Team Up (fire-and-forget)
6. Return to base view

Supports DATA GATHERING MODE to collect monster samples for OCR tuning.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy.typing as npt

import cv2
import numpy as np

from utils.adb_helper import ADBHelper
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.union_war_panel_detector import UnionWarPanelDetector
from utils.rally_plus_matcher import RallyPlusMatcher
from utils.rally_monster_validator import RallyMonsterValidator
from utils.ocr_client import OCRClient
from utils.hero_selector import HeroSelector
from utils.return_to_base_view import return_to_base_view
from utils.back_button_matcher import BackButtonMatcher
from utils.debug_screenshot import save_debug_screenshot
from utils.safe_grass_matcher import find_safe_grass

# Flow name for debug screenshots
FLOW_NAME = "rally_join"

# Import config values
# Type aliases for config values
MonsterConfig = dict[str, Any]
EventConfig = dict[str, Any]

try:
    from config import (
        RALLY_MONSTERS as _RALLY_MONSTERS,
        RALLY_DATA_GATHERING_MODE as _RALLY_DATA_GATHERING_MODE,
        RALLY_IGNORE_DAILY_LIMIT as _RALLY_IGNORE_DAILY_LIMIT,
        RALLY_IGNORE_DAILY_LIMIT_EVENTS as _RALLY_IGNORE_DAILY_LIMIT_EVENTS,
    )
    RALLY_MONSTERS: list[MonsterConfig] = _RALLY_MONSTERS
    RALLY_DATA_GATHERING_MODE: bool = _RALLY_DATA_GATHERING_MODE
    RALLY_IGNORE_DAILY_LIMIT: bool = _RALLY_IGNORE_DAILY_LIMIT
    RALLY_IGNORE_DAILY_LIMIT_EVENTS: list[EventConfig] = _RALLY_IGNORE_DAILY_LIMIT_EVENTS
except ImportError:
    # Fallback defaults if config not updated yet
    RALLY_MONSTERS = [{"name": "Zombie Overlord", "auto_join": True, "max_level": 130, "has_level": True}]
    RALLY_DATA_GATHERING_MODE = False
    RALLY_IGNORE_DAILY_LIMIT = False
    RALLY_IGNORE_DAILY_LIMIT_EVENTS = []


from datetime import datetime, timezone, timedelta


def _should_ignore_daily_limit() -> bool:
    """
    Check if daily limit should be ignored (click Confirm instead of Cancel).

    Returns True if:
    - RALLY_IGNORE_DAILY_LIMIT global flag is True, OR
    - Current UTC time falls within any event in RALLY_IGNORE_DAILY_LIMIT_EVENTS

    Event boundaries use SERVER RESET time (02:00 UTC):
    - Start: 02:00 UTC on start date
    - End: 02:00 UTC on the day AFTER end date
    Example: end="2025-12-28" means active until 2025-12-29 02:00 UTC
    """
    if RALLY_IGNORE_DAILY_LIMIT:
        return True

    if RALLY_IGNORE_DAILY_LIMIT_EVENTS:
        now = datetime.now(timezone.utc)
        for event in RALLY_IGNORE_DAILY_LIMIT_EVENTS:
            # Parse dates and add server reset time (02:00 UTC)
            start_date = datetime.strptime(event["start"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            end_date = datetime.strptime(event["end"], "%Y-%m-%d").replace(tzinfo=timezone.utc)

            # Event starts at 02:00 UTC on start date
            event_start = start_date.replace(hour=2, minute=0, second=0)
            # Event ends at 02:00 UTC on the day AFTER end date
            event_end = (end_date + timedelta(days=1)).replace(hour=2, minute=0, second=0)

            if event_start <= now < event_end:
                print(f"[RALLY-JOIN]   Within {event['name']} event period - ignoring daily limit")
                return True

    return False


# DEBUG_DIR now handled by save_debug_screenshot utility

# Team Up button template path
TEAM_UP_TEMPLATE_PATH = Path(__file__).parent.parent.parent / "templates" / "ground_truth" / "team_up_button_4k.png"

# Daily limit dialog template path (includes "Tip" header + full text about daily rally rewards)
DAILY_LIMIT_DIALOG_PATH = Path(__file__).parent.parent.parent / "templates" / "ground_truth" / "daily_rally_limit_dialog_4k.png"

# Cancel button template path
CANCEL_BUTTON_TEMPLATE_PATH = Path(__file__).parent.parent.parent / "templates" / "ground_truth" / "cancel_button_4k.png"

# Fixed positions and regions for buttons (4K resolution)
# Team Up button: template 368x134, position around (1728, 1581)
TEAM_UP_REGION = (1700, 1550, 420, 180)  # (x, y, w, h) - slightly larger than template
TEAM_UP_CLICK = (1912, 1648)  # center click position

# Cancel button: template 368x130, position around (1486, 1226)
CANCEL_REGION = (1450, 1200, 420, 180)  # (x, y, w, h)
CANCEL_CLICK = (1670, 1291)  # center click position

# Confirm button: right side of daily limit dialog
CONFIRM_CLICK = (2150, 1291)  # center click position (same Y as Cancel)


def _verify_button_at_region(
    frame: npt.NDArray[Any],
    template: npt.NDArray[Any],
    region: tuple[int, int, int, int],
    threshold: float = 0.05,
) -> tuple[bool, float]:
    """
    Verify a button exists at a fixed region.

    Args:
        frame: BGR screenshot
        template: Template image
        region: (x, y, w, h) region to check
        threshold: Match threshold (lower = stricter)

    Returns:
        (found, score) tuple
    """
    rx, ry, rw, rh = region
    roi = frame[ry:ry+rh, rx:rx+rw]

    if roi.shape[0] < template.shape[0] or roi.shape[1] < template.shape[1]:
        return False, 1.0

    result = cv2.matchTemplate(roi, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, _, _ = cv2.minMaxLoc(result)
    return min_val <= threshold, float(min_val)


def _poll_for_button(
    win: WindowsScreenshotHelper,
    template: npt.NDArray[Any],
    region: tuple[int, int, int, int],
    click_pos: tuple[int, int],
    name: str,
    timeout: float = 3.0,
    threshold: float = 0.05,
) -> tuple[bool, npt.NDArray[Any]]:
    """
    Poll for a button at fixed region, click when found.

    Args:
        win: WindowsScreenshotHelper
        template: Template image
        region: (x, y, w, h) region to check
        click_pos: (x, y) position to click
        name: Button name for logging
        timeout: Max seconds to wait
        threshold: Match threshold

    Returns:
        (success, frame) - success=True if button found, frame is last screenshot
    """
    frame = win.get_screenshot_cv2()
    start_time = time.time()
    while time.time() - start_time < timeout:
        frame = win.get_screenshot_cv2()
        found, score = _verify_button_at_region(frame, template, region, threshold)

        if found:
            print(f"[RALLY-JOIN]   {name} verified (score={score:.4f})")
            return True, frame

        time.sleep(0.3)

    print(f"[RALLY-JOIN]   {name} NOT FOUND after {timeout}s timeout")
    return False, frame


def _wait_for_team_up_panel(
    win: WindowsScreenshotHelper,
    timeout: float = 5.0,
) -> npt.NDArray[Any] | None:
    """
    Wait for Team Up panel to fully load by detecting the Team Up button at fixed region.

    Args:
        win: WindowsScreenshotHelper instance
        timeout: Maximum seconds to wait

    Returns:
        frame: Screenshot with panel loaded, or None if timeout
    """
    template: npt.NDArray[Any] | None = cv2.imread(str(TEAM_UP_TEMPLATE_PATH))
    if template is None:
        print("[RALLY-JOIN] WARNING: team_up_button_4k.png not found")
        return None

    start_time = time.time()
    while time.time() - start_time < timeout:
        frame = win.get_screenshot_cv2()
        found, score = _verify_button_at_region(frame, template, TEAM_UP_REGION, threshold=0.05)

        if found:
            print(f"[RALLY-JOIN]   Team Up panel loaded (score={score:.4f})")
            return frame

        print(f"[RALLY-JOIN]   Waiting for panel... (score={score:.4f})")
        time.sleep(0.5)

    print("[RALLY-JOIN]   TIMEOUT waiting for Team Up panel")
    return None


def _check_daily_limit_dialog(
    win: WindowsScreenshotHelper,
    timeout: float = 2.0,
) -> bool:
    """
    Poll for daily rally limit dialog after clicking Team Up.

    Args:
        win: WindowsScreenshotHelper instance
        timeout: Maximum seconds to wait

    Returns:
        True if dialog detected (need to cancel), False if no dialog
    """
    template: npt.NDArray[Any] | None = cv2.imread(str(DAILY_LIMIT_DIALOG_PATH))
    if template is None:
        print("[RALLY-JOIN] WARNING: daily_rally_rewards_dialog_4k.png not found")
        return False

    # Search in center region only (dialogs appear in center, not at edges)
    # This prevents false positives on empty white Union War panel
    CENTER_REGION = (1200, 600, 1400, 800)  # x, y, w, h - center of 4K screen
    rx, ry, rw, rh = CENTER_REGION

    start_time = time.time()
    while time.time() - start_time < timeout:
        frame = win.get_screenshot_cv2()

        # Crop to center region
        roi = frame[ry:ry+rh, rx:rx+rw]

        # Check if template fits in ROI
        if roi.shape[0] < template.shape[0] or roi.shape[1] < template.shape[1]:
            time.sleep(0.3)
            continue

        result = cv2.matchTemplate(roi, template, cv2.TM_SQDIFF_NORMED)
        min_val, _, _, _ = cv2.minMaxLoc(result)

        # Tighter threshold (0.03) + center region = no false positives
        if min_val < 0.03:
            print(f"[RALLY-JOIN]   Daily limit dialog detected (score={min_val:.4f})")
            return True

        time.sleep(0.3)

    return False


def _get_monster_config(monster_name: str) -> dict[str, Any] | None:
    """
    Get monster config by name from RALLY_MONSTERS.

    Args:
        monster_name: Name of the monster (case-insensitive)

    Returns:
        Monster config dict or None if not found
    """
    for monster in RALLY_MONSTERS:
        if monster['name'].lower() == monster_name.lower():
            return monster
    return None


def rally_join_flow(adb: ADBHelper, union_boss_mode: bool = False) -> dict[str, Any]:
    """
    Main rally joining flow.

    Assumes Union War panel is already open.

    Args:
        adb: ADB helper instance
        union_boss_mode: If True, use any idle hero instead of leftmost only

    Returns:
        dict: {'success': bool, 'monster_name': str | None}
    """
    print("[RALLY-JOIN] Starting rally join flow")

    # Check if we should ignore daily limits (special events like Winter Fest)
    ignore_limit = _should_ignore_daily_limit()
    if ignore_limit:
        print("[RALLY-JOIN] Daily limit checking DISABLED (special event active)")

    # Initialize components
    win = WindowsScreenshotHelper()
    panel_detector = UnionWarPanelDetector()
    plus_matcher = RallyPlusMatcher()
    ocr = OCRClient()
    monster_validator = RallyMonsterValidator(
        ocr_client=ocr,
        monsters_config=RALLY_MONSTERS,
        data_gathering_mode=RALLY_DATA_GATHERING_MODE,
        ignore_daily_limit=ignore_limit
    )
    hero_selector = HeroSelector()
    back_button_matcher = BackButtonMatcher()

    # Step 0: Check for leftover daily limit dialog and dismiss if present
    # This prevents infinite loop when daemon re-triggers flow with dialog still on screen
    frame = win.get_screenshot_cv2()
    _save_debug_screenshot(frame, "STEP0 flow start")

    if _check_daily_limit_dialog(win, timeout=0.5):
        frame = win.get_screenshot_cv2()
        _save_debug_screenshot(frame, "STEP0 daily limit dialog found")
        if _should_ignore_daily_limit():
            print("[RALLY-JOIN] Daily limit dialog at flow start - clicking Confirm (ignoring limit)")
            adb.tap(*CONFIRM_CLICK)
        else:
            print("[RALLY-JOIN] Daily limit dialog detected at flow start - dismissing")
            adb.tap(*CANCEL_CLICK)
        time.sleep(0.5)
        frame = win.get_screenshot_cv2()
        _save_debug_screenshot(frame, "STEP0 AFTER dismiss dialog")

        # Dismiss any leftover Team Up panel underneath by clicking grass
        print("[RALLY-JOIN] Dismissing any leftover panel by clicking grass...")
        grass_pos = find_safe_grass(frame, debug=False)
        if grass_pos:
            _save_debug_screenshot(frame, "STEP0 CLICKING grass", f"pos={grass_pos}")
            adb.tap(*grass_pos)
            time.sleep(0.5)
            frame = win.get_screenshot_cv2()
            _save_debug_screenshot(frame, "STEP0 AFTER grass click")

        _cleanup_and_exit(adb, win, back_button_matcher)
        return {'success': False, 'monster_name': None}

    # Step 1: Validate panel state
    print("[RALLY-JOIN] Step 1: Validating panel state")
    frame = win.get_screenshot_cv2()
    _save_debug_screenshot(frame, "STEP1 panel check")

    valid, message, details = panel_detector.validate_panel_state(frame)
    print(f"[RALLY-JOIN]   Panel validation: {message}")
    print(f"[RALLY-JOIN]   Details: heading={details['heading_present']} (score={details['heading_score']:.4f}), " +
          f"tab={details['tab_selected']} (score={details['tab_score']:.4f})")

    if not valid:
        print(f"[RALLY-JOIN] Panel not valid: {message}. Exiting.")
        _save_debug_screenshot(frame, "STEP1 FAIL panel invalid", message)
        _cleanup_and_exit(adb, win, back_button_matcher)
        return {'success': False, 'monster_name': None}

    _save_debug_screenshot(frame, "STEP1 panel valid")

    # Step 2: Find all plus buttons
    print("[RALLY-JOIN] Step 2: Finding rally plus buttons")
    plus_buttons = plus_matcher.find_all_plus_buttons(frame)
    print(f"[RALLY-JOIN]   Found {len(plus_buttons)} plus button(s)")
    _save_debug_screenshot(frame, "STEP2 found plus buttons", f"count={len(plus_buttons)}")

    if not plus_buttons:
        print("[RALLY-JOIN] No rallies available. Exiting.")
        _save_debug_screenshot(frame, "STEP2 FAIL no rallies")
        _cleanup_and_exit(adb, win, back_button_matcher)
        return {'success': False, 'monster_name': None}

    # Log all detected plus buttons
    for i, (x, y, score) in enumerate(plus_buttons):
        print(f"[RALLY-JOIN]   Rally {i}: plus at ({x}, {y}), score={score:.4f}")

    # Step 3: Click-first approach - click each rally, validate AFTER panel opens
    # This is MUCH faster than OCR-ing all rallies upfront (which takes 1-2s each)
    print("[RALLY-JOIN] Step 3: Click-first validation")

    # Save original frame for OCR (monster positions are relative to plus buttons)
    original_frame = frame

    for i, (plus_x, plus_y, plus_score) in enumerate(plus_buttons):
        print(f"[RALLY-JOIN]   Trying rally {i} at ({plus_x}, {plus_y})")

        # Click immediately - no OCR delay
        click_x, click_y = plus_matcher.get_click_position(plus_x, plus_y)
        _save_debug_screenshot(original_frame, f"STEP3 CLICKING rally {i}", f"pos=({click_x}, {click_y})")
        adb.tap(click_x, click_y)

        # Wait for Team Up panel (poll, not fixed sleep)
        panel_frame = _wait_for_team_up_panel(win, timeout=3.0)
        if panel_frame is None:
            print(f"[RALLY-JOIN]   Rally {i}: Panel didn't open, trying next")
            frame = win.get_screenshot_cv2()
            _save_debug_screenshot(frame, f"STEP3 rally {i} panel FAILED to open")
            continue

        _save_debug_screenshot(panel_frame, f"STEP3 rally {i} panel opened")

        # Validate monster from ORIGINAL frame (monster positions are fixed relative to plus buttons)
        should_join, monster_name, level, raw_text = monster_validator.validate_monster(
            original_frame, plus_x, plus_y, rally_index=i
        )

        print(f"[RALLY-JOIN]     OCR: {monster_name} Lv.{level} -> should_join={should_join}")
        _save_debug_screenshot(panel_frame, f"STEP3 OCR result", f"{monster_name} Lv{level} join={should_join}")

        if should_join:
            print(f"[RALLY-JOIN]   MATCH: {monster_name} Lv.{level}")
            _save_debug_screenshot(panel_frame, f"STEP3 MATCH found", f"{monster_name} Lv{level}")
            # Continue with hero selection (panel is already open)
            frame = panel_frame
            break
        else:
            # Wrong monster - dismiss Team Up panel by clicking grass
            print(f"[RALLY-JOIN]   Skipping {monster_name} Lv.{level}, dismissing panel")
            dismiss_frame = win.get_screenshot_cv2()
            _save_debug_screenshot(dismiss_frame, f"STEP3 skip rally {i}", f"{monster_name}")
            grass_pos = find_safe_grass(dismiss_frame, debug=False)
            if grass_pos:
                _save_debug_screenshot(dismiss_frame, f"STEP3 CLICKING grass", f"pos={grass_pos}")
                adb.tap(*grass_pos)
                time.sleep(0.5)
                frame = win.get_screenshot_cv2()
                _save_debug_screenshot(frame, f"STEP3 AFTER grass click")
                # Verify panel dismissed - if still open, abort and recover
                if _wait_for_team_up_panel(win, timeout=0.5) is not None:
                    print("[RALLY-JOIN]   Panel still open after grass click - recovering")
                    _save_debug_screenshot(frame, f"STEP3 FAIL panel still open")
                    return_to_base_view(adb, win, debug=False)
                    return {'success': False, 'monster_name': None}
            else:
                # No grass found - use return_to_base_view to recover
                print("[RALLY-JOIN]   No grass found - recovering")
                _save_debug_screenshot(dismiss_frame, f"STEP3 FAIL no grass found")
                return_to_base_view(adb, win, debug=False)
                return {'success': False, 'monster_name': None}
    else:
        # No matching rallies found after trying all
        print("[RALLY-JOIN] No matching rallies found. Exiting.")
        frame = win.get_screenshot_cv2()
        _save_debug_screenshot(frame, "STEP3 FAIL no matching rallies")
        _cleanup_and_exit(adb, win, back_button_matcher)
        return {'success': False, 'monster_name': None}

    # Panel is already open from the loop above
    _save_debug_screenshot(frame, "STEP4 before hero selection")

    # DEBUG: Log all slot scores
    debug_selector = HeroSelector()
    statuses = debug_selector.get_all_slot_status(frame)
    print(f"[RALLY-JOIN]   Zz detection scores:")
    for s in statuses:
        print(f"[RALLY-JOIN]     Slot {s['id']}: score={s['score']:.6f} idle={s['is_idle']}")

    # Step 5: Select idle hero (REQUIRE Zz - only join if hero is idle)
    if union_boss_mode:
        print("[RALLY-JOIN] Step 5: Selecting ANY idle hero (Union Boss mode)")
        idle_slot = hero_selector.find_any_idle(frame, zz_mode='require')
    else:
        print("[RALLY-JOIN] Step 5: Selecting leftmost idle hero (must have Zz)")
        idle_slot = hero_selector.find_leftmost_idle(frame, zz_mode='require')

    if not idle_slot:
        print("[RALLY-JOIN] No idle heroes found (no Zz icons). Better luck next time!")
        _save_debug_screenshot(frame, "STEP5 FAIL no idle heroes")
        _cleanup_and_exit(adb, win, back_button_matcher)
        return {'success': False, 'monster_name': monster_name}

    print(f"[RALLY-JOIN]   Idle hero found at slot {idle_slot['id']}, clicking")
    _save_debug_screenshot(frame, f"STEP5 CLICKING hero slot {idle_slot['id']}", f"pos={idle_slot['click']}")
    adb.tap(*idle_slot['click'])
    time.sleep(0.3)

    frame = win.get_screenshot_cv2()
    _save_debug_screenshot(frame, "STEP5 AFTER hero click")

    # Step 6: Click Team Up button (poll for it at fixed region)
    print("[RALLY-JOIN] Step 6: Clicking Team Up button")

    team_up_template: npt.NDArray[Any] | None = cv2.imread(str(TEAM_UP_TEMPLATE_PATH))
    if team_up_template is None:
        print("[RALLY-JOIN] WARNING: team_up_button_4k.png not found, aborting")
        _save_debug_screenshot(frame, "STEP6 FAIL no teamup template")
        _cleanup_and_exit(adb, win, back_button_matcher)
        return {'success': False, 'monster_name': monster_name}

    # Poll for Team Up button at fixed region (3s timeout)
    found, frame = _poll_for_button(win, team_up_template, TEAM_UP_REGION,
                                     TEAM_UP_CLICK, "Team Up button", timeout=3.0)
    if not found:
        print("[RALLY-JOIN] Team Up button not found at expected region, aborting")
        _save_debug_screenshot(frame, "STEP6 FAIL teamup not found")
        _cleanup_and_exit(adb, win, back_button_matcher)
        return {'success': False, 'monster_name': monster_name}

    _save_debug_screenshot(frame, "STEP6 CLICKING Team Up", f"pos={TEAM_UP_CLICK}")
    # Click at fixed position (button is always here when found)
    adb.tap(*TEAM_UP_CLICK)

    time.sleep(0.3)
    frame = win.get_screenshot_cv2()
    _save_debug_screenshot(frame, "STEP6 AFTER Team Up click")

    # Step 6b: Check for daily limit dialog
    if _check_daily_limit_dialog(win, timeout=2.0):
        frame = win.get_screenshot_cv2()
        _save_debug_screenshot(frame, "STEP6 daily limit dialog found")
        if _should_ignore_daily_limit():
            # Ignore daily limit - click Confirm and continue
            print(f"[RALLY-JOIN]   Daily limit reached but ignoring - clicking Confirm")
            _save_debug_screenshot(frame, "STEP6 CLICKING Confirm ignore limit")
            adb.tap(*CONFIRM_CLICK)
            time.sleep(0.5)
            frame = win.get_screenshot_cv2()
            _save_debug_screenshot(frame, "STEP6 AFTER Confirm click")
            # Don't mark as exhausted, don't return early - fall through to success path
        else:
            # Respect daily limit - click Cancel and exit
            print(f"[RALLY-JOIN]   Daily limit reached for {monster_name}!")

            # Poll for Cancel button at fixed region (2s timeout)
            cancel_template: npt.NDArray[Any] | None = cv2.imread(str(CANCEL_BUTTON_TEMPLATE_PATH))
            if cancel_template is not None:
                found, frame = _poll_for_button(win, cancel_template, CANCEL_REGION,
                                                CANCEL_CLICK, "Cancel button", timeout=2.0, threshold=0.1)
                if found:
                    _save_debug_screenshot(frame, "STEP6 CLICKING Cancel")
                    adb.tap(*CANCEL_CLICK)
                else:
                    print("[RALLY-JOIN]   Cancel button not at expected region, clicking back instead")
                    _save_debug_screenshot(frame, "STEP6 Cancel not found clicking back")
                    back_button_matcher.click(adb)
            else:
                print("[RALLY-JOIN]   Cancel template not found, clicking back instead")
                _save_debug_screenshot(frame, "STEP6 no cancel template clicking back")
                back_button_matcher.click(adb)
            time.sleep(0.5)

            frame = win.get_screenshot_cv2()
            _save_debug_screenshot(frame, "STEP6 AFTER Cancel click")

            # CRITICAL: Dismiss the Team Up panel that's still open underneath!
            # Click grass to close it before cleanup
            print("[RALLY-JOIN]   Dismissing Team Up panel by clicking grass...")
            grass_pos = find_safe_grass(frame, debug=False)
            if grass_pos:
                _save_debug_screenshot(frame, "STEP6 CLICKING grass to dismiss panel", f"pos={grass_pos}")
                adb.tap(*grass_pos)
                time.sleep(0.5)
                frame = win.get_screenshot_cv2()
                _save_debug_screenshot(frame, "STEP6 AFTER grass click")
            else:
                print("[RALLY-JOIN]   No grass found - will use return_to_base_view")
                _save_debug_screenshot(frame, "STEP6 no grass using return_to_base")

            # Mark monster as exhausted for today (only if track_daily_limit is True)
            if monster_name is not None:
                monster_config = _get_monster_config(monster_name)
                if monster_config and monster_config.get('track_daily_limit', True):
                    from utils.scheduler import get_scheduler, DaemonScheduler
                    scheduler = get_scheduler()
                    limit_name = f"rally_{monster_name.lower().replace(' ', '_')}"
                    reset_time = DaemonScheduler.get_next_server_reset()
                    scheduler.mark_exhausted(limit_name, reset_time)
                    print(f"[RALLY-JOIN]   Marked {monster_name} as exhausted until {reset_time}")
                else:
                    print(f"[RALLY-JOIN]   {monster_name} has track_daily_limit=False, not marking exhausted")

            # Cleanup and exit
            _cleanup_and_exit(adb, win, back_button_matcher)
            return {'success': False, 'monster_name': monster_name}

    time.sleep(0.5)
    frame = win.get_screenshot_cv2()
    _save_debug_screenshot(frame, "STEP7 before cleanup")

    # Step 7: Cleanup and return
    print("[RALLY-JOIN] Step 7: Cleanup and return to base")
    _cleanup_and_exit(adb, win, back_button_matcher)

    print(f"[RALLY-JOIN] Successfully joined {monster_name} Lv.{level} rally")
    return {'success': True, 'monster_name': monster_name}


def _cleanup_and_exit(
    adb: ADBHelper,
    win: WindowsScreenshotHelper,
    back_button_matcher: BackButtonMatcher,
) -> None:
    """
    Dismiss floating panels and return to base view.

    Args:
        adb: ADB helper
        win: Screenshot helper
        back_button_matcher: Back button matcher (unused, kept for API compatibility)
    """
    # Check for daily limit dialog that may have appeared late
    # This dialog can appear with server delay AFTER the main check in Step 6b
    daily_limit_template: npt.NDArray[Any] | None = cv2.imread(str(DAILY_LIMIT_DIALOG_PATH))
    if daily_limit_template is not None:
        frame = win.get_screenshot_cv2()
        _save_debug_screenshot(frame, "CLEANUP checking for late dialog")

        # Search in center region only (same as _check_daily_limit_dialog)
        CENTER_REGION = (1200, 600, 1400, 800)  # x, y, w, h
        rx, ry, rw, rh = CENTER_REGION
        roi = frame[ry:ry+rh, rx:rx+rw]

        if roi.shape[0] >= daily_limit_template.shape[0] and roi.shape[1] >= daily_limit_template.shape[1]:
            result = cv2.matchTemplate(roi, daily_limit_template, cv2.TM_SQDIFF_NORMED)
            min_val, _, _, _ = cv2.minMaxLoc(result)

            if min_val < 0.03:  # Tighter threshold
                print(f"[RALLY-JOIN]   Late daily limit dialog detected in cleanup (score={min_val:.4f})")
                _save_debug_screenshot(frame, "CLEANUP late dialog found", f"score={min_val:.4f}")
                if _should_ignore_daily_limit():
                    print("[RALLY-JOIN]   Clicking Confirm (ignoring daily limit)")
                    adb.tap(*CONFIRM_CLICK)
                else:
                    print("[RALLY-JOIN]   Clicking Cancel to dismiss")
                    adb.tap(*CANCEL_CLICK)
                time.sleep(0.5)
                frame = win.get_screenshot_cv2()
                _save_debug_screenshot(frame, "CLEANUP AFTER dialog dismiss")

                # Also dismiss any Team Up panel underneath
                grass_pos = find_safe_grass(frame, debug=False)
                if grass_pos:
                    print("[RALLY-JOIN]   Clicking grass to dismiss panel")
                    adb.tap(*grass_pos)
                    time.sleep(0.5)

    # Use centralized return_to_base_view for all back button handling
    print("[RALLY-JOIN]   Returning to base view...")
    return_to_base_view(adb, win, debug=False)


# Debug screenshot directory for rally flow
RALLY_DEBUG_DIR = Path(__file__).parent.parent.parent / "screenshots" / "debug" / "rally_join"
RALLY_DEBUG_DIR.mkdir(parents=True, exist_ok=True)


def _save_debug_screenshot(frame: npt.NDArray[Any], label: str, extra: str = "") -> None:
    """
    Save debug screenshot with step text annotated on image.

    Args:
        frame: BGR screenshot
        label: Description label for filename
        extra: Extra info to add to annotation
    """
    annotated = frame.copy()
    text = f"RALLY: {label}"
    if extra:
        text += f" | {extra}"
    # Draw black background for text
    cv2.rectangle(annotated, (10, 10), (1800, 80), (0, 0, 0), -1)
    # Draw white text
    cv2.putText(annotated, text, (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)

    timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]
    filename = RALLY_DEBUG_DIR / f"{timestamp}_{label.replace(' ', '_').lower()}.png"
    cv2.imwrite(str(filename), annotated)
    print(f"[RALLY-JOIN]   DEBUG: {filename.name}")
