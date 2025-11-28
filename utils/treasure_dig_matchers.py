"""
Treasure digging matchers for detecting UI elements in the treasure hunting sequence.

All use cv2.TM_SQDIFF_NORMED at fixed locations.

Templates and coordinates (4K resolution):
- Treasure digging marker: (1731, 870) size 342x279, click (1902, 1009)
- Gather button: (1843, 1278) size 146x175, click (1916, 1365)
- March button: (1728, 1578) size 372x141, click (1914, 1648)
- Zz sleep icon: (1935, 1836) size 61x58, click (1965, 1865)
- Treasure ready circle: (1800, 665) size 231x250, click (1915, 790)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np


class TreasureDiggingMarkerMatcher:
    """Detects treasure chest/digging animation marker when at treasure location."""

    ICON_X = 1731
    ICON_Y = 870
    ICON_WIDTH = 342
    ICON_HEIGHT = 279
    CLICK_X = 1902
    CLICK_Y = 1009

    def __init__(
        self,
        template_path: Optional[Path] = None,
        debug_dir: Optional[Path] = None,
        threshold: float = 0.15,
    ) -> None:
        base_dir = Path(__file__).resolve().parent.parent

        if template_path is None:
            template_path = base_dir / "templates" / "ground_truth" / "treasure_digging_marker_4k.png"

        self.template_path = Path(template_path)
        self.debug_dir = debug_dir or (base_dir / "templates" / "debug")
        self.threshold = threshold

        self.debug_dir.mkdir(parents=True, exist_ok=True)

        self.template = cv2.imread(str(self.template_path), cv2.IMREAD_GRAYSCALE)
        if self.template is None:
            raise FileNotFoundError(f"Template not found: {self.template_path}")

    def is_present(self, frame: np.ndarray, save_debug: bool = False) -> tuple[bool, float]:
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

    def __init__(
        self,
        template_path: Optional[Path] = None,
        debug_dir: Optional[Path] = None,
        threshold: float = 0.1,
    ) -> None:
        base_dir = Path(__file__).resolve().parent.parent

        if template_path is None:
            template_path = base_dir / "templates" / "ground_truth" / "gather_button_4k.png"

        self.template_path = Path(template_path)
        self.debug_dir = debug_dir or (base_dir / "templates" / "debug")
        self.threshold = threshold

        self.debug_dir.mkdir(parents=True, exist_ok=True)

        self.template = cv2.imread(str(self.template_path), cv2.IMREAD_GRAYSCALE)
        if self.template is None:
            raise FileNotFoundError(f"Template not found: {self.template_path}")

    def is_present(self, frame: np.ndarray, save_debug: bool = False) -> tuple[bool, float]:
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

    def __init__(
        self,
        template_path: Optional[Path] = None,
        debug_dir: Optional[Path] = None,
        threshold: float = 0.1,
    ) -> None:
        base_dir = Path(__file__).resolve().parent.parent

        if template_path is None:
            template_path = base_dir / "templates" / "ground_truth" / "march_button_4k.png"

        self.template_path = Path(template_path)
        self.debug_dir = debug_dir or (base_dir / "templates" / "debug")
        self.threshold = threshold

        self.debug_dir.mkdir(parents=True, exist_ok=True)

        self.template = cv2.imread(str(self.template_path), cv2.IMREAD_GRAYSCALE)
        if self.template is None:
            raise FileNotFoundError(f"Template not found: {self.template_path}")

    def is_present(self, frame: np.ndarray, save_debug: bool = False) -> tuple[bool, float]:
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

        return is_present, score

    def click(self, adb_helper) -> None:
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)


class ZzSleepIconMatcher:
    """Detects Zz sleep icon above character portraits (used to find idle characters)."""

    # This is the RIGHTMOST Zz icon position from the screenshot
    # In practice, we may need to search for multiple Zz icons
    ICON_X = 1935
    ICON_Y = 1836
    ICON_WIDTH = 61
    ICON_HEIGHT = 58
    CLICK_X = 1965
    CLICK_Y = 1865

    def __init__(
        self,
        template_path: Optional[Path] = None,
        debug_dir: Optional[Path] = None,
        threshold: float = 0.1,
    ) -> None:
        base_dir = Path(__file__).resolve().parent.parent

        if template_path is None:
            template_path = base_dir / "templates" / "ground_truth" / "zz_sleep_icon_4k.png"

        self.template_path = Path(template_path)
        self.debug_dir = debug_dir or (base_dir / "templates" / "debug")
        self.threshold = threshold

        self.debug_dir.mkdir(parents=True, exist_ok=True)

        self.template = cv2.imread(str(self.template_path), cv2.IMREAD_GRAYSCALE)
        if self.template is None:
            raise FileNotFoundError(f"Template not found: {self.template_path}")

    def is_present(self, frame: np.ndarray, save_debug: bool = False) -> tuple[bool, float]:
        """Check if Zz icon is present at fixed location."""
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

        return is_present, score

    def find_rightmost_zz(self, frame: np.ndarray) -> Optional[tuple[int, int]]:
        """
        Search for all Zz icons in the march prompt area and return rightmost one.

        The march prompt shows character portraits with Zz icons above idle ones.
        We want to click on the rightmost idle character.

        Returns:
            (x, y) click position of rightmost Zz icon, or None if not found
        """
        if frame is None or frame.size == 0:
            return None

        # Search region: the row of character portraits in march prompt
        # Y: 1780-1920 (where Zz icons appear)
        # X: 1400-2200 (across character portraits)
        SEARCH_Y_START = 1780
        SEARCH_Y_END = 1920
        SEARCH_X_START = 1400
        SEARCH_X_END = 2200

        search_roi = frame[
            SEARCH_Y_START:SEARCH_Y_END,
            SEARCH_X_START:SEARCH_X_END
        ]

        if len(search_roi.shape) == 3:
            search_gray = cv2.cvtColor(search_roi, cv2.COLOR_BGR2GRAY)
        else:
            search_gray = search_roi

        # Template match to find all Zz icons
        result = cv2.matchTemplate(search_gray, self.template, cv2.TM_SQDIFF_NORMED)

        # Find all matches below threshold
        locations = np.where(result <= self.threshold)

        if len(locations[0]) == 0:
            return None

        # Find rightmost match
        rightmost_x = 0
        rightmost_y = 0
        for y, x in zip(locations[0], locations[1]):
            if x > rightmost_x:
                rightmost_x = x
                rightmost_y = y

        # Convert to full frame coordinates and center of icon
        click_x = SEARCH_X_START + rightmost_x + self.ICON_WIDTH // 2
        click_y = SEARCH_Y_START + rightmost_y + self.ICON_HEIGHT // 2

        return click_x, click_y

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

    def __init__(
        self,
        template_path: Optional[Path] = None,
        debug_dir: Optional[Path] = None,
        threshold: float = 0.15,
    ) -> None:
        base_dir = Path(__file__).resolve().parent.parent

        if template_path is None:
            template_path = base_dir / "templates" / "ground_truth" / "treasure_ready_circle_4k.png"

        self.template_path = Path(template_path)
        self.debug_dir = debug_dir or (base_dir / "templates" / "debug")
        self.threshold = threshold

        self.debug_dir.mkdir(parents=True, exist_ok=True)

        self.template = cv2.imread(str(self.template_path), cv2.IMREAD_GRAYSCALE)
        if self.template is None:
            raise FileNotFoundError(f"Template not found: {self.template_path}")

    def is_present(self, frame: np.ndarray, save_debug: bool = False) -> tuple[bool, float]:
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

        return is_present, score

    def click(self, adb_helper) -> None:
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)
