"""
Treasure map icon template matcher for bouncing scroll detection.

Uses SINGLE template with mask for precise detection:
- treasure_map_4k.png + treasure_map_mask_4k.png

Analysis of 20 back-to-back screenshots showed:
- Group A (15/20 frames): IDENTICAL pixels at bounce position
- Bounced frames (5/20): No exact pairs found

Strategy: Use Group A template only - catches 15/20 frames with score < 0.001.
Over 2-3 consecutive screenshots, the bounce will return to Group A position.

Templates are in: templates/ground_truth/treasure_map/

Usage:
    from treasure_map_matcher import TreasureMapMatcher

    matcher = TreasureMapMatcher()
    is_present, score = matcher.is_present(frame)
    if is_present:
        matcher.click(adb)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt

from utils.template_matcher import match_template

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper


class TreasureMapMatcher:
    """
    Presence detector for treasure map icon at FIXED location.

    Uses single template with mask for precise detection (15/20 frames).
    Over 2-3 screenshots, bounce returns to detectable position.

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

    # Single template with mask (auto-detected by match_template)
    TEMPLATE = "treasure_map/treasure_map_4k.png"
    DEFAULT_THRESHOLD = 0.01  # Tight threshold - Group A frames match with score < 0.001

    def __init__(self, threshold: float | None = None, debug_dir: Any = None) -> None:
        """
        Initialize treasure map icon presence detector.

        Args:
            threshold: Maximum difference score (default 0.05)
            debug_dir: Ignored (kept for backward compatibility)
        """
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def is_present(self, frame: npt.NDArray[Any], save_debug: bool = False) -> tuple[bool, float]:
        """
        Check if treasure map icon is present at FIXED location.

        Uses single template with mask for precise matching.
        Detects 15/20 bounce frames with score < 0.001.

        Args:
            frame: BGR image frame from screenshot
            save_debug: Ignored (kept for backward compatibility)

        Returns:
            Tuple of (is_present, score)
        """
        if frame is None or frame.size == 0:
            return False, 1.0

        search_region = (self.ICON_X, self.ICON_Y, self.ICON_WIDTH, self.ICON_HEIGHT)

        # Single template with auto-detected mask
        found, score, _ = match_template(
            frame, self.TEMPLATE,
            search_region=search_region,
            threshold=self.threshold
        )

        return found, score

    def click(self, adb_helper: ADBHelper) -> None:
        """Click at the FIXED treasure map icon center position."""
        adb_helper.tap(self.CLICK_X, self.CLICK_Y, source="matcher:treasure_map:click")
