"""
Handshake icon template matcher for Union button detection.

Uses cv2.TM_SQDIFF_NORMED for pixel-difference based matching at fixed location.
Template extracted from 4K screenshot at coordinates (3088, 1780) with size 155x127.

TM_SQDIFF_NORMED provides strong binary separation:
- Handshake present: score ~0.01 (LOW difference = good match)
- Handshake absent: score ~0.5+ (HIGH difference = no match)

Usage:
    from handshake_icon_matcher import HandshakeIconMatcher
    from adb_helper import ADBHelper

    matcher = HandshakeIconMatcher()
    adb = ADBHelper()

    # Capture and match
    full_path, _ = adb.take_screenshot("temp.png")
    frame = cv2.imread(full_path)
    match = matcher.find(frame)

    if match:
        matcher.click_center(adb, match)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np


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

    This is NOT a search tool - it checks if the handshake icon exists at the
    exact coordinates where it was originally extracted.

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

    def __init__(
        self,
        template_path: Optional[Path] = None,
        debug_dir: Optional[Path] = None,
        threshold: float = 0.05,
    ) -> None:
        """
        Initialize handshake icon presence detector.

        Args:
            template_path: Path to handshake template (default: templates/ground_truth/handshake_iter2.png)
            debug_dir: Directory for debug output (default: templates/debug/)
            threshold: Maximum difference score (default 0.05 for strict matching with TM_SQDIFF_NORMED)
                      Lower values = stricter matching. Score < threshold means match found.
        """
        base_dir = Path(__file__).resolve().parent

        if template_path is None:
            template_path = base_dir / "templates" / "ground_truth" / "handshake_iter2.png"

        self.template_path = Path(template_path)
        self.debug_dir = debug_dir or (base_dir / "templates" / "debug")
        self.threshold = threshold

        # Create debug directory
        self.debug_dir.mkdir(parents=True, exist_ok=True)

        # Load template
        self.template = cv2.imread(str(self.template_path), cv2.IMREAD_GRAYSCALE)
        if self.template is None:
            raise FileNotFoundError(f"Template not found: {self.template_path}")

    def is_present(
        self,
        frame: np.ndarray,
        save_debug: bool = True,
    ) -> tuple[bool, float]:
        """
        Check if handshake icon is present at FIXED location.

        This extracts the exact region where the template was found originally
        and checks if it still matches. Does NOT search.

        Args:
            frame: BGR image frame from screenshot
            save_debug: If True, save debug crops to debug_dir

        Returns:
            Tuple of (is_present, score)
        """
        if frame is None or frame.size == 0:
            return False, 0.0

        # Extract EXACT region where icon should be
        roi = frame[
            self.ICON_Y:self.ICON_Y + self.ICON_HEIGHT,
            self.ICON_X:self.ICON_X + self.ICON_WIDTH
        ]

        # Convert to grayscale
        if len(roi.shape) == 3:
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            roi_gray = roi

        # Match template against this EXACT region using squared difference
        # TM_SQDIFF_NORMED: Lower score = better match (opposite of correlation methods)
        result = cv2.matchTemplate(roi_gray, self.template, cv2.TM_SQDIFF_NORMED)
        min_val, _, _, _ = cv2.minMaxLoc(result)

        score = float(min_val)
        is_present = score <= self.threshold  # Inverted: lower score = better match

        if save_debug and is_present:
            self._save_debug_crop(roi, score)

        return is_present, score

    def click(self, adb_helper) -> None:
        """
        Click at the FIXED handshake icon center position.

        ALWAYS clicks at (3165, 1843) regardless of detection.
        Call is_present() first to check if icon is actually there.

        Args:
            adb_helper: ADBHelper instance
        """
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)

    def _save_debug_crop(self, roi: np.ndarray, score: float) -> None:
        """Save ROI region for debugging."""
        try:
            if roi.size == 0:
                return

            debug_path = self.debug_dir / f"handshake_present_{score:.3f}.png"
            cv2.imwrite(str(debug_path), roi)
        except Exception:
            pass
