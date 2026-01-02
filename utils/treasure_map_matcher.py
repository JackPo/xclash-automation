"""
Treasure map icon template matcher for bouncing scroll detection.

Uses template_matcher for fixed-position detection at (2096, 1540).

Usage:
    from treasure_map_matcher import TreasureMapMatcher

    matcher = TreasureMapMatcher()
    is_present, score = matcher.is_present(frame)
    if is_present:
        matcher.click(adb)
"""
from __future__ import annotations

import numpy as np

from utils.template_matcher import match_template


class TreasureMapMatcher:
    """
    Presence detector for treasure map icon at FIXED location.

    FIXED specs (4K resolution):
    - Extraction position: (2096, 1540)
    - Size: 158x162 pixels
    - Click position (ALWAYS): (2175, 1621)
    """

    # HARDCODED coordinates - these NEVER change
    ICON_X = 2096
    ICON_Y = 1540
    ICON_WIDTH = 158
    ICON_HEIGHT = 162
    CLICK_X = 2175
    CLICK_Y = 1621

    TEMPLATE_NAME = "treasure_map_4k.png"
    DEFAULT_THRESHOLD = 0.05

    def __init__(self, threshold: float = None, debug_dir=None) -> None:
        """
        Initialize treasure map icon presence detector.

        Args:
            threshold: Maximum difference score (default 0.05)
            debug_dir: Ignored (kept for backward compatibility)
        """
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def is_present(self, frame: np.ndarray, save_debug: bool = False) -> tuple[bool, float]:
        """
        Check if treasure map icon is present at FIXED location.

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
        """Click at the FIXED treasure map icon center position."""
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)
