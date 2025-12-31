"""
Treasure digging matchers for detecting UI elements in the treasure hunting sequence.

All use template_matcher for fixed-position detection.

Templates and coordinates (4K resolution):
- Treasure digging marker: (1731, 870) size 342x279, click (1902, 1009)
- Gather button: (1843, 1278) size 146x175, click (1916, 1365)
- March button: (1728, 1578) size 372x141, click (1914, 1648)
- Zz sleep icon: (1935, 1836) size 61x58, click (1965, 1865)
- Treasure ready circle: (1800, 665) size 231x250, click (1915, 790)
"""
from __future__ import annotations

import numpy as np
from typing import Optional, Tuple

from utils.template_matcher import match_template, match_template_fixed


class TreasureDiggingMarkerMatcher:
    """Detects treasure chest/digging animation marker when at treasure location."""

    ICON_X = 1731
    ICON_Y = 870
    ICON_WIDTH = 342
    ICON_HEIGHT = 279
    CLICK_X = 1902
    CLICK_Y = 1009

    TEMPLATE_NAME = "treasure_digging_marker_4k.png"
    DEFAULT_THRESHOLD = 0.15

    def __init__(self, threshold: float = None) -> None:
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def is_present(self, frame: np.ndarray, save_debug: bool = False) -> tuple[bool, float]:
        if frame is None or frame.size == 0:
            return False, 1.0

        is_present, score, _ = match_template_fixed(
            frame,
            self.TEMPLATE_NAME,
            position=(self.ICON_X, self.ICON_Y),
            size=(self.ICON_WIDTH, self.ICON_HEIGHT),
            threshold=self.threshold
        )

        return is_present, score

    def click(self, adb_helper) -> None:
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)


class GatherButtonMatcher:
    """Detects the green Gather button in treasure dialogs."""

    ICON_X = 1843
    ICON_Y = 1278
    ICON_WIDTH = 146
    ICON_HEIGHT = 175
    CLICK_X = 1916
    CLICK_Y = 1365

    TEMPLATE_NAME = "gather_button_4k.png"
    DEFAULT_THRESHOLD = 0.1

    def __init__(self, threshold: float = None) -> None:
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def is_present(self, frame: np.ndarray, save_debug: bool = False) -> tuple[bool, float]:
        if frame is None or frame.size == 0:
            return False, 1.0

        is_present, score, _ = match_template_fixed(
            frame,
            self.TEMPLATE_NAME,
            position=(self.ICON_X, self.ICON_Y),
            size=(self.ICON_WIDTH, self.ICON_HEIGHT),
            threshold=self.threshold
        )

        return is_present, score

    def click(self, adb_helper) -> None:
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)


class MarchButtonMatcher:
    """Detects the blue March button in march prompts."""

    ICON_X = 1728
    ICON_Y = 1578
    ICON_WIDTH = 372
    ICON_HEIGHT = 141
    CLICK_X = 1914
    CLICK_Y = 1648

    TEMPLATE_NAME = "march_button_4k.png"
    DEFAULT_THRESHOLD = 0.1

    def __init__(self, threshold: float = None) -> None:
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def is_present(self, frame: np.ndarray, save_debug: bool = False) -> tuple[bool, float]:
        if frame is None or frame.size == 0:
            return False, 1.0

        is_present, score, _ = match_template_fixed(
            frame,
            self.TEMPLATE_NAME,
            position=(self.ICON_X, self.ICON_Y),
            size=(self.ICON_WIDTH, self.ICON_HEIGHT),
            threshold=self.threshold
        )

        return is_present, score

    def click(self, adb_helper) -> None:
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)


class ZzSleepIconMatcher:
    """Detects Zz sleep icon above character portraits (used to find idle characters)."""

    ICON_X = 1935
    ICON_Y = 1836
    ICON_WIDTH = 61
    ICON_HEIGHT = 58
    CLICK_X = 1965
    CLICK_Y = 1865

    # Search region for finding all Zz icons
    SEARCH_REGION = (1400, 1780, 800, 140)  # x, y, w, h

    TEMPLATE_NAME = "zz_icon_template_4k.png"
    DEFAULT_THRESHOLD = 0.1

    def __init__(self, threshold: float = None) -> None:
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def is_present(self, frame: np.ndarray, save_debug: bool = False) -> tuple[bool, float]:
        """Check if Zz icon is present at fixed location."""
        if frame is None or frame.size == 0:
            return False, 1.0

        is_present, score, _ = match_template_fixed(
            frame,
            self.TEMPLATE_NAME,
            position=(self.ICON_X, self.ICON_Y),
            size=(self.ICON_WIDTH, self.ICON_HEIGHT),
            threshold=self.threshold
        )

        return is_present, score

    def find_rightmost_zz(self, frame: np.ndarray) -> Optional[Tuple[int, int]]:
        """
        Search for all Zz icons in the march prompt area and return rightmost one.

        Returns:
            (x, y) click position of rightmost Zz icon, or None if not found
        """
        if frame is None or frame.size == 0:
            return None

        found, score, location = match_template(
            frame,
            self.TEMPLATE_NAME,
            search_region=self.SEARCH_REGION,
            threshold=self.threshold
        )

        if found and location:
            return location

        return None

    def click(self, adb_helper) -> None:
        """Click at the fixed Zz icon position."""
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)

    def click_rightmost(self, adb_helper, frame: np.ndarray) -> bool:
        """
        Find and click the rightmost Zz icon in the march prompt.

        Returns:
            True if clicked, False if no Zz icon found
        """
        pos = self.find_rightmost_zz(frame)
        if pos:
            adb_helper.tap(pos[0], pos[1])
            return True
        return False


class TreasureReadyCircleMatcher:
    """Detects the blue circle that appears when treasure is ready to collect."""

    ICON_X = 1800
    ICON_Y = 665
    ICON_WIDTH = 231
    ICON_HEIGHT = 250
    CLICK_X = 1915
    CLICK_Y = 790

    TEMPLATE_NAME = "treasure_ready_circle_4k.png"
    DEFAULT_THRESHOLD = 0.15

    def __init__(self, threshold: float = None) -> None:
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def is_present(self, frame: np.ndarray, save_debug: bool = False) -> tuple[bool, float]:
        if frame is None or frame.size == 0:
            return False, 1.0

        is_present, score, _ = match_template_fixed(
            frame,
            self.TEMPLATE_NAME,
            position=(self.ICON_X, self.ICON_Y),
            size=(self.ICON_WIDTH, self.ICON_HEIGHT),
            threshold=self.threshold
        )

        return is_present, score

    def click(self, adb_helper) -> None:
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)
