"""
Promote Button Matcher - Detects "Promote" button in upgrade panel.

Uses template_matcher for fixed-location detection.
Position: (2065, 1648), Size: 181x54
Click position: (2157, 1697) - center of full button
"""
from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt

from utils.template_matcher import match_template

# Fixed location for promote text
PROMOTE_REGION = (2065, 1648, 181, 54)  # x, y, width, height

# Click position (center of button, not text)
PROMOTE_CLICK = (2157, 1697)

# Match threshold (TM_SQDIFF_NORMED - lower is better)
THRESHOLD = 0.1


class PromoteButtonMatcher:
    """Detects Promote button using fixed-location template matching."""

    TEMPLATE_NAME = "promote_text_4k.png"

    def __init__(self, threshold: float | None = None):
        self.threshold = threshold if threshold is not None else THRESHOLD

    def is_present(self, frame: npt.NDArray[Any], debug: bool = False) -> tuple[bool, float]:
        """
        Check if Promote button is visible at fixed location.

        Args:
            frame: BGR numpy array (screenshot)
            debug: Print debug info if True

        Returns:
            tuple: (is_present: bool, score: float)
        """
        if frame is None or frame.size == 0:
            return False, 1.0

        x, y, w, h = PROMOTE_REGION
        is_match, score, _ = match_template(frame, self.TEMPLATE_NAME, search_region=(x, y, w, h),
            threshold=self.threshold
        )

        if debug:
            status = "present" if is_match else "absent"
            print(f"Promote button: {status} (score={score:.4f}, threshold={self.threshold})")

        return is_match, score

    def get_click_position(self) -> tuple[int, int]:
        """Return the click position for the Promote button."""
        return PROMOTE_CLICK


# Module-level singleton
_matcher = None


def get_matcher() -> PromoteButtonMatcher:
    """Get or create singleton matcher instance."""
    global _matcher
    if _matcher is None:
        _matcher = PromoteButtonMatcher()
    return _matcher


def is_promote_visible(frame: npt.NDArray[Any], debug: bool = False) -> tuple[bool, float]:
    """Check if Promote button is visible."""
    return get_matcher().is_present(frame, debug=debug)


def get_promote_click() -> tuple[int, int]:
    """Get click position for Promote button."""
    return get_matcher().get_click_position()


if __name__ == "__main__":
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()

    is_present, score = is_promote_visible(frame, debug=True)
    print(f"Promote button present: {is_present}, score: {score:.4f}")
    print(f"Click position: {get_promote_click()}")
