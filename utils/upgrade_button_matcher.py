"""
Upgrade Button Matcher - Detects available/unavailable upgrade buttons in hero detail view.

Uses template_matcher for search-based detection.
Compares two templates to distinguish between green (available) and grayed (unavailable) upgrade buttons.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt

from utils.template_matcher import match_template

# Fixed search region for upgrade button (4K resolution)
UPGRADE_BUTTON_REGION = (1700, 1750, 450, 160)  # x, y, w, h

# Click position (center of button)
UPGRADE_BUTTON_CLICK = (1919, 1829)

# Matching threshold
THRESHOLD = 0.1  # TM_SQDIFF_NORMED - lower is better


class UpgradeButtonMatcher:
    """Detects upgrade button state using two-template comparison."""

    AVAILABLE_TEMPLATE = "upgrade_button_available_4k.png"
    UNAVAILABLE_TEMPLATE = "upgrade_button_unavailable_4k.png"

    def __init__(self, threshold: float | None = None):
        self.threshold = threshold if threshold is not None else THRESHOLD

    def check_upgrade_available(self, frame: npt.NDArray[Any], debug: bool = False) -> tuple[bool, float, float]:
        """
        Check if upgrade button is available (green) or unavailable (grayed).

        Args:
            frame: Full screenshot (BGR numpy array)
            debug: If True, print debug info

        Returns:
            (is_available, available_score, unavailable_score)
            is_available is True if green upgrade button detected
        """
        if frame is None or frame.size == 0:
            return False, 1.0, 1.0

        # Match both templates in the search region
        _, available_score, _ = match_template(
            frame,
            self.AVAILABLE_TEMPLATE,
            search_region=UPGRADE_BUTTON_REGION,
            threshold=self.threshold
        )

        _, unavailable_score, _ = match_template(
            frame,
            self.UNAVAILABLE_TEMPLATE,
            search_region=UPGRADE_BUTTON_REGION,
            threshold=self.threshold
        )

        if debug:
            print(f"  Upgrade button - available: {available_score:.4f}, unavailable: {unavailable_score:.4f}")

        # Return True if available matches better than unavailable
        # Both must be under threshold to be considered a valid button
        if available_score < self.threshold and available_score < unavailable_score:
            return True, available_score, unavailable_score
        elif unavailable_score < self.threshold:
            return False, available_score, unavailable_score
        else:
            # Neither matches well - button not visible
            return False, available_score, unavailable_score

    def get_click_position(self) -> tuple[int, int]:
        """Get the click position for the upgrade button."""
        return UPGRADE_BUTTON_CLICK


if __name__ == '__main__':
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    print("Taking screenshot...")
    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()

    matcher = UpgradeButtonMatcher()
    is_available, avail_score, unavail_score = matcher.check_upgrade_available(frame, debug=True)

    print(f"\nUpgrade button available: {is_available}")
    print(f"  Available score: {avail_score:.4f}")
    print(f"  Unavailable score: {unavail_score:.4f}")
