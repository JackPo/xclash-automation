"""
Disconnection Dialog Matcher - Detects "Disconnected from server" popup.

This dialog appears when the user opens the game on mobile, disconnecting BlueStacks.
When detected, the daemon should wait 5 minutes before clicking Confirm to give
the user time to manage things on mobile.

Templates:
- disconnection_dialog_4k.png - Full dialog with "Tip" header AND "Disconnected from the server" message
- confirm_button_4k.png - Yellow Confirm button to click after waiting
"""

import cv2
import numpy as np
from pathlib import Path

# Template paths
TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"
DIALOG_TEMPLATE = TEMPLATES_DIR / "disconnection_dialog_4k.png"
CONFIRM_BUTTON_TEMPLATE = TEMPLATES_DIR / "confirm_button_4k.png"

# Fixed positions (4K resolution)
DIALOG_REGION = (1400, 650, 1020, 380)  # Search region for full dialog
CONFIRM_BUTTON_CLICK = (1912, 1289)  # Center of Confirm button

# Thresholds
THRESHOLD = 0.05  # TM_SQDIFF_NORMED - lower is better

_dialog_template = None
_confirm_template = None


def _load_templates():
    """Load and cache templates."""
    global _dialog_template, _confirm_template

    if _dialog_template is None:
        _dialog_template = cv2.imread(str(DIALOG_TEMPLATE), cv2.IMREAD_GRAYSCALE)
    if _confirm_template is None:
        _confirm_template = cv2.imread(str(CONFIRM_BUTTON_TEMPLATE), cv2.IMREAD_GRAYSCALE)

    return _dialog_template, _confirm_template


def is_disconnection_dialog_visible(frame, debug=False) -> tuple[bool, float]:
    """
    Check if the disconnection dialog is visible.

    Looks for both "Tip" header AND "Disconnected from the server" message
    to specifically identify this dialog type.

    Args:
        frame: BGR screenshot (numpy array)
        debug: Enable debug output

    Returns:
        (is_visible, score) tuple
    """
    dialog_template, _ = _load_templates()

    if dialog_template is None:
        if debug:
            print("  Disconnection dialog: template not found")
        return False, 1.0

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame

    # Search in the dialog region
    x, y, w, h = DIALOG_REGION
    roi = gray[y:y+h, x:x+w]

    result = cv2.matchTemplate(roi, dialog_template, cv2.TM_SQDIFF_NORMED)
    min_val, _, _, _ = cv2.minMaxLoc(result)

    is_visible = min_val <= THRESHOLD

    if debug:
        print(f"  Disconnection dialog: score={min_val:.4f}, visible={is_visible}")

    return is_visible, min_val


def get_confirm_button_position() -> tuple[int, int]:
    """Return the click position for the Confirm button."""
    return CONFIRM_BUTTON_CLICK
