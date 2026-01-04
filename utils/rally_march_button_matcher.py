"""
Rally March Button Matcher - Detects red flag march button in TOWN/WORLD view.

The march button appears as an overlay notification when a teammate starts a rally.
Uses template_matcher for Y-axis search at fixed X coordinate.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt

from utils.template_matcher import match_template


class RallyMarchButtonMatcher:
    """Detects rally march button using fixed X + Y search."""

    # March button coordinates
    MARCH_BUTTON_X = 3655  # FIXED X coordinate (right side of screen)
    MARCH_BUTTON_WIDTH = 154
    MARCH_BUTTON_HEIGHT = 73

    # Y-axis search range
    SEARCH_Y_START = 400
    SEARCH_Y_END = 1800

    TEMPLATE_NAME = "rally_march_button_small_4k.png"
    DEFAULT_THRESHOLD = 0.05

    def __init__(self, threshold: float | None = None) -> None:
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def find_march_button(self, frame: npt.NDArray[Any]) -> tuple[int, int, float] | None:
        """
        Search Y-axis at fixed X for march button.

        Uses a single large search region (fixed X, full Y range).

        Args:
            frame: BGR screenshot from WindowsScreenshotHelper

        Returns:
            (x, y, score) tuple if button found, None otherwise
            Note: x,y is the CENTER of the button
        """
        if frame is None or frame.size == 0:
            return None

        # Search region: fixed X, full Y range
        search_region = (
            self.MARCH_BUTTON_X,
            self.SEARCH_Y_START,
            self.MARCH_BUTTON_WIDTH,
            self.SEARCH_Y_END - self.SEARCH_Y_START
        )

        found, score, location = match_template(
            frame,
            self.TEMPLATE_NAME,
            search_region=search_region,
            threshold=self.threshold
        )

        if found and location:
            return (location[0], location[1], score)

        return None

    def is_present(self, frame: npt.NDArray[Any]) -> tuple[bool, float]:
        """
        Check if march button is present on screen.

        Args:
            frame: BGR screenshot from WindowsScreenshotHelper

        Returns:
            (present, score) - True if button detected, best score from search
        """
        match = self.find_march_button(frame)
        if match:
            _, _, score = match
            return True, score
        return False, 1.0

    def get_click_position(self, march_x: int, march_y: int) -> tuple[int, int]:
        """
        Calculate click position for march button.

        Note: match_template already returns center position, so just return as-is.

        Args:
            march_x: X coordinate of button center
            march_y: Y coordinate of button center

        Returns:
            (click_x, click_y) - Center of button
        """
        return march_x, march_y
