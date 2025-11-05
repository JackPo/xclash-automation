#!/usr/bin/env python3
"""
Manual zoom testing - uses existing minitouch commands from discover_zoom_adb.py
Interactive tool to calibrate zoom step by step
"""

import subprocess
import time
import cv2
import numpy as np
from pathlib import Path

# ADB config
ADB = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
DEVICE = "emulator-5554"

def zoom_in_minitouch():
    """Zoom in using minitouch pinch-out (fingers move apart)
    NOTE: With 100ms waits, this actually zooms OUT"""
    commands = """d 0 15104 9216 50
d 1 17664 9216 50
c
w 100
m 0 13952 9216 50
m 1 18816 9216 50
c
w 100
m 0 12800 9216 50
m 1 19968 9216 50
c
w 100
u 0
u 1
c
"""

    cmd = [ADB, "-s", DEVICE, "shell", "/data/local/tmp/minitouch -i"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        proc.communicate(input=commands, timeout=2)
    except:
        proc.kill()
    time.sleep(1)  # Wait for zoom animation

def zoom_out_minitouch():
    """Zoom out using minitouch pinch-in (fingers move together)
    NOTE: With 100ms waits, this actually zooms IN"""
    commands = """d 0 12800 9216 50
d 1 19968 9216 50
c
w 100
m 0 13952 9216 50
m 1 18816 9216 50
c
w 100
m 0 15104 9216 50
m 1 17664 9216 50
c
w 100
u 0
u 1
c
"""

    cmd = [ADB, "-s", DEVICE, "shell", "/data/local/tmp/minitouch -i"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        proc.communicate(input=commands, timeout=2)
    except:
        proc.kill()
    time.sleep(1)  # Wait for zoom animation

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

def check_current_zoom():
    """Check current zoom level and compare to reference"""
    print("="*60)
    print("ZOOM CHECK")
    print("="*60)

    # Reference (from rightnow.png)
    ref_sizes = detect_castles("rightnow.png")
    ref_avg_w, ref_avg_h = get_average_size(ref_sizes)
    print(f"\nReference (rightnow.png):")
    print(f"  Castles: {len(ref_sizes)}")
    print(f"  Size: {ref_avg_w:.1f} x {ref_avg_h:.1f} px")

    # Current
    print(f"\nCapturing current screenshot...")
    capture_screenshot("current_zoom_check.png")

    curr_sizes = detect_castles("current_zoom_check.png")
    curr_avg_w, curr_avg_h = get_average_size(curr_sizes)
    print(f"\nCurrent:")
    print(f"  Castles: {len(curr_sizes)}")
    print(f"  Size: {curr_avg_w:.1f} x {curr_avg_h:.1f} px")

    # Compare
    width_diff = curr_avg_w - ref_avg_w
    height_diff = curr_avg_h - ref_avg_h

    print(f"\nDifference:")
    print(f"  Width: {width_diff:+.1f}px")
    print(f"  Height: {height_diff:+.1f}px")

    tolerance = 2.0

    if abs(width_diff) < tolerance and abs(height_diff) < tolerance:
        print(f"\n*** CALIBRATED! ***")
        print(f"Castle sizes match reference (within {tolerance}px)")
        return "CALIBRATED"
    elif height_diff < -tolerance:
        print(f"\nAction needed: ZOOM IN (castle height too small)")
        return "ZOOM_IN"
    elif height_diff > tolerance:
        print(f"\nAction needed: ZOOM OUT (castle height too large)")
        return "ZOOM_OUT"
    elif width_diff < -tolerance:
        print(f"\nAction needed: ZOOM IN (castle width too small)")
        return "ZOOM_IN"
    elif width_diff > tolerance:
        print(f"\nAction needed: ZOOM OUT (castle width too large)")
        return "ZOOM_OUT"
    else:
        print(f"\n*** CALIBRATED! ***")
        return "CALIBRATED"

def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_zoom_manual.py check       - Check current zoom")
        print("  python test_zoom_manual.py in          - Zoom IN once")
        print("  python test_zoom_manual.py out         - Zoom OUT once")
        print("  python test_zoom_manual.py auto        - Auto-calibrate (will ask confirmation each step)")
        return

    action = sys.argv[1].lower()

    if action == "check":
        check_current_zoom()

    elif action == "in":
        print("Zooming IN...")
        zoom_in_minitouch()
        print("Done. Run 'python test_zoom_manual.py check' to verify.")

    elif action == "out":
        print("Zooming OUT...")
        zoom_out_minitouch()
        print("Done. Run 'python test_zoom_manual.py check' to verify.")

    elif action == "auto":
        print("AUTO-CALIBRATION MODE")
        print("I will check zoom and ask you to confirm each step.\n")

        step = 0
        while True:
            step += 1
            print(f"\n{'='*60}")
            print(f"STEP {step}")
            print(f"{'='*60}")

            result = check_current_zoom()

            if result == "CALIBRATED":
                print(f"\nCalibration complete in {step} step(s)!")
                break

            print(f"\n>>> Recommended action: {result}")
            confirm = input("Execute this action? (y/n): ")

            if confirm.lower() != 'y':
                print("Stopped by user.")
                break

            if result == "ZOOM_IN":
                print("Executing zoom IN...")
                zoom_in_minitouch()
            elif result == "ZOOM_OUT":
                print("Executing zoom OUT...")
                zoom_out_minitouch()

    else:
        print(f"Unknown action: {action}")

if __name__ == "__main__":
    main()
