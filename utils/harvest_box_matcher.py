"""
Harvest box matcher for gift box icon detection on Heroes button.

Uses cv2.TM_SQDIFF_NORMED at fixed location.
Template extracted from 4K screenshot at coordinates (2100, 1540) with size 154x157.

FIXED specs (4K resolution):
- Extraction position: (2100, 1540)
- Size: 154x157 pixels
- Click position: (2177, 1618) - center of template
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np


class HarvestBoxMatcher:
    """
    Presence detector for harvest box icon at FIXED location.
    """

    # HARDCODED coordinates - these NEVER change
    ICON_X = 2100
    ICON_Y = 1540
    ICON_WIDTH = 154
    ICON_HEIGHT = 157
    CLICK_X = 2177
    CLICK_Y = 1618

    def __init__(
        self,
        template_path: Optional[Path] = None,
        debug_dir: Optional[Path] = None,
        threshold: float = 0.1,
    ) -> None:
        """
        Initialize harvest box detector.

        Args:
            template_path: Path to template (default: templates/ground_truth/harvest_box_4k.png)
            debug_dir: Directory for debug output
            threshold: Maximum difference score (default 0.1)
        """
        base_dir = Path(__file__).resolve().parent.parent

        if template_path is None:
            template_path = base_dir / "templates" / "ground_truth" / "harvest_box_4k.png"

        self.template_path = Path(template_path)
        self.debug_dir = debug_dir or (base_dir / "templates" / "debug")
        self.threshold = threshold

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
        Check if harvest box icon is present at FIXED location.

        Args:
            frame: BGR image frame from screenshot
            save_debug: If True, save debug crops

        Returns:
            Tuple of (is_present, score)
        """
        if frame is None or frame.size == 0:
            return False, 1.0

        roi = frame[
            self.ICON_Y:self.ICON_Y + self.ICON_HEIGHT,
            self.ICON_X:self.ICON_X + self.ICON_WIDTH
        ]

        if len(roi.shape) == 3:
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            roi_gray = roi

        result = cv2.matchTemplate(roi_gray, self.template, cv2.TM_SQDIFF_NORMED)
        min_val, _, _, _ = cv2.minMaxLoc(result)

        score = float(min_val)
        is_present = score <= self.threshold

        if save_debug and is_present:
            self._save_debug_crop(roi, score)

        return is_present, score

    def click(self, adb_helper) -> None:
        """Click at the FIXED harvest box center position."""
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)

    def _save_debug_crop(self, roi: np.ndarray, score: float) -> None:
        """Save ROI region for debugging."""
        try:
            if roi.size == 0:
                return
            debug_path = self.debug_dir / f"harvest_box_present_{score:.3f}.png"
            cv2.imwrite(str(debug_path), roi)
        except Exception:
            pass
