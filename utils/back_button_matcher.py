"""
Back button matcher - SEARCHES for back buttons across the screen.

Uses template_matcher to find back buttons anywhere in the bottom portion.
Tries multiple templates to handle different button styles.

Templates:
- back_button_4k.png - Standard back button
- back_button_light_4k.png - Light colored variant
- back_button_union_4k.png - Union panel back button (has mask)

All templates use TM_SQDIFF_NORMED: lower score = better match, ~0.0 is perfect.
This matcher normalizes scores to a common 0-1 range where higher is always better.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt

from utils.template_matcher import match_template

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper


class BackButtonMatcher:
    """
    Search-based detector for back buttons.
    Finds back button anywhere in search region and returns click position.

    All templates use SQDIFF_NORMED (lower=better). Normalizes scores for comparison.
    """

    # Templates to try (in order)
    TEMPLATES = [
        "back_button_union_4k.png",       # Has mask - uses SQDIFF with mask
        "back_button_union_ice_4k.png",   # Ice theme variant (has mask)
        "back_button_4k.png",              # No mask - uses SQDIFF
        "back_button_light_4k.png",        # No mask - uses SQDIFF
    ]

    # Search in LEFT portion of bottom half only - back buttons are typically on the left
    # Position 1407 is the typical back button X coordinate
    # Restricting to left 1600px avoids false positives from center-screen popups
    # (Union Center, building popups, etc.)
    SEARCH_REGION = (0, 1080, 1600, 1080)  # x, y, w, h - left side of bottom half

    def __init__(self, threshold: float | None = None, debug_dir: Any = None) -> None:
        # Let template_matcher use default threshold (0.1 for non-masked, 0.05 for masked)
        self.threshold = threshold

    def find(self, frame: npt.NDArray[Any]) -> tuple[bool, float, tuple[int, int] | None, str | None]:
        """
        Search for back button in frame.

        Returns:
            (found: bool, score: float, click_pos: tuple or None, template_name: str or None)
            - found: True if any template matched
            - score: Raw score of best match (interpretation depends on method)
            - click_pos: Center of detected button, or None
            - template_name: Which template matched, or None
        """
        if frame is None or frame.size == 0:
            return False, 1.0, None, None

        best_normalized = -1.0  # Higher is better in normalized space
        best_raw_score = 1.0
        best_pos = None
        best_template = None

        for template_name in self.TEMPLATES:
            found, raw_score, location = match_template(
                frame,
                template_name,
                search_region=self.SEARCH_REGION,
                threshold=self.threshold  # None = use template_matcher defaults
            )

            if found:
                # Normalize score to 0-1 where higher is better
                # All templates use SQDIFF: invert so higher is better
                normalized = 1.0 - raw_score

                # Pick best match in normalized space
                if normalized > best_normalized:
                    best_normalized = normalized
                    best_raw_score = raw_score
                    best_template = template_name
                    if location:
                        best_pos = location

        found = best_normalized >= 0
        return found, best_raw_score, best_pos, best_template

    def is_template_present(self, frame: npt.NDArray[Any], template_name: str,
                            near_pos: tuple[int, int] | None = None,
                            tolerance: int = 30) -> bool:
        """
        Check if a SPECIFIC template is present, optionally near a position.

        Args:
            frame: Screenshot
            template_name: Specific template to check (e.g., "back_button_union_4k.png")
            near_pos: If provided, only return True if found within tolerance of this position
            tolerance: Max pixel distance from near_pos (default 30)

        Returns:
            True if template is present (and near position if specified)
        """
        if frame is None or frame.size == 0:
            return False

        found, score, location = match_template(
            frame,
            template_name,
            search_region=self.SEARCH_REGION,
            threshold=self.threshold
        )

        if not found:
            return False

        if near_pos and location:
            dx = abs(location[0] - near_pos[0])
            dy = abs(location[1] - near_pos[1])
            if dx > tolerance or dy > tolerance:
                return False  # Found but at different position

        return True

    def is_present(self, frame: npt.NDArray[Any], save_debug: bool = False) -> tuple[bool, float]:
        """Legacy API - returns (found, score) without position."""
        found, score, _, _ = self.find(frame)
        return found, score

    def click(self, adb_helper: ADBHelper, detected_pos: tuple[int, int] | None = None) -> None:
        """Click back button at detected position, or fallback to fixed position.

        Args:
            adb_helper: ADBHelper instance
            detected_pos: Optional (x, y) position from find(). If None, uses fixed fallback.
        """
        pos = detected_pos if detected_pos else (1407, 2055)
        adb_helper.tap(*pos, source="matcher:back_button:click")
