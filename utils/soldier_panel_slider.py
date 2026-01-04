"""
Soldier Panel Slider Helper - Shared slider control for Soldier Training panel.

Used by:
- soldier_upgrade_flow.py (promotions)
- barracks_training_flow.py (timed training)
- soldier_training_flow.py (basic training)

All coordinates are for 4K resolution (3840x2160).
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy.typing as npt

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

# Slider constants (4K resolution) - Soldier Training panel
# Calibrated 2026-01-04 via iterative testing
SLIDER_Y = 1175  # Y coordinate of slider track center
SLIDER_MIN_X = 1604  # Left edge of track (after minus button)
SLIDER_MAX_X = 2137  # Right edge of track (before plus button) - CLICK HERE FOR MAX

# Search region for slider circle template matching
SEARCH_Y_START = 1145
SEARCH_Y_END = 1205
SEARCH_X_START = 1604  # Left edge of track
SEARCH_X_END = 2137    # Right edge of track

# Plus/Minus buttons (center positions)
PLUS_BUTTON = (2208, 1175)
MINUS_BUTTON = (1525, 1175)

# Template path
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "ground_truth" / "slider_circle_4k.png"

_template_cache: npt.NDArray[Any] | None = None


def _get_template() -> npt.NDArray[Any] | None:
    """Load and cache the slider circle template."""
    global _template_cache
    if _template_cache is None:
        _template_cache = cv2.imread(str(TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)
    return _template_cache


def find_slider_circle(frame: npt.NDArray[Any]) -> tuple[int | None, int | None, float]:
    """Find slider circle position using full-frame template matching.

    Args:
        frame: BGR screenshot (numpy array)

    Returns:
        (x, y, score) tuple where x,y is the circle center,
        or (None, None, score) if not found (score > 0.1)
    """
    template = _get_template()
    if template is None:
        return None, None, 1.0

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame

    # Full frame search to find slider at any Y position
    result = cv2.matchTemplate(gray, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)

    if min_val < 0.1:
        h, w = template.shape[:2]
        x = min_loc[0] + w // 2
        y = min_loc[1] + h // 2
        return x, y, min_val
    return None, None, min_val


def find_plus_button(frame: npt.NDArray[Any]) -> tuple[int | None, int | None, float]:
    """Find plus button position using template matching.

    Returns:
        (x, y, score) tuple where x,y is the button center,
        or (None, None, score) if not found
    """
    template_path = Path(__file__).parent.parent / "templates" / "ground_truth" / "hospital_plus_button_4k.png"
    template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
    if template is None:
        return None, None, 1.0  # type: ignore[unreachable]

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    result = cv2.matchTemplate(gray, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)

    if min_val < 0.1:
        h, w = template.shape[:2]
        x = min_loc[0] + w // 2
        y = min_loc[1] + h // 2
        return x, y, min_val
    return None, None, min_val


def drag_slider_to_max(adb: ADBHelper, frame: npt.NDArray[Any], debug: bool = False) -> bool:
    """Find plus button and click on rightmost edge of slider track.

    Args:
        adb: ADBHelper instance
        frame: BGR screenshot (required to find plus button Y position)
        debug: Enable debug logging

    Returns:
        bool: True if successful
    """
    # Find plus button to get correct Y position (different screens have different Y)
    plus_x, plus_y, score = find_plus_button(frame)

    if plus_x is None or plus_y is None:
        if debug:
            print(f"  ERROR: Plus button not found (score={score:.4f})")
        return False

    # Track right edge is 54 pixels left of plus button center
    track_right_x = plus_x - 54

    if debug:
        print(f"  Plus button at ({plus_x}, {plus_y}), clicking track right edge ({track_right_x}, {plus_y})...")

    adb.tap(track_right_x, plus_y)
    return True


def drag_slider_to_position(adb: ADBHelper, frame: npt.NDArray[Any], target_x: int, debug: bool = False) -> bool:
    """Find slider and drag to a specific X position.

    Args:
        adb: ADBHelper instance
        frame: BGR screenshot (numpy array)
        target_x: Target X coordinate for slider
        debug: Enable debug logging

    Returns:
        bool: True if successful
    """
    circle_x, circle_y, score = find_slider_circle(frame)
    if circle_x is None or circle_y is None:
        if debug:
            print(f"  ERROR: Slider not found (score={score:.4f})")
        return False

    if debug:
        print(f"  Slider at ({circle_x}, {circle_y}), dragging to ({target_x}, {circle_y})...")

    adb.swipe(circle_x, circle_y, target_x, circle_y, duration=500)
    return True


def calculate_slider_position(ratio: float) -> int:
    """Calculate slider X position for a given ratio (0.0 to 1.0).

    Args:
        ratio: Value between 0.0 (min) and 1.0 (max)

    Returns:
        X coordinate for slider position
    """
    ratio = max(0.0, min(1.0, ratio))  # Clamp to [0, 1]
    slider_width = SLIDER_MAX_X - SLIDER_MIN_X
    return SLIDER_MIN_X + int(ratio * slider_width)
