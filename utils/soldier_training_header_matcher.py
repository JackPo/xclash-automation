"""
Soldier Training Header Matcher - Verifies soldier training panel is open.

Fixed position: (1670, 313) size 491x65
Template: soldier_training_header_4k.png
"""

from pathlib import Path
import cv2

# Template path
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "ground_truth" / "soldier_training_header_4k.png"

# Fixed position for header
HEADER_X = 1670
HEADER_Y = 313
HEADER_WIDTH = 491
HEADER_HEIGHT = 65

# Match threshold (TM_SQDIFF_NORMED - lower is better)
MATCH_THRESHOLD = 0.1


class SoldierTrainingHeaderMatcher:
    """Detects if soldier training panel is open."""

    def __init__(self):
        self.template = cv2.imread(str(TEMPLATE_PATH))
        if self.template is None:
            raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")

    def is_panel_open(self, frame, debug=False):
        """
        Check if soldier training panel is open.

        Args:
            frame: BGR numpy array screenshot
            debug: Enable debug output

        Returns:
            tuple: (is_open: bool, score: float)
        """
        # Use full frame template matching
        result = cv2.matchTemplate(frame, self.template, cv2.TM_SQDIFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        x, y = min_loc
        is_open = min_val < MATCH_THRESHOLD

        if debug:
            print(f"  Soldier training header: score={min_val:.6f} at ({x}, {y})")
            print(f"  Panel open: {is_open}")

        return is_open, min_val


# Singleton instance
_matcher = None

def get_matcher():
    global _matcher
    if _matcher is None:
        _matcher = SoldierTrainingHeaderMatcher()
    return _matcher


def is_panel_open(frame, debug=False):
    """Convenience function to check if panel is open."""
    return get_matcher().is_panel_open(frame, debug=debug)
