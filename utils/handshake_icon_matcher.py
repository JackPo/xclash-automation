"""
Handshake icon template matcher for Union button detection.

Uses template_matcher for fixed-position detection at (3088, 1780).

Usage:
    from handshake_icon_matcher import HandshakeIconMatcher

    matcher = HandshakeIconMatcher()
    is_present, score = matcher.is_present(frame)
    if is_present:
        matcher.click(adb)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import numpy as np

from utils.template_matcher import match_template_fixed


@dataclass
class TemplateMatch:
    """Represents a single template match result."""

    label: str
    score: float
    center: Tuple[int, int]
    top_left: Tuple[int, int]
    bottom_right: Tuple[int, int]


class HandshakeIconMatcher:
    """
    Presence detector for handshake icon at FIXED location.

    FIXED specs (4K resolution):
    - Extraction position: (3088, 1780)
    - Size: 155x127 pixels
    - Click position (ALWAYS): (3165, 1843)
    """

    # HARDCODED coordinates - these NEVER change
    ICON_X = 3088
    ICON_Y = 1780
    ICON_WIDTH = 155
    ICON_HEIGHT = 127
    CLICK_X = 3165
    CLICK_Y = 1843

    TEMPLATE_NAME = "handshake_iter2.png"
    DEFAULT_THRESHOLD = 0.04

    def __init__(self, threshold: float = None, debug_dir=None) -> None:
        """
        Initialize handshake icon presence detector.

        Args:
            threshold: Maximum difference score (default 0.04)
            debug_dir: Ignored (kept for backward compatibility)
        """
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def is_present(self, frame: np.ndarray, save_debug: bool = False) -> tuple[bool, float]:
        """
        Check if handshake icon is present at FIXED location.

        Args:
            frame: BGR image frame from screenshot
            save_debug: Ignored (kept for backward compatibility)

        Returns:
            Tuple of (is_present, score)
        """
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
        """Click at the FIXED handshake icon center position."""
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)
