"""
Rally Plus Button Matcher - Detects join rally plus buttons.

Uses template_matcher for full-frame search, then filters to slot 4 position.
"""

import numpy as np
from typing import List, Tuple

from utils.template_matcher import match_template


class RallyPlusMatcher:
    """Detects rally plus buttons using full-frame search."""

    # Plus button coordinates (from docs/joining_rallies.md)
    PLUS_BUTTON_X = 1902  # Slot 4 (rightmost plus button position)
    PLUS_BUTTON_WIDTH = 130
    PLUS_BUTTON_HEIGHT = 130

    TEMPLATE_NAME = "rally_plus_button_4k.png"
    DEFAULT_THRESHOLD = 0.05

    def __init__(self, threshold: float = None):
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def find_all_plus_buttons(self, frame: np.ndarray) -> List[Tuple[int, int, float]]:
        """
        Search entire frame for plus buttons using template matching.

        Strategy:
        1. Run template matching on ENTIRE frame
        2. Find all matches below threshold
        3. Filter to keep only matches near X=1902 (slot 4 position)
        4. Return all matches sorted by Y (top to bottom)

        Args:
            frame: BGR screenshot from WindowsScreenshotHelper

        Returns:
            List of (x, y, score) tuples sorted by Y coordinate (top to bottom)
            Note: x,y is the CENTER of the button
        """
        import cv2

        if frame is None or frame.size == 0:
            return []

        # Load template for full-frame search
        from pathlib import Path
        template_path = Path(__file__).parent.parent / "templates" / "ground_truth" / self.TEMPLATE_NAME
        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            return []

        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Template matching on ENTIRE frame
        result = cv2.matchTemplate(frame_gray, template, cv2.TM_SQDIFF_NORMED)

        # Find all matches below threshold
        locations = np.where(result <= self.threshold)

        matches = []
        for pt in zip(*locations[::-1]):  # Switch x and y
            x, y = pt
            score = float(result[y, x])

            # Filter: only keep matches near slot 4 X position (within 10 pixels)
            if abs(x - self.PLUS_BUTTON_X) <= 10:
                # Convert to center position
                center_x = x + self.PLUS_BUTTON_WIDTH // 2
                center_y = y + self.PLUS_BUTTON_HEIGHT // 2
                matches.append((center_x, center_y, score))

        # Remove duplicate detections (within 50 pixels vertically)
        filtered_matches = self._filter_duplicates(matches)

        # Sort by Y coordinate (top to bottom)
        filtered_matches.sort(key=lambda m: m[1])

        return filtered_matches

    def _filter_duplicates(self, matches: List[Tuple[int, int, float]]) -> List[Tuple[int, int, float]]:
        """
        Remove duplicate detections that are close together.

        Strategy: Keep the match with the best (lowest) score among nearby matches.
        """
        if not matches:
            return []

        sorted_matches = sorted(matches, key=lambda m: m[1])

        filtered = []
        MIN_DISTANCE = 50

        for match in sorted_matches:
            x, y, score = match

            is_duplicate = False
            for i, (fx, fy, fscore) in enumerate(filtered):
                if abs(y - fy) < MIN_DISTANCE:
                    is_duplicate = True
                    if score < fscore:
                        filtered[i] = match
                    break

            if not is_duplicate:
                filtered.append(match)

        return filtered

    def get_click_position(self, plus_x: int, plus_y: int) -> Tuple[int, int]:
        """
        Get click position for a plus button.

        Note: find_all_plus_buttons already returns center positions.
        """
        return plus_x, plus_y
