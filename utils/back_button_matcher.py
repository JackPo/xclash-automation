"""
Back button matcher - SEARCHES for back buttons across the screen.

Uses template_matcher to find back buttons anywhere in the bottom portion.
Tries multiple templates to handle different button styles.

Templates:
- back_button_4k.png - Standard back button (SQDIFF - no mask)
- back_button_light_4k.png - Light colored variant (SQDIFF - no mask)
- back_button_union_4k.png - Union panel back button (CCORR - has mask)

IMPORTANT: Templates use different matching methods based on mask presence:
- SQDIFF (no mask): lower score = better match, ~0.0 is perfect
- CCORR (with mask): higher score = better match, ~1.0 is perfect

This matcher normalizes scores to a common 0-1 range where higher is always better.
"""
from __future__ import annotations

import numpy as np

from utils.template_matcher import match_template, has_mask


class BackButtonMatcher:
    """
    Search-based detector for back buttons.
    Finds back button anywhere in search region and returns click position.

    Handles mixed SQDIFF/CCORR templates by normalizing scores.
    """

    # Templates to try (in order)
    TEMPLATES = [
        "back_button_union_4k.png",   # Has mask - uses CCORR
        "back_button_4k.png",          # No mask - uses SQDIFF
        "back_button_light_4k.png",    # No mask - uses SQDIFF
    ]

    # Search in bottom half of screen where back buttons typically appear
    SEARCH_REGION = (0, 1080, 3840, 1080)  # x, y, w, h - bottom half

    def __init__(self, threshold: float = None, debug_dir=None) -> None:
        # Don't enforce a single threshold - let template_matcher use method-appropriate defaults
        # SQDIFF uses 0.1, CCORR uses 0.90 by default
        self.threshold = threshold

    def find(self, frame: np.ndarray) -> tuple[bool, float, tuple[int, int] | None]:
        """
        Search for back button in frame.

        Returns:
            (found: bool, score: float, click_pos: tuple or None)
            - found: True if any template matched
            - score: Raw score of best match (interpretation depends on method)
            - click_pos: Center of detected button, or None
        """
        if frame is None or frame.size == 0:
            return False, 1.0, None

        best_normalized = -1.0  # Higher is better in normalized space
        best_raw_score = 1.0
        best_pos = None

        for template_name in self.TEMPLATES:
            found, raw_score, location = match_template(
                frame,
                template_name,
                search_region=self.SEARCH_REGION,
                threshold=self.threshold  # None = use template_matcher defaults
            )

            if found:
                # Normalize score to 0-1 where higher is better
                if has_mask(template_name):
                    # CCORR: already 0-1, higher is better
                    normalized = raw_score
                else:
                    # SQDIFF: invert so higher is better
                    normalized = 1.0 - raw_score

                # Pick best match in normalized space
                if normalized > best_normalized:
                    best_normalized = normalized
                    best_raw_score = raw_score
                    if location:
                        best_pos = location

        found = best_normalized >= 0
        return found, best_raw_score, best_pos

    def is_present(self, frame: np.ndarray, save_debug: bool = False) -> tuple[bool, float]:
        """Legacy API - returns (found, score) without position."""
        found, score, _ = self.find(frame)
        return found, score

    def click(self, adb_helper) -> None:
        """Legacy API - clicks fixed position. Use find() for dynamic position."""
        adb_helper.tap(1407, 2055)
