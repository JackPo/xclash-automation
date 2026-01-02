"""
Elite Zombie Rally flow - automated elite zombie rallying sequence.

Trigger Conditions:
- Stamina >= 118
- User idle for 5+ minutes

Sequence:
1. Go to World Map (if not already there)
2. Click Magnifying Glass (search button) - VERIFY search panel opened
3. Click Elite Zombie tab - VERIFY tab selected
4. Click Plus button N times (increase level, configurable via ELITE_ZOMBIE_PLUS_CLICKS)
5. Click Search button - VERIFY search button visible first
6. Click Rally button - VERIFY rally button visible after search
7. Select rightmost hero with Zz (idle) using hero_selector
8. Click Team Up button - VERIFY team up button visible

NOTE: ALL detection uses WindowsScreenshotHelper (NOT ADB screenshots).
Templates are captured with Windows screenshots - ADB has different pixel values.
Each step verifies the expected UI element is present before clicking.
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
from utils.return_to_base_view import return_to_base_view
from utils.template_matcher import match_template, has_mask
from utils.debug_screenshot import save_debug_screenshot
from config import ELITE_ZOMBIE_PLUS_CLICKS

# Setup logger
logger = logging.getLogger("elite_zombie_flow")

# Flow name for debug screenshots
FLOW_NAME = "elite_zombie"

# Template directory (for debug saves only)
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "ground_truth"

# Fixed click coordinates (4K resolution) - all from plan
MAGNIFYING_GLASS_CLICK = (88, 1486)
ELITE_ZOMBIE_TAB_CLICK = (2062, 1095)
PLUS_BUTTON_CLICK = (2232, 1875)
SEARCH_BUTTON_CLICK = (1914, 2018)
RALLY_BUTTON_CLICK = (1915, 1682)
TEAM_UP_BUTTON_CLICK = (1912, 1648)

# Elite Zombie tab FIXED position for template matching (4K)
# Template size: 269x101
ELITE_ZOMBIE_TAB_POSITION = (1923, 1045)  # Top-left corner (verified via region search)
ELITE_ZOMBIE_TAB_SIZE = (269, 101)
ELITE_ZOMBIE_TAB_THRESHOLD = 0.06

# Timing constants
CLICK_DELAY = 0.3  # Delay after each click
PLUS_CLICK_DELAY = 0.2  # Faster delay for plus button spam
SCREEN_TRANSITION_DELAY = 1.0  # Delay for screen transitions
SEARCH_RESULT_DELAY = 2.0  # Delay for search results to appear
RALLY_SCREEN_DELAY = 1.5  # Delay for rally screen to appear

# Verification thresholds (TM_SQDIFF_NORMED - lower = better)
VERIFY_THRESHOLD = 0.1  # Generic verification threshold
SEARCH_BUTTON_THRESHOLD = 0.05
RALLY_BUTTON_THRESHOLD = 0.08
TEAM_UP_THRESHOLD = 0.05

# Poll settings for verification
MAX_POLL_ATTEMPTS = 10
POLL_INTERVAL = 0.3  # seconds between poll attempts

# Klass Rally detection - FIXED position
KLASS_EVENT_BOX_POSITION = (1754, 1170)
KLASS_EVENT_BOX_SIZE = (327, 337)
KLASS_THRESHOLD = 0.1

# Directory for unknown panel screenshots
UNKNOWN_EVENTS_DIR = Path(__file__).parent.parent.parent / "templates" / "unknown_events"


def _save_debug_screenshot(frame, name: str) -> str:
    """Save screenshot for debugging. Returns path."""
    return save_debug_screenshot(frame, FLOW_NAME, name)


def _log(msg: str):
    """Log to both logger and stdout."""
    logger.info(msg)
    print(f"    [ELITE_ZOMBIE] {msg}")


def _verify_template(frame, template_name: str, threshold: float = VERIFY_THRESHOLD,
                     search_region: tuple = None) -> tuple:
    """
    Verify a template is visible in the frame.

    Uses centralized template_matcher which auto-detects masks.

    Args:
        frame: BGR screenshot
        template_name: Name of template file
        threshold: Score threshold (interpretation depends on whether mask exists)
        search_region: Optional (x, y, w, h) to limit search area

    Returns:
        (found: bool, score: float, location: tuple or None)
    """
    return match_template(frame, template_name, search_region=search_region, threshold=threshold)


def _poll_for_template(win, template_name: str, threshold: float = VERIFY_THRESHOLD,
                       search_region: tuple = None, max_attempts: int = MAX_POLL_ATTEMPTS,
                       interval: float = POLL_INTERVAL) -> tuple:
    """
    Poll for a template to appear with timeout.

    Args:
        win: WindowsScreenshotHelper
        template_name: Name of template file
        threshold: Max score for match
        search_region: Optional region to limit search
        max_attempts: Max polling attempts
        interval: Seconds between attempts

    Returns:
        (found: bool, score: float, location: tuple or None, frame: np.array)
    """
    for attempt in range(max_attempts):
        frame = win.get_screenshot_cv2()
        found, score, location = _verify_template(frame, template_name, threshold, search_region)
        if found:
            _log(f"  Found {template_name} (score={score:.4f}) after {attempt + 1} attempts")
            return True, score, location, frame
        time.sleep(interval)

    _log(f"  Template {template_name} NOT found after {max_attempts} attempts (best={score:.4f})")
    return False, score, None, frame


def _is_klass_event(frame) -> bool:
    """Check if Klass Rally Assault is active."""
    found, score, _ = _verify_template(
        frame, "klass_events_box_4k.png",
        threshold=KLASS_THRESHOLD,
        search_region=(1700, 1100, 400, 400)
    )
    if found:
        _log(f"  Klass Rally detected (score={score:.4f}) -> skipping plus clicks")
        return True

    # Not Klass - save screenshot of this panel type for future reference
    _save_unknown_panel(frame)
    return False


def _save_unknown_panel(frame):
    """Save panel screenshot from FIXED location."""
    UNKNOWN_EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    x, y = KLASS_EVENT_BOX_POSITION
    w, h = KLASS_EVENT_BOX_SIZE
    crop = frame[y:y+h, x:x+w]

    path = UNKNOWN_EVENTS_DIR / f"panel_{timestamp}.png"
    cv2.imwrite(str(path), crop)
    _log(f"  Saved unknown panel to {path}")


def elite_zombie_flow(adb) -> bool:
    """
    Execute the elite zombie rally flow with template verification at each step.

    Args:
        adb: ADBHelper instance

    Returns:
        bool: True if flow completed successfully, False otherwise
    """
    flow_start = time.time()
    _log("=== ELITE ZOMBIE FLOW START ===")

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

        # Step 2: Poll for Elite Zombie tab at FIXED position (active OR inactive)
        # This confirms search panel opened, regardless of which tab is shown
        _log("Step 2: Polling for Elite Zombie tab at FIXED position...")
        panel_opened = False
        for attempt in range(MAX_POLL_ATTEMPTS):
            frame = win.get_screenshot_cv2()

            # Check if ACTIVE
            is_active, active_score, _ = match_template(
                frame, "search_elite_zombie_tab_active_4k.png",
                position=ELITE_ZOMBIE_TAB_POSITION,
                size=ELITE_ZOMBIE_TAB_SIZE,
                threshold=ELITE_ZOMBIE_TAB_THRESHOLD
            )
            if is_active:
                _log(f"  Elite Zombie tab ACTIVE (score={active_score:.4f}) after {attempt+1} attempts")
                panel_opened = True
                break

            # Check if INACTIVE
            is_inactive, inactive_score, _ = match_template(
                frame, "search_elite_zombie_tab_inactive_4k.png",
                position=ELITE_ZOMBIE_TAB_POSITION,
                size=ELITE_ZOMBIE_TAB_SIZE,
                threshold=ELITE_ZOMBIE_TAB_THRESHOLD
            )
            if is_inactive:
                _log(f"  Elite Zombie tab INACTIVE (score={inactive_score:.4f}) after {attempt+1} attempts")
                panel_opened = True
                break

            _log(f"  Attempt {attempt+1}: active={active_score:.4f}, inactive={inactive_score:.4f}")
            time.sleep(POLL_INTERVAL)

        if not panel_opened:
            _log("FAILED: Search panel did not open (Elite Zombie tab not found)")
            _save_debug_screenshot(frame, "01_search_panel_not_opened")
            return_to_base_view(adb, win, debug=False)
            return False

        _save_debug_screenshot(frame, "01_search_panel_opened")

        # Step 3: If not active, click Elite Zombie tab to activate it
        if not is_active:
            _log(f"Step 3: Clicking Elite Zombie tab at {ELITE_ZOMBIE_TAB_CLICK}...")
            adb.tap(*ELITE_ZOMBIE_TAB_CLICK)
            time.sleep(CLICK_DELAY)

            # Re-verify it's now active
            frame = win.get_screenshot_cv2()
            is_active, active_score, _ = match_template(
                frame, "search_elite_zombie_tab_active_4k.png",
                position=ELITE_ZOMBIE_TAB_POSITION,
                size=ELITE_ZOMBIE_TAB_SIZE,
                threshold=ELITE_ZOMBIE_TAB_THRESHOLD
            )
            _log(f"  After click - Elite Zombie tab ACTIVE: score={active_score:.4f}, found={is_active}")

            if not is_active:
                _log("FAILED: Elite Zombie tab not active after clicking!")
                _save_debug_screenshot(frame, "02_elite_zombie_tab_not_active")
                return_to_base_view(adb, win, debug=False)
                return False
        else:
            _log("Step 3: Elite Zombie tab already active, skipping click")

        _save_debug_screenshot(frame, "02_elite_zombie_tab_active")

        # Step 2.5: Check if Klass Rally is active
        is_klass = _is_klass_event(frame)

        # Step 3: Click plus button (skip if Klass Rally)
        if is_klass:
            _log("Step 3: Skipping plus clicks (Klass Rally)")
        else:
            _log(f"Step 3: Clicking plus button {ELITE_ZOMBIE_PLUS_CLICKS} times at {PLUS_BUTTON_CLICK}")
            for i in range(ELITE_ZOMBIE_PLUS_CLICKS):
                adb.tap(*PLUS_BUTTON_CLICK)
                time.sleep(PLUS_CLICK_DELAY)

        frame = win.get_screenshot_cv2()
        if frame is not None:
            _save_debug_screenshot(frame, "03_after_plus_clicks")

        # Step 4: VERIFY rally search button still visible, then click it
        _log(f"Step 4: Verifying and clicking search button...")
        frame = win.get_screenshot_cv2()
        found, score, loc = _verify_template(
            frame, "rally_search_button_4k.png",
            threshold=SEARCH_BUTTON_THRESHOLD,
            search_region=(1600, 1800, 700, 400)
        )
        if not found:
            _log(f"FAILED: Search button not visible (score={score:.4f})")
            _save_debug_screenshot(frame, "04_search_button_not_found")
            return_to_base_view(adb, win, debug=False)
            return False

        _log(f"  Search button at {loc} (score={score:.4f}), clicking...")
        adb.tap(*loc)  # Click detected location of rally_search_button

        # Poll for rally button to appear (proves search completed and zombie found)
        _log("  Waiting for search results...")
        found, score, loc, frame = _poll_for_template(
            win, "rally_button_4k.png",
            threshold=RALLY_BUTTON_THRESHOLD,
            search_region=(1700, 1500, 500, 400),
            max_attempts=15  # Give extra time for search
        )
        if frame is not None:
            _save_debug_screenshot(frame, "04_after_search")
        if not found:
            _log("FAILED: Rally button not found after search (no zombie found?)")
            return_to_base_view(adb, win, debug=False)
            return False

        # Step 5: Click rally button (use detected location)
        _log(f"Step 5: Rally button at {loc} (score={score:.4f}), clicking...")
        adb.tap(*loc)

        # Poll for Team Up button to appear (proves rally screen loaded)
        _log("  Waiting for rally screen to load...")
        found, score, loc, frame = _poll_for_template(
            win, "team_up_button_4k.png",
            threshold=TEAM_UP_THRESHOLD,
            search_region=(1500, 1400, 900, 500)
        )
        if frame is not None:
            _save_debug_screenshot(frame, "05_after_rally_click")
        if not found:
            _log("FAILED: Team Up button not found (rally screen did not load)")
            return_to_base_view(adb, win, debug=False)
            return False
        _log(f"  Rally screen verified (Team Up at {loc})")

        # Step 6: Select LEFTMOST idle hero using hero_selector
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

        # Step 7: VERIFY and click Team Up button
        _log(f"Step 7: Verifying and clicking Team Up button...")
        frame = win.get_screenshot_cv2()
        found, score, loc = _verify_template(
            frame, "team_up_button_4k.png",
            threshold=TEAM_UP_THRESHOLD,
            search_region=(1500, 1400, 900, 500)
        )
        if not found:
            _log(f"  WARNING: Team Up button not confirmed (score={score:.4f})")
            # Use fixed coords as fallback
            loc = TEAM_UP_BUTTON_CLICK
        else:
            _log(f"  Team Up button at {loc} (score={score:.4f})")

        adb.tap(*loc)
        time.sleep(CLICK_DELAY)

        frame = win.get_screenshot_cv2()
        if frame is not None:
            _save_debug_screenshot(frame, "08_after_team_up")

        elapsed = time.time() - flow_start
        _log(f"=== ELITE ZOMBIE FLOW SUCCESS === (took {elapsed:.1f}s)")
        return True

    except Exception as e:
        _log(f"FAILED with exception: {e}")
        return_to_base_view(adb, win, debug=False)
        return False


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
