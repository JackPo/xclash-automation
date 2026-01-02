"""
Disconnection Dialog Matcher - Detects "Disconnected from server" popup.

This dialog appears when the user opens the game on mobile, disconnecting BlueStacks.
When detected, the daemon should wait 5 minutes before clicking Confirm to give
the user time to manage things on mobile.
"""

import numpy as np

from utils.template_matcher import match_template

# Fixed positions (4K resolution)
DIALOG_REGION = (1400, 650, 1020, 380)  # x, y, width, height
CONFIRM_BUTTON_CLICK = (1912, 1289)  # Center of Confirm button

# Threshold
THRESHOLD = 0.05


def is_disconnection_dialog_visible(frame: np.ndarray, debug: bool = False) -> tuple[bool, float]:
    """
    Check if the disconnection dialog is visible.

    Args:
        frame: BGR screenshot (numpy array)
        debug: Enable debug output

    Returns:
        (is_visible, score) tuple
    """
    if frame is None or frame.size == 0:
        return False, 1.0

    x, y, w, h = DIALOG_REGION
    is_visible, score, _ = match_template(frame, "disconnection_dialog_4k.png", search_region=(x, y, w, h),
        threshold=THRESHOLD
    )

    if debug:
        print(f"  Disconnection dialog: score={score:.4f}, visible={is_visible}")

    return is_visible, score


def get_confirm_button_position() -> tuple[int, int]:
    """Return the click position for the Confirm button."""
    return CONFIRM_BUTTON_CLICK
