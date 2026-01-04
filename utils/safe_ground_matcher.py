"""
Safe Ground Matcher - Finds clickable ground tiles to dismiss popups.

Uses COLOR matching (not grayscale) to distinguish gray stone from tan popups.
"""
from __future__ import annotations

import cv2
import numpy as np
import numpy.typing as npt
from pathlib import Path
from typing import Any

# Search region - center area of screen where ground tiles are visible
SEARCH_REGION = (500, 400, 2800, 1800)  # (x, y, width, height)

# Match threshold (TM_SQDIFF_NORMED - lower is better)
MATCH_THRESHOLD = 0.02

# Template path - resolve from module location, not CWD
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "ground_truth" / "safe_ground_tile_4k.png"

# Cached template (BGR color)
_template: npt.NDArray[Any] | None = None


def _load_template() -> npt.NDArray[Any] | None:
    """Load template in COLOR (BGR), not grayscale."""
    global _template
    if _template is None:
        _template = cv2.imread(str(TEMPLATE_PATH), cv2.IMREAD_COLOR)
    return _template


def find_safe_ground(frame: npt.NDArray[Any], debug: bool = False) -> tuple[int, int] | None:
    """
    Find safe ground tile using COLOR matching.

    Args:
        frame: BGR numpy array screenshot
        debug: Print debug info

    Returns:
        (x, y) click position if found, None otherwise
    """
    if frame is None or frame.size == 0:
        return None

    template = _load_template()
    if template is None:
        if debug:
            print("  SafeGround: Template not found")
        return None

    # Extract search region
    x, y, w, h = SEARCH_REGION
    search_area = frame[y:y+h, x:x+w]

    th, tw = template.shape[:2]

    # Check if search area is large enough
    if search_area.shape[0] < th or search_area.shape[1] < tw:
        return None

    # COLOR matching - TM_SQDIFF_NORMED on BGR
    result = cv2.matchTemplate(search_area, template, cv2.TM_SQDIFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    score = min_val  # Lower is better for SQDIFF

    if debug:
        print(f"  SafeGround: score={score:.4f}, threshold={MATCH_THRESHOLD}")

    if score <= MATCH_THRESHOLD:
        # Convert to frame coordinates (center of match)
        match_x = x + min_loc[0] + tw // 2
        match_y = y + min_loc[1] + th // 2
        if debug:
            print(f"  SafeGround: Found at ({match_x}, {match_y})")
        return (match_x, match_y)

    if debug:
        print(f"  SafeGround: Not found (score {score:.4f} > threshold {MATCH_THRESHOLD})")
    return None


class SafeGroundMatcher:
    """Wrapper class for compatibility."""

    def __init__(self, threshold: float | None = None) -> None:
        self.threshold = threshold if threshold is not None else MATCH_THRESHOLD

    def find_ground(self, frame: npt.NDArray[Any], debug: bool = False) -> tuple[int, int] | None:
        return find_safe_ground(frame, debug=debug)


def get_matcher() -> SafeGroundMatcher:
    return SafeGroundMatcher()
