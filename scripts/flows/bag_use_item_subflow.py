"""
Bag Use Item Subflow - Shared logic for using items with slider.

Handles the common "use dialog" that appears when clicking bag items:
1. Verify Use button present
2. Verify Plus button present
3. Find slider X position
4. Drag slider to max
5. Click Use button
6. Click back to close dialog

Used by bag_resources_flow.py (diamonds) and bag_hero_flow.py (chests).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import cv2
import numpy as np

# Fixed positions (4K resolution)
# Use button can be at different Y positions depending on dialog type
USE_BUTTON_X_REGION = (1750, 2100)  # X range to search
USE_BUTTON_Y_REGION = (1400, 1700)  # Y range to search (covers both dialog types)
SLIDER_Y_REGION = (1400, 1650)  # Y range for slider search
SLIDER_RIGHT_X = 2400  # Far right of slider track to drag to max
BACK_BUTTON_CLICK = (1407, 2055)

# Bag header region for verification (same as bag_special_flow)
BAG_TAB_REGION = (1352, 32, 1127, 90)

# Thresholds - bag header needs strict 0.01, dialog elements (use button, slider) can be looser
BAG_HEADER_THRESHOLD = 0.01
DIALOG_THRESHOLD = 0.1  # Use button/slider detection

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "ground_truth"

# Cache templates
_use_template = None
_plus_template = None
_slider_template = None
_bag_tab_template = None


def _load_template(name: str) -> np.ndarray:
    """Load a template image in grayscale."""
    path = TEMPLATES_DIR / name
    template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if template is None:
        raise FileNotFoundError(f"Template not found: {path}")
    return template


def _get_templates():
    """Load and cache templates."""
    global _use_template, _plus_template, _slider_template, _bag_tab_template
    if _use_template is None:
        _use_template = _load_template("use_button_4k.png")
        _plus_template = _load_template("plus_button_4k.png")
        _slider_template = _load_template("slider_circle_4k.png")
        _bag_tab_template = _load_template("bag_tab_4k.png")
    return _use_template, _plus_template, _slider_template, _bag_tab_template


def _verify_bag_screen(frame_gray: np.ndarray, bag_tab_template: np.ndarray,
                       threshold: float = BAG_HEADER_THRESHOLD) -> tuple[bool, float]:
    """Check if the Bag header is visible."""
    x, y, w, h = BAG_TAB_REGION
    roi = frame_gray[y:y+h, x:x+w]
    result = cv2.matchTemplate(roi, bag_tab_template, cv2.TM_SQDIFF_NORMED)
    min_val, _, _, _ = cv2.minMaxLoc(result)
    return min_val <= threshold, min_val


def _find_use_button(frame_gray: np.ndarray, template: np.ndarray,
                     threshold: float = DIALOG_THRESHOLD) -> tuple[tuple[int, int] | None, float]:
    """
    Find Use button in the search region.

    Returns:
        ((click_x, click_y), score) or (None, score) if not found
    """
    th, tw = template.shape
    x1, x2 = USE_BUTTON_X_REGION
    y1, y2 = USE_BUTTON_Y_REGION

    roi = frame_gray[y1:y2, x1:x2]
    result = cv2.matchTemplate(roi, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)

    if min_val <= threshold:
        # Convert ROI coords back to frame coords and get center
        click_x = x1 + min_loc[0] + tw // 2
        click_y = y1 + min_loc[1] + th // 2
        return (click_x, click_y), min_val
    return None, min_val


def _find_slider(frame_gray: np.ndarray, slider_template: np.ndarray,
                 threshold: float = DIALOG_THRESHOLD) -> tuple[tuple[int, int] | None, float]:
    """
    Find slider circle in the search region.

    Returns:
        ((x, y), score) or (None, score) if not found
    """
    sh, sw = slider_template.shape
    y1, y2 = SLIDER_Y_REGION

    roi = frame_gray[y1:y2, :]
    result = cv2.matchTemplate(roi, slider_template, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)

    if min_val <= threshold:
        slider_x = min_loc[0] + sw // 2
        slider_y = y1 + min_loc[1] + sh // 2
        return (slider_x, slider_y), min_val
    return None, min_val


def use_item_subflow(adb, win, debug: bool = False) -> bool:
    """
    Handle the use dialog: verify, drag slider, click use, click back.

    Assumes the use dialog is already open (after clicking an item).

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        debug: Enable debug output

    Returns:
        True if successful, False if verification failed
    """
    use_template, plus_template, slider_template, bag_tab_template = _get_templates()

    # Take screenshot for verification
    frame = win.get_screenshot_cv2()
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Find Use button (searches Y range to handle different dialog positions)
    use_pos, score = _find_use_button(frame_gray, use_template)
    if debug:
        print(f"  Use button: found={use_pos is not None}, score={score:.4f}")
    if use_pos is None:
        if debug:
            print("  ERROR: Use dialog not detected")
        return False

    use_click_x, use_click_y = use_pos

    # Find slider position (searches Y range)
    slider_pos, score = _find_slider(frame_gray, slider_template)
    if slider_pos is None:
        if debug:
            print(f"  ERROR: Slider not found (score={score:.4f})")
        return False

    slider_x, slider_y = slider_pos
    if debug:
        print(f"  Slider at ({slider_x}, {slider_y}), score={score:.4f}")

    # Drag slider to max (use found Y position)
    if debug:
        print(f"  Dragging slider from ({slider_x}, {slider_y}) to ({SLIDER_RIGHT_X}, {slider_y})...")
    adb.swipe(slider_x, slider_y, SLIDER_RIGHT_X, slider_y, duration=500)
    time.sleep(0.3)

    # Click Use button at found position
    if debug:
        print(f"  Clicking Use button at ({use_click_x}, {use_click_y})...")
    adb.tap(use_click_x, use_click_y)
    time.sleep(1.0)  # Initial wait for use animation

    # Poll for bag screen - click back until Bag header is visible
    max_attempts = 10
    for attempt in range(max_attempts):
        if debug:
            print(f"  Clicking back (attempt {attempt + 1})...")
        adb.tap(*BACK_BUTTON_CLICK)
        time.sleep(0.5)

        # Check if we're back at the bag screen
        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        is_bag, score = _verify_bag_screen(frame_gray, bag_tab_template)

        if debug:
            print(f"    Bag header check: visible={is_bag}, score={score:.4f}")

        if is_bag:
            if debug:
                print("  Back at bag screen!")
            return True

    if debug:
        print(f"  ERROR: Could not return to bag screen after {max_attempts} attempts")
    return False
