"""
Gem bubble matcher for gem harvest detection.

Uses template_matcher for fixed-position detection.
Coordinates loaded from config.GEM_BUBBLE - override in config_local.py for your town layout.
"""
from __future__ import annotations

import numpy as np

from config import GEM_BUBBLE, THRESHOLDS
from utils.template_matcher import match_template_fixed


class GemMatcher:
    """Presence detector for gem bubble at configurable location."""

    ICON_X = GEM_BUBBLE['region'][0]
    ICON_Y = GEM_BUBBLE['region'][1]
    ICON_WIDTH = GEM_BUBBLE['region'][2]
    ICON_HEIGHT = GEM_BUBBLE['region'][3]
    CLICK_X = GEM_BUBBLE['click'][0]
    CLICK_Y = GEM_BUBBLE['click'][1]

    TEMPLATE_NAME = "gem_tight_4k.png"
    DEFAULT_THRESHOLD = THRESHOLDS.get('gem', 0.13)

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
