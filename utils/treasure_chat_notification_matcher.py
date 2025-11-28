"""
Treasure chat notification matcher for detecting the chat banner.

Uses cv2.TM_SQDIFF_NORMED with SEARCH-based detection.
The banner moves vertically, so we search a vertical strip.
Clicks on the underlined Kingdom link (e.g., "Kingdom #49 X:579 Y:399").

SPECS (4K resolution):
- Template extracted at: (1532, 1408), size 768x181
- Kingdom link offset from banner top: 134 pixels down
- Kingdom link X: 2040 (fixed horizontal position)
- Search region: X=1500-2320, Y=1200-1700 (vertical search range)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np


class TreasureChatNotificationMatcher:
    """
    Search-based detector for treasure chat notification banner.
    Finds banner position and clicks on the Kingdom link.
    """

    # Search region - banner can appear at different Y positions
    SEARCH_X = 1500
    SEARCH_Y = 1200
    SEARCH_WIDTH = 820  # Wide enough for 768px template + some margin
    SEARCH_HEIGHT = 500  # Vertical search range

    # Click offset from banner top-left to Kingdom link
    CLICK_OFFSET_X = 508  # 2040 - 1532 = 508 pixels right of banner left edge
    CLICK_OFFSET_Y = 134  # Kingdom link is 134 pixels down from banner top

    # Default threshold (TM_SQDIFF_NORMED - lower is better)
    DEFAULT_THRESHOLD = 0.1

    def __init__(
        self,
        template_path: Optional[Path] = None,
        debug_dir: Optional[Path] = None,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        """
        Initialize treasure chat notification detector.

        Args:
            template_path: Path to template (default: templates/ground_truth/treasure_chat_notification_4k.png)
            debug_dir: Directory for debug output
            threshold: Maximum difference score (default 0.1)
        """
        base_dir = Path(__file__).resolve().parent.parent

        if template_path is None:
            template_path = base_dir / "templates" / "ground_truth" / "treasure_chat_notification_4k.png"

        self.template_path = Path(template_path)
        self.debug_dir = debug_dir or (base_dir / "templates" / "debug")
        self.threshold = threshold

        self.debug_dir.mkdir(parents=True, exist_ok=True)

        self.template = cv2.imread(str(self.template_path), cv2.IMREAD_GRAYSCALE)
        if self.template is None:
            raise FileNotFoundError(f"Template not found: {self.template_path}")

        self.template_h, self.template_w = self.template.shape[:2]

    def is_present(
        self,
        frame: np.ndarray,
        save_debug: bool = False,
    ) -> Tuple[bool, float, Optional[Tuple[int, int]]]:
        """
        Check if treasure chat notification banner is present.

        Searches a vertical region for the banner template.

        Args:
            frame: BGR image frame from screenshot
            save_debug: If True, save debug crops

        Returns:
            Tuple of (is_present, score, found_position)
            - is_present: True if banner found
            - score: Match score (lower = better for TM_SQDIFF_NORMED)
            - found_position: (x, y) of banner top-left in full frame coords, or None
        """
        if frame is None or frame.size == 0:
            return False, 1.0, None

        # Extract search region
        roi = frame[
            self.SEARCH_Y:self.SEARCH_Y + self.SEARCH_HEIGHT,
            self.SEARCH_X:self.SEARCH_X + self.SEARCH_WIDTH
        ]

        if roi.size == 0:
            return False, 1.0, None

        if len(roi.shape) == 3:
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            roi_gray = roi

        # Check if ROI is large enough for template
        if roi_gray.shape[0] < self.template_h or roi_gray.shape[1] < self.template_w:
            return False, 1.0, None

        # Template match
        result = cv2.matchTemplate(roi_gray, self.template, cv2.TM_SQDIFF_NORMED)
        min_val, _, min_loc, _ = cv2.minMaxLoc(result)

        score = float(min_val)
        is_present = score <= self.threshold

        if is_present:
            # Convert ROI-relative position to full frame position
            found_x = self.SEARCH_X + min_loc[0]
            found_y = self.SEARCH_Y + min_loc[1]
            found_position = (found_x, found_y)

            if save_debug:
                self._save_debug_crop(roi, score, min_loc)
        else:
            found_position = None

        return is_present, score, found_position

    def get_click_position(
        self,
        found_position: Tuple[int, int],
    ) -> Tuple[int, int]:
        """
        Calculate click position for Kingdom link based on found banner position.

        Args:
            found_position: (x, y) of banner top-left from is_present()

        Returns:
            (x, y) click coordinates for the Kingdom link
        """
        click_x = found_position[0] + self.CLICK_OFFSET_X
        click_y = found_position[1] + self.CLICK_OFFSET_Y
        return click_x, click_y

    def click(self, adb_helper, found_position: Tuple[int, int]) -> None:
        """
        Click on the Kingdom link at the calculated position.

        Args:
            adb_helper: ADB helper instance
            found_position: (x, y) of banner top-left from is_present()
        """
        click_x, click_y = self.get_click_position(found_position)
        adb_helper.tap(click_x, click_y)

    def detect_and_click(
        self,
        frame: np.ndarray,
        adb_helper,
        save_debug: bool = False,
    ) -> Tuple[bool, float]:
        """
        Convenience method: detect banner and click Kingdom link if found.

        Args:
            frame: BGR image frame from screenshot
            adb_helper: ADB helper instance
            save_debug: If True, save debug crops

        Returns:
            Tuple of (clicked, score)
        """
        is_present, score, found_position = self.is_present(frame, save_debug)

        if is_present and found_position:
            self.click(adb_helper, found_position)
            return True, score

        return False, score

    def _save_debug_crop(
        self,
        roi: np.ndarray,
        score: float,
        match_loc: Tuple[int, int],
    ) -> None:
        """Save ROI region for debugging with match location marked."""
        try:
            if roi.size == 0:
                return

            # Draw rectangle at match location
            debug_img = roi.copy()
            if len(debug_img.shape) == 2:
                debug_img = cv2.cvtColor(debug_img, cv2.COLOR_GRAY2BGR)

            cv2.rectangle(
                debug_img,
                match_loc,
                (match_loc[0] + self.template_w, match_loc[1] + self.template_h),
                (0, 255, 0),
                2
            )

            # Mark click position
            click_x = match_loc[0] + self.CLICK_OFFSET_X
            click_y = match_loc[1] + self.CLICK_OFFSET_Y
            cv2.circle(debug_img, (click_x, click_y), 10, (0, 0, 255), -1)

            debug_path = self.debug_dir / f"treasure_chat_notification_present_{score:.3f}.png"
            cv2.imwrite(str(debug_path), debug_img)
        except Exception:
            pass
