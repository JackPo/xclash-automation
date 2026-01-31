"""
Shield Active Matcher - Detects if player currently has shield protection active.

The shield icon appears at the same position as bloodlust (below fist icon)
when the player has an active shield protecting their city.

Template: shield_active_icon_4k.png (62x62)
Position: (283, 287) - same as bloodlust icon location
"""
from __future__ import annotations

from typing import Any

import numpy.typing as npt

from utils.template_matcher import match_template

# Fixed position for shield active icon (4K resolution)
# Same position as bloodlust - they don't appear simultaneously
SHIELD_ACTIVE_POSITION = (283, 287)
SHIELD_ACTIVE_SIZE = (62, 62)
SHIELD_ACTIVE_THRESHOLD = 0.08  # TM_SQDIFF_NORMED - lower is better

TEMPLATE_NAME = "shield_active_icon_4k.png"


def is_shield_active(frame: npt.NDArray[Any], debug: bool = False) -> tuple[bool, float]:
    """
    Check if player currently has shield protection active.

    Args:
        frame: BGR numpy array (screenshot)
        debug: Print debug info

    Returns:
        tuple: (is_active, score)
            - is_active: True if shield icon detected
            - score: Match score (lower is better for SQDIFF)
    """
    found, score, _ = match_template(
        frame,
        TEMPLATE_NAME,
        search_region=(*SHIELD_ACTIVE_POSITION, *SHIELD_ACTIVE_SIZE),
        threshold=SHIELD_ACTIVE_THRESHOLD
    )

    if debug:
        status = "SHIELD ACTIVE" if found else "No shield"
        print(f"[SHIELD] {status} (score={score:.4f}, threshold={SHIELD_ACTIVE_THRESHOLD})")

    return found, score


if __name__ == "__main__":
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()

    active, score = is_shield_active(frame, debug=True)

    if active:
        print("You have shield protection active!")
    else:
        print("No shield protection - city is vulnerable.")
