"""
Rally Plus Button Matcher - Detects join rally plus buttons.

Uses fixed X coordinate and searches Y-axis to find all plus buttons
in the rightmost column of the rally list.
"""

from pathlib import Path
import cv2
import numpy as np
from typing import List, Tuple


class RallyPlusMatcher:
    """Detects rally plus buttons using fixed X + Y search."""

    # Plus button coordinates (from docs/joining_rallies.md)
    PLUS_BUTTON_X = 1902  # Slot 4 (rightmost plus button position)
    PLUS_BUTTON_WIDTH = 130
    PLUS_BUTTON_HEIGHT = 130
    PLUS_BUTTON_THRESHOLD = 0.05  # TM_SQDIFF_NORMED

    # Y-axis search range
    SEARCH_Y_START = 400
    SEARCH_Y_END = 1800
    SEARCH_STEP = 10  # Search every 10 pixels

    def __init__(self, threshold=None):
        """
        Initialize matcher with plus button template.

        Args:
            threshold: Optional custom threshold (default from config)
        """
        template_dir = Path(__file__).parent.parent / "templates" / "ground_truth"
        template_path = template_dir / "rally_plus_button_4k.png"

        if not template_path.exists():
            raise FileNotFoundError(f"Rally plus button template not found: {template_path}")

        self.template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        self.threshold = threshold if threshold is not None else self.PLUS_BUTTON_THRESHOLD

    def find_all_plus_buttons(self, frame) -> List[Tuple[int, int, float]]:
        """
        Search entire frame for plus buttons using template matching.

        Strategy:
        1. Run template matching on ENTIRE frame (no ROI extraction)
        2. Find all matches below threshold
        3. Filter to keep only matches near X=1902 (slot 4 position)
        4. Return all matches sorted by Y (top to bottom)

        Args:
            frame: BGR screenshot from WindowsScreenshotHelper

        Returns:
            List of (x, y, score) tuples sorted by Y coordinate (top to bottom)
            Empty list if no buttons found
        """
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Template matching on ENTIRE frame
        result = cv2.matchTemplate(frame_gray, self.template, cv2.TM_SQDIFF_NORMED)

        # Find all matches below threshold
        locations = np.where(result <= self.threshold)

        matches = []
        for pt in zip(*locations[::-1]):  # Switch x and y
            x, y = pt
            score = float(result[y, x])

            # Filter: only keep matches near slot 4 X position (within 10 pixels)
            if abs(x - self.PLUS_BUTTON_X) <= 10:
                matches.append((x, y, score))

        # Remove duplicate detections (within 50 pixels vertically)
        filtered_matches = self._filter_duplicates(matches)

        # Sort by Y coordinate (top to bottom)
        filtered_matches.sort(key=lambda m: m[1])

        return filtered_matches

    def _filter_duplicates(self, matches: List[Tuple[int, int, float]]) -> List[Tuple[int, int, float]]:
        """
        Remove duplicate detections that are close together.

        Strategy: Keep the match with the best (lowest) score among nearby matches.

        Args:
            matches: List of (x, y, score) tuples

        Returns:
            Filtered list with duplicates removed
        """
        if not matches:
            return []

        # Sort by Y coordinate
        sorted_matches = sorted(matches, key=lambda m: m[1])

        filtered = []
        MIN_DISTANCE = 50  # Minimum Y distance between separate buttons

        for match in sorted_matches:
            x, y, score = match

            # Check if this is too close to any already-added match
            is_duplicate = False
            for i, (fx, fy, fscore) in enumerate(filtered):
                if abs(y - fy) < MIN_DISTANCE:
                    # Duplicate found - keep the better score
                    is_duplicate = True
                    if score < fscore:
                        # This match is better, replace the existing one
                        filtered[i] = match
                    break

            if not is_duplicate:
                filtered.append(match)

        return filtered

    def get_click_position(self, plus_x: int, plus_y: int) -> Tuple[int, int]:
        """
        Calculate click position for a plus button.

        Args:
            plus_x: X coordinate of plus button top-left
            plus_y: Y coordinate of plus button top-left

        Returns:
            (click_x, click_y) - Center of button
        """
        click_x = plus_x + self.PLUS_BUTTON_WIDTH // 2
        click_y = plus_y + self.PLUS_BUTTON_HEIGHT // 2
        return click_x, click_y
