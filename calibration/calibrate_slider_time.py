"""
Slider Time Calibration Script

Moves the slider to 30 positions and OCRs the training time at each position.
Builds a linear model: time_seconds = slope * x_position + intercept

This allows us to calculate: target_x = (target_time - intercept) / slope

Run with the training panel open (soldier level selected, slider visible).
"""

import sys
import time
import json
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.adb_helper import ADBHelper
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.ocr_client import OCRClient, ensure_ocr_server


# Slider parameters (4K resolution)
SLIDER_Y = 1170
SLIDER_LEFT_X = 1600   # MIN position (leftmost)
SLIDER_RIGHT_X = 2133  # MAX position (rightmost)

# Template for finding circle
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "ground_truth" / "slider_circle_4k.png"

# Search region for template matching
SEARCH_Y_START = 1100
SEARCH_Y_END = 1250
SEARCH_X_START = 1400
SEARCH_X_END = 2300

# Train button time OCR region
TRAIN_BUTTON_POS = (1969, 1399)
TRAIN_TIME_REGION = (50, 80, 280, 45)  # x_offset, y_offset, width, height

# Number of calibration points
NUM_POINTS = 30


def find_circle(frame, template):
    """Find slider circle using template matching.

    Returns:
        X coordinate of circle center, or None if not found
    """
    search_region = frame[SEARCH_Y_START:SEARCH_Y_END, SEARCH_X_START:SEARCH_X_END]
    result = cv2.matchTemplate(search_region, template, cv2.TM_SQDIFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if min_val < 0.1:
        template_h, template_w = template.shape[:2]
        circle_x = SEARCH_X_START + min_loc[0] + template_w // 2
        return circle_x, min_val
    return None, min_val


def ocr_training_time(frame, ocr):
    """OCR the training time from the train button.

    Returns:
        Time in seconds, or None if OCR fails
    """
    x = TRAIN_BUTTON_POS[0] + TRAIN_TIME_REGION[0]
    y = TRAIN_BUTTON_POS[1] + TRAIN_TIME_REGION[1]
    w = TRAIN_TIME_REGION[2]
    h = TRAIN_TIME_REGION[3]

    time_crop = frame[y:y+h, x:x+w].copy()
    time_str = ocr.extract_text(time_crop)

    # Parse HH:MM:SS or H:MM:SS
    try:
        time_str = time_str.strip()
        parts = time_str.split(':')
        if len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
            return h * 3600 + m * 60 + s, time_str
        elif len(parts) == 2:
            m, s = int(parts[0]), int(parts[1])
            return m * 60 + s, time_str
    except:
        pass

    return None, time_str


def drag_to_position(adb, win, template, target_x):
    """Drag the slider circle to target_x.

    Returns:
        Actual X position after drag
    """
    # Find current circle position
    frame = win.get_screenshot_cv2()
    circle_x, score = find_circle(frame, template)

    if circle_x is None:
        print(f"    ERROR: Could not find circle (score={score:.4f})")
        return None

    # Drag from current to target
    adb.swipe(circle_x, SLIDER_Y, target_x, SLIDER_Y, duration=400)
    time.sleep(0.4)

    # Verify final position
    frame = win.get_screenshot_cv2()
    actual_x, score = find_circle(frame, template)

    return actual_x


def main():
    print("=" * 70, flush=True)
    print("SLIDER TIME CALIBRATION", flush=True)
    print("=" * 70, flush=True)
    print(flush=True)
    print("This script will:", flush=True)
    print("1. Move slider to MIN, record position and time", flush=True)
    print("2. Move slider to MAX, record position and time", flush=True)
    print(f"3. Sample {NUM_POINTS} random positions and OCR each time", flush=True)
    print("4. Build a linear model: time = slope * x + intercept", flush=True)
    print(flush=True)
    print("Make sure the training panel is open with a soldier level selected!", flush=True)
    print(flush=True)

    # Load template
    if not TEMPLATE_PATH.exists():
        print(f"ERROR: Template not found: {TEMPLATE_PATH}", flush=True)
        return

    template = cv2.imread(str(TEMPLATE_PATH))
    if template is None:
        print("ERROR: Could not load template", flush=True)
        return

    print(f"Template loaded: {template.shape}", flush=True)

    # Initialize helpers
    print("Initializing ADB...", flush=True)
    adb = ADBHelper()
    print("Initializing WindowsScreenshotHelper...", flush=True)
    win = WindowsScreenshotHelper()
    print("Checking OCR server...", flush=True)
    if not ensure_ocr_server(auto_start=True):
        print("ERROR: Could not start OCR server!", flush=True)
        sys.exit(1)
    ocr = OCRClient()
    print("All helpers initialized!", flush=True)
    print(flush=True)

    data_points = []

    # ========================================
    # STEP 1: Find circle, drag to MIN (far left)
    # ========================================
    print("=" * 70, flush=True)
    print("STEP 1: Moving to MINIMUM position", flush=True)
    print("=" * 70, flush=True)

    # Find circle
    frame = win.get_screenshot_cv2()
    circle_x, score = find_circle(frame, template)
    if circle_x is None:
        print(f"ERROR: Cannot find circle (score={score:.4f})", flush=True)
        return
    print(f"  Circle found at X={circle_x} (score={score:.4f})", flush=True)

    # Drag to far left (X=1500 to ensure we hit the min)
    print(f"  Dragging from {circle_x} to 1500 (far left)...", flush=True)
    adb.swipe(circle_x, SLIDER_Y, 1500, SLIDER_Y, duration=500)
    time.sleep(0.5)

    # Find circle again to get actual min_x
    frame = win.get_screenshot_cv2()
    min_x, score = find_circle(frame, template)
    if min_x is None:
        print(f"ERROR: Cannot find circle after MIN drag (score={score:.4f})", flush=True)
        return
    print(f"  MIN position: X={min_x} (score={score:.4f})", flush=True)

    # OCR the time at MIN
    time_seconds, time_str = ocr_training_time(frame, ocr)
    if time_seconds is None:
        print(f"ERROR: Cannot OCR time at MIN (got: '{time_str}')", flush=True)
        return
    min_time = time_seconds
    print(f"  MIN time: {time_str} = {min_time} seconds", flush=True)

    data_points.append({
        "target_x": 1500,
        "actual_x": int(min_x),
        "time_str": time_str,
        "time_seconds": min_time
    })

    # ========================================
    # STEP 2: Find circle, drag to MAX (far right)
    # ========================================
    print(flush=True)
    print("=" * 70, flush=True)
    print("STEP 2: Moving to MAXIMUM position", flush=True)
    print("=" * 70, flush=True)

    # Find circle
    frame = win.get_screenshot_cv2()
    circle_x, score = find_circle(frame, template)
    if circle_x is None:
        print(f"ERROR: Cannot find circle (score={score:.4f})", flush=True)
        return
    print(f"  Circle found at X={circle_x} (score={score:.4f})", flush=True)

    # Drag to far right (X=2200 to ensure we hit the max)
    print(f"  Dragging from {circle_x} to 2200 (far right)...", flush=True)
    adb.swipe(circle_x, SLIDER_Y, 2200, SLIDER_Y, duration=500)
    time.sleep(0.5)

    # Find circle again to get actual max_x
    frame = win.get_screenshot_cv2()
    max_x, score = find_circle(frame, template)
    if max_x is None:
        print(f"ERROR: Cannot find circle after MAX drag (score={score:.4f})", flush=True)
        return
    print(f"  MAX position: X={max_x} (score={score:.4f})", flush=True)

    # OCR the time at MAX
    time_seconds, time_str = ocr_training_time(frame, ocr)
    if time_seconds is None:
        print(f"ERROR: Cannot OCR time at MAX (got: '{time_str}')", flush=True)
        return
    max_time = time_seconds
    print(f"  MAX time: {time_str} = {max_time} seconds", flush=True)

    data_points.append({
        "target_x": 2200,
        "actual_x": int(max_x),
        "time_str": time_str,
        "time_seconds": max_time
    })

    # ========================================
    # STEP 3: Sample random positions
    # ========================================
    print(flush=True)
    print("=" * 70, flush=True)
    print(f"STEP 3: Sampling {NUM_POINTS} random positions between X={min_x} and X={max_x}", flush=True)
    print("=" * 70, flush=True)
    print(flush=True)

    # Generate random target positions between min_x and max_x
    import random
    random_targets = [random.randint(int(min_x), int(max_x)) for _ in range(NUM_POINTS)]

    print(f"{'#':>3} | {'Target X':>10} | {'Actual X':>10} | {'Time':>12} | {'Seconds':>10}", flush=True)
    print("-" * 70, flush=True)

    for i, target_x in enumerate(random_targets):
        # Find circle
        frame = win.get_screenshot_cv2()
        circle_x, score = find_circle(frame, template)

        if circle_x is None:
            print(f"{i+1:>3} | {target_x:>10} | {'NO CIRCLE':>10} | {'-':>12} | {'-':>10}", flush=True)
            continue

        # Drag from circle to target
        adb.swipe(circle_x, SLIDER_Y, target_x, SLIDER_Y, duration=400)
        time.sleep(0.4)

        # Find circle again to get actual position
        frame = win.get_screenshot_cv2()
        actual_x, score = find_circle(frame, template)

        if actual_x is None:
            print(f"{i+1:>3} | {target_x:>10} | {'LOST':>10} | {'-':>12} | {'-':>10}", flush=True)
            continue

        # OCR the time
        time_seconds, time_str = ocr_training_time(frame, ocr)

        if time_seconds is None:
            print(f"{i+1:>3} | {target_x:>10} | {actual_x:>10} | {'OCR FAIL':>12} | {'-':>10}", flush=True)
            continue

        print(f"{i+1:>3} | {target_x:>10} | {actual_x:>10} | {time_str:>12} | {time_seconds:>10}", flush=True)

        data_points.append({
            "target_x": int(target_x),
            "actual_x": int(actual_x),
            "time_str": time_str,
            "time_seconds": time_seconds
        })

    print("-" * 70, flush=True)
    print(flush=True)

    # Analyze results
    if len(data_points) < 2:
        print("ERROR: Not enough data points to build model", flush=True)
        return

    # Extract data for regression
    x_values = np.array([p["actual_x"] for p in data_points])
    y_values = np.array([p["time_seconds"] for p in data_points])

    # Linear regression: time = slope * x + intercept
    slope, intercept = np.polyfit(x_values, y_values, 1)

    # Calculate R² (coefficient of determination)
    y_pred = slope * x_values + intercept
    ss_res = np.sum((y_values - y_pred) ** 2)
    ss_tot = np.sum((y_values - np.mean(y_values)) ** 2)
    r_squared = 1 - (ss_res / ss_tot)

    # Calculate RMSE
    rmse = np.sqrt(np.mean((y_values - y_pred) ** 2))

    print("=" * 70, flush=True)
    print("CALIBRATION RESULTS", flush=True)
    print("=" * 70, flush=True)
    print(flush=True)
    print(f"Data points collected: {len(data_points)}", flush=True)
    print(f"X range: {x_values.min()} to {x_values.max()}", flush=True)
    print(f"Time range: {y_values.min()}s to {y_values.max()}s", flush=True)
    print(flush=True)
    print("LINEAR MODEL:", flush=True)
    print(f"  time_seconds = {slope:.6f} * x + {intercept:.2f}", flush=True)
    print(flush=True)
    print(f"  R² (coefficient of determination): {r_squared:.6f}", flush=True)
    print(f"  RMSE (root mean square error): {rmse:.2f} seconds", flush=True)
    print(flush=True)
    print("INVERSE FORMULA (to calculate target X for a given time):", flush=True)
    print(f"  target_x = (target_seconds - {intercept:.2f}) / {slope:.6f}", flush=True)
    print(flush=True)

    # Examples
    print("EXAMPLES:", flush=True)
    for target_hours in [1, 2, 4, 8]:
        target_secs = target_hours * 3600
        target_x = (target_secs - intercept) / slope
        if SLIDER_LEFT_X <= target_x <= SLIDER_RIGHT_X:
            print(f"  {target_hours}h ({target_secs}s) -> X = {target_x:.0f}", flush=True)
        else:
            print(f"  {target_hours}h ({target_secs}s) -> X = {target_x:.0f} (OUT OF RANGE)", flush=True)
    print(flush=True)

    # Save calibration
    calibration = {
        "timestamp": datetime.now().isoformat(),
        "min_x": int(min_x),
        "max_x": int(max_x),
        "min_time_seconds": int(min_time),
        "max_time_seconds": int(max_time),
        "slope": float(slope),
        "intercept": float(intercept),
        "r_squared": float(r_squared),
        "rmse_seconds": float(rmse),
        "num_points": len(data_points),
        "data_points": data_points
    }

    output_path = Path(__file__).parent.parent / "slider_time_calibration.json"
    with open(output_path, 'w') as f:
        json.dump(calibration, f, indent=2)

    print(f"Calibration saved to: {output_path}", flush=True)
    print(flush=True)
    print("=" * 70, flush=True)
    print("COPY THESE VALUES TO training_slider_helper.py:", flush=True)
    print("=" * 70, flush=True)
    print(f"TIME_SLOPE = {slope:.6f}", flush=True)
    print(f"TIME_INTERCEPT = {intercept:.2f}", flush=True)
    print(flush=True)


if __name__ == "__main__":
    main()
