"""
Under Attack Matcher - Detects crossed swords icon indicating player is being attacked.

The crossed swords icon appears at a fixed position on the right side of the screen
when another player is attacking your city.

Template: crossed_swords_icon_4k.png (122x107)
Position: (3664, 1233)
"""
from __future__ import annotations

from typing import Any

import numpy.typing as npt

from utils.template_matcher import match_template

# Fixed position for under attack icon (4K resolution)
UNDER_ATTACK_POSITION = (3664, 1233)
UNDER_ATTACK_SIZE = (122, 107)
UNDER_ATTACK_THRESHOLD = 0.08  # TM_SQDIFF_NORMED - lower is better

TEMPLATE_NAME = "crossed_swords_icon_4k.png"


def is_under_attack(frame: npt.NDArray[Any], debug: bool = False) -> tuple[bool, float]:
    """
    Check if the player is currently under attack.

    Args:
        frame: BGR numpy array (screenshot)
        debug: Print debug info

    Returns:
        tuple: (is_under_attack, score)
            - is_under_attack: True if crossed swords icon detected
            - score: Match score (lower is better for SQDIFF)
    """
    found, score, _ = match_template(
        frame,
        TEMPLATE_NAME,
        search_region=(*UNDER_ATTACK_POSITION, *UNDER_ATTACK_SIZE),
        threshold=UNDER_ATTACK_THRESHOLD
    )

    if debug:
        status = "UNDER ATTACK!" if found else "Safe"
        print(f"[ATTACK] {status} (score={score:.4f}, threshold={UNDER_ATTACK_THRESHOLD})")

    return found, score


if __name__ == "__main__":
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()

    under_attack, score = is_under_attack(frame, debug=True)

    if under_attack:
        print("WARNING: You are being attacked!")
    else:
        print("All clear - no attack detected.")
