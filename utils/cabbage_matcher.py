"""
Cabbage bubble matcher for cabbage harvest detection.

Uses template_matcher for fixed-position detection.

Coordinates loaded from config.CABBAGE_BUBBLE - override in config_local.py for your town layout.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt

from config import CABBAGE_BUBBLE, THRESHOLDS
from utils.template_matcher import match_template

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper


class CabbageMatcher:
    """
    Presence detector for cabbage bubble at configurable location.
    """

    ICON_X = CABBAGE_BUBBLE['region'][0]
    ICON_Y = CABBAGE_BUBBLE['region'][1]
    ICON_WIDTH = CABBAGE_BUBBLE['region'][2]
    ICON_HEIGHT = CABBAGE_BUBBLE['region'][3]
    CLICK_X = CABBAGE_BUBBLE['click'][0]
    CLICK_Y = CABBAGE_BUBBLE['click'][1]

    TEMPLATE_NAME = "cabbage_tight_4k.png"
    DEFAULT_THRESHOLD = THRESHOLDS.get('cabbage', 0.05)

    def __init__(self, threshold: float | None = None, debug_dir: Any = None) -> None:
        # debug_dir ignored - kept for backward compatibility
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def is_present(self, frame: npt.NDArray[Any], save_debug: bool = False) -> tuple[bool, float]:
        if frame is None or frame.size == 0:
            return False, 1.0

        is_present, score, _ = match_template(frame, self.TEMPLATE_NAME, search_region=(self.ICON_X, self.ICON_Y, self.ICON_WIDTH, self.ICON_HEIGHT),
            threshold=self.threshold
        )

        return is_present, score

    def click(self, adb_helper: ADBHelper) -> None:
        adb_helper.tap(self.CLICK_X, self.CLICK_Y)
