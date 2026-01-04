"""
Harvest Box flow - complete harvest sequence.

Step 1: Click the harvest box icon at fixed position (2177, 1618)
Step 2: Wait briefly for dialog to appear
Step 3: Find harvest_surprise_box_4k.png vertically (it moves) and click it
Step 4: Click Open button at fixed position (1918, 1254)
Step 5: Use back_from_chat_flow to close all dialogs

Templates:
- Trigger icon: templates/ground_truth/harvest_box_4k.png (154x157 at 2100,1540)
- Dialog box: templates/ground_truth/harvest_surprise_box_4k.png (791x253, moves vertically)
- Open button: templates/ground_truth/open_button_4k.png (242x99 at 1797,1205)
"""

from __future__ import annotations

from pathlib import Path
import time
from typing import TYPE_CHECKING, Any, cast

import cv2
import numpy.typing as npt

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

from .back_from_chat_flow import back_from_chat_flow

# Template for the dialog box (moves vertically)
SURPRISE_BOX_TEMPLATE = Path(__file__).parent.parent.parent / "templates" / "ground_truth" / "harvest_surprise_box_4k.png"

# Matching threshold for dialog - looser because text inside changes
MATCH_THRESHOLD = 0.7

# Fixed click positions
HARVEST_ICON_CLICK_X = 2177
HARVEST_ICON_CLICK_Y = 1618

OPEN_BUTTON_X = 1918
OPEN_BUTTON_Y = 1254


def harvest_box_flow(
    adb: ADBHelper,
    screenshot_helper: WindowsScreenshotHelper | None = None,
) -> bool:
    """
    Complete harvest box flow: icon -> surprise box -> open -> back.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance (optional, will create one if not provided)

    Returns:
        True if successful, False otherwise
    """
    from utils.windows_screenshot_helper import WindowsScreenshotHelper as WSHelper

    # Step 1: Click the harvest box icon
    print(f"    [HARVEST] Step 1: Clicking icon at ({HARVEST_ICON_CLICK_X}, {HARVEST_ICON_CLICK_Y})")
    adb.tap(HARVEST_ICON_CLICK_X, HARVEST_ICON_CLICK_Y)

    # Step 2: Wait for dialog to appear
    time.sleep(0.5)

    # Step 3: Find and click the surprise box dialog
    # ALWAYS use Windows screenshot - never ADB (different pixel values, won't match templates)
    win = screenshot_helper if screenshot_helper else WSHelper()
    frame = win.get_screenshot_cv2()

    # Load template (cast needed because cv2.imread can return None at runtime)
    template = cast(npt.NDArray[Any] | None, cv2.imread(str(SURPRISE_BOX_TEMPLATE)))
    if template is None:
        print(f"    [HARVEST] Template not found: {SURPRISE_BOX_TEMPLATE}")
        return False

    # Convert both to grayscale for matching
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

    # Template matching with correlation (tolerates text changes)
    result = cv2.matchTemplate(frame_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    print(f"    [HARVEST] Step 2: Dialog match score: {max_val:.3f} (threshold: {MATCH_THRESHOLD})")

    if max_val < MATCH_THRESHOLD:
        print(f"    [HARVEST] Dialog not found (score {max_val:.3f} < {MATCH_THRESHOLD})")
        return False

    # Found! Calculate click position (center of template)
    template_h, template_w = template_gray.shape
    top_left = max_loc
    center_x = top_left[0] + template_w // 2
    center_y = top_left[1] + template_h // 2

    print(f"    [HARVEST] Step 3: Clicking surprise box at ({center_x}, {center_y})")
    adb.tap(center_x, center_y)

    # Step 4: Click Open button
    time.sleep(0.5)
    print(f"    [HARVEST] Step 4: Clicking Open at ({OPEN_BUTTON_X}, {OPEN_BUTTON_Y})")
    adb.tap(OPEN_BUTTON_X, OPEN_BUTTON_Y)

    # Step 5: Close all dialogs using back_from_chat_flow
    time.sleep(0.5)
    print("    [HARVEST] Step 5: Closing dialogs with back_from_chat_flow")
    back_from_chat_flow(adb, screenshot_helper)

    print("    [HARVEST] Flow complete")
    return True
