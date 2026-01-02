"""
Back button matcher - SEARCHES for back buttons across the screen.

Uses template_matcher to find back buttons anywhere in the bottom portion.
Tries multiple templates to handle different button styles.

Templates:
- back_button_4k.png - Standard back button
- back_button_light_4k.png - Light colored variant
- back_button_union_4k.png - Union panel back button
"""
from __future__ import annotations

import numpy as np

from utils.template_matcher import match_template


class BackButtonMatcher:
    """
    Search-based detector for back buttons.
    Finds back button anywhere in search region and returns click position.
    """

    # Templates to try (in order)
    TEMPLATES = [
        "back_button_union_4k.png",
        "back_button_4k.png",
        "back_button_light_4k.png",
    ]

    # Search in bottom half of screen where back buttons typically appear
    SEARCH_REGION = (0, 1080, 3840, 1080)  # x, y, w, h - bottom half

    # Tight threshold to avoid false positives
    DEFAULT_THRESHOLD = 0.05

    def __init__(self, threshold: float = None, debug_dir=None) -> None:
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def find(self, frame: np.ndarray) -> tuple[bool, float, tuple[int, int] | None]:
        """
        Search for back button in frame.

        Returns:
            (found: bool, score: float, click_pos: tuple or None)
            click_pos is center of detected button
        """
        if frame is None or frame.size == 0:
            return False, 1.0, None

        best_score = 1.0
        best_pos = None
        best_found = False

        for template_name in self.TEMPLATES:
            found, score, location = match_template(
                frame,
                template_name,
                search_region=self.SEARCH_REGION,
                threshold=self.threshold
            )

            if found and score < best_score:
                best_score = score
                best_found = True
                # match_template already returns center coordinates
                if location:
                    best_pos = location

        return best_found, best_score, best_pos

    def is_present(self, frame: np.ndarray, save_debug: bool = False) -> tuple[bool, float]:
        """Legacy API - returns (found, score) without position."""
        found, score, _ = self.find(frame)
        return found, score

    def click(self, adb_helper) -> None:
        """Legacy API - clicks fixed position. Use find() for dynamic position."""
        adb_helper.tap(1407, 2055)
