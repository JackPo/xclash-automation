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

import time
from pathlib import Path
import cv2

from utils.adb_helper import ADBHelper
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.union_war_panel_detector import UnionWarPanelDetector
from utils.rally_plus_matcher import RallyPlusMatcher
from utils.rally_monster_validator import RallyMonsterValidator
from utils.ocr_client import OCRClient
from utils.hero_selector import HeroSelector
from utils.return_to_base_view import return_to_base_view
from utils.back_button_matcher import BackButtonMatcher


# Import config values
try:
    from config import (
        RALLY_MONSTERS,
        RALLY_DATA_GATHERING_MODE
    )
except ImportError:
    # Fallback defaults if config not updated yet
    RALLY_MONSTERS = [{"name": "Zombie Overlord", "auto_join": True, "max_level": 130, "has_level": True}]
    RALLY_DATA_GATHERING_MODE = False


# Debug directory
DEBUG_DIR = Path(__file__).parent.parent.parent / "templates" / "debug" / "rally_join_flow"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

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


def _verify_button_at_region(frame, template, region, threshold=0.05):
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
    return min_val <= threshold, min_val


def _poll_for_button(win, template, region, click_pos, name, timeout=3.0, threshold=0.05):
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


def _wait_for_team_up_panel(win, timeout=5.0):
    """
    Wait for Team Up panel to fully load by detecting the Team Up button at fixed region.

    Args:
        win: WindowsScreenshotHelper instance
        timeout: Maximum seconds to wait

    Returns:
        frame: Screenshot with panel loaded, or None if timeout
    """
    template = cv2.imread(str(TEAM_UP_TEMPLATE_PATH))
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


def _check_daily_limit_dialog(win, timeout=2.0) -> bool:
    """
    Poll for daily rally limit dialog after clicking Team Up.

    Args:
        win: WindowsScreenshotHelper instance
        timeout: Maximum seconds to wait

    Returns:
        True if dialog detected (need to cancel), False if no dialog
    """
    template = cv2.imread(str(DAILY_LIMIT_DIALOG_PATH))
    if template is None:
        print("[RALLY-JOIN] WARNING: daily_rally_rewards_dialog_4k.png not found")
        return False

    start_time = time.time()
    while time.time() - start_time < timeout:
        frame = win.get_screenshot_cv2()
        result = cv2.matchTemplate(frame, template, cv2.TM_SQDIFF_NORMED)
        min_val, _, _, _ = cv2.minMaxLoc(result)

        if min_val < 0.05:  # Dialog found (tight threshold - template includes full text)
            print(f"[RALLY-JOIN]   Daily limit dialog detected (score={min_val:.4f})")
            return True

        time.sleep(0.3)

    return False


def _get_monster_config(monster_name: str) -> dict | None:
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


def rally_join_flow(adb: ADBHelper, union_boss_mode: bool = False) -> dict:
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

    # Initialize components
    win = WindowsScreenshotHelper()
    panel_detector = UnionWarPanelDetector()
    plus_matcher = RallyPlusMatcher()
    ocr = OCRClient()
    monster_validator = RallyMonsterValidator(
        ocr_client=ocr,
        monsters_config=RALLY_MONSTERS,
        data_gathering_mode=RALLY_DATA_GATHERING_MODE
    )
    hero_selector = HeroSelector()
    back_button_matcher = BackButtonMatcher()

    # Step 0: Check for leftover daily limit dialog and dismiss if present
    # This prevents infinite loop when daemon re-triggers flow with dialog still on screen
    if _check_daily_limit_dialog(win, timeout=0.5):
        print("[RALLY-JOIN] Daily limit dialog detected at flow start - dismissing")
        adb.tap(*CANCEL_CLICK)  # Click Cancel
        time.sleep(0.5)
        _cleanup_and_exit(adb, win, back_button_matcher)
        return {'success': False, 'monster_name': None}

    # Step 1: Validate panel state
    print("[RALLY-JOIN] Step 1: Validating panel state")
    frame = win.get_screenshot_cv2()
    _save_debug_screenshot(frame, "01_panel_check")

    valid, message, details = panel_detector.validate_panel_state(frame)
    print(f"[RALLY-JOIN]   Panel validation: {message}")
    print(f"[RALLY-JOIN]   Details: heading={details['heading_present']} (score={details['heading_score']:.4f}), " +
          f"tab={details['tab_selected']} (score={details['tab_score']:.4f})")

    if not valid:
        print(f"[RALLY-JOIN] Panel not valid: {message}. Exiting.")
        _cleanup_and_exit(adb, win, back_button_matcher)
        return {'success': False, 'monster_name': None}

    # Step 2: Find all plus buttons
    print("[RALLY-JOIN] Step 2: Finding rally plus buttons")
    plus_buttons = plus_matcher.find_all_plus_buttons(frame)
    print(f"[RALLY-JOIN]   Found {len(plus_buttons)} plus button(s)")

    if not plus_buttons:
        print("[RALLY-JOIN] No rallies available. Exiting.")
        _cleanup_and_exit(adb, win, back_button_matcher)
        return {'success': False, 'monster_name': None}

    # Log all detected plus buttons
    for i, (x, y, score) in enumerate(plus_buttons):
        print(f"[RALLY-JOIN]   Rally {i}: plus at ({x}, {y}), score={score:.4f}")

    # Step 3: Validate monsters and find first match
    print("[RALLY-JOIN] Step 3: Validating monsters")
    matched_rally = None

    for i, (plus_x, plus_y, plus_score) in enumerate(plus_buttons):
        print(f"[RALLY-JOIN]   Checking rally {i} at ({plus_x}, {plus_y})")

        # Validate monster
        should_join, monster_name, level, raw_text = monster_validator.validate_monster(
            frame, plus_x, plus_y, rally_index=i
        )

        print(f"[RALLY-JOIN]     OCR text: {raw_text!r}")
        if monster_name and level is not None:
            print(f"[RALLY-JOIN]     Parsed: {monster_name} Lv.{level}")
            print(f"[RALLY-JOIN]     Should join: {should_join}")

        if should_join:
            matched_rally = (plus_x, plus_y, monster_name, level)
            print(f"[RALLY-JOIN]   MATCH FOUND: {monster_name} Lv.{level} at rally {i}")
            break

    if not matched_rally:
        print("[RALLY-JOIN] No matching rallies found. Exiting.")
        _cleanup_and_exit(adb, win, back_button_matcher)
        return {'success': False, 'monster_name': None}

    plus_x, plus_y, monster_name, level = matched_rally

    # Step 4: Click the plus button (VERIFY it's still there)
    print(f"[RALLY-JOIN] Step 4: Clicking plus button for {monster_name} Lv.{level}")

    # Re-detect plus button to verify it's still there
    frame = win.get_screenshot_cv2()
    plus_buttons = plus_matcher.find_all_plus_buttons(frame)
    target_found = any(abs(px - plus_x) < 50 and abs(py - plus_y) < 50
                       for px, py, _ in plus_buttons)

    if not target_found:
        print("[RALLY-JOIN] Plus button no longer at expected position, aborting")
        _cleanup_and_exit(adb, win, back_button_matcher)
        return {'success': False, 'monster_name': monster_name}

    click_x, click_y = plus_matcher.get_click_position(plus_x, plus_y)
    adb.tap(click_x, click_y)

    # Wait for Team Up panel to fully load (polling instead of fixed sleep)
    frame = _wait_for_team_up_panel(win, timeout=5.0)
    if frame is None:
        print("[RALLY-JOIN] Failed to load Team Up panel. Exiting.")
        _cleanup_and_exit(adb, win, back_button_matcher)
        return {'success': False, 'monster_name': monster_name}

    _save_debug_screenshot(frame, "02_after_plus_click")

    # DEBUG: Save the EXACT frame we're passing to hero selector
    cv2.imwrite("zz_detection_frame.png", frame)

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
        _cleanup_and_exit(adb, win, back_button_matcher)
        return {'success': False, 'monster_name': monster_name}

    print(f"[RALLY-JOIN]   Idle hero found at slot {idle_slot['id']}, clicking")
    adb.tap(*idle_slot['click'])
    time.sleep(0.3)

    frame = win.get_screenshot_cv2()
    _save_debug_screenshot(frame, "03_after_hero_select")

    # Step 6: Click Team Up button (poll for it at fixed region)
    print("[RALLY-JOIN] Step 6: Clicking Team Up button")

    team_up_template = cv2.imread(str(TEAM_UP_TEMPLATE_PATH))
    if team_up_template is None:
        print("[RALLY-JOIN] WARNING: team_up_button_4k.png not found, aborting")
        _cleanup_and_exit(adb, win, back_button_matcher)
        return {'success': False, 'monster_name': monster_name}

    # Poll for Team Up button at fixed region (3s timeout)
    found, frame = _poll_for_button(win, team_up_template, TEAM_UP_REGION,
                                     TEAM_UP_CLICK, "Team Up button", timeout=3.0)
    if not found:
        print("[RALLY-JOIN] Team Up button not found at expected region, aborting")
        _cleanup_and_exit(adb, win, back_button_matcher)
        return {'success': False, 'monster_name': monster_name}

    # Click at fixed position (button is always here when found)
    adb.tap(*TEAM_UP_CLICK)

    # Step 6b: Check for daily limit dialog
    if _check_daily_limit_dialog(win, timeout=2.0):
        print(f"[RALLY-JOIN]   Daily limit reached for {monster_name}!")

        # Poll for Cancel button at fixed region (2s timeout)
        cancel_template = cv2.imread(str(CANCEL_BUTTON_TEMPLATE_PATH))
        if cancel_template is not None:
            found, frame = _poll_for_button(win, cancel_template, CANCEL_REGION,
                                            CANCEL_CLICK, "Cancel button", timeout=2.0, threshold=0.1)
            if found:
                adb.tap(*CANCEL_CLICK)
            else:
                print("[RALLY-JOIN]   Cancel button not at expected region, clicking back instead")
                back_button_matcher.click(adb)
        else:
            print("[RALLY-JOIN]   Cancel template not found, clicking back instead")
            back_button_matcher.click(adb)
        time.sleep(0.5)

        # Mark monster as exhausted for today (only if track_daily_limit is True)
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
    _save_debug_screenshot(frame, "04_after_team_up")

    # Step 7: Cleanup and return
    print("[RALLY-JOIN] Step 7: Cleanup and return to base")
    _cleanup_and_exit(adb, win, back_button_matcher)

    print(f"[RALLY-JOIN] Successfully joined {monster_name} Lv.{level} rally")
    return {'success': True, 'monster_name': monster_name}


def _cleanup_and_exit(adb: ADBHelper, win: WindowsScreenshotHelper, back_button_matcher: BackButtonMatcher):
    """
    Click back buttons and return to town.

    NO blind clicks - only click where back button is verified via template matching.
    The return_to_base_view() handles any remaining cleanup.

    Args:
        adb: ADB helper
        win: Screenshot helper
        back_button_matcher: Back button matcher
    """
    # Click back button up to 3 times (VERIFIED via matcher)
    for attempt in range(3):
        time.sleep(0.3)
        frame = win.get_screenshot_cv2()
        back_present, score = back_button_matcher.is_present(frame)

        if back_present:
            print(f"[RALLY-JOIN]   Clicking back button (attempt {attempt+1}, score={score:.4f})")
            back_button_matcher.click(adb)
            time.sleep(0.5)
        else:
            break

    # Return to base view (robust recovery)
    return_to_base_view(adb, win, debug=False)


def _save_debug_screenshot(frame, label: str):
    """
    Save debug screenshot with timestamp and label.

    Args:
        frame: BGR screenshot
        label: Description label for filename
    """
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{label}.png"
    filepath = DEBUG_DIR / filename
    cv2.imwrite(str(filepath), frame)
