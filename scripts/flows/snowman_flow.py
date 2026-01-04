"""
Snowman Party flow - handles the full snowman prize claiming sequence.

Sequence:
1. Detect "Snowman Party" chat message
2. Click on chat message to navigate to snowman location
3. Wait for snowman to appear, verify arrival
4. (PLACEHOLDER) Click claim bubble above snowman
5. Return to base view

NOTE: Claim bubble step is a placeholder - template will be added later.

DEBUG: This flow saves screenshots at every step to templates/debug/snowman_flow/
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import numpy.typing as npt

from utils.debug_screenshot import save_debug_screenshot
from utils.return_to_base_view import return_to_base_view
from utils.snowman_chat_matcher import SnowmanChatMatcher
from utils.snowman_matcher import SnowmanMatcher
from utils.windows_screenshot_helper import WindowsScreenshotHelper

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

# Setup logger
logger = logging.getLogger("snowman_flow")

# Flow name for debug screenshots
FLOW_NAME = "snowman"

# Timing constants
INITIAL_DELAY = 1.0
CHECK_INTERVAL = 0.5
MAX_ATTEMPTS = 15
NAV_WAIT_SECONDS = 3.0  # Wait for map navigation after clicking chat


def _save_debug_screenshot(frame: npt.NDArray[Any], name: str) -> str:
    """Save screenshot for debugging. Returns path."""
    return save_debug_screenshot(frame, FLOW_NAME, name)


def _log(msg: str) -> None:
    """Log to both logger and stdout."""
    logger.info(msg)
    print(f"    [SNOWMAN] {msg}")


def snowman_flow(adb: ADBHelper) -> bool:
    """
    Handle full snowman prize claiming sequence.

    Args:
        adb: ADBHelper instance

    Returns:
        bool: True if prize was claimed, False otherwise
    """
    flow_start = time.time()
    _log("=== SNOWMAN FLOW START ===")

    win = WindowsScreenshotHelper()

    # Step 1: Find and click "Snowman Party" chat message
    _log("Step 1: Looking for 'Snowman Party' chat message...")
    chat_clicked = _wait_and_click_chat_message(adb, win)
    if not chat_clicked:
        _log(f"FAILED at Step 1 (chat message) after {time.time() - flow_start:.1f}s")
        return False

    # Step 2: Wait for navigation and verify snowman is visible
    time.sleep(NAV_WAIT_SECONDS)
    _log("Step 2: Verifying snowman is visible...")
    snowman_pos = _wait_for_snowman(adb, win)
    if not snowman_pos:
        _log(f"FAILED at Step 2 (snowman not found) after {time.time() - flow_start:.1f}s")
        return_to_base_view(adb, win)
        return False

    # Step 3: Click claim bubble (PLACEHOLDER)
    _log("Step 3: Looking for claim bubble... (PLACEHOLDER - not implemented yet)")
    # TODO: Add claim bubble detection and clicking when template is available
    # For now, just click on the snowman position to attempt interaction
    _log(f"  Clicking snowman at {snowman_pos} (placeholder action)")
    adb.tap(*snowman_pos)
    time.sleep(1.0)

    # Take debug screenshot after clicking
    frame = win.get_screenshot_cv2()
    _save_debug_screenshot(frame, "03_after_snowman_click")

    # Step 4: Return to base view
    _log("Step 4: Returning to base view...")
    return_to_base_view(adb, win)

    elapsed = time.time() - flow_start
    _log(f"=== SNOWMAN FLOW END === (took {elapsed:.1f}s)")
    return True


def _wait_and_click_chat_message(adb: ADBHelper, win: WindowsScreenshotHelper) -> bool:
    """Wait for 'Snowman Party' chat message and click it."""
    chat_matcher = SnowmanChatMatcher()

    for attempt in range(MAX_ATTEMPTS):
        frame = win.get_screenshot_cv2()
        is_present, score, found_pos = chat_matcher.is_present(frame)

        _save_debug_screenshot(frame, f"01_chat_check_{attempt+1}_score{score:.3f}")
        _log(f"  Chat check {attempt+1}/{MAX_ATTEMPTS}: present={is_present}, score={score:.4f}")

        if is_present and found_pos:
            _save_debug_screenshot(frame, f"01_chat_FOUND_score{score:.3f}")
            # found_pos is already the center of the message
            click_x, click_y = found_pos
            _log(f"  Chat message FOUND at {found_pos}, clicking at ({click_x}, {click_y})")
            adb.tap(click_x, click_y)
            return True

        time.sleep(CHECK_INTERVAL)

    _log(f"  Chat message NOT FOUND after {MAX_ATTEMPTS} attempts")
    return False


def _wait_for_snowman(
    adb: ADBHelper, win: WindowsScreenshotHelper
) -> tuple[int, int] | None:
    """Wait for snowman to appear on screen after navigation."""
    snowman_matcher = SnowmanMatcher()

    for attempt in range(MAX_ATTEMPTS):
        frame = win.get_screenshot_cv2()
        is_present, score, found_pos = snowman_matcher.is_present(frame)

        _save_debug_screenshot(frame, f"02_snowman_check_{attempt+1}_score{score:.3f}")
        _log(f"  Snowman check {attempt+1}/{MAX_ATTEMPTS}: present={is_present}, score={score:.4f}")

        if is_present and found_pos:
            _save_debug_screenshot(frame, f"02_snowman_FOUND_score{score:.3f}")
            _log(f"  Snowman FOUND at center {found_pos}")
            return found_pos

        time.sleep(CHECK_INTERVAL)

    _log(f"  Snowman NOT FOUND after {MAX_ATTEMPTS} attempts")
    return None


# Placeholder for future claim bubble detection
def _wait_and_click_claim_bubble(adb: ADBHelper, win: WindowsScreenshotHelper) -> bool:
    """
    Wait for claim bubble above snowman and click it.

    PLACEHOLDER: Not implemented - waiting for claim bubble template.
    """
    _log("  Claim bubble detection not implemented yet")
    return False


if __name__ == "__main__":
    # Test mode
    from utils.adb_helper import ADBHelper

    print("Testing Snowman Flow...")
    adb = ADBHelper()
    success = snowman_flow(adb)
    print(f"Flow result: {'SUCCESS' if success else 'FAILED'}")
