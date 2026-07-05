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
from __future__ import annotations

import sys
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING, Any

import numpy.typing as npt

# Add parent dirs to path for imports
_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import cv2

from utils.view_state_detector import detect_view, go_to_world, ViewState
from utils.hero_selector import HeroSelector
from utils.return_to_base_view import return_to_base_view
from utils.template_matcher import match_template
from utils.debug_screenshot import save_debug_screenshot
from utils.zombie_level_helper import set_zombie_level, read_zombie_level
from config import ELITE_ZOMBIE_LEVEL_CLICKS, DEBUG_ELITE_ZOMBIE_FLOW

from utils.windows_screenshot_helper import WindowsScreenshotHelper


def _get_level_clicks() -> int:
    """Get effective ELITE_ZOMBIE_LEVEL_CLICKS (signed: +N=plus, -N=minus)."""
    try:
        from utils.config_overrides import get_override_manager
        manager = get_override_manager()
        value, _ = manager.get_effective('ELITE_ZOMBIE_LEVEL_CLICKS', ELITE_ZOMBIE_LEVEL_CLICKS)
        return int(value)
    except ImportError:
        return ELITE_ZOMBIE_LEVEL_CLICKS

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

# Type alias for numpy arrays
NDArray = npt.NDArray[Any]

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
MINUS_BUTTON_CLICK = (1545, 1869)  # Blue minus button left of slider
SEARCH_BUTTON_CLICK = (1914, 2018)
RALLY_BUTTON_CLICK = (1915, 1682)
TEAM_UP_BUTTON_CLICK = (1912, 1648)

# Elite Zombie tab FIXED position for template matching (4K)
# Template size: 269x101
ELITE_ZOMBIE_TAB_REGION = (1923, 1045, 269, 101)  # x, y, w, h
ELITE_ZOMBIE_TAB_THRESHOLD = 0.06

# Timing constants
from utils.timings import (
    CLICK_DELAY_FAST as CLICK_DELAY,  # Delay after each click
    SCREEN_TRANSITION_DELAY_FAST as SCREEN_TRANSITION_DELAY,  # Delay for screen transitions
)
PLUS_CLICK_DELAY = 0.2  # Faster delay for plus button spam
SEARCH_RESULT_DELAY = 2.0  # Delay for search results to appear
RALLY_SCREEN_DELAY = 1.5  # Delay for rally screen to appear

# Verification thresholds (TM_SQDIFF_NORMED - lower = better)
VERIFY_THRESHOLD = 0.1  # Generic verification threshold
SEARCH_BUTTON_THRESHOLD = 0.05
RALLY_BUTTON_THRESHOLD = 0.08
TEAM_UP_THRESHOLD = 0.05

# Unfreeze button - appears when zombie is frozen (uses masked template)
UNFREEZE_BUTTON_REGION = (1600, 1200, 500, 600)  # x, y, w, h - bottom center
UNFREEZE_BUTTON_THRESHOLD = 0.05  # Masked SQDIFF

# Poll settings for verification
MAX_POLL_ATTEMPTS = 10
from utils.timings import POLL_INTERVAL  # seconds between poll attempts

# Level button search regions (4K) - constrain search to LEFT or RIGHT of slider
# This prevents finding the wrong button since plus/minus templates look similar
MINUS_BUTTON_REGION = (1400, 1800, 300, 150)  # x, y, w, h - LEFT side of slider
PLUS_BUTTON_REGION = (2050, 1800, 300, 150)   # x, y, w, h - RIGHT side of slider

# Klass Rally detection - FIXED position
KLASS_EVENT_BOX_POSITION = (1754, 1170)
KLASS_EVENT_BOX_SIZE = (327, 337)
KLASS_THRESHOLD = 0.1

# Directory for unknown panel screenshots
UNKNOWN_EVENTS_DIR = Path(__file__).parent.parent.parent / "templates" / "unknown_events"


def _save_debug_screenshot(frame: NDArray, name: str, click_pos: tuple[int, int] | None = None) -> str:
    """Save screenshot for debugging. Returns path.

    Args:
        frame: Screenshot to save
        name: Filename suffix
        click_pos: Optional (x, y) position to draw click marker
    """
    if not DEBUG_ELITE_ZOMBIE_FLOW:
        return ""
    # Save directly to flow-specific directory
    from pathlib import Path
    from datetime import datetime
    debug_dir = Path(__file__).parent.parent.parent / "screenshots" / "debug" / FLOW_NAME
    debug_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]
    filepath = debug_dir / f"{timestamp}_{name}.png"

    # If click position provided, annotate the image
    if click_pos is not None:
        annotated = frame.copy()
        x, y = click_pos
        # Draw red circle at click position
        cv2.circle(annotated, (x, y), 30, (0, 0, 255), 4)
        # Draw crosshairs
        cv2.line(annotated, (x - 50, y), (x + 50, y), (0, 0, 255), 3)
        cv2.line(annotated, (x, y - 50), (x, y + 50), (0, 0, 255), 3)
        # Add text label
        cv2.putText(annotated, f"CLICK: ({x}, {y})", (x + 40, y - 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        cv2.imwrite(str(filepath), annotated)
    else:
        cv2.imwrite(str(filepath), frame)

    print(f"    [ELITE_ZOMBIE] DEBUG: {filepath.name}")
    return str(filepath)


def _log(msg: str) -> None:
    """Log to both logger and stdout."""
    logger.info(msg)
    print(f"    [ELITE_ZOMBIE] {msg}")


def _verify_template(
    frame: NDArray,
    template_name: str,
    threshold: float | None = None,
    search_region: tuple[int, int, int, int] | None = None
) -> tuple[bool, float, tuple[int, int] | None]:
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


def _poll_for_template(
    win: WindowsScreenshotHelper,
    template_name: str,
    threshold: float | None = None,
    search_region: tuple[int, int, int, int] | None = None,
    max_attempts: int = MAX_POLL_ATTEMPTS,
    interval: float = POLL_INTERVAL
) -> tuple[bool, float, tuple[int, int] | None, NDArray]:
    """
    Poll for a template to appear with timeout.

    Args:
        win: WindowsScreenshotHelper
        template_name: Name of template file
        threshold: Score threshold (None = use auto-detected default based on mask)
        search_region: Optional region to limit search
        max_attempts: Max polling attempts
        interval: Seconds between attempts

    Returns:
        (found: bool, score: float, location: tuple or None, frame: np.array)
    """
    frame: NDArray = win.get_screenshot_cv2()
    score: float = 1.0
    for attempt in range(max_attempts):
        frame = win.get_screenshot_cv2()
        found, score, location = _verify_template(frame, template_name, threshold, search_region)
        if found:
            _log(f"  Found {template_name} (score={score:.4f}) after {attempt + 1} attempts")
            return True, score, location, frame
        time.sleep(interval)

    _log(f"  Template {template_name} NOT found after {max_attempts} attempts (best={score:.4f})")
    return False, score, None, frame


def _is_klass_event(frame: NDArray) -> bool:
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


def _save_unknown_panel(frame: NDArray) -> None:
    """Save panel screenshot from FIXED location."""
    UNKNOWN_EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    x, y = KLASS_EVENT_BOX_POSITION
    w, h = KLASS_EVENT_BOX_SIZE
    crop = frame[y:y+h, x:x+w]

    path = UNKNOWN_EVENTS_DIR / f"panel_{timestamp}.png"
    cv2.imwrite(str(path), crop)
    _log(f"  Saved unknown panel to {path}")


def _apply_level_adjustment(
    adb: ADBHelper,
    win: WindowsScreenshotHelper,
    level_clicks: int | None = None,
    target_level: int | None = None,
) -> None:
    """Apply level adjustment to the search panel slider.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        level_clicks: Relative adjustment (+N = plus, -N = minus)
        target_level: Absolute target level (uses OCR)
    """
    # If target_level provided, use OCR-based adjustment
    if target_level is not None:
        _log(f"  Re-applying level via OCR (target={target_level})")
        set_zombie_level(adb, win, target_level, debug=DEBUG_ELITE_ZOMBIE_FLOW)
        return

    # Otherwise use level_clicks
    if level_clicks is None or level_clicks == 0:
        return

    if level_clicks > 0:
        button_template = "plus_button_4k.png"
        button_name = "plus"
        clicks = level_clicks
    else:
        button_template = "minus_button_4k.png"
        button_name = "minus"
        clicks = abs(level_clicks)

    search_region = MINUS_BUTTON_REGION if level_clicks < 0 else PLUS_BUTTON_REGION
    frame = win.get_screenshot_cv2()
    found, score, button_pos = match_template(
        frame, button_template,
        search_region=search_region,
        threshold=0.15
    )
    if found and button_pos:
        _log(f"  Re-applying {clicks} {button_name} clicks at {button_pos}")
        for i in range(clicks):
            adb.tap(*button_pos, source=f"flow:elite_zombie:{button_name}_button_retry")
            time.sleep(PLUS_CLICK_DELAY)
    else:
        fallback_pos = PLUS_BUTTON_CLICK if level_clicks > 0 else MINUS_BUTTON_CLICK
        _log(f"  Re-applying {clicks} {button_name} clicks at fallback {fallback_pos}")
        for i in range(clicks):
            adb.tap(*fallback_pos, source=f"flow:elite_zombie:{button_name}_button_fallback_retry")
            time.sleep(PLUS_CLICK_DELAY)


def _check_and_click_unfreeze(
    adb: ADBHelper,
    win: WindowsScreenshotHelper,
) -> str:
    """
    Check if unfreeze button is visible and click it if so.

    This happens when the zombie is frozen - we need to unfreeze before rallying.

    Returns:
        "unfreeze_to_rally" - unfreeze clicked and rally panel opened (skip to rally step)
        "unfreeze_retry" - unfreeze clicked but need to retry search
        "none" - no unfreeze button found
    """
    frame = win.get_screenshot_cv2()
    found, score, center = match_template(
        frame, "unfreeze_button_4k.png",
        search_region=UNFREEZE_BUTTON_REGION,
        threshold=UNFREEZE_BUTTON_THRESHOLD
    )

    if found and center is not None:
        _log(f"  FROZEN ZOMBIE: Unfreeze button found (score={score:.4f}), clicking...")
        _save_debug_screenshot(frame, "unfreeze_detected", click_pos=center)
        adb.tap(*center, source="flow:elite_zombie:unfreeze")
        time.sleep(2.0)  # Wait for unfreeze animation

        # Check if march button visible (unfreeze goes straight to march screen)
        frame = win.get_screenshot_cv2()
        march_found, march_score, march_loc = match_template(
            frame, "march_button_4k.png",
            search_region=(1500, 1400, 900, 500),
            threshold=0.08
        )
        if march_found:
            _log(f"  Unfreeze opened march screen directly (March at {march_loc}, score={march_score:.4f})")
            return "unfreeze_to_march"

        return "unfreeze_retry"

    return "none"


def elite_zombie_flow(
    adb: ADBHelper,
    level_clicks: int | None = None,
    target_level: int | None = None
) -> bool:
    """
    Execute the elite zombie rally flow with template verification at each step.

    Args:
        adb: ADBHelper instance
        level_clicks: Signed int for level adjustment (+N = plus clicks, -N = minus clicks).
                      If None, uses ELITE_ZOMBIE_LEVEL_CLICKS from config.
                      Ignored if target_level is provided.
        target_level: If provided, use OCR to read current level and adjust to this target.
                      Takes precedence over level_clicks.

    Returns:
        bool: True if flow completed successfully, False otherwise
    """
    # Import at runtime to avoid circular imports
    from utils.windows_screenshot_helper import WindowsScreenshotHelper as WSHelper

    flow_start = time.time()
    _log("=== ELITE ZOMBIE FLOW START ===")

    win = WSHelper()

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
        adb.tap(*MAGNIFYING_GLASS_CLICK, source="flow:elite_zombie:magnifying_glass")
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
                search_region=ELITE_ZOMBIE_TAB_REGION,
                threshold=ELITE_ZOMBIE_TAB_THRESHOLD
            )
            if is_active:
                _log(f"  Elite Zombie tab ACTIVE (score={active_score:.4f}) after {attempt+1} attempts")
                panel_opened = True
                break

            # Check if INACTIVE
            is_inactive, inactive_score, _ = match_template(
                frame, "search_elite_zombie_tab_inactive_4k.png",
                search_region=ELITE_ZOMBIE_TAB_REGION,
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
            adb.tap(*ELITE_ZOMBIE_TAB_CLICK, source="flow:elite_zombie:elite_zombie_tab")
            time.sleep(CLICK_DELAY)

            # Re-verify it's now active
            frame = win.get_screenshot_cv2()
            is_active, active_score, _ = match_template(
                frame, "search_elite_zombie_tab_active_4k.png",
                search_region=ELITE_ZOMBIE_TAB_REGION,
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

        # Wait for slider to be ready before clicking minus/plus
        time.sleep(0.5)

        # Step 3: Adjust level
        # Priority: target_level (OCR) > level_clicks > config default
        # Skip if Klass Rally is active
        if is_klass:
            _log("Step 3: Skipping level adjustment (Klass Rally)")
        elif target_level is not None:
            _log(f"Step 3: Setting level to {target_level} via OCR...")
            if set_zombie_level(adb, win, target_level, debug=DEBUG_ELITE_ZOMBIE_FLOW):
                _log(f"Step 3: Level set to {target_level}")
            else:
                _log(f"Step 3: WARNING - Could not confirm level {target_level}, continuing anyway")
        else:
            # Use level_clicks (from param or config)
            if level_clicks is None:
                level_clicks = _get_level_clicks()

            if level_clicks > 0:
                button_template = "plus_button_4k.png"
                button_name = "plus"
                clicks = level_clicks
                search_region = PLUS_BUTTON_REGION
                frame = win.get_screenshot_cv2()
                found, score, button_pos = match_template(
                    frame, button_template,
                    search_region=search_region,
                    threshold=0.15
                )
                if found and button_pos:
                    _log(f"Step 3: Found {button_name} button at {button_pos} (score={score:.4f}) in region {search_region}")
                    _log(f"Step 3: Clicking {button_name} button {clicks} times")
                    _save_debug_screenshot(frame, f"03_CLICKING_{button_name}_button", click_pos=button_pos)
                    for i in range(clicks):
                        adb.tap(*button_pos, source=f"flow:elite_zombie:{button_name}_button")
                        time.sleep(PLUS_CLICK_DELAY)
                else:
                    _log(f"Step 3: WARNING - {button_name} button not found (score={score:.4f}) in region {search_region}, using fallback")
                    fallback_pos = PLUS_BUTTON_CLICK
                    _save_debug_screenshot(frame, f"03_FALLBACK_{button_name}_button", click_pos=fallback_pos)
                    for i in range(clicks):
                        adb.tap(*fallback_pos, source=f"flow:elite_zombie:{button_name}_button_fallback")
                        time.sleep(PLUS_CLICK_DELAY)
            elif level_clicks < 0:
                button_template = "minus_button_4k.png"
                button_name = "minus"
                clicks = abs(level_clicks)
                search_region = MINUS_BUTTON_REGION
                frame = win.get_screenshot_cv2()
                found, score, button_pos = match_template(
                    frame, button_template,
                    search_region=search_region,
                    threshold=0.15
                )
                if found and button_pos:
                    _log(f"Step 3: Found {button_name} button at {button_pos} (score={score:.4f}) in region {search_region}")
                    _log(f"Step 3: Clicking {button_name} button {clicks} times")
                    _save_debug_screenshot(frame, f"03_CLICKING_{button_name}_button", click_pos=button_pos)
                    for i in range(clicks):
                        adb.tap(*button_pos, source=f"flow:elite_zombie:{button_name}_button")
                        time.sleep(PLUS_CLICK_DELAY)
                else:
                    _log(f"Step 3: WARNING - {button_name} button not found (score={score:.4f}) in region {search_region}, using fallback")
                    fallback_pos = MINUS_BUTTON_CLICK
                    _save_debug_screenshot(frame, f"03_FALLBACK_{button_name}_button", click_pos=fallback_pos)
                    for i in range(clicks):
                        adb.tap(*fallback_pos, source=f"flow:elite_zombie:{button_name}_button_fallback")
                        time.sleep(PLUS_CLICK_DELAY)
            else:
                _log("Step 3: No level adjustment (level_clicks=0)")

        frame = win.get_screenshot_cv2()
        if frame is not None:
            if target_level is not None:
                dir_str = f"target_{target_level}"
            elif level_clicks is not None and level_clicks > 0:
                dir_str = "plus"
            elif level_clicks is not None and level_clicks < 0:
                dir_str = "minus"
            else:
                dir_str = "no"
            _save_debug_screenshot(frame, f"03_after_{dir_str}_clicks")

        # Step 4: VERIFY rally search button still visible, then click it (with unfreeze retry)
        max_search_attempts = 3
        rally_button_found = False
        rally_button_loc = None
        rally_button_score = 0.0
        skip_to_team_up = False  # Set if unfreeze opens rally panel directly

        for search_attempt in range(max_search_attempts):
            _log(f"Step 4: Verifying and clicking search button (attempt {search_attempt + 1})...")
            frame = win.get_screenshot_cv2()
            found, score, loc = _verify_template(
                frame, "rally_search_button_4k.png",
                threshold=SEARCH_BUTTON_THRESHOLD,
                search_region=(1600, 1800, 700, 400)
            )
            if not found:
                # Recovery: if search panel collapsed but Rally is already visible on world map,
                # proceed using Rally instead of hard-failing this run.
                rally_visible, rally_score, rally_loc = _verify_template(
                    frame, "rally_button_4k.png",
                    threshold=RALLY_BUTTON_THRESHOLD,
                    search_region=(1500, 1000, 800, 900)
                )
                if rally_visible and rally_loc is not None:
                    _log(
                        f"  Search button missing, but Rally already visible at {rally_loc} "
                        f"(score={rally_score:.4f})"
                    )
                    rally_button_found = True
                    rally_button_score = rally_score
                    rally_button_loc = rally_loc
                    _save_debug_screenshot(frame, "04_search_missing_but_rally_visible", click_pos=rally_button_loc)
                    break

                _log(f"FAILED: Search button not visible (score={score:.4f})")
                _save_debug_screenshot(frame, "04_search_button_not_found")
                return_to_base_view(adb, win, debug=False)
                return False

            _log(f"  Search button at {loc} (score={score:.4f}), clicking...")
            assert loc is not None  # Guaranteed by found == True check above
            adb.tap(*loc, source="flow:elite_zombie:search_button")

            # Wait for search to complete and camera to pan to zombie
            time.sleep(SEARCH_RESULT_DELAY)

            # Check for BOTH Rally and Unfreeze buttons - frozen zombies show both
            _log("  Checking for Rally and Unfreeze buttons...")
            frame = win.get_screenshot_cv2()

            # Check unfreeze FIRST - frozen zombies need unfreezing before rally works
            unfreeze_found, unfreeze_score, unfreeze_center = match_template(
                frame, "unfreeze_button_4k.png",
                search_region=UNFREEZE_BUTTON_REGION,
                threshold=UNFREEZE_BUTTON_THRESHOLD
            )

            if unfreeze_found:
                _log(f"  FROZEN ZOMBIE detected (unfreeze score={unfreeze_score:.4f})")
                _save_debug_screenshot(frame, "frozen_zombie_detected", click_pos=unfreeze_center)
                # Handle unfreeze - this will click unfreeze and handle the result
                unfreeze_result = _check_and_click_unfreeze(adb, win)

                if unfreeze_result == "unfreeze_to_march":
                    # Unfreezing a frozen zombie opens the SOLO ATTACK march screen
                    # (troops already loaded, "Victory is assured"). Clicking March
                    # here LAUNCHES the attack -- that IS the beast-training action
                    # and scores points. Do NOT loop back to search for a rally: the
                    # attack is the completed action. (Old behavior re-searched, found
                    # the same still-frozen zombie, and burned all 3 attempts doing
                    # nothing -> "Rally button not found" -> 0 rallies.)
                    _log("  Unfreeze opened attack march screen, clicking March to ATTACK...")
                    frame = win.get_screenshot_cv2()
                    found, score, loc = match_template(
                        frame, "march_button_4k.png",
                        search_region=(1500, 1400, 900, 500),
                        threshold=0.08
                    )
                    if found and loc:
                        _save_debug_screenshot(frame, "unfreeze_march_attack", click_pos=loc)
                        adb.tap(*loc, source="flow:elite_zombie:unfreeze_attack_march")
                        time.sleep(SCREEN_TRANSITION_DELAY)
                        # Confirm the attack launched: the march screen should close.
                        after = win.get_screenshot_cv2()
                        still_open, _, _ = match_template(
                            after, "march_button_4k.png",
                            search_region=(1500, 1400, 900, 500),
                            threshold=0.08
                        )
                        if still_open:
                            # March didn't launch (not enough troops / stale panel).
                            _log("  March did not launch after unfreeze attack -- treating as failed")
                            return_to_base_view(adb, win, target=ViewState.WORLD, debug=False)
                            return False
                        _log("  Unfreeze ATTACK launched (march away) -- counts as rally")
                        return_to_base_view(adb, win, target=ViewState.WORLD, debug=False)
                        return True
                    else:
                        _log("FAILED: March button not found after unfreeze")
                        return_to_base_view(adb, win, debug=False)
                        return False
                elif unfreeze_result == "unfreeze_retry":
                    _log("  Unfreeze clicked, retrying search...")
                    continue  # Retry search after unfreeze
                # If unfreeze_result == "none", continue to rally button check below

            # Poll for rally button to appear (proves search completed and zombie found)
            _log("  Waiting for Rally button...")
            rally_button_found, rally_button_score, rally_button_loc, frame = _poll_for_template(
                win, "rally_button_4k.png",
                threshold=RALLY_BUTTON_THRESHOLD,
                search_region=(1500, 1000, 800, 900),
                max_attempts=15
            )
            if frame is not None:
                _save_debug_screenshot(frame, "04_after_search", click_pos=rally_button_loc)
            break  # Exit retry loop

        # Skip rally button click if unfreeze already opened the panel
        if skip_to_team_up:
            _log("Step 5: Skipped (unfreeze opened rally panel directly)")
        else:
            if not rally_button_found:
                _log("FAILED: Rally button not found after search (no zombie found?)")
                return_to_base_view(adb, win, debug=False)
                return False

            # Use the found rally button location
            loc = rally_button_loc
            score = rally_button_score

            # Step 5: Click rally button (use detected location)
            _log(f"Step 5: Rally button at {loc} (score={score:.4f}), clicking...")
            assert loc is not None  # Guaranteed by found == True check above
            # Save BEFORE click with annotated position
            _save_debug_screenshot(frame, "04b_CLICKING_rally", click_pos=loc)
            adb.tap(*loc, source="flow:elite_zombie:rally_button")

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

            # Find LEFTMOST AVAILABLE hero (require Zz icon = idle/available)
            # Elite zombie = YOU start the rally as leader
            # Pick leftmost available hero so strongest heroes are used first
            idle_slot = hero_selector.find_leftmost_idle(frame, zz_mode='require')

            if idle_slot:
                click_pos = idle_slot['click']
                _log(f"  Clicking leftmost available slot {idle_slot['id']} at {click_pos}")
                # Save BEFORE click with annotated position
                _save_debug_screenshot(frame, "06b_CLICKING_hero", click_pos=click_pos)
                adb.tap(*click_pos, source="flow:elite_zombie:hero_slot")
                time.sleep(CLICK_DELAY)
            else:
                _log("  ERROR: No available hero found (all heroes busy)")

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
            tap_loc = TEAM_UP_BUTTON_CLICK
        else:
            _log(f"  Team Up button at {loc} (score={score:.4f})")
            assert loc is not None  # Guaranteed when found == True
            tap_loc = loc

        # Save BEFORE click with annotated position
        _save_debug_screenshot(frame, "07b_CLICKING_team_up", click_pos=tap_loc)
        adb.tap(*tap_loc, source="flow:elite_zombie:team_up_button")
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
    import argparse
    from utils.adb_helper import ADBHelper

    parser = argparse.ArgumentParser(description="Elite Zombie Rally Flow")
    parser.add_argument("--level-clicks", type=int, default=None,
                        help="Level adjustment: positive=plus, negative=minus (e.g., -2, -1, 0, +1, +2)")
    parser.add_argument("--target-level", type=int, default=None,
                        help="Target level (1-50). Uses OCR to read current and adjust. Takes precedence over --level-clicks")
    args = parser.parse_args()

    adb = ADBHelper()
    if args.target_level is not None:
        print(f"Testing Elite Zombie Flow (target_level={args.target_level})...")
    elif args.level_clicks is not None:
        print(f"Testing Elite Zombie Flow (level_clicks={args.level_clicks})...")
    else:
        print("Testing Elite Zombie Flow (using config defaults)...")
    print("=" * 50)

    success = elite_zombie_flow(
        adb,
        level_clicks=args.level_clicks,
        target_level=args.target_level
    )

    print("=" * 50)
    if success:
        print("Flow completed successfully!")
    else:
        print("Flow FAILED!")
