"""
Corn harvest bubble matcher for farm harvest detection.

Uses template_matcher for fixed-position detection.
Coordinates loaded from config.CORN_BUBBLE - override in config_local.py for your town layout.
"""
from __future__ import annotations

import numpy as np

from config import CORN_BUBBLE, THRESHOLDS
from utils.template_matcher import match_template


class CornHarvestMatcher:
    """
    Presence detector for corn harvest bubble at configurable location.
    """

    # Load from config (can be overridden in config_local.py)
    ICON_X = CORN_BUBBLE['region'][0]
    ICON_Y = CORN_BUBBLE['region'][1]
    ICON_WIDTH = CORN_BUBBLE['region'][2]
    ICON_HEIGHT = CORN_BUBBLE['region'][3]
    CLICK_X = CORN_BUBBLE['click'][0]
    CLICK_Y = CORN_BUBBLE['click'][1]

    TEMPLATE_NAME = "corn_harvest_bubble_4k.png"
    DEFAULT_THRESHOLD = THRESHOLDS.get('corn', 0.06)

    def __init__(self, threshold: float = None, debug_dir=None) -> None:
        """
        Initialize corn harvest bubble detector.

        Args:
            threshold: Maximum difference score (default from config.THRESHOLDS)
            debug_dir: Ignored (kept for backward compatibility)
        """
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def is_present(self, frame: np.ndarray, save_debug: bool = False) -> tuple[bool, float]:
        """
        Check if corn harvest bubble is present at FIXED location.

        Args:
            frame: BGR image frame from screenshot
            save_debug: Ignored (kept for backward compatibility)

        Returns:
            Tuple of (is_present, score)
        """
        if frame is None or frame.size == 0:
            return False, 1.0

        is_present, score, _ = match_template(frame, self.TEMPLATE_NAME, search_region=(self.ICON_X, self.ICON_Y, self.ICON_WIDTH, self.ICON_HEIGHT),
            threshold=self.threshold
        )

        return is_present, score

    def click(self, adb_helper) -> None:
        """Click at the FIXED corn bubble center position."""
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)
