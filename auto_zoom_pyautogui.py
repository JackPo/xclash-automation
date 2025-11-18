#!/usr/bin/env python3
"""
Automated zoom calibration using pyautogui to send keyboard input
"""

import pyautogui
import pygetwindow as gw
import subprocess
import time
import cv2
import numpy as np

# ADB config
ADB = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
DEVICE = "emulator-5554"

def focus_bluestacks():
    """Find and focus BlueStacks window"""
    windows = gw.getWindowsWithTitle("BlueStacks")
    if not windows:
        windows = gw.getWindowsWithTitle("HD-Player")

    if windows:
        win = windows[0]
        try:
            if win.isMinimized:
                win.restore()
            win.activate()
        except Exception as e:
            # Ignore activation errors - window might still be focused
            pass
        time.sleep(0.5)  # Wait for window to be focused
        return True
    return False

def zoom_in():
    """Send Shift+A to zoom in"""
    if not focus_bluestacks():
        print("ERROR: Could not find BlueStacks window!")
        return False

    pyautogui.hotkey('shift', 'a')
    time.sleep(1.0)  # Wait for zoom animation
    return True

def zoom_out():
    """Send Shift+Z to zoom out"""
    if not focus_bluestacks():
        print("ERROR: Could not find BlueStacks window!")
        return False

    pyautogui.hotkey('shift', 'z')
    time.sleep(1.0)  # Wait for zoom animation
    return True

def capture_screenshot(output_path):
    """Capture screenshot from device"""
    subprocess.run([ADB, "-s", DEVICE, "shell", "screencap", "/sdcard/temp.png"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([ADB, "-s", DEVICE, "pull", "/sdcard/temp.png", output_path],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def detect_castles(image_path):
    """Detect castles and return their sizes"""
    img = cv2.imread(str(image_path))
    if img is None:
        return []

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower = np.array([0, 0, 180])
    upper = np.array([180, 40, 255])
    mask = cv2.inRange(hsv, lower, upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    castle_sizes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if 35 <= w <= 70 and 35 <= h <= 70:
            aspect_ratio = w / h
            if 0.7 <= aspect_ratio <= 1.4:
                # Filter edge castles
                if x > 50 and x + w < img.shape[1] - 50 and y > 50 and y + h < img.shape[0] - 50:
                    castle_sizes.append((w, h))

    return castle_sizes

def get_average_size(sizes):
    """Get average width and height"""
    if not sizes:
        return 0, 0
    avg_w = np.mean([s[0] for s in sizes])
    avg_h = np.mean([s[1] for s in sizes])
    return avg_w, avg_h

def main():
    print("="*60)
    print("AUTOMATED ZOOM CALIBRATION (pyautogui)")
    print("="*60)

    # Get reference castle sizes
    print("\nAnalyzing reference screenshot...")
    ref_sizes = detect_castles("rightnow.png")
    ref_avg_w, ref_avg_h = get_average_size(ref_sizes)
    print(f"Reference: {len(ref_sizes)} castles, size {ref_avg_w:.1f} x {ref_avg_h:.1f} px")

    tolerance = 2.0  # pixels
    iteration = 0
    max_iterations = 50  # Safety limit

    while iteration < max_iterations:
        iteration += 1
        print(f"\n[Iteration {iteration}]")

        # Capture current screenshot
        capture_screenshot("temp_calibrate.png")

        # Detect castles
        curr_sizes = detect_castles("temp_calibrate.png")
        curr_avg_w, curr_avg_h = get_average_size(curr_sizes)

        print(f"  Current: {len(curr_sizes)} castles, size {curr_avg_w:.1f} x {curr_avg_h:.1f} px")

        # Check if calibrated
        width_diff = curr_avg_w - ref_avg_w
        height_diff = curr_avg_h - ref_avg_h

        print(f"  Diff: width={width_diff:+.1f}px, height={height_diff:+.1f}px")

        if abs(width_diff) < tolerance and abs(height_diff) < tolerance:
            print(f"\n{'='*60}")
            print(f"CALIBRATION COMPLETE!")
            print(f"{'='*60}")
            print(f"Iterations: {iteration}")
            print(f"Final size: {curr_avg_w:.1f} x {curr_avg_h:.1f} px")
            print(f"Reference:  {ref_avg_w:.1f} x {ref_avg_h:.1f} px")
            break

        # Determine zoom direction (prioritize height)
        if height_diff < -tolerance:
            print(f"  Action: Sending Shift+A (zoom in - height too small)")
            if not zoom_in():
                print("ERROR: Failed to send zoom command!")
                break
        elif height_diff > tolerance:
            print(f"  Action: Sending Shift+Z (zoom out - height too large)")
            if not zoom_out():
                print("ERROR: Failed to send zoom command!")
                break
        elif width_diff < -tolerance:
            print(f"  Action: Sending Shift+A (zoom in - width too small)")
            if not zoom_in():
                print("ERROR: Failed to send zoom command!")
                break
        elif width_diff > tolerance:
            print(f"  Action: Sending Shift+Z (zoom out - width too large)")
            if not zoom_out():
                print("ERROR: Failed to send zoom command!")
                break

    if iteration >= max_iterations:
        print(f"\nWARNING: Reached max iterations ({max_iterations}) without calibration")

if __name__ == "__main__":
    main()
