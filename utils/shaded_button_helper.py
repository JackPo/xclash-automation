"""
Shaded button helper - dismiss popups by clicking shaded World/Town button.

When popups are blocking the screen, the World/Town button appears shaded/dimmed.
Two levels of shading:
- world_button_shaded_4k.png: Light shading (some popups)
- world_button_shaded_dark_4k.png: Dark shading (modal dialogs like Union Duel)

Clicking it repeatedly dismisses popups until the button returns to normal.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

BASE_DIR = Path(__file__).resolve().parent.parent / "templates" / "ground_truth"

# Button location (same as view_state_detector)
BUTTON_X, BUTTON_Y = 3600, 1920
BUTTON_W, BUTTON_H = 240, 240
BUTTON_CLICK = (3720, 2040)  # Center of button

SHADED_THRESHOLD = 0.05  # TM_SQDIFF_NORMED - lower = better match

# Both shaded templates
SHADED_TEMPLATES = [
    "world_button_shaded_4k.png",       # Light shading
    "world_button_shaded_dark_4k.png",  # Dark shading (modal dialogs)
]


def is_button_shaded(frame: npt.NDArray[Any], debug: bool = False) -> tuple[bool, float]:
    """
    Check if World/Town button is shaded (indicates popups blocking).

    Checks both light and dark shaded templates.

    Returns (is_shaded, best_score)
    """
    roi = frame[BUTTON_Y:BUTTON_Y+BUTTON_H, BUTTON_X:BUTTON_X+BUTTON_W]
    if len(roi.shape) == 3:
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    else:
        roi_gray = roi

    best_score = 1.0
    best_template = None

    for template_name in SHADED_TEMPLATES:
        template_path = BASE_DIR / template_name
        if not template_path.exists():
            continue

        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            continue  # type: ignore[unreachable]

        result = cv2.matchTemplate(roi_gray, template, cv2.TM_SQDIFF_NORMED)
        score = cv2.minMaxLoc(result)[0]

        if debug:
            print(f"  {template_name}: {score:.4f}")

        if score < best_score:
            best_score = score
            best_template = template_name

    is_shaded = best_score <= SHADED_THRESHOLD

    if debug:
        if is_shaded:
            print(f"Button SHADED (best: {best_template}, score={best_score:.4f})")
        else:
            print(f"Button NOT shaded (best score={best_score:.4f})")

    return is_shaded, best_score


def dismiss_popups(adb: ADBHelper, win: WindowsScreenshotHelper, max_clicks: int = 10, debug: bool = False) -> bool:
    """
    Click shaded button repeatedly until popups are dismissed.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        max_clicks: Maximum clicks before giving up
        debug: Print debug info

    Returns:
        True if popups dismissed (button no longer shaded), False if still shaded
    """
    for i in range(max_clicks):
        frame = win.get_screenshot_cv2()
        shaded, score = is_button_shaded(frame, debug=debug)

        if not shaded:
            if debug:
                print(f"Button not shaded after {i} clicks")
            return True

        if debug:
            print(f"Button shaded (score={score:.4f}), clicking to dismiss popup {i+1}/{max_clicks}")

        adb.tap(*BUTTON_CLICK)
        time.sleep(0.5)

    if debug:
        print(f"Still shaded after {max_clicks} clicks")
    return False
