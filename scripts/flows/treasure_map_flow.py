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
"""
import time

import cv2

from utils.treasure_chat_notification_matcher import TreasureChatNotificationMatcher
from utils.treasure_dig_matchers import (
    TreasureDiggingMarkerMatcher,
    GatherButtonMatcher,
    MarchButtonMatcher,
    ZzSleepIconMatcher,
    TreasureReadyCircleMatcher,
)
from utils.back_button_matcher import BackButtonMatcher

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


def treasure_map_flow(adb):
    """
    Handle full treasure hunting sequence.

    Args:
        adb: ADBHelper instance

    Returns:
        bool: True if treasure was collected, False otherwise
    """
    print(f"    [FLOW] Treasure map: clicking icon ({CLICK_X}, {CLICK_Y})")
    adb.tap(CLICK_X, CLICK_Y)

    # Step 1: Wait for and click chat notification
    time.sleep(INITIAL_DELAY)
    if not _wait_and_click_chat_notification(adb):
        return False

    # Step 2: Wait for map to load and click on treasure
    time.sleep(2.0)  # Wait for map navigation
    if not _wait_and_click_digging_marker(adb):
        return False

    # Step 3: Click Gather button
    time.sleep(1.0)
    if not _wait_and_click_gather(adb):
        return False

    # Step 4: Select character (rightmost Zz) and click March
    time.sleep(0.5)
    if not _select_character_and_march(adb):
        return False

    # Step 5: Wait for march to complete and collect treasure
    if not _wait_and_collect_treasure(adb):
        return False

    # Step 6: Click back button to exit
    time.sleep(1.0)
    _click_back_until_gone(adb)

    # Step 7: Return to town and verify
    time.sleep(1.0)
    if not _return_to_town(adb):
        print("    [FLOW] Warning: Could not verify return to town")

    print("    [FLOW] Treasure collected successfully!")
    return True


def _wait_and_click_chat_notification(adb) -> bool:
    """Wait for chat notification and click Kingdom link."""
    notification_matcher = TreasureChatNotificationMatcher()

    for attempt in range(MAX_ATTEMPTS):
        screenshot_path = adb.take_screenshot("treasure_flow_check.png")
        frame = cv2.imread(screenshot_path)

        if frame is None:
            time.sleep(CHECK_INTERVAL)
            continue

        is_present, score, found_pos = notification_matcher.is_present(frame)

        if is_present and found_pos:
            click_x, click_y = notification_matcher.get_click_position(found_pos)
            print(f"    [FLOW] Chat notification found at {found_pos}, score={score:.4f}")
            print(f"    [FLOW] Clicking Kingdom link at ({click_x}, {click_y})")
            adb.tap(click_x, click_y)
            return True

        print(f"    [FLOW] Waiting for chat notification... ({attempt + 1}/{MAX_ATTEMPTS})")
        time.sleep(CHECK_INTERVAL)

    print("    [FLOW] Chat notification not found")
    return False


def _wait_and_click_digging_marker(adb) -> bool:
    """Wait for treasure digging marker and click it."""
    marker_matcher = TreasureDiggingMarkerMatcher()

    for attempt in range(MAX_ATTEMPTS):
        screenshot_path = adb.take_screenshot("treasure_flow_check.png")
        frame = cv2.imread(screenshot_path)

        if frame is None:
            time.sleep(CHECK_INTERVAL)
            continue

        is_present, score = marker_matcher.is_present(frame)

        if is_present:
            print(f"    [FLOW] Digging marker found, score={score:.4f}")
            print(f"    [FLOW] Clicking treasure at ({marker_matcher.CLICK_X}, {marker_matcher.CLICK_Y})")
            marker_matcher.click(adb)
            return True

        print(f"    [FLOW] Waiting for digging marker... ({attempt + 1}/{MAX_ATTEMPTS})")
        time.sleep(CHECK_INTERVAL)

    print("    [FLOW] Digging marker not found")
    return False


def _wait_and_click_gather(adb) -> bool:
    """Wait for Gather button and click it."""
    gather_matcher = GatherButtonMatcher()

    for attempt in range(MAX_ATTEMPTS):
        screenshot_path = adb.take_screenshot("treasure_flow_check.png")
        frame = cv2.imread(screenshot_path)

        if frame is None:
            time.sleep(CHECK_INTERVAL)
            continue

        is_present, score = gather_matcher.is_present(frame)

        if is_present:
            print(f"    [FLOW] Gather button found, score={score:.4f}")
            print(f"    [FLOW] Clicking Gather at ({gather_matcher.CLICK_X}, {gather_matcher.CLICK_Y})")
            gather_matcher.click(adb)
            return True

        print(f"    [FLOW] Waiting for Gather button... ({attempt + 1}/{MAX_ATTEMPTS})")
        time.sleep(CHECK_INTERVAL)

    print("    [FLOW] Gather button not found")
    return False


def _select_character_and_march(adb) -> bool:
    """Select rightmost idle character and click March."""
    zz_matcher = ZzSleepIconMatcher()
    march_matcher = MarchButtonMatcher()

    for attempt in range(MAX_ATTEMPTS):
        screenshot_path = adb.take_screenshot("treasure_flow_check.png")
        frame = cv2.imread(screenshot_path)

        if frame is None:
            time.sleep(CHECK_INTERVAL)
            continue

        # First check if March button is visible (indicates we're on march screen)
        march_present, march_score = march_matcher.is_present(frame)

        if march_present:
            # Find and click rightmost Zz icon
            zz_pos = zz_matcher.find_rightmost_zz(frame)
            if zz_pos:
                print(f"    [FLOW] Found rightmost Zz at ({zz_pos[0]}, {zz_pos[1]})")
                adb.tap(zz_pos[0], zz_pos[1])
                time.sleep(0.5)

                # Take new screenshot and click March
                screenshot_path = adb.take_screenshot("treasure_flow_check.png")
                frame = cv2.imread(screenshot_path)
                march_present, _ = march_matcher.is_present(frame)

                if march_present:
                    print(f"    [FLOW] Clicking March at ({march_matcher.CLICK_X}, {march_matcher.CLICK_Y})")
                    march_matcher.click(adb)
                    return True
            else:
                # No Zz found, maybe all characters are busy - just click March anyway
                print("    [FLOW] No Zz icon found, clicking March anyway")
                march_matcher.click(adb)
                return True

        print(f"    [FLOW] Waiting for march screen... ({attempt + 1}/{MAX_ATTEMPTS})")
        time.sleep(CHECK_INTERVAL)

    print("    [FLOW] March screen not found")
    return False


def _wait_and_collect_treasure(adb) -> bool:
    """Wait for treasure to be ready and collect it, keep clicking until circle turns white."""
    ready_matcher = TreasureReadyCircleMatcher()

    start_time = time.time()
    check_count = 0

    # Phase 1: Wait for blue circle to appear
    while (time.time() - start_time) < MAX_MARCH_WAIT_SECONDS:
        check_count += 1
        screenshot_path = adb.take_screenshot("treasure_flow_check.png")
        frame = cv2.imread(screenshot_path)

        if frame is None:
            time.sleep(MARCH_PROGRESS_CHECK_INTERVAL)
            continue

        is_present, score = ready_matcher.is_present(frame)

        if is_present:
            print(f"    [FLOW] Blue circle found! score={score:.4f}")
            print(f"    [FLOW] Clicking to collect at ({ready_matcher.CLICK_X}, {ready_matcher.CLICK_Y})")
            ready_matcher.click(adb)

            # Phase 2: Keep clicking until blue circle is gone (turns white = collected)
            time.sleep(0.5)
            for click_attempt in range(10):
                screenshot_path = adb.take_screenshot("treasure_flow_check.png")
                frame = cv2.imread(screenshot_path)

                if frame is None:
                    time.sleep(0.5)
                    continue

                still_blue, score = ready_matcher.is_present(frame)

                if not still_blue:
                    print(f"    [FLOW] Circle turned white - treasure collected!")
                    return True

                print(f"    [FLOW] Still blue (score={score:.4f}), clicking again...")
                ready_matcher.click(adb)
                time.sleep(0.5)

            # After 10 attempts, assume collected
            print("    [FLOW] Assuming treasure collected after multiple clicks")
            return True

        elapsed = int(time.time() - start_time)
        if check_count % 10 == 0:  # Only log every 10 checks to reduce spam
            print(f"    [FLOW] Waiting for treasure... ({elapsed}s elapsed, check #{check_count})")
        time.sleep(MARCH_PROGRESS_CHECK_INTERVAL)

    print(f"    [FLOW] Timed out waiting for treasure after {MAX_MARCH_WAIT_SECONDS}s")
    return False


def _click_back_until_gone(adb) -> None:
    """Click back button repeatedly until it's no longer visible."""
    back_matcher = BackButtonMatcher()

    for click_num in range(BACK_BUTTON_MAX_CLICKS):
        screenshot_path = adb.take_screenshot("treasure_flow_check.png")
        frame = cv2.imread(screenshot_path)

        if frame is None:
            time.sleep(CHECK_INTERVAL)
            continue

        is_present, score = back_matcher.is_present(frame)

        if not is_present:
            print(f"    [FLOW] Back button gone after {click_num} clicks")
            return

        print(f"    [FLOW] Clicking back button (click #{click_num + 1})")
        back_matcher.click(adb)
        time.sleep(0.5)

    print(f"    [FLOW] Back button still visible after {BACK_BUTTON_MAX_CLICKS} clicks")


def _return_to_town(adb) -> bool:
    """Switch to town view using view_state_detector."""
    from utils.view_state_detector import go_to_town
    return go_to_town(adb, debug=False)
