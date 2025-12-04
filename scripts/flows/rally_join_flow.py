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


def rally_join_flow(adb: ADBHelper) -> bool:
    """
    Main rally joining flow.

    Assumes Union War panel is already open.

    Args:
        adb: ADB helper instance

    Returns:
        True if successfully joined a rally, False otherwise
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
        return False

    # Step 2: Find all plus buttons
    print("[RALLY-JOIN] Step 2: Finding rally plus buttons")
    plus_buttons = plus_matcher.find_all_plus_buttons(frame)
    print(f"[RALLY-JOIN]   Found {len(plus_buttons)} plus button(s)")

    if not plus_buttons:
        print("[RALLY-JOIN] No rallies available. Exiting.")
        _cleanup_and_exit(adb, win, back_button_matcher)
        return False

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
            print(f"[RALLY-JOIN]   ✓ MATCH FOUND: {monster_name} Lv.{level} at rally {i}")
            break

    if not matched_rally:
        print("[RALLY-JOIN] No matching rallies found. Exiting.")
        _cleanup_and_exit(adb, win, back_button_matcher)
        return False

    plus_x, plus_y, monster_name, level = matched_rally

    # Step 4: Click the plus button
    print(f"[RALLY-JOIN] Step 4: Clicking plus button for {monster_name} Lv.{level}")
    click_x, click_y = plus_matcher.get_click_position(plus_x, plus_y)
    adb.tap(click_x, click_y)
    time.sleep(0.5)

    frame = win.get_screenshot_cv2()
    _save_debug_screenshot(frame, "02_after_plus_click")

    # Step 5: Select leftmost hero (any hero can join rally)
    print("[RALLY-JOIN] Step 5: Selecting leftmost hero")
    idle_slot = hero_selector.find_leftmost_idle(frame, require_zz=False)

    if not idle_slot:
        print("[RALLY-JOIN] No heroes available. Aborting rally join.")
        _cleanup_and_exit(adb, win, back_button_matcher)
        return False

    print(f"[RALLY-JOIN]   Hero found at slot {idle_slot['id']}, clicking")
    adb.tap(*idle_slot['click'])
    time.sleep(0.3)

    frame = win.get_screenshot_cv2()
    _save_debug_screenshot(frame, "03_after_hero_select")

    # Step 6: Click Team Up button (fire-and-forget)
    print("[RALLY-JOIN] Step 6: Clicking Team Up button")
    # Use fixed Team Up button position (similar to treasure map flow)
    # TODO: Create TeamUpButtonMatcher if needed, for now use known position
    TEAM_UP_X = 1919  # From hero upgrade flow
    TEAM_UP_Y = 1829
    adb.tap(TEAM_UP_X, TEAM_UP_Y)
    time.sleep(0.5)

    frame = win.get_screenshot_cv2()
    _save_debug_screenshot(frame, "04_after_team_up")

    # Step 7: Cleanup and return
    print("[RALLY-JOIN] Step 7: Cleanup and return to base")
    _cleanup_and_exit(adb, win, back_button_matcher)

    print(f"[RALLY-JOIN] ✓ Successfully joined {monster_name} Lv.{level} rally")
    return True


def _cleanup_and_exit(adb: ADBHelper, win: WindowsScreenshotHelper, back_button_matcher: BackButtonMatcher):
    """
    Click back buttons and return to town.

    Args:
        adb: ADB helper
        win: Screenshot helper
        back_button_matcher: Back button matcher
    """
    # Click back button up to 2 times to close dialogs
    for attempt in range(2):
        time.sleep(0.3)
        frame = win.get_screenshot_cv2()
        back_present, _ = back_button_matcher.is_present(frame)

        if back_present:
            print(f"[RALLY-JOIN]   Clicking back button (attempt {attempt+1})")
            back_button_matcher.click(adb)
            time.sleep(0.5)
        else:
            break

    # Return to base view
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
