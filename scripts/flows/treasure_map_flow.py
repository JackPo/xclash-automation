"""
Treasure map flow - handles the full treasure hunting sequence.

Sequence:
1. Click treasure map icon (triggered by daemon)
2. Wait for chat notification banner to appear
3. Click on the Kingdom link to navigate to treasure location
4. Wait for map to load, then click on treasure digging marker
5. Detect Gather prompt → click Gather button
6. Detect march prompt → click rightmost Zz character
7. Click March button
8. Keep checking until blue circle (treasure ready) appears
9. Click blue circle to collect treasure
10. Click back button to exit
11. Return to town and verify

NOTE: ALL detection uses WindowsScreenshotHelper (NOT ADB screenshots).
Templates are captured with Windows screenshots - ADB has different pixel values.

DEBUG: This flow saves screenshots at every step to templates/debug/treasure_flow/
"""
from __future__ import annotations

import time
import logging
from typing import TYPE_CHECKING, Any

import numpy.typing as npt

from utils.treasure_chat_notification_matcher import TreasureChatNotificationMatcher
from utils.treasure_dig_matchers import (
    TreasureDiggingMarkerMatcher,
    GatherButtonMatcher,
    MarchButtonMatcher,
    TreasureReadyCircleMatcher,
)
from utils.back_button_matcher import BackButtonMatcher
from utils.hero_selector import HeroSelector
from utils.debug_screenshot import save_debug_screenshot

from utils.windows_screenshot_helper import WindowsScreenshotHelper

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

# Setup logger
logger = logging.getLogger("treasure_map_flow")

# Flow name for debug screenshots
FLOW_NAME = "treasure_flow"

# Fixed click coordinates for treasure map icon (4K resolution)
CLICK_X = 2175
CLICK_Y = 1621

# Timing constants
INITIAL_DELAY = 1.0
CHECK_INTERVAL = 0.5
MAX_ATTEMPTS = 15
MARCH_PROGRESS_CHECK_INTERVAL = 1.0  # Check every 1 second during march - RUSH to get it!
MAX_MARCH_WAIT_SECONDS = 600  # 10 minutes max wait for march
BACK_BUTTON_MAX_CLICKS = 5  # Max back button clicks to exit


def _save_debug_screenshot(frame: npt.NDArray[Any], name: str) -> str:
    """Save screenshot for debugging. Returns path."""
    return save_debug_screenshot(frame, FLOW_NAME, name)


def _log(msg: str) -> None:
    """Log to both logger and stdout."""
    logger.info(msg)
    print(f"    [FLOW] {msg}")


def treasure_map_flow(adb: ADBHelper) -> bool:
    """
    Handle full treasure hunting sequence.

    Args:
        adb: ADBHelper instance

    Returns:
        bool: True if treasure was collected, False otherwise
    """
    flow_start = time.time()
    _log(f"=== TREASURE FLOW START ===")
    _log(f"Clicking treasure map icon at ({CLICK_X}, {CLICK_Y})")
    adb.tap(CLICK_X, CLICK_Y)

    # Take screenshot right after clicking icon
    win = WindowsScreenshotHelper()
    time.sleep(0.3)
    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "01_after_icon_click")

    # Step 1: Wait for and click chat notification
    time.sleep(INITIAL_DELAY)
    _log("Step 1: Looking for chat notification...")
    if not _wait_and_click_chat_notification(adb):
        _log(f"FAILED at Step 1 (chat notification) after {time.time() - flow_start:.1f}s")
        return False

    # Step 2: Wait for map to load and click on treasure
    time.sleep(2.0)  # Wait for map navigation
    _log("Step 2: Looking for digging marker...")
    if not _wait_and_click_digging_marker(adb):
        _log(f"FAILED at Step 2 (digging marker) after {time.time() - flow_start:.1f}s")
        return False

    # Step 3: Click Gather button
    time.sleep(1.0)
    _log("Step 3: Looking for Gather button...")
    if not _wait_and_click_gather(adb):
        _log(f"FAILED at Step 3 (gather button) after {time.time() - flow_start:.1f}s")
        return False

    # Step 4: Select character (rightmost Zz) and click March
    time.sleep(0.5)
    _log("Step 4: Looking for march screen...")
    if not _select_character_and_march(adb):
        _log(f"FAILED at Step 4 (march screen) after {time.time() - flow_start:.1f}s")
        return False

    # Step 5: Wait for march to complete and collect treasure
    _log("Step 5: Waiting for treasure to be ready...")
    if not _wait_and_collect_treasure(adb):
        _log(f"FAILED at Step 5 (collect treasure) after {time.time() - flow_start:.1f}s")
        return False

    # Step 6: Return to base view
    time.sleep(1.0)
    _log("Step 6: Returning to base view...")
    from utils.return_to_base_view import return_to_base_view
    return_to_base_view(adb, win, debug=False)

    elapsed = time.time() - flow_start
    _log(f"=== TREASURE FLOW SUCCESS === (took {elapsed:.1f}s)")
    return True


def _wait_and_click_chat_notification(adb: ADBHelper) -> bool:
    """Wait for chat notification and click Kingdom link. Scrolls up if not visible."""

    notification_matcher = TreasureChatNotificationMatcher()
    win = WindowsScreenshotHelper()

    # Chat scroll parameters - swipe UP to reveal content BELOW (treasure notification)
    CHAT_CENTER_X = 1920
    CHAT_SWIPE_START_Y = 1400  # Start lower (bottom)
    CHAT_SWIPE_END_Y = 800     # End higher (top) = swipe UP
    MAX_SCROLL_ATTEMPTS = 5
    CHECKS_BEFORE_SCROLL = 2   # Check twice before scrolling

    scroll_count = 0
    check_count = 0

    for attempt in range(MAX_ATTEMPTS + MAX_SCROLL_ATTEMPTS * CHECKS_BEFORE_SCROLL):
        frame = win.get_screenshot_cv2()

        is_present, score, found_pos = notification_matcher.is_present(frame)

        # Save every attempt for debugging
        _save_debug_screenshot(frame, f"02_chat_check_{attempt+1}_score{score:.3f}")

        _log(f"  Chat check {attempt+1}: present={is_present}, score={score:.4f}, pos={found_pos}")

        if is_present and found_pos:
            click_x, click_y = notification_matcher.get_click_position(found_pos)
            _save_debug_screenshot(frame, f"03_chat_FOUND_score{score:.3f}")
            _log(f"  Chat notification FOUND at {found_pos}, clicking Kingdom link at ({click_x}, {click_y})")
            adb.tap(click_x, click_y)
            return True

        check_count += 1

        # After CHECKS_BEFORE_SCROLL checks without finding, scroll up
        if check_count >= CHECKS_BEFORE_SCROLL and scroll_count < MAX_SCROLL_ATTEMPTS:
            _log(f"  Not found, scrolling UP in chat (scroll {scroll_count+1}/{MAX_SCROLL_ATTEMPTS})...")
            adb.swipe(CHAT_CENTER_X, CHAT_SWIPE_START_Y, CHAT_CENTER_X, CHAT_SWIPE_END_Y, duration=300)
            scroll_count += 1
            check_count = 0
            time.sleep(0.5)  # Wait for scroll animation
            continue

        time.sleep(CHECK_INTERVAL)

    _log(f"  Chat notification NOT FOUND after {MAX_ATTEMPTS} attempts and {scroll_count} scrolls")
    return False


def _wait_and_click_digging_marker(adb: ADBHelper) -> bool:
    """Wait for treasure digging marker and click it."""

    marker_matcher = TreasureDiggingMarkerMatcher()
    win = WindowsScreenshotHelper()

    for attempt in range(MAX_ATTEMPTS):
        frame = win.get_screenshot_cv2()

        is_present, score = marker_matcher.is_present(frame)

        # Save every attempt for debugging
        _save_debug_screenshot(frame, f"04_marker_check_{attempt+1}_score{score:.3f}")

        _log(f"  Marker check {attempt+1}/{MAX_ATTEMPTS}: present={is_present}, score={score:.4f}, threshold={marker_matcher.threshold}")

        if is_present:
            _save_debug_screenshot(frame, f"05_marker_FOUND_score{score:.3f}")
            _log(f"  Digging marker FOUND, clicking at ({marker_matcher.CLICK_X}, {marker_matcher.CLICK_Y})")
            marker_matcher.click(adb)
            return True

        time.sleep(CHECK_INTERVAL)

    _log(f"  Digging marker NOT FOUND after {MAX_ATTEMPTS} attempts")
    return False


def _wait_and_click_gather(adb: ADBHelper) -> bool:
    """Wait for Gather button and click it."""

    gather_matcher = GatherButtonMatcher()
    win = WindowsScreenshotHelper()

    for attempt in range(MAX_ATTEMPTS):
        frame = win.get_screenshot_cv2()

        is_present, score = gather_matcher.is_present(frame)

        # Save every attempt for debugging
        _save_debug_screenshot(frame, f"06_gather_check_{attempt+1}_score{score:.3f}")

        _log(f"  Gather check {attempt+1}/{MAX_ATTEMPTS}: present={is_present}, score={score:.4f}, threshold={gather_matcher.threshold}")

        if is_present:
            _save_debug_screenshot(frame, f"07_gather_FOUND_score{score:.3f}")
            _log(f"  Gather button FOUND, clicking at ({gather_matcher.CLICK_X}, {gather_matcher.CLICK_Y})")
            gather_matcher.click(adb)
            return True

        time.sleep(CHECK_INTERVAL)

    _log(f"  Gather button NOT FOUND after {MAX_ATTEMPTS} attempts")
    return False


def _select_character_and_march(adb: ADBHelper) -> bool:
    """Select rightmost character (prefer idle with Zz, but fallback to any) and click March."""

    hero_selector = HeroSelector()
    march_matcher = MarchButtonMatcher()
    win = WindowsScreenshotHelper()

    for attempt in range(MAX_ATTEMPTS):
        frame = win.get_screenshot_cv2()

        # First check if March button is visible (indicates we're on march screen)
        march_present, march_score = march_matcher.is_present(frame)

        # Save every attempt for debugging
        _save_debug_screenshot(frame, f"08_march_check_{attempt+1}_score{march_score:.3f}")

        _log(f"  March check {attempt+1}/{MAX_ATTEMPTS}: present={march_present}, score={march_score:.4f}, threshold={march_matcher.threshold}")

        if march_present:
            _save_debug_screenshot(frame, f"09_march_FOUND_score{march_score:.3f}")

            # Find rightmost hero (prefer Zz, but fallback to any hero if no Zz exists)
            slot = hero_selector.find_rightmost_idle(frame, zz_mode='prefer')
            if slot:
                _log(f"  Found rightmost hero at slot {slot['id']}, clicking {slot['click']}...")
                adb.tap(*slot['click'])
                time.sleep(0.5)

                # Take new screenshot and click March
                frame = win.get_screenshot_cv2()
                if frame is not None:
                    _save_debug_screenshot(frame, "10_after_hero_click")
                march_present, _ = march_matcher.is_present(frame)

                if march_present:
                    _log(f"  Clicking March at ({march_matcher.CLICK_X}, {march_matcher.CLICK_Y})")
                    march_matcher.click(adb)
                    return True
            else:
                # Should never happen since zz_mode='prefer' always returns a slot
                _log("  ERROR: No hero slot found (should not happen with zz_mode='prefer')")
                return False

        time.sleep(CHECK_INTERVAL)

    _log(f"  March screen NOT FOUND after {MAX_ATTEMPTS} attempts")
    return False


def _wait_and_collect_treasure(adb: ADBHelper) -> bool:
    """Wait for treasure to be ready and collect it, keep clicking until circle turns white."""

    ready_matcher = TreasureReadyCircleMatcher()
    win = WindowsScreenshotHelper()

    start_time = time.time()
    check_count = 0
    last_screenshot_time = 0.0

    _log(f"  Waiting up to {MAX_MARCH_WAIT_SECONDS}s for blue circle (threshold={ready_matcher.threshold})")

    # Phase 1: Wait for blue circle to appear
    frame: npt.NDArray[Any] | None = None
    while (time.time() - start_time) < MAX_MARCH_WAIT_SECONDS:
        check_count += 1
        frame = win.get_screenshot_cv2()

        is_present, score = ready_matcher.is_present(frame)
        elapsed = int(time.time() - start_time)

        # Save screenshot every 30 seconds during wait
        if time.time() - last_screenshot_time >= 30:
            _save_debug_screenshot(frame, f"11_waiting_{elapsed}s_score{score:.3f}")
            last_screenshot_time = time.time()
            _log(f"  Waiting... {elapsed}s elapsed, check #{check_count}, score={score:.4f}")

        if is_present:
            _save_debug_screenshot(frame, f"12_blue_circle_FOUND_score{score:.3f}")
            _log(f"  Blue circle FOUND after {elapsed}s! score={score:.4f}")
            _log(f"  Clicking to collect at ({ready_matcher.CLICK_X}, {ready_matcher.CLICK_Y})")
            ready_matcher.click(adb)

            # Phase 2: Keep clicking until blue circle is CONFIRMED gone
            # Require 3 consecutive "not blue" frames to prevent false positives
            # from click animations causing score fluctuations
            time.sleep(0.5)
            consecutive_not_blue = 0
            REQUIRED_CONSECUTIVE = 3

            for click_attempt in range(20):  # Increased from 10
                frame = win.get_screenshot_cv2()

                still_blue, score = ready_matcher.is_present(frame)
                _save_debug_screenshot(frame, f"13_collect_click_{click_attempt+1}_score{score:.3f}")

                if not still_blue:
                    consecutive_not_blue += 1
                    _log(f"  Not blue ({consecutive_not_blue}/{REQUIRED_CONSECUTIVE}), score={score:.4f}")
                    if consecutive_not_blue >= REQUIRED_CONSECUTIVE:
                        _save_debug_screenshot(frame, "14_treasure_COLLECTED")
                        _log(f"  Circle gone for {REQUIRED_CONSECUTIVE} consecutive checks - COLLECTED!")
                        return True
                else:
                    # Reset counter if blue detected again
                    consecutive_not_blue = 0
                    _log(f"  Still blue (score={score:.4f}), clicking again ({click_attempt+1}/20)...")
                    ready_matcher.click(adb)

                time.sleep(0.5)

            # After 20 attempts without 3 consecutive "not blue", warn but still return True
            # (better to proceed than get stuck)
            _log("  WARNING: Could not confirm collection after 20 attempts - proceeding anyway")
            return True

        time.sleep(MARCH_PROGRESS_CHECK_INTERVAL)

    if frame is not None:
        _save_debug_screenshot(frame, f"15_TIMEOUT_after_{MAX_MARCH_WAIT_SECONDS}s")
    _log(f"  TIMEOUT waiting for treasure after {MAX_MARCH_WAIT_SECONDS}s")
    return False


def _click_back_until_gone(adb: ADBHelper) -> None:
    """Click back button repeatedly until it's no longer visible."""

    back_matcher = BackButtonMatcher()
    win = WindowsScreenshotHelper()

    for click_num in range(BACK_BUTTON_MAX_CLICKS):
        frame = win.get_screenshot_cv2()

        is_present, score = back_matcher.is_present(frame)
        _save_debug_screenshot(frame, f"16_back_check_{click_num+1}_score{score:.3f}")
        _log(f"  Back check {click_num+1}: present={is_present}, score={score:.4f}")

        if not is_present:
            _log(f"  Back button gone after {click_num} clicks")
            return

        _log(f"  Clicking back button (click #{click_num + 1})")
        back_matcher.click(adb)
        time.sleep(0.5)

    _log(f"  Back button still visible after {BACK_BUTTON_MAX_CLICKS} clicks")


def _return_to_town(adb: ADBHelper) -> bool:
    """Switch to town view using view_state_detector."""
    from utils.view_state_detector import go_to_town
    return go_to_town(adb, debug=False)
