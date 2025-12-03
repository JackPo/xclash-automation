"""
Slider Calibration Script

Moves slider to multiple positions and uses template matching to find
actual circle position. Builds a calibration mapping.

Strategy:
1. For each target X position, swipe slider from far left to target
2. Take screenshot with WindowsScreenshotHelper
3. Use template matching to find actual circle center
4. Record: (commanded_x, actual_x)
5. Analyze to find scaling/offset relationship
"""

import sys
import time
import cv2
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.adb_helper import ADBHelper
from utils.windows_screenshot_helper import WindowsScreenshotHelper


# Current assumed coordinates
SLIDER_Y = 1170
SLIDER_LEFT_X = 1601   # Assumed MIN
SLIDER_RIGHT_X = 2117  # Assumed MAX

# Template path
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "ground_truth" / "slider_circle_4k.png"

# Search region for template matching (vertical band around slider)
SEARCH_Y_START = 1100
SEARCH_Y_END = 1250
SEARCH_X_START = 1400  # Wide range to find circle anywhere
SEARCH_X_END = 2300


def find_circle_position(frame, template):
    """
    Find slider circle using template matching.

    Returns:
        (x, y, score) - center coordinates and match score
        or (None, None, None) if not found
    """
    # Crop search region
    search_region = frame[SEARCH_Y_START:SEARCH_Y_END, SEARCH_X_START:SEARCH_X_END]

    # Template match with TM_SQDIFF_NORMED (lower = better)
    result = cv2.matchTemplate(search_region, template, cv2.TM_SQDIFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if min_val < 0.1:  # Good match threshold
        template_h, template_w = template.shape[:2]
        # Convert back to full image coordinates
        center_x = SEARCH_X_START + min_loc[0] + template_w // 2
        center_y = SEARCH_Y_START + min_loc[1] + template_h // 2
        return center_x, center_y, min_val

    return None, None, min_val


def find_and_drag_circle(adb, win, template, target_x):
    """
    Find the circle using template matching, then drag it to target_x.

    Returns:
        The starting X position of the circle, or None if not found
    """
    # Take screenshot
    frame = win.get_screenshot_cv2()

    # Find current circle position
    current_x, current_y, score = find_circle_position(frame, template)

    if current_x is None:
        print(f"    WARNING: Could not find circle (score={score:.4f})")
        return None

    # Drag from current to target
    adb.swipe(current_x, SLIDER_Y, target_x, SLIDER_Y, duration=400)
    time.sleep(0.4)

    return current_x


def reset_slider_to_min(adb, win, template):
    """Drag slider circle all the way to the left."""
    # Find and drag to far left
    for _ in range(3):  # Multiple drags to ensure we hit the minimum
        find_and_drag_circle(adb, win, template, 1400)
        time.sleep(0.2)


def swipe_to_position(adb, target_x, current_x=None):
    """
    Swipe from current position (or left edge) to target_x.
    DEPRECATED - use find_and_drag_circle instead.
    """
    if current_x is None:
        current_x = 1400  # Start from far left

    adb.swipe(current_x, SLIDER_Y, target_x, SLIDER_Y, duration=400)
    time.sleep(0.4)


def main():
    print("=" * 70)
    print("SLIDER CALIBRATION SCRIPT")
    print("=" * 70)
    print()

    # Load template
    if not TEMPLATE_PATH.exists():
        print(f"ERROR: Template not found: {TEMPLATE_PATH}")
        return

    template = cv2.imread(str(TEMPLATE_PATH))
    if template is None:
        print(f"ERROR: Could not load template")
        return

    print(f"Template loaded: {template.shape}")
    print()

    # Initialize helpers
    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    # Test positions - spread across the slider range
    # We'll drag to these X positions
    test_positions = [
        1500, 1550, 1600, 1650, 1700, 1750, 1800, 1850, 1900, 1950,
        2000, 2050, 2100, 2150, 2200
    ]

    results = []

    print("Starting calibration...")
    print("First, resetting slider to minimum position...")
    reset_slider_to_min(adb, win, template)
    time.sleep(0.5)

    print("-" * 80)
    print(f"{'#':>3} | {'Target X':>10} | {'Start X':>10} | {'Actual X':>10} | {'Score':>8} | {'Delta':>8}")
    print("-" * 80)

    for i, target_x in enumerate(test_positions):
        # Find current position and drag to target
        start_x = find_and_drag_circle(adb, win, template, target_x)
        time.sleep(0.3)

        # Take screenshot to verify where we ended up
        frame = win.get_screenshot_cv2()

        # Find actual circle position
        actual_x, actual_y, score = find_circle_position(frame, template)

        if actual_x is not None:
            delta = actual_x - target_x
            results.append({
                'target': target_x,
                'start': start_x,
                'actual_x': actual_x,
                'actual_y': actual_y,
                'score': score,
                'delta': delta
            })
            print(f"{i+1:>3} | {target_x:>10} | {start_x if start_x else 'N/A':>10} | {actual_x:>10} | {score:>8.4f} | {delta:>+8}")
        else:
            print(f"{i+1:>3} | {target_x:>10} | {start_x if start_x else 'N/A':>10} | {'NOT FOUND':>10} | {score:>8.4f} | {'-':>8}")

    print("-" * 70)
    print()

    # Analyze results
    if len(results) >= 2:
        print("ANALYSIS:")
        print("-" * 70)

        # Extract data
        targets = np.array([r['target'] for r in results])
        actuals = np.array([r['actual_x'] for r in results])

        # Linear regression: actual = m * target + b
        # Using numpy polyfit
        m, b = np.polyfit(targets, actuals, 1)

        print(f"Linear fit: actual_x = {m:.4f} * target_x + {b:.2f}")
        print()

        # Calculate residuals
        predicted = m * targets + b
        residuals = actuals - predicted

        print(f"Mean delta (target vs actual): {np.mean([r['delta'] for r in results]):.1f}")
        print(f"Std delta: {np.std([r['delta'] for r in results]):.1f}")
        print(f"Max residual: {np.max(np.abs(residuals)):.1f}")
        print()

        # Find actual min/max
        min_actual = np.min(actuals)
        max_actual = np.max(actuals)

        print(f"Actual range observed:")
        print(f"  Min position: {min_actual}")
        print(f"  Max position: {max_actual}")
        print(f"  Range: {max_actual - min_actual}")
        print()

        # Derive scaling formula
        print("CALIBRATION FORMULA:")
        print("-" * 70)
        if abs(m - 1.0) < 0.1:
            # Nearly 1:1, just offset
            print(f"Relationship is ~1:1 with offset")
            print(f"To hit actual position A, drag to target: A + {-b:.0f}")
        else:
            print(f"To hit actual position A, drag to target: (A - {b:.2f}) / {m:.4f}")

        print()
        print("RECOMMENDED UPDATES for training_slider_helper.py:")
        if m != 0:
            print(f"  # Calibration: target_x = (desired_x - {b:.1f}) / {m:.4f}")
            print(f"  # Or: target_x = desired_x * {1/m:.4f} + {-b/m:.1f}")

    else:
        print("Not enough data points for analysis")

    print()
    print("=" * 70)
    print("Calibration complete!")


if __name__ == "__main__":
    main()
