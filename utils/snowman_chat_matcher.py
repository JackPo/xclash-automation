"""
Snowman Party chat message matcher.

Detects the yellow "Snowman Party" chat bubble that appears when a snowman spawns.
Uses search-based detection (banner can appear anywhere vertically in chat).

SPECS (4K resolution):
- Template: snowman_party_chat_4k.png (772x80)
- Search region: Full vertical strip in chat area
- Click on message to navigate to snowman location
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt

from utils.template_matcher import match_template

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper


class SnowmanChatMatcher:
    """
    Search-based detector for "Snowman Party" chat message.
    """

    # Search region - chat panel appears in CENTER of screen when opened
    SEARCH_REGION = (1100, 0, 1700, 2160)  # x, y, w, h (full screen height)

    TEMPLATE_NAME = "snowman_party_chat_4k.png"
    DEFAULT_THRESHOLD = 0.1

    def __init__(self, threshold: float | None = None) -> None:
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def is_present(self, frame: npt.NDArray[Any]) -> tuple[bool, float, tuple[int, int] | None]:
        """
        Check if "Snowman Party" chat message is visible.

        Args:
            frame: BGR image frame from screenshot

        Returns:
            Tuple of (is_present, score, found_position)
            - is_present: True if message found
            - score: Match score (lower = better)
            - found_position: (x, y) center of message, or None
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

    def click(self, adb_helper: ADBHelper, found_position: tuple[int, int]) -> None:
        """Click on the chat message center."""
        adb_helper.tap(*found_position)
