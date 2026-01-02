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

# Add parent dirs to path for imports
_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import cv2
import numpy as np

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.return_to_base_view import return_to_base_view
from utils.template_matcher import match_template_fixed, match_template_all

# Setup logger
logger = logging.getLogger("union_technology_flow")

# Template paths (for reference only - using template_matcher)
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "ground_truth"

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

def _is_on_technology_panel(frame: np.ndarray) -> tuple[bool, float]:
    """Check if we're on the Union Technology panel by matching header at fixed position."""
    found, score, _ = match_template_fixed(
        frame, "union_technology_header_4k.png",
        position=(HEADER_X, HEADER_Y),
        size=(HEADER_WIDTH, HEADER_HEIGHT),
        threshold=HEADER_THRESHOLD
    )
    return found, score


def _is_donate_dialog_visible(frame: np.ndarray) -> tuple[bool, float]:
    """Check if donate dialog is visible by matching donate_200 button at fixed position."""
    found, score, _ = match_template_fixed(
        frame, "tech_donate_200_button_4k.png",
        position=(DONATE_BUTTON_X, DONATE_BUTTON_Y),
        size=(DONATE_BUTTON_WIDTH, DONATE_BUTTON_HEIGHT),
        threshold=DONATE_BUTTON_THRESHOLD
    )
    return found, score


def _find_thumbs_up_badge_topmost(frame: np.ndarray) -> tuple[int, int, float] | None:
    """Find the red thumbs up badge with lowest Y value (top-most). Returns (center_x, center_y, score) or None."""
    # Use match_template_all which returns CENTER coordinates sorted by Y
    matches = match_template_all(
        frame, "tech_donate_thumbs_up_4k.png",
        threshold=THUMBS_UP_THRESHOLD,
        min_distance=MIN_DISTANCE_BETWEEN_MATCHES
    )

    if not matches:
        return None

    # First match is top-most (sorted by Y)
    return matches[0]


def _save_debug_screenshot(frame, name: str) -> str:
    """Save screenshot for debugging. Returns path."""
    from utils.debug_screenshot import save_debug_screenshot
    return save_debug_screenshot(frame, "union_technology", name)


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
    badge = _find_thumbs_up_badge_topmost(frame)

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
