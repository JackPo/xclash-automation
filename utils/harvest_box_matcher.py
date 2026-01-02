"""
Harvest box matcher for gift box icon detection on Heroes button.

Uses template_matcher for fixed-position detection at (2100, 1540).
"""
from __future__ import annotations

import numpy as np

from utils.template_matcher import match_template


class HarvestBoxMatcher:
    """
    Presence detector for harvest box icon at FIXED location.

    FIXED specs (4K resolution):
    - Extraction position: (2100, 1540)
    - Size: 154x157 pixels
    - Click position: (2177, 1618)
    """

    ICON_X = 2100
    ICON_Y = 1540
    ICON_WIDTH = 154
    ICON_HEIGHT = 157
    CLICK_X = 2177
    CLICK_Y = 1618

    TEMPLATE_NAME = "harvest_box_4k.png"
    DEFAULT_THRESHOLD = 0.1

    def __init__(self, threshold: float = None, debug_dir=None) -> None:
        # debug_dir ignored - kept for backward compatibility
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def is_present(self, frame: np.ndarray, save_debug: bool = False) -> tuple[bool, float]:
        if frame is None or frame.size == 0:
            return False, 1.0

        is_present, score, _ = match_template(frame, self.TEMPLATE_NAME, search_region=(self.ICON_X, self.ICON_Y, self.ICON_WIDTH, self.ICON_HEIGHT),
            threshold=self.threshold
        )

        return is_present, score

    def click(self, adb_helper) -> None:
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)
