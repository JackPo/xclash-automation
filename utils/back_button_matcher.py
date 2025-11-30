"""
Back button matcher for detecting chat/dialog windows.

Uses cv2.TM_SQDIFF_NORMED with a single tight template.
Fixed position detection - no search needed.

FIXED specs (4K resolution):
- Position: (1345, 2002) size 107x111 pixels
- Click position: (1407, 2055) - center of back button
- Threshold: 0.05 (TM_SQDIFF_NORMED, lower = better)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np


class BackButtonMatcher:
    """
    Presence detector for back button at FIXED location.
    Uses TM_SQDIFF_NORMED (lower score = better match).
    """

    # Fixed position coordinates (after template crop adjustments)
    POSITION_X = 1345
    POSITION_Y = 2002
    WIDTH = 107
    HEIGHT = 111

    # Click position (center of back button)
    CLICK_X = 1407
    CLICK_Y = 2055

    # Threshold for TM_SQDIFF_NORMED (lower = better)
    THRESHOLD = 0.06

    def __init__(
        self,
        debug_dir: Optional[Path] = None,
    ) -> None:
        """
        Initialize back button detector.

        Args:
            debug_dir: Directory for debug output
        """
        base_dir = Path(__file__).resolve().parent.parent

        # Single template
        self.template_path = base_dir / "templates" / "ground_truth" / "back_button_union_4k.png"

        self.debug_dir = debug_dir or (base_dir / "templates" / "debug")
        self.debug_dir.mkdir(parents=True, exist_ok=True)

        self.template = cv2.imread(str(self.template_path), cv2.IMREAD_GRAYSCALE)
        if self.template is None:
            raise FileNotFoundError(f"Template not found: {self.template_path}")

    def is_present(
        self,
        frame: np.ndarray,
        save_debug: bool = False,
    ) -> tuple[bool, float]:
        """
        Check if back button is present at FIXED location.

        Args:
            frame: BGR image frame from screenshot
            save_debug: If True, save debug crops

        Returns:
            Tuple of (is_present, score) - score is TM_SQDIFF_NORMED (lower = better)
        """
        if frame is None or frame.size == 0:
            return False, 1.0

        # Extract ROI at fixed position
        roi = frame[
            self.POSITION_Y:self.POSITION_Y + self.HEIGHT,
            self.POSITION_X:self.POSITION_X + self.WIDTH
        ]

        if roi.size == 0:
            return False, 1.0

        if len(roi.shape) == 3:
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            roi_gray = roi

        # Template match with TM_SQDIFF_NORMED (lower = better)
        result = cv2.matchTemplate(roi_gray, self.template, cv2.TM_SQDIFF_NORMED)
        min_val, _, _, _ = cv2.minMaxLoc(result)
        score = float(min_val)

        is_present = score <= self.THRESHOLD

        if save_debug:
            self._save_debug_crop(roi, score, is_present)

        return is_present, score

    def click(self, adb_helper) -> None:
        """Click at the FIXED back button position."""
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)

    def _save_debug_crop(self, roi: np.ndarray, score: float, is_present: bool) -> None:
        """Save ROI region for debugging."""
        try:
            if roi.size == 0:
                return
            status = "present" if is_present else "absent"
            debug_path = self.debug_dir / f"back_button_{status}_{score:.3f}.png"
            cv2.imwrite(str(debug_path), roi)
        except Exception:
            pass
