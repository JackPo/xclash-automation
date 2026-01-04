"""
Zombie Attack flow - automated zombie attack sequence.

Trigger: Manual only (via WebSocket API)

Sequence:
1. Go to World Map (if not already there)
2. Click Magnifying Glass (search button) - VERIFY search panel opened
3. Click Zombie tab if not active - VERIFY tab selected
4. Click zombie type card (Iron Mine, Food, or Gold)
5. Click Plus button N times (increase level)
6. Click Search button
7. Click Attack button - VERIFY attack button visible
8. Select rightmost soldier using hero_selector
9. Return to base view

NOTE: ALL detection uses WindowsScreenshotHelper (NOT ADB screenshots).
"""
from __future__ import annotations

import sys
import time
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

import numpy.typing as npt


class ZombieCardConfig(TypedDict):
    """Type definition for zombie card configuration."""
    template: str
    pos: tuple[int, int]
    click: tuple[int, int]

from utils.windows_screenshot_helper import WindowsScreenshotHelper

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

# Add parent dirs to path for imports
_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import cv2

from utils.windows_screenshot_helper import WindowsScreenshotHelper  # noqa: F401 (runtime import)
from utils.view_state_detector import detect_view, go_to_world, ViewState
from utils.hero_selector import HeroSelector
from utils.return_to_base_view import return_to_base_view
from utils.template_matcher import match_template
from utils.debug_screenshot import save_debug_screenshot

# Setup logger
logger = logging.getLogger("zombie_attack_flow")

# Flow name for debug screenshots
FLOW_NAME = "zombie_attack"

# Fixed click coordinates (4K resolution)
MAGNIFYING_GLASS_CLICK = (88, 1486)
ZOMBIE_TAB_CLICK = (1512, 1092)
PLUS_BUTTON_CLICK = (2232, 1875)
SEARCH_BUTTON_CLICK = (1914, 2018)

# Zombie tab FIXED position for template matching (4K)
# Template size: 265x95
ZOMBIE_TAB_REGION = (1363, 1047, 265, 95)  # x, y, w, h
ZOMBIE_TAB_THRESHOLD = 0.06

# Zombie type cards - FIXED positions (4K)
# All cards are 340x375 (aligned via B&W correlation + manual centering)
# Panel is cropped at (1340, 900), cards at y=250 in panel
ZOMBIE_CARD_SIZE = (340, 375)
ZOMBIE_CARDS: dict[str, ZombieCardConfig] = {
    'iron_mine': {
        'template': 'zombie_iron_mine_card_4k.png',
        'pos': (1387, 1150),   # panel x=47 + 1340
        'click': (1557, 1337), # center: 1387 + 170
    },
    'food': {
        'template': 'zombie_food_card_4k.png',
        'pos': (1746, 1150),   # panel x=406 + 1340
        'click': (1916, 1337), # center: 1746 + 170
    },
    'gold': {
        'template': 'zombie_gold_card_4k.png',
        'pos': (2111, 1150),   # panel x=771 + 1340
        'click': (2281, 1337), # center: 2111 + 170
    },
}

# Timing constants
CLICK_DELAY = 0.3
PLUS_CLICK_DELAY = 0.2
SCREEN_TRANSITION_DELAY = 1.0
SEARCH_RESULT_DELAY = 2.0

# Verification thresholds
VERIFY_THRESHOLD = 0.1
SEARCH_BUTTON_THRESHOLD = 0.05
ATTACK_BUTTON_THRESHOLD = 0.08

# Attack button FIXED position (4K) - uses masked template
# Location returned by match_template is CENTER, so top-left for search_region:
ATTACK_BUTTON_POS = (1840, 1594)  # top-left
ATTACK_BUTTON_SIZE = (153, 177)
ATTACK_BUTTON_CLICK = (1916, 1682)  # center

# March button FIXED position (4K)
MARCH_BUTTON_POS = (1738, 1578)  # top-left
MARCH_BUTTON_SIZE = (372, 141)
MARCH_BUTTON_CLICK = (1924, 1648)  # center

# Poll settings
MAX_POLL_ATTEMPTS = 10
POLL_INTERVAL = 0.3


def _save_debug_screenshot(frame: npt.NDArray[Any], name: str) -> str:
    """Save screenshot for debugging."""
    return save_debug_screenshot(frame, FLOW_NAME, name)


def _log(msg: str) -> None:
    """Log to both logger and stdout."""
    logger.info(msg)
    print(f"    [ZOMBIE_ATTACK] {msg}")


def _verify_template(
    frame: npt.NDArray[Any],
    template_name: str,
    threshold: float | None = None,
    search_region: tuple[int, int, int, int] | None = None
) -> tuple[bool, float, tuple[int, int] | None]:
    """Verify a template is visible in the frame."""
    return match_template(frame, template_name, search_region=search_region, threshold=threshold)


def _poll_for_template(
    win: WindowsScreenshotHelper,
    template_name: str,
    threshold: float | None = None,
    search_region: tuple[int, int, int, int] | None = None,
    max_attempts: int = MAX_POLL_ATTEMPTS,
    interval: float = POLL_INTERVAL
) -> tuple[bool, float, tuple[int, int] | None, npt.NDArray[Any] | None]:
    """Poll for a template to appear with timeout."""
    frame: npt.NDArray[Any] | None = None
    score = 1.0
    for attempt in range(max_attempts):
        frame = win.get_screenshot_cv2()
        found, score, location = _verify_template(frame, template_name, threshold, search_region)
        if found:
            _log(f"  Found {template_name} (score={score:.4f}) after {attempt + 1} attempts")
            return True, score, location, frame
        time.sleep(interval)

    _log(f"  Template {template_name} NOT found after {max_attempts} attempts (best={score:.4f})")
    return False, score, None, frame


def zombie_attack_flow(adb: ADBHelper, zombie_type: str = 'iron_mine', plus_clicks: int = 5) -> bool:
    """
    Execute the zombie attack flow.

    Args:
        adb: ADBHelper instance
        zombie_type: 'iron_mine', 'food', or 'gold'
        plus_clicks: Number of times to click plus button (default 10)

    Returns:
        bool: True if flow completed successfully, False otherwise
    """
    flow_start = time.time()
    _log(f"=== ZOMBIE ATTACK FLOW START (type={zombie_type}, plus={plus_clicks}) ===")

    if zombie_type not in ZOMBIE_CARDS:
        _log(f"FAILED: Invalid zombie_type '{zombie_type}'. Must be: iron_mine, food, gold")
        return False

    zombie_config = ZOMBIE_CARDS[zombie_type]
    win = WindowsScreenshotHelper()

    try:
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

        # Step 2: Poll for Zombie tab at FIXED position (active OR inactive)
        _log("Step 2: Polling for Zombie tab at FIXED position...")
        panel_opened = False
        is_active = False
        for attempt in range(MAX_POLL_ATTEMPTS):
            frame = win.get_screenshot_cv2()

            # Check if ACTIVE
            is_active, active_score, _ = match_template(
                frame, "search_zombie_tab_active_4k.png",
                search_region=ZOMBIE_TAB_REGION,
                threshold=ZOMBIE_TAB_THRESHOLD
            )
            if is_active:
                _log(f"  Zombie tab ACTIVE (score={active_score:.4f}) after {attempt+1} attempts")
                panel_opened = True
                break

            # Check if INACTIVE
            is_inactive, inactive_score, _ = match_template(
                frame, "search_zombie_tab_inactive_4k.png",
                search_region=ZOMBIE_TAB_REGION,
                threshold=ZOMBIE_TAB_THRESHOLD
            )
            if is_inactive:
                _log(f"  Zombie tab INACTIVE (score={inactive_score:.4f}) after {attempt+1} attempts")
                panel_opened = True
                break

            _log(f"  Attempt {attempt+1}: active={active_score:.4f}, inactive={inactive_score:.4f}")
            time.sleep(POLL_INTERVAL)

        if not panel_opened:
            _log("FAILED: Search panel did not open (Zombie tab not found)")
            _save_debug_screenshot(frame, "01_search_panel_not_opened")
            return_to_base_view(adb, win, debug=False)
            return False

        _save_debug_screenshot(frame, "01_search_panel_opened")

        # Step 3: If not active, click Zombie tab to activate it
        if not is_active:
            _log(f"Step 3: Clicking Zombie tab at {ZOMBIE_TAB_CLICK}...")
            adb.tap(*ZOMBIE_TAB_CLICK)
            time.sleep(CLICK_DELAY)

            # Re-verify it's now active
            frame = win.get_screenshot_cv2()
            is_active, active_score, _ = match_template(
                frame, "search_zombie_tab_active_4k.png",
                search_region=ZOMBIE_TAB_REGION,
                threshold=ZOMBIE_TAB_THRESHOLD
            )
            _log(f"  After click - Zombie tab ACTIVE: score={active_score:.4f}, found={is_active}")
        else:
            _log("Step 3: Zombie tab already active, skipping click")

        _save_debug_screenshot(frame, "02_zombie_tab_active")

        # Step 4: Click zombie type card
        _log(f"Step 4: Clicking {zombie_type} card at {zombie_config['click']}")
        adb.tap(*zombie_config['click'])
        time.sleep(CLICK_DELAY)

        frame = win.get_screenshot_cv2()
        _save_debug_screenshot(frame, f"03_after_{zombie_type}_click")

        # Step 5: Click plus button
        _log(f"Step 5: Clicking plus button {plus_clicks} times at {PLUS_BUTTON_CLICK}")
        for i in range(plus_clicks):
            adb.tap(*PLUS_BUTTON_CLICK)
            time.sleep(PLUS_CLICK_DELAY)

        frame = win.get_screenshot_cv2()
        _save_debug_screenshot(frame, "04_after_plus_clicks")

        # Step 6: Click Search button
        _log(f"Step 6: Clicking search button at {SEARCH_BUTTON_CLICK}")
        adb.tap(*SEARCH_BUTTON_CLICK)
        time.sleep(SEARCH_RESULT_DELAY)

        # Step 7: Poll for Attack button at FIXED position (masked template)
        # search_region = (x, y, w, h) where (x,y) is top-left
        attack_region = (*ATTACK_BUTTON_POS, *ATTACK_BUTTON_SIZE)
        _log(f"Step 7: Waiting for attack button at {ATTACK_BUTTON_POS}...")
        found = False
        score = 0.0
        for attempt in range(15):
            frame = win.get_screenshot_cv2()
            found, score, _ = match_template(
                frame, "royal_city_attack_button_4k.png",
                search_region=attack_region,
                threshold=0.99  # Masked CCORR, score ~0.9996 for match
            )
            if found:
                _log(f"  Attack button found (score={score:.4f}) after {attempt + 1} attempts")
                break
            time.sleep(POLL_INTERVAL)

        _save_debug_screenshot(frame, "05_after_search")

        if not found:
            _log(f"FAILED: Attack button not found after 15 attempts (score={score:.4f})")
            return_to_base_view(adb, win, debug=False)
            return False

        # Step 8: Click attack button at fixed position
        _log(f"Step 8: Clicking attack button at {ATTACK_BUTTON_CLICK}...")
        adb.tap(*ATTACK_BUTTON_CLICK)
        time.sleep(SCREEN_TRANSITION_DELAY)

        frame = win.get_screenshot_cv2()
        _save_debug_screenshot(frame, "06_after_attack_click")

        # Step 9: Select RIGHTMOST soldier using hero_selector
        _log("Step 9: Finding rightmost soldier...")

        hero_selector = HeroSelector()
        frame = win.get_screenshot_cv2()

        if frame is not None:
            _save_debug_screenshot(frame, "07_soldier_selection_screen")

            # Get all slot status for debugging
            all_status = hero_selector.get_all_slot_status(frame)
            for status in all_status:
                idle_str = "Zz PRESENT (idle)" if status['is_idle'] else "NO Zz (busy)"
                _log(f"  Slot {status['id']}: score={status['score']:.4f} -> {idle_str}")

            # Find RIGHTMOST soldier WITH Zz (idle hero, available to send)
            idle_slot = hero_selector.find_rightmost_idle(frame, zz_mode='require')

            if idle_slot:
                click_pos = idle_slot['click']
                _log(f"  Clicking rightmost slot {idle_slot['id']} at {click_pos}")
                adb.tap(*click_pos)
                time.sleep(CLICK_DELAY)
            else:
                _log("  ERROR: No soldier slot found!")

        frame = win.get_screenshot_cv2()
        _save_debug_screenshot(frame, "08_after_soldier_selection")

        # Step 10: Poll for and click March button (full frame search, use detected location)
        _log(f"Step 10: Waiting for march button...")
        found = False
        score = 1.0
        march_loc = None
        for attempt in range(10):
            frame = win.get_screenshot_cv2()
            found, score, march_loc = match_template(
                frame, "march_button_4k.png",
                threshold=0.05  # SQDIFF, lower is better
            )
            if found:
                _log(f"  March button found at {march_loc} (score={score:.4f}) after {attempt + 1} attempts")
                break
            time.sleep(POLL_INTERVAL)

        if found and march_loc:
            _log(f"Clicking march button at detected location {march_loc}...")
            adb.tap(*march_loc)
            time.sleep(SCREEN_TRANSITION_DELAY)
        else:
            _log(f"WARNING: March button not found (score={score:.4f}), continuing anyway...")

        # Return to base view
        _log("Returning to base view...")
        return_to_base_view(adb, win, debug=False)

        elapsed = time.time() - flow_start
        _log(f"=== ZOMBIE ATTACK FLOW SUCCESS === (took {elapsed:.1f}s)")
        return True

    except Exception as e:
        _log(f"FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return_to_base_view(adb, win, debug=False)
        return False


if __name__ == "__main__":
    import argparse
    from utils.adb_helper import ADBHelper

    parser = argparse.ArgumentParser(description="Zombie Attack Flow")
    parser.add_argument("--type", choices=['iron_mine', 'food', 'gold'], default='iron_mine',
                        help="Zombie type to attack")
    parser.add_argument("--plus-clicks", type=int, default=10,
                        help="Number of plus button clicks")
    args = parser.parse_args()

    adb = ADBHelper()
    print(f"Testing Zombie Attack Flow (type={args.type}, plus={args.plus_clicks})...")
    print("=" * 50)

    success = zombie_attack_flow(adb, zombie_type=args.type, plus_clicks=args.plus_clicks)

    print("=" * 50)
    if success:
        print("Flow completed successfully!")
    else:
        print("Flow FAILED!")
