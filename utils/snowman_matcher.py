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

from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np


class SnowmanMatcher:
    """
    Search-based detector for snowman on the map.
    """

    # Search the center area of the screen (snowman should be centered after nav)
    SEARCH_X = 1000
    SEARCH_Y = 500
    SEARCH_WIDTH = 1800
    SEARCH_HEIGHT = 1200

    # Default threshold (TM_SQDIFF_NORMED - lower is better)
    DEFAULT_THRESHOLD = 0.1

    def __init__(
        self,
        template_path: Optional[Path] = None,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        base_dir = Path(__file__).resolve().parent.parent

        if template_path is None:
            template_path = base_dir / "templates" / "ground_truth" / "snowman_4k.png"

        self.template_path = Path(template_path)
        self.threshold = threshold

        self.template = cv2.imread(str(self.template_path), cv2.IMREAD_GRAYSCALE)
        if self.template is None:
            raise FileNotFoundError(f"Template not found: {self.template_path}")

        self.template_h, self.template_w = self.template.shape[:2]

    def is_present(
        self,
        frame: np.ndarray,
    ) -> Tuple[bool, float, Optional[Tuple[int, int]]]:
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

        # Extract search region
        roi = frame[
            self.SEARCH_Y:self.SEARCH_Y + self.SEARCH_HEIGHT,
            self.SEARCH_X:self.SEARCH_X + self.SEARCH_WIDTH
        ]

        if roi.size == 0:
            return False, 1.0, None

        if len(roi.shape) == 3:
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            roi_gray = roi

        # Check if ROI is large enough
        if roi_gray.shape[0] < self.template_h or roi_gray.shape[1] < self.template_w:
            return False, 1.0, None

        # Template match
        result = cv2.matchTemplate(roi_gray, self.template, cv2.TM_SQDIFF_NORMED)
        min_val, _, min_loc, _ = cv2.minMaxLoc(result)

        score = float(min_val)
        is_present = score <= self.threshold

        if is_present:
            # Return center position of snowman
            found_x = self.SEARCH_X + min_loc[0] + self.template_w // 2
            found_y = self.SEARCH_Y + min_loc[1] + self.template_h // 2
            found_position = (found_x, found_y)
        else:
            found_position = None

        return is_present, score, found_position

    def click(self, adb_helper, found_position: Tuple[int, int]) -> None:
        """Click on the snowman center."""
        adb_helper.tap(*found_position)
