"""
Union Technology Donation Flow - Donate to union technology research.

Trigger Conditions:
- User idle for 20+ minutes
- No other flows currently running (lowest priority)
- At most once per hour (cooldown: 60 minutes)

Sequence:
1. Click Union button (bottom bar)
2. Click Union Technology button
3. Validate we're on the Technology panel (header check at fixed position)
4. Find red thumbs up badge (pick highest Y if multiple matches)
5. Click the badge
6. Validate donate dialog (donate_200 button at fixed position)
7. Long press (1 second hold) on donate button
8. Use return_to_base_view() to exit

NOTE: ALL detection uses WindowsScreenshotHelper (NOT ADB screenshots).
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
import numpy as np

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.view_state_detector import detect_view, ViewState
from utils.return_to_base_view import return_to_base_view

# Setup logger
logger = logging.getLogger("union_technology_flow")

# Debug output directory
DEBUG_DIR = Path(__file__).parent.parent.parent / "screenshots" / "debug" / "union_technology_flow"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

# Template paths
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "ground_truth"
UNION_TECHNOLOGY_HEADER_TEMPLATE = TEMPLATES_DIR / "union_technology_header_4k.png"
TECH_DONATE_THUMBS_UP_TEMPLATE = TEMPLATES_DIR / "tech_donate_thumbs_up_4k.png"
TECH_DONATE_200_BUTTON_TEMPLATE = TEMPLATES_DIR / "tech_donate_200_button_4k.png"

# Fixed click coordinates (4K resolution)
UNION_BUTTON_CLICK = (3165, 2033)  # Union button on bottom bar
UNION_TECHNOLOGY_CLICK = (2175, 1382)  # Union Technology menu item
DONATE_BUTTON_CLICK = (2157, 1535)  # Donate 200 button center

# Header validation (fixed position)
HEADER_X = 1608
HEADER_Y = 209
HEADER_WIDTH = 611
HEADER_HEIGHT = 69
HEADER_THRESHOLD = 0.05  # TM_SQDIFF_NORMED (lower = better)

# Donate 200 button validation (fixed position)
DONATE_BUTTON_X = 1973
DONATE_BUTTON_Y = 1470
DONATE_BUTTON_WIDTH = 369
DONATE_BUTTON_HEIGHT = 130
DONATE_BUTTON_THRESHOLD = 0.05

# Thumbs up badge detection (whole screen search)
THUMBS_UP_THRESHOLD = 0.05  # TM_SQDIFF_NORMED threshold
MIN_DISTANCE_BETWEEN_MATCHES = 50  # Pixels, to avoid duplicate detections

# Timing constants
CLICK_DELAY = 0.5
SCREEN_TRANSITION_DELAY = 1.5
LONG_PRESS_DURATION = 3000  # 3 seconds in milliseconds

# Load templates once
_header_template = None
_thumbs_up_template = None
_donate_button_template = None


def _get_header_template():
    global _header_template
    if _header_template is None:
        _header_template = cv2.imread(str(UNION_TECHNOLOGY_HEADER_TEMPLATE), cv2.IMREAD_GRAYSCALE)
    return _header_template


def _get_thumbs_up_template():
    global _thumbs_up_template
    if _thumbs_up_template is None:
        _thumbs_up_template = cv2.imread(str(TECH_DONATE_THUMBS_UP_TEMPLATE), cv2.IMREAD_GRAYSCALE)
    return _thumbs_up_template


def _get_donate_button_template():
    global _donate_button_template
    if _donate_button_template is None:
        _donate_button_template = cv2.imread(str(TECH_DONATE_200_BUTTON_TEMPLATE), cv2.IMREAD_GRAYSCALE)
    return _donate_button_template


def _is_on_technology_panel(frame: np.ndarray) -> tuple[bool, float]:
    """Check if we're on the Union Technology panel by matching header at fixed position."""
    template = _get_header_template()
    if template is None:
        return False, 1.0

    # Extract ROI at fixed position
    roi = frame[HEADER_Y:HEADER_Y + HEADER_HEIGHT, HEADER_X:HEADER_X + HEADER_WIDTH]

    if len(roi.shape) == 3:
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    else:
        roi_gray = roi

    # Resize template if needed to match ROI
    if roi_gray.shape != template.shape:
        template_resized = cv2.resize(template, (roi_gray.shape[1], roi_gray.shape[0]))
    else:
        template_resized = template

    # Template match
    result = cv2.matchTemplate(roi_gray, template_resized, cv2.TM_SQDIFF_NORMED)
    min_val, _, _, _ = cv2.minMaxLoc(result)
    score = float(min_val)

    is_on_panel = score <= HEADER_THRESHOLD
    return is_on_panel, score


def _is_donate_dialog_visible(frame: np.ndarray) -> tuple[bool, float]:
    """Check if donate dialog is visible by matching donate_200 button at fixed position."""
    template = _get_donate_button_template()
    if template is None:
        return False, 1.0

    # Extract ROI at fixed position
    roi = frame[DONATE_BUTTON_Y:DONATE_BUTTON_Y + DONATE_BUTTON_HEIGHT,
                DONATE_BUTTON_X:DONATE_BUTTON_X + DONATE_BUTTON_WIDTH]

    if len(roi.shape) == 3:
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    else:
        roi_gray = roi

    # Resize template if needed to match ROI
    if roi_gray.shape != template.shape:
        template_resized = cv2.resize(template, (roi_gray.shape[1], roi_gray.shape[0]))
    else:
        template_resized = template

    # Template match
    result = cv2.matchTemplate(roi_gray, template_resized, cv2.TM_SQDIFF_NORMED)
    min_val, _, _, _ = cv2.minMaxLoc(result)
    score = float(min_val)

    is_visible = score <= DONATE_BUTTON_THRESHOLD
    return is_visible, score


def _find_thumbs_up_badge_highest_y(frame: np.ndarray) -> tuple[int, int, float] | None:
    """Find the red thumbs up badge with highest Y value. Returns (x, y, score) or None."""
    template = _get_thumbs_up_template()
    if template is None:
        return None

    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame

    h, w = template.shape
    result = cv2.matchTemplate(gray, template, cv2.TM_SQDIFF_NORMED)

    # Find all matches below threshold
    matches = []
    locations = np.where(result < THUMBS_UP_THRESHOLD)

    for pt in zip(*locations[::-1]):  # x, y format
        score = result[pt[1], pt[0]]
        center_x = pt[0] + w // 2
        center_y = pt[1] + h // 2
        matches.append((center_x, center_y, float(score)))

    if not matches:
        return None

    # Remove duplicates (matches too close together)
    filtered = []
    for match in sorted(matches, key=lambda x: x[2]):  # Sort by score
        x, y, score = match
        is_duplicate = False
        for fx, fy, _ in filtered:
            if abs(x - fx) < MIN_DISTANCE_BETWEEN_MATCHES and abs(y - fy) < MIN_DISTANCE_BETWEEN_MATCHES:
                is_duplicate = True
                break
        if not is_duplicate:
            filtered.append(match)

    if not filtered:
        return None

    # Pick the one with lowest Y value (top-most / higher position on screen)
    lowest_y_match = min(filtered, key=lambda x: x[1])
    return lowest_y_match


def _save_debug_screenshot(frame, name: str) -> str:
    """Save screenshot for debugging. Returns path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = DEBUG_DIR / f"{timestamp}_{name}.png"
    cv2.imwrite(str(path), frame)
    return str(path)


def _log(msg: str):
    """Log to both logger and stdout."""
    logger.info(msg)
    print(f"    [UNION_TECH] {msg}")


def union_technology_flow(adb) -> bool:
    """
    Execute the union technology donation flow.

    Args:
        adb: ADBHelper instance

    Returns:
        bool: True if flow completed successfully, False otherwise
    """
    flow_start = time.time()
    _log("=== UNION TECHNOLOGY FLOW START ===")

    win = WindowsScreenshotHelper()

    # Step 1: Click Union button
    _log(f"Step 1: Clicking Union button at {UNION_BUTTON_CLICK}")
    adb.tap(*UNION_BUTTON_CLICK)
    time.sleep(SCREEN_TRANSITION_DELAY)

    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "01_after_union_click")

    # Step 2: Click Union Technology
    _log(f"Step 2: Clicking Union Technology at {UNION_TECHNOLOGY_CLICK}")
    adb.tap(*UNION_TECHNOLOGY_CLICK)
    time.sleep(SCREEN_TRANSITION_DELAY)

    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "02_after_technology_click")

    # Step 3: Validate we're on Technology panel
    is_on_panel, header_score = _is_on_technology_panel(frame)
    _log(f"Step 3: Header validation - on_panel={is_on_panel}, score={header_score:.4f}")

    if not is_on_panel:
        _log("FAILED: Not on Union Technology panel, aborting")
        return_to_base_view(adb, win, debug=False)
        return False

    # Step 4: Find red thumbs up badge (highest Y)
    badge = _find_thumbs_up_badge_highest_y(frame)

    if badge is None:
        _log("No donation badge found, nothing to donate")
        return_to_base_view(adb, win, debug=False)
        elapsed = time.time() - flow_start
        _log(f"=== UNION TECHNOLOGY FLOW COMPLETE (no donations) === (took {elapsed:.1f}s)")
        return True

    badge_x, badge_y, badge_score = badge
    _log(f"Step 4: Found badge at ({badge_x}, {badge_y}) score={badge_score:.4f}")

    # Step 5: Click the badge
    _log(f"Step 5: Clicking badge at ({badge_x}, {badge_y})")
    adb.tap(badge_x, badge_y)
    time.sleep(SCREEN_TRANSITION_DELAY)

    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "05_after_badge_click")

    # Step 6: Validate donate dialog appeared
    is_dialog_visible, dialog_score = _is_donate_dialog_visible(frame)
    _log(f"Step 6: Donate dialog validation - visible={is_dialog_visible}, score={dialog_score:.4f}")

    if not is_dialog_visible:
        _log("WARNING: Donate dialog not detected, trying to click anyway")

    # Step 7: Long press on donate button (3 second hold)
    _log(f"Step 7: Long pressing donate button at {DONATE_BUTTON_CLICK} for 3 seconds")
    x, y = DONATE_BUTTON_CLICK
    adb.swipe(x, y, x, y, duration=LONG_PRESS_DURATION)
    time.sleep(CLICK_DELAY)

    frame = win.get_screenshot_cv2()
    if frame is not None:
        _save_debug_screenshot(frame, "07_after_donate")

    # Step 8: Return to base view
    _log("Step 8: Returning to base view")
    return_to_base_view(adb, win, debug=False)

    elapsed = time.time() - flow_start
    _log(f"=== UNION TECHNOLOGY FLOW SUCCESS === (took {elapsed:.1f}s)")
    return True


if __name__ == "__main__":
    # Test the flow manually
    from utils.adb_helper import ADBHelper

    adb = ADBHelper()
    print("Testing Union Technology Flow...")
    print("=" * 50)

    success = union_technology_flow(adb)

    print("=" * 50)
    if success:
        print("Flow completed successfully!")
    else:
        print("Flow FAILED!")
