#!/usr/bin/env python3
"""
Automatically adjust zoom using pinch gestures until calibrated.
"""

import subprocess
import time

# ADB command
ADB = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
DEVICE = "emulator-5554"

def zoom_in():
    """Zoom in using pinch gesture (move fingers apart)"""
    # Screen center approximately 960x540 (1920x1080 / 2)
    cx, cy = 960, 540

    # Start position (fingers close together)
    x1_start, y1_start = cx - 100, cy
    x2_start, y2_start = cx + 100, cy

    # End position (fingers far apart)
    x1_end, y1_end = cx - 400, cy
    x2_end, y2_end = cx + 400, cy

    # Duration in milliseconds
    duration = 300

    # Perform pinch gesture (two finger swipe simultaneously)
    cmd = f"input swipe {x1_start} {y1_start} {x1_end} {y1_end} {duration} & input swipe {x2_start} {y2_start} {x2_end} {y2_end} {duration}"
    subprocess.run([ADB, "-s", DEVICE, "shell", cmd], check=True)
    print("Zoomed IN")
    time.sleep(0.5)  # Wait for animation

def zoom_out():
    """Zoom out using pinch gesture (move fingers together)"""
    cx, cy = 960, 540

    # Start position (fingers far apart)
    x1_start, y1_start = cx - 400, cy
    x2_start, y2_start = cx + 400, cy

    # End position (fingers close together)
    x1_end, y1_end = cx - 100, cy
    x2_end, y2_end = cx + 100, cy

    duration = 300

    cmd = f"input swipe {x1_start} {y1_start} {x1_end} {y1_end} {duration} & input swipe {x2_start} {y2_start} {x2_end} {y2_end} {duration}"
    subprocess.run([ADB, "-s", DEVICE, "shell", cmd], check=True)
    print("Zoomed OUT")
    time.sleep(0.5)

def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python auto_zoom.py [in|out] [steps]")
        print("Example: python auto_zoom.py in 3")
        return

    direction = sys.argv[1].lower()
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    for i in range(steps):
        if direction == "in":
            zoom_in()
        elif direction == "out":
            zoom_out()
        else:
            print(f"Invalid direction: {direction}")
            return

        print(f"Step {i+1}/{steps} complete")

    print(f"\nZoom adjustment complete. Run calibrate_zoom.py to check.")

if __name__ == "__main__":
    main()
