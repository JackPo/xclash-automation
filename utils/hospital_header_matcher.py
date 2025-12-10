"""
Hospital Header Matcher - Verifies hospital healing panel is open.

Fixed position: (1793, 330) size 246x60
Template: hospital_header_4k.png
"""

from pathlib import Path
import cv2

# Template path
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "ground_truth" / "hospital_header_4k.png"

# Fixed position for header
HEADER_X = 1793
HEADER_Y = 330
HEADER_WIDTH = 246
HEADER_HEIGHT = 60

# Match threshold (TM_SQDIFF_NORMED - lower is better)
MATCH_THRESHOLD = 0.1


class HospitalHeaderMatcher:
    """Detects if hospital healing panel is open."""

    def __init__(self):
        self.template = cv2.imread(str(TEMPLATE_PATH))
        if self.template is None:
            raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")

    def is_panel_open(self, frame, debug=False):
        """
        Check if hospital healing panel is open.

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
            print(f"  Hospital header: score={min_val:.6f} at ({x}, {y})")
            print(f"  Panel open: {is_open}")

        return is_open, min_val


# Singleton instance
_matcher = None

def get_matcher():
    global _matcher
    if _matcher is None:
        _matcher = HospitalHeaderMatcher()
    return _matcher


def is_panel_open(frame, debug=False):
    """Convenience function to check if panel is open."""
    return get_matcher().is_panel_open(frame, debug=debug)
