"""
Rally March Button Matcher - Detects red flag march button in TOWN/WORLD view.

The march button appears as an overlay notification when a teammate starts a rally.
Uses fixed X coordinate and searches Y-axis to find the button.
"""

from pathlib import Path
import cv2
import numpy as np
from typing import List, Tuple, Optional


class RallyMarchButtonMatcher:
    """Detects rally march button using fixed X + Y search."""

    # March button coordinates (from joining_team.png)
    MARCH_BUTTON_X = 3655  # FIXED X coordinate (right side of screen)
    MARCH_BUTTON_WIDTH = 154
    MARCH_BUTTON_HEIGHT = 73  # Using small version (core button only)
    MARCH_BUTTON_THRESHOLD = 0.05  # TM_SQDIFF_NORMED

    # Y-axis search range
    SEARCH_Y_START = 400
    SEARCH_Y_END = 1800
    SEARCH_STEP = 10  # Search every 10 pixels

    def __init__(self, threshold=None):
        """
        Initialize matcher with march button template.

        Args:
            threshold: Optional custom threshold (default 0.05)
        """
        template_dir = Path(__file__).parent.parent / "templates" / "ground_truth"
        template_path = template_dir / "rally_march_button_small_4k.png"

        if not template_path.exists():
            raise FileNotFoundError(f"Rally march button template not found: {template_path}")

        self.template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        self.threshold = threshold if threshold is not None else self.MARCH_BUTTON_THRESHOLD

    def find_march_button(self, frame) -> Optional[Tuple[int, int, float]]:
        """
        Search Y-axis at fixed X for march button.

        Strategy:
        1. Fix X coordinate to right side of screen
        2. Search entire Y range for template match
        3. Return first (best) match found

        Args:
            frame: BGR screenshot from WindowsScreenshotHelper

        Returns:
            (x, y, score) tuple if button found, None otherwise
        """
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        best_match = None
        best_score = 1.0  # Start with worst possible score

        # Search Y-axis at fixed X
        for y in range(self.SEARCH_Y_START, self.SEARCH_Y_END - self.MARCH_BUTTON_HEIGHT, self.SEARCH_STEP):
            # Extract ROI at (FIXED_X, current_y)
            roi = frame_gray[
                y : y + self.MARCH_BUTTON_HEIGHT,
                self.MARCH_BUTTON_X : self.MARCH_BUTTON_X + self.MARCH_BUTTON_WIDTH
            ]

            # Skip if ROI is wrong size (edge of screen)
            if roi.shape[0] != self.MARCH_BUTTON_HEIGHT or roi.shape[1] != self.MARCH_BUTTON_WIDTH:
                continue

            # Template matching
            result = cv2.matchTemplate(roi, self.template, cv2.TM_SQDIFF_NORMED)
            min_val = cv2.minMaxLoc(result)[0]
            score = float(min_val)

            # Check threshold and keep best match
            if score <= self.threshold and score < best_score:
                best_match = (self.MARCH_BUTTON_X, y, score)
                best_score = score

        return best_match

    def is_present(self, frame) -> Tuple[bool, float]:
        """
        Check if march button is present on screen.

        Args:
            frame: BGR screenshot from WindowsScreenshotHelper

        Returns:
            (present, score) - True if button detected, best score from search
        """
        match = self.find_march_button(frame)
        if match:
            _, _, score = match
            return True, score
        return False, 1.0

    def get_click_position(self, march_x: int, march_y: int) -> Tuple[int, int]:
        """
        Calculate click position for march button.

        Args:
            march_x: X coordinate of button top-left
            march_y: Y coordinate of button top-left

        Returns:
            (click_x, click_y) - Center of button
        """
        click_x = march_x + self.MARCH_BUTTON_WIDTH // 2
        click_y = march_y + self.MARCH_BUTTON_HEIGHT // 2
        return click_x, click_y

    def click(self, adb_helper):
        """
        Click the march button at its last detected position.

        Note: This assumes you've already called find_march_button() or is_present()
        to detect the button position. For daemon use, call find_march_button() first.

        Args:
            adb_helper: ADBHelper instance
        """
        # This is a simplified version for consistency with other matchers
        # In daemon, we'll call find_march_button() directly and use that position
        pass
