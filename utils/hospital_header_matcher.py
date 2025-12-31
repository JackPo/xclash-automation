"""
Hospital Header Matcher - Verifies hospital healing panel is open.

Uses template_matcher for search-based detection.
Template: hospital_header_4k.png
"""

import numpy as np

from utils.template_matcher import match_template

# Match threshold (TM_SQDIFF_NORMED - lower is better)
MATCH_THRESHOLD = 0.1


class HospitalHeaderMatcher:
    """Detects if hospital healing panel is open."""

    TEMPLATE_NAME = "hospital_header_4k.png"

    def __init__(self, threshold: float = None):
        self.threshold = threshold if threshold is not None else MATCH_THRESHOLD

    def is_panel_open(self, frame: np.ndarray, debug: bool = False) -> tuple[bool, float]:
        """
        Check if hospital healing panel is open.

        Args:
            frame: BGR numpy array screenshot
            debug: Enable debug output

        Returns:
            tuple: (is_open: bool, score: float)
        """
        if frame is None or frame.size == 0:
            return False, 1.0

        is_open, score, location = match_template(
            frame,
            self.TEMPLATE_NAME,
            threshold=self.threshold
        )

        if debug:
            print(f"  Hospital header: score={score:.6f} at {location}")
            print(f"  Panel open: {is_open}")

        return is_open, score


# Singleton instance
_matcher = None


def get_matcher() -> HospitalHeaderMatcher:
    global _matcher
    if _matcher is None:
        _matcher = HospitalHeaderMatcher()
    return _matcher


def is_panel_open(frame: np.ndarray, debug: bool = False) -> tuple[bool, float]:
    """Convenience function to check if panel is open."""
    return get_matcher().is_panel_open(frame, debug=debug)
