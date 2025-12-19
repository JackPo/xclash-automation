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

from pathlib import Path
import cv2
import numpy as np

# Template path
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"
GROUND_TEMPLATE_PATH = TEMPLATE_DIR / "safe_ground_tile_4k.png"

# Search region - center area of screen where ground tiles are visible
# Avoid edges where UI elements are
SEARCH_REGION = (500, 400, 2800, 1800)  # (x, y, width, height)

# Match threshold (TM_SQDIFF_NORMED - lower is better)
MATCH_THRESHOLD = 0.15  # Looser threshold since ground tiles vary slightly


class SafeGroundMatcher:
    """Finds safe ground tiles to click for popup dismissal."""

    def __init__(self):
        self.template = cv2.imread(str(GROUND_TEMPLATE_PATH))
        if self.template is None:
            print(f"Warning: Could not load {GROUND_TEMPLATE_PATH}")
        self.threshold = MATCH_THRESHOLD

    def find_ground(self, frame: np.ndarray, debug: bool = False) -> tuple[int, int] | None:
        """
        Find a safe ground tile in the frame.

        Args:
            frame: BGR numpy array screenshot
            debug: Print debug info

        Returns:
            (x, y) click position if found, None otherwise
        """
        if self.template is None:
            return None

        # Extract search region to speed up matching
        rx, ry, rw, rh = SEARCH_REGION
        roi = frame[ry:ry+rh, rx:rx+rw]

        # Template match
        result = cv2.matchTemplate(roi, self.template, cv2.TM_SQDIFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if debug:
            print(f"  SafeGround: score={min_val:.4f}, threshold={self.threshold}")

        if min_val <= self.threshold:
            # Convert ROI coords back to frame coords
            roi_x, roi_y = min_loc
            frame_x = rx + roi_x + self.template.shape[1] // 2
            frame_y = ry + roi_y + self.template.shape[0] // 2

            if debug:
                print(f"  SafeGround: Found at ({frame_x}, {frame_y})")

            return (frame_x, frame_y)

        if debug:
            print(f"  SafeGround: Not found (score {min_val:.4f} > threshold {self.threshold})")
        return None


# Singleton instance
_matcher = None


def get_matcher() -> SafeGroundMatcher:
    """Get singleton matcher instance."""
    global _matcher
    if _matcher is None:
        _matcher = SafeGroundMatcher()
    return _matcher


def find_safe_ground(frame: np.ndarray, debug: bool = False) -> tuple[int, int] | None:
    """
    Convenience function to find safe ground tile.

    Args:
        frame: BGR numpy array screenshot
        debug: Print debug info

    Returns:
        (x, y) click position if found, None otherwise
    """
    return get_matcher().find_ground(frame, debug=debug)
