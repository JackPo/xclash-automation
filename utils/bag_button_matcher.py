"""
Bag button matcher for resource claiming icon detection.

Uses template_matcher for fixed-position detection.

FIXED specs (4K resolution):
- Detection region: (3679, 1577) size 86x93
- Click position: (3732, 1633) - center of original detection
- NOT affected by dog house alignment - always at this fixed position
"""
from __future__ import annotations

import numpy as np

from utils.template_matcher import match_template


class BagButtonMatcher:
    """
    Presence detector for BAG button at FIXED location.
    Used to verify bag button is visible before clicking.
    """

    ICON_X = 3679
    ICON_Y = 1577
    ICON_WIDTH = 86
    ICON_HEIGHT = 93
    CLICK_X = 3732
    CLICK_Y = 1633

    TEMPLATE_NAME = "bag_button_4k.png"
    DEFAULT_THRESHOLD = 0.1

    def __init__(self, threshold: float = None) -> None:
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
