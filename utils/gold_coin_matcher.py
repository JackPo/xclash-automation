"""
Gold coin bubble matcher for gold harvest detection.

Uses cv2.TM_SQDIFF_NORMED at fixed location.
Template tightly cropped to just the coin icon (no bubble border).

FIXED specs (4K resolution):
- Extraction position: (1369, 800) - tight crop of coin only
- Size: 53x43 pixels (coin icon only)
- Click position: (1395, 835)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np


class GoldCoinMatcher:
    """
    Presence detector for gold coin bubble at FIXED location.
    """

    # HARDCODED coordinates - these NEVER change
    # Tight crop: original (1347,788) + crop offset (22,12)
    ICON_X = 1369
    ICON_Y = 800
    ICON_WIDTH = 53
    ICON_HEIGHT = 43  # Tight crop - coin icon only
    CLICK_X = 1395
    CLICK_Y = 835

    def __init__(
        self,
        template_path: Optional[Path] = None,
        debug_dir: Optional[Path] = None,
        threshold: float = 0.06,
    ) -> None:
        """
        Initialize gold coin bubble detector.

        Args:
            template_path: Path to template (default: templates/ground_truth/gold_coin_tight_4k.png)
            debug_dir: Directory for debug output
            threshold: Maximum difference score (default 0.06 for tight template)
        """
        base_dir = Path(__file__).resolve().parent.parent

        if template_path is None:
            template_path = base_dir / "templates" / "ground_truth" / "gold_coin_tight_4k.png"

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
        Check if gold coin bubble is present at FIXED location.

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
        """Click at the FIXED gold coin bubble center position."""
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)

    def _save_debug_crop(self, roi: np.ndarray, score: float) -> None:
        """Save ROI region for debugging."""
        try:
            if roi.size == 0:
                return
            debug_path = self.debug_dir / f"gold_present_{score:.3f}.png"
            cv2.imwrite(str(debug_path), roi)
        except Exception:
            pass
