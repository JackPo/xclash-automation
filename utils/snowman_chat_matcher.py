"""
Snowman Party chat message matcher.

Detects the yellow "Snowman Party" chat bubble that appears when a snowman spawns.
Uses search-based detection (banner can appear anywhere vertically in chat).

SPECS (4K resolution):
- Template: snowman_party_chat_4k.png (772x80)
- Search region: Full vertical strip in chat area
- Click on message to navigate to snowman location
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np


class SnowmanChatMatcher:
    """
    Search-based detector for "Snowman Party" chat message.
    """

    # Search region - chat panel appears in CENTER of screen when opened
    SEARCH_X = 1100
    SEARCH_Y = 0
    SEARCH_WIDTH = 1700  # Chat panel is centered ~1200-2800
    SEARCH_HEIGHT = 2160  # Full screen height

    # Click offset from template top-left to center of message
    CLICK_OFFSET_X = 386  # 772/2 = center
    CLICK_OFFSET_Y = 40   # 80/2 = center

    # Default threshold (TM_SQDIFF_NORMED - lower is better)
    DEFAULT_THRESHOLD = 0.1

    def __init__(
        self,
        template_path: Optional[Path] = None,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        base_dir = Path(__file__).resolve().parent.parent

        if template_path is None:
            template_path = base_dir / "templates" / "ground_truth" / "snowman_party_chat_4k.png"

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
        Check if "Snowman Party" chat message is visible.

        Args:
            frame: BGR image frame from screenshot

        Returns:
            Tuple of (is_present, score, found_position)
            - is_present: True if message found
            - score: Match score (lower = better)
            - found_position: (x, y) of message top-left, or None
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
            found_x = self.SEARCH_X + min_loc[0]
            found_y = self.SEARCH_Y + min_loc[1]
            found_position = (found_x, found_y)
        else:
            found_position = None

        return is_present, score, found_position

    def get_click_position(self, found_position: Tuple[int, int]) -> Tuple[int, int]:
        """Calculate click position from found template position."""
        click_x = found_position[0] + self.CLICK_OFFSET_X
        click_y = found_position[1] + self.CLICK_OFFSET_Y
        return click_x, click_y

    def click(self, adb_helper, found_position: Tuple[int, int]) -> None:
        """Click on the chat message."""
        click_x, click_y = self.get_click_position(found_position)
        adb_helper.tap(click_x, click_y)
