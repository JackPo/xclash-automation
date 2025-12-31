"""
Snowman location matcher - verifies arrival at snowman location.

Used after clicking the "Snowman Party" chat message to verify we navigated
to the correct location and the snowman is visible on screen.

SPECS (4K resolution):
- Template: snowman_4k.png (254x212)
- Search-based detection (snowman can be anywhere on screen after navigation)
- Center click position for interacting with snowman
"""
from __future__ import annotations

import numpy as np
from typing import Optional, Tuple

from utils.template_matcher import match_template


class SnowmanMatcher:
    """
    Search-based detector for snowman on the map.
    """

    # Search the center area of the screen (snowman should be centered after nav)
    SEARCH_REGION = (1000, 500, 1800, 1200)  # x, y, w, h

    TEMPLATE_NAME = "snowman_4k.png"
    DEFAULT_THRESHOLD = 0.1

    def __init__(self, threshold: float = None) -> None:
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def is_present(self, frame: np.ndarray) -> Tuple[bool, float, Optional[Tuple[int, int]]]:
        """
        Check if snowman is visible on screen.

        Args:
            frame: BGR image frame from screenshot

        Returns:
            Tuple of (is_present, score, found_position)
            - is_present: True if snowman found
            - score: Match score (lower = better)
            - found_position: (x, y) center of snowman, or None
        """
        if frame is None or frame.size == 0:
            return False, 1.0, None

        found, score, location = match_template(
            frame,
            self.TEMPLATE_NAME,
            search_region=self.SEARCH_REGION,
            threshold=self.threshold
        )

        return found, score, location if found else None

    def click(self, adb_helper, found_position: Tuple[int, int]) -> None:
        """Click on the snowman center."""
        adb_helper.tap(*found_position)
