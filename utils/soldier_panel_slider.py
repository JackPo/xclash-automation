"""
Soldier Panel Slider Helper - Shared slider control for Soldier Training panel.

Used by:
- soldier_upgrade_flow.py (promotions)
- barracks_training_flow.py (timed training)
- soldier_training_flow.py (basic training)

All coordinates are for 4K resolution (3840x2160).
"""

import cv2
from pathlib import Path

# Slider constants (4K resolution)
SLIDER_Y = 1170
SLIDER_MIN_X = 1600  # Circle center at MIN (leftmost)
SLIDER_MAX_X = 2132  # Circle center at MAX (rightmost)

# Search region for slider circle template matching
SEARCH_Y_START = 1100
SEARCH_Y_END = 1250
SEARCH_X_START = 1400
SEARCH_X_END = 2300

# Plus/Minus buttons
PLUS_BUTTON = (2207, 1179)
MINUS_BUTTON = (1526, 1177)

# Template path
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "ground_truth" / "slider_circle_4k.png"

_template_cache = None


def _get_template():
    """Load and cache the slider circle template."""
    global _template_cache
    if _template_cache is None:
        _template_cache = cv2.imread(str(TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)
    return _template_cache


def find_slider_circle(frame):
    """Find slider circle position using template matching.

    Args:
        frame: BGR screenshot (numpy array)

    Returns:
        (x, score) tuple where x is the circle center X coordinate,
        or (None, score) if not found (score > 0.1)
    """
    template = _get_template()
    if template is None:
        return None, 1.0

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    search_region = gray[SEARCH_Y_START:SEARCH_Y_END, SEARCH_X_START:SEARCH_X_END]

    result = cv2.matchTemplate(search_region, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)

    if min_val < 0.1:
        h, w = template.shape[:2]
        x = SEARCH_X_START + min_loc[0] + w // 2
        return x, min_val
    return None, min_val


def drag_slider_to_max(adb, frame, debug=False):
    """Find slider and drag to maximum position.

    Args:
        adb: ADBHelper instance
        frame: BGR screenshot (numpy array)
        debug: Enable debug logging

    Returns:
        bool: True if successful
    """
    circle_x, score = find_slider_circle(frame)
    if circle_x is None:
        if debug:
            print(f"  ERROR: Slider not found (score={score:.4f})")
        return False

    if debug:
        print(f"  Slider at x={circle_x}, dragging to max ({SLIDER_MAX_X})...")

    adb.swipe(circle_x, SLIDER_Y, SLIDER_MAX_X, SLIDER_Y, duration=500)
    return True


def drag_slider_to_position(adb, frame, target_x, debug=False):
    """Find slider and drag to a specific X position.

    Args:
        adb: ADBHelper instance
        frame: BGR screenshot (numpy array)
        target_x: Target X coordinate for slider
        debug: Enable debug logging

    Returns:
        bool: True if successful
    """
    circle_x, score = find_slider_circle(frame)
    if circle_x is None:
        if debug:
            print(f"  ERROR: Slider not found (score={score:.4f})")
        return False

    if debug:
        print(f"  Slider at x={circle_x}, dragging to {target_x}...")

    adb.swipe(circle_x, SLIDER_Y, target_x, SLIDER_Y, duration=500)
    return True


def calculate_slider_position(ratio):
    """Calculate slider X position for a given ratio (0.0 to 1.0).

    Args:
        ratio: Value between 0.0 (min) and 1.0 (max)

    Returns:
        X coordinate for slider position
    """
    ratio = max(0.0, min(1.0, ratio))  # Clamp to [0, 1]
    slider_width = SLIDER_MAX_X - SLIDER_MIN_X
    return SLIDER_MIN_X + int(ratio * slider_width)
