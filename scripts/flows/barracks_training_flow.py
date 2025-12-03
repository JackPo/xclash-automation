"""
Barracks Training Flow - Train soldiers at a specific level for a target time.

Called when training panel is ALREADY OPEN (icon_daemon clicked the bubble).

Args:
    soldier_level: int (3-8) - which soldier level to train (default 4)
    target_hours: float - target training time in hours (default 4.0)
    pack_resources: bool - whether to pack resources after (default True, NOT YET IMPLEMENTED)
"""

import sys
import time
import cv2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.adb_helper import ADBHelper
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.ocr_client import OCRClient
from scripts.flows.soldier_training_flow import find_and_click_soldier_level

# Calibration constants (from calibration 2024-12-03)
TIME_SLOPE = 183.627743
TIME_INTERCEPT = -293869.64

# Slider parameters
SLIDER_Y = 1170
SEARCH_Y_START = 1100
SEARCH_Y_END = 1250
SEARCH_X_START = 1400
SEARCH_X_END = 2300

# Train button time OCR
TRAIN_BUTTON_POS = (1969, 1399)
TRAIN_TIME_REGION = (50, 80, 280, 45)
TRAIN_BUTTON_CENTER = (2155, 1464)

# Plus/Minus buttons
PLUS_BUTTON = (2207, 1179)
MINUS_BUTTON = (1526, 1177)

# Template path
TEMPLATE_PATH = Path(__file__).parent.parent.parent / "templates" / "ground_truth" / "slider_circle_4k.png"


def find_circle(frame, template):
    """Find slider circle, return X coord or None."""
    search_region = frame[SEARCH_Y_START:SEARCH_Y_END, SEARCH_X_START:SEARCH_X_END]
    result = cv2.matchTemplate(search_region, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)

    if min_val < 0.1:
        template_h, template_w = template.shape[:2]
        return SEARCH_X_START + min_loc[0] + template_w // 2, min_val
    return None, min_val


def ocr_time(frame, ocr):
    """OCR training time, return seconds and string."""
    x = TRAIN_BUTTON_POS[0] + TRAIN_TIME_REGION[0]
    y = TRAIN_BUTTON_POS[1] + TRAIN_TIME_REGION[1]
    w, h = TRAIN_TIME_REGION[2], TRAIN_TIME_REGION[3]

    crop = frame[y:y+h, x:x+w].copy()
    time_str = ocr.extract_text(crop).strip()

    try:
        parts = time_str.split(':')
        if len(parts) == 3:
            hr, mn, sc = int(parts[0]), int(parts[1]), int(parts[2])
            return hr * 3600 + mn * 60 + sc, time_str
    except:
        pass
    return None, time_str


def calculate_target_x(target_seconds):
    """Use calibration formula to get X position for target time."""
    return int((target_seconds - TIME_INTERCEPT) / TIME_SLOPE)


def barracks_training_flow(adb, soldier_level=4, target_hours=4.0, pack_resources=True, debug=False):
    """
    Train soldiers at the barracks with configurable level and time.

    ASSUMES: Training panel is already open (called from icon_daemon after bubble click).

    Args:
        adb: ADBHelper instance
        soldier_level: int (3-8) - which soldier level to train
        target_hours: float - target training time in hours
        pack_resources: bool - pack resources after (NOT YET IMPLEMENTED)
        debug: bool - enable debug logging

    Returns:
        bool: True if training started successfully
    """
    win = WindowsScreenshotHelper()

    if debug:
        print(f"Barracks Training Flow", flush=True)
        print(f"  soldier_level={soldier_level}, target_hours={target_hours}, pack_resources={pack_resources}", flush=True)

    target_seconds = int(target_hours * 3600)

    # Step 1: Find and click soldier level using existing function
    if debug:
        print(f"Step 1: Finding and clicking Lv{soldier_level} tile", flush=True)

    if not find_and_click_soldier_level(adb, win, soldier_level, debug=debug):
        print(f"  ERROR: Could not find Lv{soldier_level} tile", flush=True)
        return False

    time.sleep(0.8)

    # Step 2: Load template and OCR
    template = cv2.imread(str(TEMPLATE_PATH))
    if template is None:
        print("  ERROR: Could not load slider template", flush=True)
        return False

    ocr = OCRClient()

    # Step 3: Push slider to MAX to read full time
    if debug:
        print("Step 2: Push slider to MAX", flush=True)

    frame = win.get_screenshot_cv2()
    circle_x, score = find_circle(frame, template)
    if circle_x is None:
        print(f"  ERROR: Cannot find circle (score={score:.4f})", flush=True)
        return False

    adb.swipe(circle_x, SLIDER_Y, 2200, SLIDER_Y, duration=500)
    time.sleep(0.5)

    frame = win.get_screenshot_cv2()
    max_x, _ = find_circle(frame, template)
    max_secs, max_str = ocr_time(frame, ocr)

    if debug:
        print(f"  MAX: X={max_x}, time={max_str} ({max_secs}s)", flush=True)

    if max_secs is None or max_secs == 0:
        print("  ERROR: Could not read max time", flush=True)
        return False

    # Check if target exceeds max
    if target_seconds >= max_secs:
        if debug:
            print(f"  Target ({target_hours}h) >= max time, using max", flush=True)
        # Already at max, click train
        adb.tap(TRAIN_BUTTON_CENTER[0], TRAIN_BUTTON_CENTER[1])
        return True

    # Step 4: Calculate target X and drag
    target_x = calculate_target_x(target_seconds)
    if debug:
        print(f"Step 3: Drag to target_x={target_x} for {target_hours}h", flush=True)

    # Iterative drag (max 5 attempts)
    for drag_attempt in range(5):
        frame = win.get_screenshot_cv2()
        circle_x, _ = find_circle(frame, template)

        if circle_x is None:
            continue

        current_secs, current_str = ocr_time(frame, ocr)
        if current_secs is None:
            continue

        diff = current_secs - target_seconds
        if debug:
            print(f"  [{drag_attempt+1}] X={circle_x}, time={current_str}, diff={diff}s ({diff/60:.1f}min)", flush=True)

        # If under target, done with dragging
        if diff < 0:
            if debug:
                print(f"  Under target, moving to fine-tune", flush=True)
            break

        # If within 5 minutes, done with dragging
        if abs(diff) <= 300:
            if debug:
                print(f"  Within tolerance, moving to fine-tune", flush=True)
            break

        # Drag to target
        adb.swipe(circle_x, SLIDER_Y, target_x, SLIDER_Y, duration=500)
        time.sleep(0.5)

    # Step 5: Fine-tune with minus button to get just UNDER target
    if debug:
        print("Step 4: Fine-tune to get just UNDER target", flush=True)

    for i in range(50):
        frame = win.get_screenshot_cv2()
        current_secs, current_str = ocr_time(frame, ocr)

        if current_secs is None:
            time.sleep(0.3)
            continue

        diff = current_secs - target_seconds

        if current_secs < target_seconds:
            # Under target - done!
            if debug:
                print(f"  SUCCESS: {current_str} (under by {-diff}s)", flush=True)
            break

        # Over target - click minus
        if debug and i % 5 == 0:
            print(f"  [{i+1}] {current_str} (over by {diff}s) -> minus", flush=True)
        adb.tap(MINUS_BUTTON[0], MINUS_BUTTON[1])
        time.sleep(0.25)

    # Step 6: Click Train button
    if debug:
        print("Step 5: Click Train button", flush=True)
    adb.tap(TRAIN_BUTTON_CENTER[0], TRAIN_BUTTON_CENTER[1])
    time.sleep(0.5)

    # TODO: pack_resources implementation
    if pack_resources:
        if debug:
            print("  (pack_resources not yet implemented)", flush=True)

    return True


if __name__ == "__main__":
    adb = ADBHelper()
    success = barracks_training_flow(adb, soldier_level=4, target_hours=4.0, debug=True)
    print(f"\nResult: {'SUCCESS' if success else 'FAILED'}")
