"""
Arms Race panel helper for Smart Mystic Beast Training flow.

Provides navigation to Arms Race panel with scroll handling, OCR of current points,
and calculation of rallies needed to reach chest3.

Key values:
- 100 points per stamina spent
- 20 stamina per rally
- 2000 points per rally (20 * 100)
- Chest3 target: dynamic from metadata (30000 for Mystic Beast Training)
- Max rallies for chest3: ceil(chest3 / 2000)
"""
from __future__ import annotations

import logging
import time
from math import ceil
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from utils.arms_race_ocr import (
    get_current_points_verified,
    detect_active_event,
    is_arms_race_panel_open,
    TITLE_REGION,
)
from utils.view_state_detector import detect_view, go_to_town, ViewState
from utils.return_to_base_view import return_to_base_view
from utils.arms_race import get_event_metadata
from utils.events_icon_matcher import EventsIconMatcher

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Points calculation
POINTS_PER_STAMINA = 100
STAMINA_PER_RALLY = 20
POINTS_PER_RALLY = STAMINA_PER_RALLY * POINTS_PER_STAMINA  # 2000

def get_chest3_target(event_name: str = "Mystic Beast Training") -> int:
    """Get chest3 target from metadata JSON."""
    meta = get_event_metadata(event_name)
    return meta["chest3"]


# Legacy constants - use get_chest3_target() for dynamic values
CHEST3_TARGET = get_chest3_target("Mystic Beast Training")
MAX_RALLIES_FOR_CHEST3 = ceil(CHEST3_TARGET / POINTS_PER_RALLY)

# Coordinates (4K resolution)
EVENTS_ICON_CLICK = (3718, 632)  # Events button on right side

# Arms Race icon position on bottom bar
ARMS_RACE_ICON_X = 1512
ARMS_RACE_ICON_Y = 1935
ARMS_RACE_ICON_W = 227
ARMS_RACE_ICON_H = 219
ARMS_RACE_ICON_CLICK = (1625, 2044)  # Center of icon

# Bottom bar scroll region (swipe left to right to reveal left content)
BOTTOM_BAR_Y = 2044  # Y at icon center
SWIPE_START_X = 1600  # Start from center
SWIPE_END_X = 1900    # Short swipe to right (300px like soldier training)
SWIPE_DURATION = 500

# Template paths
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"
INACTIVE_ICON_TEMPLATE = TEMPLATE_DIR / "arms_race_icon_inactive_4k.png"
ACTIVE_ICON_TEMPLATE = TEMPLATE_DIR / "arms_race_icon_active_4k.png"
BEAST_TRAINING_HEADER = TEMPLATE_DIR / "mystic_beast_training_4k.png"


# =============================================================================
# TEMPLATE MATCHING
# =============================================================================

def is_arms_race_icon_visible(frame: np.ndarray, use_active: bool = False) -> tuple[bool, float, tuple[int, int]]:
    """
    Check if Arms Race icon is visible anywhere in the bottom bar.

    Searches full X-axis at fixed Y range where icons appear (Y is constant,
    only X varies due to scrolling).

    Args:
        frame: BGR screenshot
        use_active: If True, check for active icon; otherwise check inactive

    Returns:
        Tuple of (is_visible, score, click_center)
    """
    template_path = ACTIVE_ICON_TEMPLATE if use_active else INACTIVE_ICON_TEMPLATE

    if not template_path.exists():
        logger.warning(f"Template not found: {template_path}")
        return False, 1.0, (0, 0)

    template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
    if template is None:
        return False, 1.0, (0, 0)

    # Convert frame to grayscale
    if len(frame.shape) == 3:
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        frame_gray = frame

    # Extract horizontal strip at fixed Y (bottom bar) - only X varies
    # Y range: 1935 to 1935+219 = 2154
    strip_y_start = ARMS_RACE_ICON_Y
    strip_y_end = ARMS_RACE_ICON_Y + ARMS_RACE_ICON_H
    strip = frame_gray[strip_y_start:strip_y_end, :]

    try:
        result = cv2.matchTemplate(strip, template, cv2.TM_SQDIFF_NORMED)
        min_val, _, min_loc, _ = cv2.minMaxLoc(result)

        # Calculate click center (add back the Y offset)
        click_x = min_loc[0] + template.shape[1] // 2
        click_y = strip_y_start + template.shape[0] // 2

        threshold = 0.05
        return min_val <= threshold, min_val, (click_x, click_y)
    except cv2.error:
        return False, 1.0, (0, 0)


def is_beast_training_header_visible(frame: np.ndarray) -> tuple[bool, float]:
    """
    Check if Mystic Beast Training header is visible.

    Returns:
        Tuple of (is_visible, score)
    """
    event_name, score = detect_active_event(frame)
    is_beast = event_name == "Mystic Beast Training" and score <= 0.1
    return is_beast, score


# =============================================================================
# NAVIGATION
# =============================================================================

def scroll_bottom_bar_left(adb) -> None:
    """Swipe bottom bar left to reveal Arms Race icon."""
    adb.swipe(SWIPE_START_X, BOTTOM_BAR_Y, SWIPE_END_X, BOTTOM_BAR_Y, duration=SWIPE_DURATION)


def ensure_arms_race_visible(adb, win, max_scrolls: int = 3) -> bool:
    """
    Scroll bottom bar until Arms Race icon found.

    Checks ACTIVE first (panel already open), then INACTIVE (need to click).
    Only scrolls if neither is found.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        max_scrolls: Maximum scroll attempts

    Returns:
        True if icon found, False otherwise
    """
    for attempt in range(max_scrolls):
        frame = win.get_screenshot_cv2()

        # Check ACTIVE first - panel might already be open
        is_active, score_active, click_active = is_arms_race_icon_visible(frame, use_active=True)
        if is_active:
            logger.debug(f"Arms Race panel already open (active, score={score_active:.4f}) at {click_active}")
            return True

        # Check INACTIVE - icon visible but panel closed
        is_inactive, score_inactive, click_inactive = is_arms_race_icon_visible(frame, use_active=False)
        if is_inactive:
            logger.debug(f"Arms Race icon found (inactive, score={score_inactive:.4f}) at {click_inactive}")
            return True

        # Neither found - scroll and retry
        logger.debug(f"Arms Race icon not visible (attempt {attempt + 1}/{max_scrolls}), scrolling...")
        scroll_bottom_bar_left(adb)
        time.sleep(0.5)

    logger.warning("Arms Race icon not found after scrolling")
    return False


def open_arms_race_panel(adb, win, debug: bool = False, max_scrolls: int = 5) -> bool:
    """
    Navigate to Arms Race panel with scroll handling.

    1. Find and click Events icon (scans right sidebar)
    2. Check ACTIVE first (panel already open)
    3. Check INACTIVE (scroll if needed, then click)
    4. Verify panel opened

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        debug: Enable debug logging
        max_scrolls: Maximum scroll attempts to find Arms Race

    Returns:
        True if successfully opened Arms Race panel
    """
    # Step 1: Find and click Events icon (scans vertically on right side)
    events_matcher = EventsIconMatcher()
    frame = win.get_screenshot_cv2()
    found, score, click_pos = events_matcher.find(frame)

    if not found:
        logger.error(f"Events icon NOT FOUND (score={score:.4f}), cannot open Arms Race panel")
        return False

    logger.info(f"Events icon found at {click_pos} (score={score:.4f}), clicking...")
    adb.tap(*click_pos)
    time.sleep(1.5)

    # Step 3: Check ACTIVE first - panel might already be open
    frame = win.get_screenshot_cv2()
    is_active, score_active, click_active = is_arms_race_icon_visible(frame, use_active=True)
    if is_active:
        logger.info(f"Arms Race panel already open (score={score_active:.4f})")
        return True

    # Step 4: Find INACTIVE icon (scroll if needed) and click
    for attempt in range(max_scrolls):
        frame = win.get_screenshot_cv2()

        # Check INACTIVE
        is_inactive, score_inactive, click_pos = is_arms_race_icon_visible(frame, use_active=False)
        if is_inactive:
            logger.info(f"Arms Race icon found (score={score_inactive:.4f}) at {click_pos}, clicking...")
            adb.tap(*click_pos)
            time.sleep(1.5)

            # Verify panel opened by checking ACTIVE
            frame = win.get_screenshot_cv2()
            is_now_active, score_now, _ = is_arms_race_icon_visible(frame, use_active=True)
            if is_now_active:
                logger.info(f"Arms Race panel opened successfully (score={score_now:.4f})")
                return True

            # Retry click once
            logger.warning("Panel not open after click, retrying...")
            adb.tap(*click_pos)
            time.sleep(1.5)

            frame = win.get_screenshot_cv2()
            is_now_active, score_now, _ = is_arms_race_icon_visible(frame, use_active=True)
            if is_now_active:
                logger.info(f"Arms Race panel opened on retry (score={score_now:.4f})")
                return True

            logger.error("Failed to open Arms Race panel after clicking")
            return False

        # Not found - scroll and retry
        logger.debug(f"Arms Race icon not visible (attempt {attempt + 1}/{max_scrolls}), scrolling...")
        scroll_bottom_bar_left(adb)
        time.sleep(0.5)

    logger.error(f"Arms Race icon not found after {max_scrolls} scrolls")
    return False


# =============================================================================
# PROGRESS CALCULATION
# =============================================================================

def get_rallies_needed(current_points: int) -> int:
    """
    Calculate rallies needed to reach chest3.

    Args:
        current_points: Current Arms Race points

    Returns:
        Number of rallies needed (0 if already at or above chest3)
    """
    points_needed = CHEST3_TARGET - current_points
    if points_needed <= 0:
        return 0
    return ceil(points_needed / POINTS_PER_RALLY)


def get_stamina_needed(rallies_needed: int) -> int:
    """Calculate stamina needed for the given number of rallies."""
    return rallies_needed * STAMINA_PER_RALLY


def calculate_boosts_needed(rallies_needed: int, current_stamina: int, stamina_per_boost: int = 40) -> int:
    """
    Calculate stamina boosts needed to complete all rallies.

    Args:
        rallies_needed: Number of rallies to complete
        current_stamina: Current stamina available
        stamina_per_boost: Stamina gained per boost (default 40, verify in-game)

    Returns:
        Number of boosts needed
    """
    total_stamina_needed = rallies_needed * STAMINA_PER_RALLY
    stamina_deficit = total_stamina_needed - current_stamina

    if stamina_deficit <= 0:
        return 0

    return ceil(stamina_deficit / stamina_per_boost)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def check_beast_training_progress(adb, win, debug: bool = False) -> dict:
    """
    Full check: open panel, verify event, calculate rallies.

    This is the main entry point for the daemon to call during
    Mystic Beast Training event.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        debug: Enable debug logging

    Returns:
        Dict with:
            - success: bool - True if check completed successfully
            - current_points: int | None - Current Arms Race points
            - rallies_needed: int | None - Rallies needed for chest3
            - stamina_needed: int | None - Stamina needed for those rallies
            - chest3_target: int - Always 30000
            - event_verified: bool - True if Mystic Beast Training header matched
    """
    result = {
        "success": False,
        "current_points": None,
        "rallies_needed": None,
        "stamina_needed": None,
        "chest3_target": CHEST3_TARGET,
        "event_verified": False,
    }

    try:
        # Open Arms Race panel
        if not open_arms_race_panel(adb, win, debug=debug):
            logger.error("Failed to open Arms Race panel")
            return result

        # Take screenshot
        frame = win.get_screenshot_cv2()

        # Verify Mystic Beast Training header
        is_beast, header_score = is_beast_training_header_visible(frame)
        result["event_verified"] = is_beast

        if not is_beast:
            logger.warning(f"Not in Mystic Beast Training event (score={header_score:.4f})")
            # Still try to get points, but mark as not verified
        else:
            logger.info(f"Mystic Beast Training verified (score={header_score:.4f})")

        # OCR current points (triple verification)
        current_points = get_current_points_verified(win, retries=3)
        if current_points is None:
            logger.warning("Failed to OCR current points (no consensus after 3 attempts)")
            # Return to base view before failing
            return_to_base_view(adb, win, debug=debug)
            return result

        result["current_points"] = current_points

        # Calculate rallies needed
        rallies_needed = get_rallies_needed(current_points)
        result["rallies_needed"] = rallies_needed
        result["stamina_needed"] = get_stamina_needed(rallies_needed)

        logger.info(
            f"Beast Training progress: {current_points}/{CHEST3_TARGET} pts, "
            f"need {rallies_needed} rallies ({result['stamina_needed']} stamina)"
        )

        result["success"] = True

    except Exception as e:
        logger.error(f"Error checking beast training progress: {e}")

    finally:
        # Always return to base view
        try:
            return_to_base_view(adb, win, debug=debug)
        except Exception as e:
            logger.warning(f"Failed to return to base view: {e}")

    return result


# =============================================================================
# GENERIC ARMS RACE CHECK (for any event)
# =============================================================================

def check_arms_race_progress(adb, win, debug: bool = False) -> dict:
    """
    Generic Arms Race check - works for ANY event.

    Opens panel, detects event, validates against scheduler, OCRs points,
    and reports which flows would trigger.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        debug: Enable debug logging

    Returns:
        Dict with:
            - success: bool
            - detected_event: str | None - Event detected from panel header
            - expected_event: str | None - Event from scheduler
            - event_match: bool - Whether detected matches expected
            - current_points: int | None
            - chest3_target: int | None - From metadata
            - points_to_chest3: int | None - Remaining points needed
            - would_trigger_flows: list[str] - Flows that would trigger
    """
    from utils.arms_race import get_arms_race_status, get_event_metadata
    from utils.arms_race_ocr import detect_active_event, get_current_points_verified

    result = {
        "success": False,
        "detected_event": None,
        "expected_event": None,
        "event_match": False,
        "current_points": None,
        "chest3_target": None,
        "points_to_chest3": None,
        "would_trigger_flows": [],
    }

    try:
        # Get expected event from scheduler
        arms_race_status = get_arms_race_status()
        expected_event = arms_race_status.get("current")
        result["expected_event"] = expected_event
        logger.info(f"Scheduler expects event: {expected_event}")

        # Open Arms Race panel
        if not open_arms_race_panel(adb, win, debug=debug):
            logger.error("Failed to open Arms Race panel")
            return result

        # Take screenshot and detect event
        frame = win.get_screenshot_cv2()
        detected_event, score = detect_active_event(frame)
        result["detected_event"] = detected_event
        logger.info(f"Detected event: {detected_event} (score={score:.4f})")

        # Validate match
        result["event_match"] = (detected_event == expected_event)
        if not result["event_match"]:
            logger.warning(f"EVENT MISMATCH: detected={detected_event}, expected={expected_event}")
        else:
            logger.info(f"Event validated: {detected_event}")

        # OCR current points (triple verification)
        current_points = get_current_points_verified(win, retries=3)
        result["current_points"] = current_points

        if current_points is None:
            logger.warning("Failed to OCR current points")
        else:
            logger.info(f"Current points: {current_points}")

            # Get chest3 target from metadata
            if detected_event:
                try:
                    meta = get_event_metadata(detected_event)
                    chest3 = meta.get("chest3")
                    result["chest3_target"] = chest3
                    if chest3:
                        result["points_to_chest3"] = max(0, chest3 - current_points)
                        logger.info(f"Chest3: {chest3}, need {result['points_to_chest3']} more points")
                except Exception as e:
                    logger.warning(f"Could not get metadata for {detected_event}: {e}")

        # Determine which flows would trigger
        flows = []
        if detected_event == "Mystic Beast Training":
            flows.append("beast_training_rally")
        elif detected_event == "Enhance Hero":
            flows.append("hero_upgrade")
        elif detected_event == "Soldier Training":
            flows.append("soldier_upgrade")

        # Check if chest3 already reached
        if result["points_to_chest3"] == 0:
            flows = [f + " (SKIPPED - chest3 reached)" for f in flows]

        result["would_trigger_flows"] = flows
        result["success"] = True

        logger.info(f"Would trigger flows: {flows}")

    except Exception as e:
        logger.error(f"Error checking arms race progress: {e}")

    finally:
        # Always return to base view
        try:
            return_to_base_view(adb, win, debug=debug)
        except Exception as e:
            logger.warning(f"Failed to return to base view: {e}")

    return result


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    print("=== Arms Race Panel Helper Test ===\n")

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        # Full progress check
        print("Running full progress check...")
        result = check_beast_training_progress(adb, win, debug=True)
        print(f"\nResult: {result}")
    else:
        # Quick test - just check if icon visible
        print("Taking screenshot...")
        frame = win.get_screenshot_cv2()

        print("\nChecking Arms Race icon visibility...")
        is_inactive, score_inactive, pos_inactive = is_arms_race_icon_visible(frame, use_active=False)
        is_active, score_active, pos_active = is_arms_race_icon_visible(frame, use_active=True)

        print(f"  Inactive icon: visible={is_inactive}, score={score_inactive:.4f}, pos={pos_inactive}")
        print(f"  Active icon: visible={is_active}, score={score_active:.4f}, pos={pos_active}")

        print("\nChecking panel state...")
        panel_open = is_arms_race_panel_open(frame)
        print(f"  Panel open: {panel_open}")

        if panel_open:
            print("\nChecking event header...")
            is_beast, header_score = is_beast_training_header_visible(frame)
            print(f"  Mystic Beast Training: {is_beast}, score={header_score:.4f}")

            print("\nOCR current points...")
            points = get_current_points(frame)
            print(f"  Current points: {points}")

            if points is not None:
                rallies = get_rallies_needed(points)
                stamina = get_stamina_needed(rallies)
                print(f"  Rallies needed: {rallies}")
                print(f"  Stamina needed: {stamina}")
