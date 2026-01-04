"""
Treasure chat notification matcher for detecting the chat banner.

Uses template_matcher for search-based detection.
The banner moves vertically, so we search a vertical strip.
Clicks on the underlined Kingdom link (e.g., "Kingdom #49 X:579 Y:399").

SPECS (4K resolution):
- Template extracted at: (1532, 1408), size 768x181
- Kingdom link offset from template center: used for click position
- Search region: X=1500-2320, Y=0-2160 (full vertical search range)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt

from utils.template_matcher import match_template

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper


class TreasureChatNotificationMatcher:
    """
    Search-based detector for treasure chat notification banner.
    Finds banner position and clicks on the Kingdom link.
    """

    # Search region - banner can appear ANYWHERE vertically
    SEARCH_REGION = (1500, 0, 820, 2160)  # x, y, w, h (full screen height)

    # Click offset from template center to Kingdom link
    # Kingdom link is near bottom center of template
    CLICK_OFFSET_X = 0  # Center horizontally
    CLICK_OFFSET_Y = 50  # 50px below center (near bottom of 181px tall template)

    TEMPLATE_NAME = "treasure_chat_notification_4k.png"
    DEFAULT_THRESHOLD = 0.1

    def __init__(self, threshold: float | None = None) -> None:
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def is_present(self, frame: npt.NDArray[Any], save_debug: bool = False) -> tuple[bool, float, tuple[int, int] | None]:
        """
        Check if treasure chat notification banner is present.

        Args:
            frame: BGR image frame from screenshot
            save_debug: Ignored (kept for API compatibility)

        Returns:
            Tuple of (is_present, score, found_position)
            - is_present: True if banner found
            - score: Match score (lower = better for TM_SQDIFF_NORMED)
            - found_position: (x, y) center of banner in frame coords, or None
        """
        if frame is None or frame.size == 0:
            return False, 1.0, None

        found, score, location = match_template(
            frame,
            self.TEMPLATE_NAME,
            search_region=self.SEARCH_REGION,
            threshold=self.threshold
        )

        return found, score, location if found else None

    def get_click_position(self, found_position: tuple[int, int]) -> tuple[int, int]:
        """
        Calculate click position for Kingdom link based on found banner center.

        Args:
            found_position: (x, y) center from is_present()

        Returns:
            (x, y) click coordinates for the Kingdom link
        """
        click_x = found_position[0] + self.CLICK_OFFSET_X
        click_y = found_position[1] + self.CLICK_OFFSET_Y
        return click_x, click_y

    def click(self, adb_helper: ADBHelper, found_position: tuple[int, int]) -> None:
        """
        Click on the Kingdom link at the calculated position.

        Args:
            adb_helper: ADB helper instance
            found_position: (x, y) center from is_present()
        """
        click_x, click_y = self.get_click_position(found_position)
        adb_helper.tap(click_x, click_y)

    def detect_and_click(self, frame: npt.NDArray[Any], adb_helper: ADBHelper, save_debug: bool = False) -> tuple[bool, float]:
        """
        Convenience method: detect banner and click Kingdom link if found.

        Args:
            frame: BGR image frame from screenshot
            adb_helper: ADB helper instance
            save_debug: Ignored

        Returns:
            Tuple of (clicked, score)
        """
        is_present, score, found_position = self.is_present(frame, save_debug)

        if is_present and found_position:
            self.click(adb_helper, found_position)
            return True, score

        return False, score
