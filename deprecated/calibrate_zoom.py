#!/usr/bin/env python3
"""
Calibrate zoom level by comparing castle sizes to the original screenshot.
"""

import subprocess
import cv2
import numpy as np
from pathlib import Path

# ADB command
ADB = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
DEVICE = "emulator-5554"

def capture_screenshot(output_path):
    """Capture screenshot from device"""
    # Take screenshot on device
    subprocess.run([ADB, "-s", DEVICE, "shell", "screencap", "/sdcard/temp.png"], check=True)
    # Pull to PC
    subprocess.run([ADB, "-s", DEVICE, "pull", "/sdcard/temp.png", output_path], check=True)
    print(f"Screenshot saved to: {output_path}")

def detect_castles(image_path):
    """Detect castles and return their sizes"""
    img = cv2.imread(str(image_path))
    if img is None:
        return []

    # Convert to HSV
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # HSV range for white/gray castles
    lower = np.array([0, 0, 180])
    upper = np.array([180, 40, 255])

    # Create mask
    mask = cv2.inRange(hsv, lower, upper)

    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    castle_sizes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)

        # Filter by size and aspect ratio
        if 35 <= w <= 70 and 35 <= h <= 70:
            aspect_ratio = w / h
            if 0.7 <= aspect_ratio <= 1.4:
                # Filter edge castles
                if x > 50 and x + w < img.shape[1] - 50 and y > 50 and y + h < img.shape[0] - 50:
                    castle_sizes.append((w, h))

    return castle_sizes

def get_average_castle_size(sizes):
    """Get average castle width and height"""
    if not sizes:
        return 0, 0
    avg_w = np.mean([s[0] for s in sizes])
    avg_h = np.mean([s[1] for s in sizes])
    return avg_w, avg_h

def main():
    print("="*60)
    print("ZOOM CALIBRATION")
    print("="*60)

    # Get reference castle size from original screenshot
    print("\nAnalyzing original screenshot (reference)...")
    ref_sizes = detect_castles("rightnow.png")
    ref_avg_w, ref_avg_h = get_average_castle_size(ref_sizes)
    print(f"Original screenshot: {len(ref_sizes)} castles detected")
    print(f"Reference castle size: {ref_avg_w:.1f} x {ref_avg_h:.1f} pixels")

    # Capture current screenshot
    print("\nCapturing current screenshot...")
    capture_screenshot("dataset/raw_screenshots/screenshot_00.png")

    # Detect castles in current screenshot
    print("\nAnalyzing current screenshot...")
    curr_sizes = detect_castles("dataset/raw_screenshots/screenshot_00.png")
    curr_avg_w, curr_avg_h = get_average_castle_size(curr_sizes)
    print(f"Current screenshot: {len(curr_sizes)} castles detected")
    print(f"Current castle size: {curr_avg_w:.1f} x {curr_avg_h:.1f} pixels")

    # Compare
    if abs(curr_avg_w - ref_avg_w) < 2 and abs(curr_avg_h - ref_avg_h) < 2:
        print(f"\nOK ZOOM LEVEL CALIBRATED!")
        print(f"Castle sizes match (within 2 pixels)")
        return True
    else:
        size_diff = curr_avg_w - ref_avg_w
        height_diff = curr_avg_h - ref_avg_h
        print(f"\nFAIL ZOOM LEVEL MISMATCH")
        print(f"Width difference: {size_diff:.1f} pixels")
        print(f"Height difference: {height_diff:.1f} pixels")
        if height_diff < 0:
            print(f"Current zoom is TOO FAR. Need to zoom IN.")
        else:
            print(f"Current zoom is TOO CLOSE. Need to zoom OUT.")
        print(f"\nPlease manually adjust zoom and run this script again.")
        return False

if __name__ == "__main__":
    main()
