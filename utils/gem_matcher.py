"""
Gem bubble matcher for gem harvest detection.

Uses cv2.TM_SQDIFF_NORMED at fixed location.
Template tightly cropped to just the gem icon (no bubble border).

FIXED specs (4K resolution):
- Extraction position: (1378, 677) - tight crop of gem only
- Size: 54x26 pixels (gem icon only)
- Click position: (1405, 696)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np


class GemMatcher:
    """
    Presence detector for gem bubble at FIXED location.
    """

    # HARDCODED coordinates - these NEVER change
    # Tight crop from bubble at (1367, 673) to (1443, 719)
    ICON_X = 1378
    ICON_Y = 677
    ICON_WIDTH = 54
    ICON_HEIGHT = 26  # Tight crop - gem icon only
    CLICK_X = 1405
    CLICK_Y = 696

    def __init__(
        self,
        template_path: Optional[Path] = None,
        debug_dir: Optional[Path] = None,
        threshold: float = 0.06,
    ) -> None:
        """
        Initialize gem bubble detector.

        Args:
            template_path: Path to template (default: templates/ground_truth/gem_tight_4k.png)
            debug_dir: Directory for debug output
            threshold: Maximum difference score (default 0.06 for tight template)
        """
        base_dir = Path(__file__).resolve().parent.parent

        if template_path is None:
            template_path = base_dir / "templates" / "ground_truth" / "gem_tight_4k.png"

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
        Check if gem bubble is present at FIXED location.

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
        """Click at the FIXED gem bubble center position."""
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)

    def _save_debug_crop(self, roi: np.ndarray, score: float) -> None:
        """Save ROI region for debugging."""
        try:
            if roi.size == 0:
                return
            debug_path = self.debug_dir / f"gem_present_{score:.3f}.png"
            cv2.imwrite(str(debug_path), roi)
        except Exception:
            pass
