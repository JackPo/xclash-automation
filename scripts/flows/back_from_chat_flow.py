"""
Back from Chat Flow

Generic action to close chat dialogs by clicking the back button.
Searches for both dark and light back button variants and clicks until neither is detected.

Templates (COLOR matching via template_matcher):
- back_button_4k.png (dark teal, gray arrow)
- back_button_light_4k.png (bright cyan, white arrow)

Click position: (1407, 2055) - center of back button
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import numpy.typing as npt

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.template_matcher import match_template

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

# Import from centralized config
from config import BACK_BUTTON_CLICK
from utils.ui_helpers import click_back

# Extract X, Y for logging purposes
BACK_BUTTON_X = BACK_BUTTON_CLICK[0]
BACK_BUTTON_Y = BACK_BUTTON_CLICK[1]

# Search region around the back button (with some margin)
SEARCH_REGION = (1300, 1950, 220, 220)  # x, y, w, h

# Matching threshold - SQDIFF (lower is better)
# 0.08 is strict enough to only match actual back buttons, not false positives
THRESHOLD = 0.08

# Templates to try
TEMPLATES = [
    "back_button_4k.png",
    "back_button_light_4k.png",
]


def _find_back_button(frame: npt.NDArray[Any]) -> tuple[bool, str | None, float]:
    """
    Search for either back button variant in the frame using COLOR matching.

    Returns:
        Tuple of (found, variant, score) where variant is template name or None
    """
    best_score: float = 1.0  # Start high for SQDIFF (lower is better)
    best_variant: str | None = None

    for template_name in TEMPLATES:
        found, score, _ = match_template(
            frame,
            template_name,
            search_region=SEARCH_REGION,
            threshold=THRESHOLD
        )
        if score < best_score:
            best_score = score
            if found:
                best_variant = template_name

    found = best_score <= THRESHOLD
    return found, best_variant, best_score


def back_from_chat_flow(
    adb: ADBHelper,
    screenshot_helper: WindowsScreenshotHelper | None = None,
    max_clicks: int = 5,
) -> int:
    """
    Close chat dialogs by clicking back button until it's gone.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance (optional, will create if not provided)
        max_clicks: Maximum number of back button clicks (default 5)

    Returns:
        Number of back buttons clicked
    """
    # Get screenshot helper
    if screenshot_helper is None:
        screenshot_helper = WindowsScreenshotHelper()

    clicks = 0

    for i in range(max_clicks):
        # Take screenshot
        frame = screenshot_helper.get_screenshot_cv2()

        # Search for back button (COLOR matching)
        found, variant, score = _find_back_button(frame)

        if not found:
            print(f"    [BACK] No back button detected (score={score:.3f}), done after {clicks} clicks")
            break

        # Click the back button
        print(f"    [BACK] Clicking back button ({variant}, score={score:.3f})")
        click_back(adb)
        clicks += 1

        # Wait for UI to update
        time.sleep(0.3)

    return clicks


# For standalone testing
if __name__ == "__main__":
    from pathlib import Path
    import sys
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(BASE_DIR))

    from utils.adb_helper import ADBHelper

    adb = ADBHelper()
    helper = WindowsScreenshotHelper()

    print("Testing back_from_chat_flow...")
    clicks = back_from_chat_flow(adb, helper)
    print(f"Done. Clicked {clicks} times.")
