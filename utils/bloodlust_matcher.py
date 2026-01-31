"""
Bloodlust Matcher - Detects bloodlust icon indicating active bloodlust state.

The bloodlust icon appears at a fixed position in the upper left area
below the fist icon when bloodlust is active. Bloodlust typically lasts 15 minutes.

Template: bloodlust_icon_4k.png (62x62)
Position: (283, 287)
"""
from __future__ import annotations

from typing import Any

import numpy.typing as npt

from utils.template_matcher import match_template

# Fixed position for bloodlust icon (4K resolution)
BLOODLUST_POSITION = (283, 287)
BLOODLUST_SIZE = (62, 62)
BLOODLUST_THRESHOLD = 0.08  # TM_SQDIFF_NORMED - lower is better

# Bloodlust duration in seconds (15 minutes)
BLOODLUST_DURATION_SECONDS = 15 * 60

TEMPLATE_NAME = "bloodlust_icon_4k.png"


def is_bloodlust_active(frame: npt.NDArray[Any], debug: bool = False) -> tuple[bool, float]:
    """
    Check if bloodlust is currently active.

    Args:
        frame: BGR numpy array (screenshot)
        debug: Print debug info

    Returns:
        tuple: (is_active, score)
            - is_active: True if bloodlust icon detected
            - score: Match score (lower is better for SQDIFF)
    """
    found, score, _ = match_template(
        frame,
        TEMPLATE_NAME,
        search_region=(*BLOODLUST_POSITION, *BLOODLUST_SIZE),
        threshold=BLOODLUST_THRESHOLD
    )

    if debug:
        status = "BLOODLUST ACTIVE!" if found else "No bloodlust"
        print(f"[BLOODLUST] {status} (score={score:.4f}, threshold={BLOODLUST_THRESHOLD})")

    return found, score


if __name__ == "__main__":
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()

    active, score = is_bloodlust_active(frame, debug=True)

    if active:
        print(f"Bloodlust is ACTIVE! Expected to end in {BLOODLUST_DURATION_SECONDS // 60} minutes.")
    else:
        print("Bloodlust is not active.")
