"""
Events icon matcher - finds and clicks the events icon on right sidebar.

Scans vertically at fixed X position (right side) to find the events icon.

Usage:
    from utils.events_icon_matcher import EventsIconMatcher

    matcher = EventsIconMatcher()
    frame = win.get_screenshot_cv2()
    found, score, click_pos = matcher.find(frame)

    if found:
        adb.tap(*click_pos)
"""
from __future__ import annotations

import numpy as np
from typing import Optional, Tuple

from utils.template_matcher import match_template


class EventsIconMatcher:
    """
    Finds events icon by scanning vertically on the right side.

    Fixed X region: 3600-3840 (right edge)
    Variable Y: full height scan
    """

    # Search region - right side vertical strip
    SEARCH_REGION = (3600, 0, 240, 2160)  # x, y, w, h

    TEMPLATE_NAME = "events_icon_4k.png"
    DEFAULT_THRESHOLD = 0.05

    def __init__(self, threshold: float = None) -> None:
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def find(self, frame: np.ndarray) -> Tuple[bool, float, Optional[Tuple[int, int]]]:
        """
        Find events icon by scanning vertically on right side.

        Returns:
            (found, score, click_position)
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

    def click(self, adb_helper, frame: np.ndarray) -> bool:
        """Find and click the events icon."""
        found, score, click_pos = self.find(frame)
        if found and click_pos:
            adb_helper.tap(*click_pos)
            return True
        return False


if __name__ == "__main__":
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    print("Testing EventsIconMatcher...")

    matcher = EventsIconMatcher()
    print(f"Template: {matcher.TEMPLATE_NAME}")
    print(f"Search region: {matcher.SEARCH_REGION}")
    print(f"Threshold: {matcher.threshold}")

    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()

    found, score, click_pos = matcher.find(frame)
    print(f"\nResult: found={found}, score={score:.6f}, click_pos={click_pos}")
