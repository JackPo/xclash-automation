"""
Demo: Set slider to 4 hours using calibration data.

1. Push slider to MAX, read full time
2. Use calibration formula to calculate 4h position
3. Iteratively drag until within ~5 minutes of target
4. Fine-tune with plus/minus buttons to get just UNDER 4 hours
"""

import sys
import time
import cv2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.adb_helper import ADBHelper
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.qwen_ocr import QwenOCR

# Calibration results (2024-12-03)
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

# Plus/Minus buttons
PLUS_BUTTON = (2207, 1179)
MINUS_BUTTON = (1526, 1177)

# Template
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "ground_truth" / "slider_circle_4k.png"


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


def seconds_to_str(secs):
    """Convert seconds to H:MM:SS."""
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return f"{h}:{m:02d}:{s:02d}"


def calculate_target_x(target_seconds):
    """Use calibration formula to get X position for target time."""
    return int((target_seconds - TIME_INTERCEPT) / TIME_SLOPE)


def time_to_x(time_seconds):
    """Convert time to expected X position."""
    return (time_seconds - TIME_INTERCEPT) / TIME_SLOPE


def main():
    print("=" * 60, flush=True)
    print("DEMO: Set Slider to 4 Hours (with iterative drag)", flush=True)
    print("=" * 60, flush=True)
    print(flush=True)

    # Load template
    template = cv2.imread(str(TEMPLATE_PATH))
    if template is None:
        print("ERROR: Could not load template", flush=True)
        return

    # Initialize
    print("Initializing...", flush=True)
    adb = ADBHelper()
    win = WindowsScreenshotHelper()
    ocr = QwenOCR()
    print("Ready!", flush=True)
    print(flush=True)

    TARGET_SECONDS = 4 * 3600  # 4 hours = 14400 seconds
    DRAG_TOLERANCE = 300  # 5 minutes - close enough for drag phase
    FINAL_TOLERANCE = 60  # 1 minute - for button fine-tuning

    print(f"Target: 4 hours = {TARGET_SECONDS} seconds", flush=True)
    print(f"Drag tolerance: {DRAG_TOLERANCE}s ({DRAG_TOLERANCE//60} min)", flush=True)
    print(flush=True)

    # ========================================
    # STEP 1: Push to MAX
    # ========================================
    print("STEP 1: Push slider to MAX", flush=True)
    print("-" * 40, flush=True)

    frame = win.get_screenshot_cv2()
    circle_x, score = find_circle(frame, template)
    if circle_x is None:
        print(f"  ERROR: Cannot find circle (score={score:.4f})", flush=True)
        return
    print(f"  Circle at X={circle_x}", flush=True)

    print(f"  Dragging to far right (2200)...", flush=True)
    adb.swipe(circle_x, SLIDER_Y, 2200, SLIDER_Y, duration=500)
    time.sleep(0.5)

    frame = win.get_screenshot_cv2()
    max_x, _ = find_circle(frame, template)
    max_secs, max_str = ocr_time(frame, ocr)

    print(f"  MAX position: X={max_x}", flush=True)
    print(f"  MAX time: {max_str} = {max_secs} seconds", flush=True)
    print(flush=True)

    # ========================================
    # STEP 2: Calculate target position
    # ========================================
    print("STEP 2: Calculate target position using calibration", flush=True)
    print("-" * 40, flush=True)

    target_x = calculate_target_x(TARGET_SECONDS)
    print(f"  target_x = (14400 + 293869.64) / 183.627743 = {target_x}", flush=True)
    print(flush=True)

    # ========================================
    # STEP 3: Iterative drag until close
    # ========================================
    print("STEP 3: Iterative drag until within 5 minutes", flush=True)
    print("-" * 40, flush=True)

    for drag_attempt in range(10):  # Max 10 drag attempts
        frame = win.get_screenshot_cv2()
        circle_x, _ = find_circle(frame, template)

        if circle_x is None:
            print(f"  [{drag_attempt+1}] ERROR: Cannot find circle", flush=True)
            continue

        # Check current time
        current_secs, current_str = ocr_time(frame, ocr)
        if current_secs is None:
            print(f"  [{drag_attempt+1}] OCR failed, dragging anyway...", flush=True)
        else:
            diff = current_secs - TARGET_SECONDS
            print(f"  [{drag_attempt+1}] At X={circle_x}, time={current_str} ({current_secs}s), diff={diff}s ({diff/60:.1f}min)", flush=True)

            # If we're UNDER target, go straight to plus button fine-tuning
            if diff < 0:
                print(f"  Under target! Moving to fine-tune phase with plus button.", flush=True)
                break

            # Check if we're close enough
            if abs(diff) <= DRAG_TOLERANCE:
                print(f"  Within drag tolerance! Moving to fine-tune phase.", flush=True)
                break

        # Calculate where we need to go based on calibration
        print(f"  Dragging from X={circle_x} to X={target_x}...", flush=True)
        adb.swipe(circle_x, SLIDER_Y, target_x, SLIDER_Y, duration=500)
        time.sleep(0.5)

        # Check where we landed
        frame = win.get_screenshot_cv2()
        new_x, _ = find_circle(frame, template)
        new_secs, new_str = ocr_time(frame, ocr)

        if new_secs:
            new_diff = new_secs - TARGET_SECONDS
            print(f"  Landed at X={new_x}, time={new_str} ({new_secs}s), diff={new_diff}s ({new_diff/60:.1f}min)", flush=True)

            if abs(new_diff) <= DRAG_TOLERANCE:
                print(f"  Within drag tolerance! Moving to fine-tune phase.", flush=True)
                break

            # Recalculate target based on actual position vs expected
            # If we're still off, adjust the target
            if new_x and new_secs:
                # Use current position to refine our next drag
                expected_x_for_time = time_to_x(new_secs)
                offset = new_x - expected_x_for_time
                target_x = calculate_target_x(TARGET_SECONDS) - int(offset)
                print(f"  Adjusted target_x to {target_x} (offset correction: {int(offset)})", flush=True)

        print(flush=True)

    print(flush=True)

    # ========================================
    # STEP 4: Fine-tune with plus/minus buttons
    # ========================================
    print("STEP 4: Fine-tune to get just UNDER 4 hours", flush=True)
    print("-" * 40, flush=True)

    for i in range(100):  # Up to 100 button presses
        frame = win.get_screenshot_cv2()
        current_secs, current_str = ocr_time(frame, ocr)

        if current_secs is None:
            print(f"  [{i+1}] OCR failed, retrying...", flush=True)
            time.sleep(0.3)
            continue

        diff = current_secs - TARGET_SECONDS

        if current_secs < TARGET_SECONDS:
            # Already under 4 hours - we're done!
            print(f"  [{i+1}] {current_str} = {current_secs}s (UNDER by {-diff}s / {-diff/60:.1f}min)", flush=True)
            print(flush=True)
            print("=" * 60, flush=True)
            print("SUCCESS!", flush=True)
            print(f"  Final time: {current_str}", flush=True)
            print(f"  Target was: {seconds_to_str(TARGET_SECONDS)}", flush=True)
            print(f"  Under by: {-diff} seconds ({-diff/60:.1f} minutes)", flush=True)
            print("=" * 60, flush=True)
            return

        # Still over 4 hours - click minus
        print(f"  [{i+1}] {current_str} = {current_secs}s (over by {diff}s / {diff/60:.1f}min) -> minus", flush=True)
        adb.tap(MINUS_BUTTON[0], MINUS_BUTTON[1])
        time.sleep(0.25)

    print("  WARNING: Could not reach target in 100 attempts", flush=True)


if __name__ == "__main__":
    main()
