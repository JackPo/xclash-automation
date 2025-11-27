"""
Back button matcher for detecting chat/dialog windows.

Uses cv2.TM_CCOEFF_NORMED with TWO templates (dark + light variants).
Returns the best match between both templates.

FIXED specs (4K resolution):
- Search region: (1300, 1950) to (1520, 2170) - 220x220 pixels
- Click position: (1407, 2055) - center of back button
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np


class BackButtonMatcher:
    """
    Presence detector for back button at FIXED location.
    Uses both dark and light template variants.
    """

    # Search region coordinates
    SEARCH_X = 1300
    SEARCH_Y = 1950
    SEARCH_WIDTH = 220
    SEARCH_HEIGHT = 220

    # Click position (center of back button)
    CLICK_X = 1407
    CLICK_Y = 2055

    def __init__(
        self,
        debug_dir: Optional[Path] = None,
        threshold: float = 0.7,
    ) -> None:
        """
        Initialize back button detector.

        Args:
            debug_dir: Directory for debug output
            threshold: Minimum match score (TM_CCOEFF_NORMED, higher = better)
        """
        base_dir = Path(__file__).resolve().parent.parent

        # Load BOTH templates
        self.template_dark_path = base_dir / "templates" / "ground_truth" / "back_button_4k.png"
        self.template_light_path = base_dir / "templates" / "ground_truth" / "back_button_light_4k.png"

        self.debug_dir = debug_dir or (base_dir / "templates" / "debug")
        self.threshold = threshold

        self.debug_dir.mkdir(parents=True, exist_ok=True)

        # For display purposes
        self.template_path = self.template_dark_path

        self.template_dark = cv2.imread(str(self.template_dark_path), cv2.IMREAD_GRAYSCALE)
        if self.template_dark is None:
            raise FileNotFoundError(f"Template not found: {self.template_dark_path}")

        self.template_light = cv2.imread(str(self.template_light_path), cv2.IMREAD_GRAYSCALE)
        if self.template_light is None:
            raise FileNotFoundError(f"Template not found: {self.template_light_path}")

    def is_present(
        self,
        frame: np.ndarray,
        save_debug: bool = False,
    ) -> tuple[bool, float]:
        """
        Check if back button is present at FIXED location.

        Uses both dark and light templates, returns best match.

        Args:
            frame: BGR image frame from screenshot
            save_debug: If True, save debug crops

        Returns:
            Tuple of (is_present, score) - score is best match (higher = better)
        """
        if frame is None or frame.size == 0:
            return False, 0.0

        # Extract search region
        roi = frame[
            self.SEARCH_Y:self.SEARCH_Y + self.SEARCH_HEIGHT,
            self.SEARCH_X:self.SEARCH_X + self.SEARCH_WIDTH
        ]

        if roi.size == 0:
            return False, 0.0

        if len(roi.shape) == 3:
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            roi_gray = roi

        # Try dark template
        result_dark = cv2.matchTemplate(roi_gray, self.template_dark, cv2.TM_CCOEFF_NORMED)
        _, max_val_dark, _, _ = cv2.minMaxLoc(result_dark)

        # Try light template
        result_light = cv2.matchTemplate(roi_gray, self.template_light, cv2.TM_CCOEFF_NORMED)
        _, max_val_light, _, _ = cv2.minMaxLoc(result_light)

        # Use best match
        score = max(float(max_val_dark), float(max_val_light))
        is_present = score >= self.threshold

        if save_debug and is_present:
            self._save_debug_crop(roi, score)

        return is_present, score

    def click(self, adb_helper) -> None:
        """Click at the FIXED back button position."""
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)

    def _save_debug_crop(self, roi: np.ndarray, score: float) -> None:
        """Save ROI region for debugging."""
        try:
            if roi.size == 0:
                return
            debug_path = self.debug_dir / f"back_button_present_{score:.3f}.png"
            cv2.imwrite(str(debug_path), roi)
        except Exception:
            pass
