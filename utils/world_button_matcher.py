"""
World button matcher for detecting when we're in TOWN view.

When the "World" button is visible, we are currently in TOWN view.
Uses cv2.TM_SQDIFF_NORMED at fixed location.

FIXED specs (4K resolution):
- Position: (3600, 1920) to corner (3840, 2160)
- Size: 240x240 pixels
- This button appears when player is in TOWN view
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np


class WorldButtonMatcher:
    """
    Presence detector for World button at FIXED location.
    When present, player is in TOWN view.
    """

    # HARDCODED coordinates for 4K (3840x2160)
    # 240x240 from corner
    ICON_X = 3600
    ICON_Y = 1920
    ICON_WIDTH = 240
    ICON_HEIGHT = 240

    def __init__(
        self,
        template_path: Optional[Path] = None,
        debug_dir: Optional[Path] = None,
        threshold: float = 0.01,
    ) -> None:
        """
        Initialize world button detector.

        Args:
            template_path: Path to template (default: templates/ground_truth/world_button.png)
            debug_dir: Directory for debug output
            threshold: Maximum difference score
        """
        base_dir = Path(__file__).resolve().parent.parent

        if template_path is None:
            template_path = base_dir / "templates" / "ground_truth" / "world_button_4k.png"

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
        Check if World button is present at FIXED location.

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

    def _save_debug_crop(self, roi: np.ndarray, score: float) -> None:
        """Save ROI region for debugging."""
        try:
            if roi.size == 0:
                return
            debug_path = self.debug_dir / f"world_button_present_{score:.3f}.png"
            cv2.imwrite(str(debug_path), roi)
        except Exception:
            pass
