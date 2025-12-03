"""
Slider Calibration Script

Systematically moves the slider to many positions and measures actual circle center
coordinates using template matching. This helps understand the true mapping between
ADB tap/swipe coordinates and visual circle positions.

Run this with the training panel open (soldier level selected, slider visible).
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


# Template for finding slider circle
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "ground_truth" / "slider_circle_4k.png"

# Search region for template matching (Y band around slider)
SEARCH_Y_MIN = 1100
SEARCH_Y_MAX = 1250
SEARCH_X_MIN = 1500
SEARCH_X_MAX = 2200

# Fixed Y for ADB swipe operations
SWIPE_Y = 1170

# Test positions to try (ADB X coordinates)
# We'll swipe from current position to each of these positions
TEST_POSITIONS = list(range(1550, 2200, 20))  # Every 20 pixels from 1550 to 2200


def find_circle_center(frame, template, debug=False):
    """Find the slider circle center using template matching.

    Returns:
        (x, y) center coordinates in full image, or None if not found
    """
    # Crop search region
    search_region = frame[SEARCH_Y_MIN:SEARCH_Y_MAX, SEARCH_X_MIN:SEARCH_X_MAX]

    # Template match
    result = cv2.matchTemplate(search_region, template, cv2.TM_SQDIFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if min_val < 0.1:  # Good match
        template_h, template_w = template.shape[:2]
        # Convert to full image coordinates (center of template)
        center_x = SEARCH_X_MIN + min_loc[0] + template_w // 2
        center_y = SEARCH_Y_MIN + min_loc[1] + template_h // 2
        return (center_x, center_y), min_val

    return None, min_val


def calibrate_slider():
    """Run the calibration procedure."""
    print("=" * 70)
    print("SLIDER CALIBRATION SCRIPT")
    print("=" * 70)
    print()
    print("This script will:")
    print("1. Move slider to various ADB X coordinates")
    print("2. Measure actual circle center via template matching")
    print("3. Build a mapping between ADB coords and visual coords")
    print()
    print("Make sure the training panel is open with slider visible!")
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

    # Initialize helpers
    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    # Results storage
    calibration_data = []

    # First, go to leftmost position to start clean
    print("\nStep 1: Moving to leftmost position...")
    adb.swipe(2100, SWIPE_Y, 1550, SWIPE_Y, duration=500)
    time.sleep(0.5)

    # Take initial screenshot to verify
    frame = win.get_screenshot_cv2()
    result, score = find_circle_center(frame, template)
    if result:
        print(f"  Initial position: circle at {result}, score={score:.4f}")
        start_x = result[0]
    else:
        print(f"  WARNING: Could not find circle initially (score={score:.4f})")
        start_x = 1600

    print(f"\nStep 2: Testing {len(TEST_POSITIONS)} positions...")
    print("-" * 70)
    print(f"{'ADB Target X':>12} | {'Visual X':>10} | {'Visual Y':>10} | {'Score':>8} | {'Delta':>8}")
    print("-" * 70)

    prev_visual_x = start_x

    for i, target_x in enumerate(TEST_POSITIONS):
        # Swipe from current position to target
        # We need to swipe from where the circle currently IS (visual coords)
        # to where we want it to GO (target ADB coords)

        # Actually, let's try a different approach:
        # First go to min, then swipe TO target from min
        if i > 0:
            # Reset to min first
            adb.swipe(prev_visual_x, SWIPE_Y, 1550, SWIPE_Y, duration=300)
            time.sleep(0.3)

        # Now swipe from min to target
        adb.swipe(1550, SWIPE_Y, target_x, SWIPE_Y, duration=300)
        time.sleep(0.4)

        # Take screenshot and find circle
        frame = win.get_screenshot_cv2()
        result, score = find_circle_center(frame, template)

        if result:
            visual_x, visual_y = result
            delta = visual_x - target_x
            print(f"{target_x:>12} | {visual_x:>10} | {visual_y:>10} | {score:>8.4f} | {delta:>+8}")

            calibration_data.append({
                'adb_target_x': target_x,
                'visual_x': visual_x,
                'visual_y': visual_y,
                'score': float(score),
                'delta': delta
            })

            prev_visual_x = visual_x
        else:
            print(f"{target_x:>12} | {'FAIL':>10} | {'':>10} | {score:>8.4f} | {'':>8}")
            calibration_data.append({
                'adb_target_x': target_x,
                'visual_x': None,
                'visual_y': None,
                'score': float(score),
                'delta': None
            })

    print("-" * 70)

    # Save calibration data
    output_file = Path(__file__).parent.parent / "slider_calibration_data.json"
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'swipe_y': SWIPE_Y,
            'test_positions': TEST_POSITIONS,
            'data': calibration_data
        }, f, indent=2)

    print(f"\nCalibration data saved to: {output_file}")

    # Analyze results
    valid_data = [d for d in calibration_data if d['visual_x'] is not None]

    if len(valid_data) >= 2:
        print("\n" + "=" * 70)
        print("ANALYSIS")
        print("=" * 70)

        adb_xs = [d['adb_target_x'] for d in valid_data]
        visual_xs = [d['visual_x'] for d in valid_data]
        deltas = [d['delta'] for d in valid_data]

        # Linear regression
        adb_xs_np = np.array(adb_xs)
        visual_xs_np = np.array(visual_xs)

        # Fit: visual_x = slope * adb_x + intercept
        slope, intercept = np.polyfit(adb_xs_np, visual_xs_np, 1)

        print(f"\nLinear fit: visual_x = {slope:.4f} * adb_x + {intercept:.2f}")
        print(f"  - If slope=1.0, no scaling")
        print(f"  - If slope<1.0, ADB coords are larger than visual")
        print(f"  - If slope>1.0, ADB coords are smaller than visual")

        # Calculate residuals
        predicted = slope * adb_xs_np + intercept
        residuals = visual_xs_np - predicted
        rmse = np.sqrt(np.mean(residuals**2))

        print(f"\nResiduals (RMSE): {rmse:.2f} pixels")

        # Min/Max ranges
        print(f"\nADB range: {min(adb_xs)} to {max(adb_xs)}")
        print(f"Visual range: {min(visual_xs)} to {max(visual_xs)}")

        # Delta stats
        print(f"\nDelta (visual - adb) stats:")
        print(f"  Min: {min(deltas)}")
        print(f"  Max: {max(deltas)}")
        print(f"  Mean: {np.mean(deltas):.1f}")

        # Suggest corrected coordinates
        print("\n" + "=" * 70)
        print("SUGGESTED CORRECTIONS")
        print("=" * 70)
        print(f"\nTo hit a visual target X, use ADB X = (visual_x - {intercept:.2f}) / {slope:.4f}")
        print(f"\nExample: To position circle at visual x=1700:")
        example_adb = (1700 - intercept) / slope
        print(f"  Use ADB x = (1700 - {intercept:.2f}) / {slope:.4f} = {example_adb:.0f}")

    else:
        print("\nNot enough valid data points to analyze")


if __name__ == "__main__":
    calibrate_slider()
