"""
AFK rewards chest matcher for idle rewards detection.

Uses template_matcher for fixed-position detection.

FIXED specs (4K resolution):
- Position: (754, 1667) size 123x85 pixels
- Click position: (805, 1709) - center of chest icon
- Threshold: 0.06 (TM_SQDIFF_NORMED, lower = better)
"""
from __future__ import annotations

import numpy as np

from utils.template_matcher import match_template_fixed


class AfkRewardsMatcher:
    """
    Presence detector for AFK rewards chest at FIXED location.
    """

    ICON_X = 754
    ICON_Y = 1667
    ICON_WIDTH = 123
    ICON_HEIGHT = 85
    CLICK_X = 805
    CLICK_Y = 1709

    TEMPLATE_NAME = "chest_timer_4k.png"
    DEFAULT_THRESHOLD = 0.06

    def __init__(self, threshold: float = None, debug_dir=None) -> None:
        # debug_dir ignored - kept for backward compatibility
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def is_present(self, frame: np.ndarray, save_debug: bool = False) -> tuple[bool, float]:
        if frame is None or frame.size == 0:
            return False, 1.0

        is_present, score, _ = match_template_fixed(
            frame,
            self.TEMPLATE_NAME,
            position=(self.ICON_X, self.ICON_Y),
            size=(self.ICON_WIDTH, self.ICON_HEIGHT),
            threshold=self.threshold
        )

        return is_present, score

    def click(self, adb_helper) -> None:
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)
