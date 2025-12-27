"""
Elite Zombie Rally flow - automated elite zombie rallying sequence.

Trigger Conditions:
- Stamina >= 118
- User idle for 5+ minutes

Sequence:
1. Go to World Map (if not already there)
2. Click Magnifying Glass (search button)
3. Click Elite Zombie tab
4. Click Plus button N times (increase level, configurable via ELITE_ZOMBIE_PLUS_CLICKS)
5. Click Search button
6. Click Rally button
7. Select rightmost hero with Zz (idle) using hero_selector
8. Click Team Up button

NOTE: ALL detection uses WindowsScreenshotHelper (NOT ADB screenshots).
Templates are captured with Windows screenshots - ADB has different pixel values.
"""
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Add parent dirs to path for imports
_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import cv2

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.view_state_detector import detect_view, go_to_world, ViewState
from utils.hero_selector import HeroSelector
from config import ELITE_ZOMBIE_PLUS_CLICKS

# Setup logger
logger = logging.getLogger("elite_zombie_flow")

# Debug output directory
DEBUG_DIR = Path(__file__).parent.parent.parent / "templates" / "debug" / "elite_zombie_flow"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

# Fixed click coordinates (4K resolution) - all from plan
MAGNIFYING_GLASS_CLICK = (88, 1486)
ELITE_ZOMBIE_TAB_CLICK = (2062, 1095)
PLUS_BUTTON_CLICK = (2232, 1875)
SEARCH_BUTTON_CLICK = (1914, 2018)
RALLY_BUTTON_CLICK = (1915, 1682)
TEAM_UP_BUTTON_CLICK = (1912, 1648)

# Timing constants
CLICK_DELAY = 0.3  # Delay after each click
PLUS_CLICK_DELAY = 0.2  # Faster delay for plus button spam
SCREEN_TRANSITION_DELAY = 1.0  # Delay for screen transitions
SEARCH_RESULT_DELAY = 2.0  # Delay for search results to appear
RALLY_SCREEN_DELAY = 1.5  # Delay for rally screen to appear


def _save_debug_screenshot(frame, name: str) -> str:
    """Save screenshot for debugging. Returns path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = DEBUG_DIR / f"{timestamp}_{name}.png"
    cv2.imwrite(str(path), frame)
    return str(path)


def _log(msg: str):
    """Log to both logger and stdout."""
    logger.info(msg)
    print(f"    [ELITE_ZOMBIE] {msg}")


def elite_zombie_flow(adb) -> bool:
    """
    Execute the elite zombie rally flow.

    Args:
        adb: ADBHelper instance

    Returns:
        bool: True if flow completed successfully, False otherwise
    """
    flow_start = time.time()
    _log("=== ELITE ZOMBIE FLOW START ===")

    win = WindowsScreenshotHelper()

    # Step 0: Ensure we're in WORLD view
    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "00_initial_state")
        state, score = detect_view(frame)
        _log(f"Current view: {state.name} (score={score:.4f})")

        if state != ViewState.WORLD:
            _log("Not in WORLD view, navigating...")
            if not go_to_world(adb, debug=False):
                _log("FAILED: Could not navigate to WORLD view")
                return False
            time.sleep(SCREEN_TRANSITION_DELAY)

    # Step 1: Click magnifying glass
    _log(f"Step 1: Clicking magnifying glass at {MAGNIFYING_GLASS_CLICK}")
    adb.tap(*MAGNIFYING_GLASS_CLICK)
    time.sleep(SCREEN_TRANSITION_DELAY)

    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "01_after_magnifying_glass")

    # Step 2: Click Elite Zombie tab
    _log(f"Step 2: Clicking Elite Zombie tab at {ELITE_ZOMBIE_TAB_CLICK}")
    adb.tap(*ELITE_ZOMBIE_TAB_CLICK)
    time.sleep(CLICK_DELAY)

    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "02_after_elite_zombie_tab")

    # Step 3: Click plus button to increase zombie level
    _log(f"Step 3: Clicking plus button {ELITE_ZOMBIE_PLUS_CLICKS} times at {PLUS_BUTTON_CLICK}")
    for i in range(ELITE_ZOMBIE_PLUS_CLICKS):
        adb.tap(*PLUS_BUTTON_CLICK)
        time.sleep(PLUS_CLICK_DELAY)

    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "03_after_plus_clicks")

    # Step 4: Click search button
    _log(f"Step 4: Clicking search button at {SEARCH_BUTTON_CLICK}")
    adb.tap(*SEARCH_BUTTON_CLICK)
    time.sleep(SEARCH_RESULT_DELAY)

    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "04_after_search")

    # Step 5: Click rally button
    _log(f"Step 5: Clicking rally button at {RALLY_BUTTON_CLICK}")
    adb.tap(*RALLY_BUTTON_CLICK)
    time.sleep(RALLY_SCREEN_DELAY)

    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "05_after_rally_click")

    # Step 6: Select LEFTMOST idle hero using hero_selector (elite zombie uses leftmost)
    _log("Step 6: Finding leftmost idle hero (Zz icon)...")

    hero_selector = HeroSelector()
    frame = win.get_screenshot_cv2()

    if frame is not None:
        _save_debug_screenshot(frame, "06_hero_selection_screen")

        # Get all slot status for debugging
        all_status = hero_selector.get_all_slot_status(frame)
        for status in all_status:
            idle_str = "Zz PRESENT (idle)" if status['is_idle'] else "NO Zz (busy)"
            _log(f"  Slot {status['id']}: score={status['score']:.4f} -> {idle_str}")

        # Find LEFTMOST hero (IGNORE Zz status - force select leftmost regardless)
        # Elite zombie = YOU start the rally as leader, troops commit when timer ends
        # Safe to use busy hero since you're initiating, not joining
        idle_slot = hero_selector.find_leftmost_idle(frame, zz_mode='ignore')

        if idle_slot:
            click_pos = idle_slot['click']
            _log(f"  Clicking leftmost slot {idle_slot['id']} at {click_pos}")
            adb.tap(*click_pos)
            time.sleep(CLICK_DELAY)
        else:
            # Should never happen with zz_mode='ignore'
            _log("  ERROR: No hero slot found! (should not happen)")

    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "07_after_hero_selection")

    # Step 7: Click Team Up button
    _log(f"Step 7: Clicking Team Up button at {TEAM_UP_BUTTON_CLICK}")
    adb.tap(*TEAM_UP_BUTTON_CLICK)
    time.sleep(CLICK_DELAY)

    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "08_after_team_up")

    elapsed = time.time() - flow_start
    _log(f"=== ELITE ZOMBIE FLOW SUCCESS === (took {elapsed:.1f}s)")
    return True


if __name__ == "__main__":
    # Test the flow manually
    from utils.adb_helper import ADBHelper

    adb = ADBHelper()
    print("Testing Elite Zombie Flow...")
    print("=" * 50)

    success = elite_zombie_flow(adb)

    print("=" * 50)
    if success:
        print("Flow completed successfully!")
    else:
        print("Flow FAILED!")
