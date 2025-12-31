"""
Safe Ground Matcher - Finds clickable ground tiles to dismiss popups.

When the daemon accidentally clicks on a building and opens a menu,
it gets stuck in UNKNOWN view state. This matcher finds the stone
pavement tiles in the town area so we can click on them to dismiss
any popup and return to clean TOWN view.

Usage:
    from utils.safe_ground_matcher import find_safe_ground

    pos = find_safe_ground(frame)
    if pos:
        adb.tap(*pos)  # Clicks on safe ground, dismissing popup
"""

import numpy as np
from typing import Optional, Tuple

from utils.template_matcher import match_template

# Search region - center area of screen where ground tiles are visible
# Avoid edges where UI elements are
SEARCH_REGION = (500, 400, 2800, 1800)  # (x, y, width, height)

# Match threshold (TM_SQDIFF_NORMED - lower is better)
MATCH_THRESHOLD = 0.01


class SafeGroundMatcher:
    """Finds safe ground tiles to click for popup dismissal."""

    TEMPLATE_NAME = "safe_ground_tile_4k.png"

    def __init__(self, threshold: float = None):
        self.threshold = threshold if threshold is not None else MATCH_THRESHOLD

    def find_ground(self, frame: np.ndarray, debug: bool = False) -> Optional[Tuple[int, int]]:
        """
        Find a safe ground tile in the frame.

        Args:
            frame: BGR numpy array screenshot
            debug: Print debug info

        Returns:
            (x, y) click position if found, None otherwise
        """
        if frame is None or frame.size == 0:
            return None

        found, score, location = match_template(
            frame,
            self.TEMPLATE_NAME,
            search_region=SEARCH_REGION,
            threshold=self.threshold
        )

        if debug:
            print(f"  SafeGround: score={score:.4f}, threshold={self.threshold}")

        if found and location:
            if debug:
                print(f"  SafeGround: Found at {location}")
            return location

        if debug:
            print(f"  SafeGround: Not found (score {score:.4f} > threshold {self.threshold})")
        return None


# Singleton instance
_matcher = None


def get_matcher() -> SafeGroundMatcher:
    """Get singleton matcher instance."""
    global _matcher
    if _matcher is None:
        _matcher = SafeGroundMatcher()
    return _matcher


def find_safe_ground(frame: np.ndarray, debug: bool = False) -> Optional[Tuple[int, int]]:
    """
    Convenience function to find safe ground tile.

    Args:
        frame: BGR numpy array screenshot
        debug: Print debug info

    Returns:
        (x, y) click position if found, None otherwise
    """
    return get_matcher().find_ground(frame, debug=debug)
