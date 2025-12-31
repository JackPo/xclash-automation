"""
Back button matcher for detecting chat/dialog windows.

Uses template_matcher for fixed-position detection.

FIXED specs (4K resolution):
- Position: (1345, 2002) size 107x111 pixels
- Click position: (1407, 2055) - center of back button
- Threshold: 0.06 (TM_SQDIFF_NORMED, lower = better)
"""
from __future__ import annotations

import numpy as np

from utils.template_matcher import match_template_fixed


class BackButtonMatcher:
    """
    Presence detector for back button at FIXED location.
    """

    POSITION_X = 1345
    POSITION_Y = 2002
    WIDTH = 107
    HEIGHT = 111

    CLICK_X = 1407
    CLICK_Y = 2055

    TEMPLATE_NAME = "back_button_union_4k.png"
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
            position=(self.POSITION_X, self.POSITION_Y),
            size=(self.WIDTH, self.HEIGHT),
            threshold=self.threshold
        )

        return is_present, score

    def click(self, adb_helper) -> None:
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)
