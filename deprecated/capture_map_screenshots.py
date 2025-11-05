#!/usr/bin/env python3
"""
Capture multiple screenshots by panning around the map.
Assumes zoom is already calibrated.
"""

import subprocess
import time
from pathlib import Path

# ADB config
ADB = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
DEVICE = "emulator-5554"

# Screen center for panning (1920x1080 resolution)
CENTER_X, CENTER_Y = 960, 540

def capture_screenshot(output_path):
    """Capture screenshot from device"""
    subprocess.run([ADB, "-s", DEVICE, "shell", "screencap", "/sdcard/temp.png"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([ADB, "-s", DEVICE, "pull", "/sdcard/temp.png", output_path],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def pan(direction, distance=400):
    """Pan the map in the given direction

    Args:
        direction: 'up', 'down', 'left', 'right', 'up-left', 'up-right', 'down-left', 'down-right'
        distance: How far to pan (pixels)
    """
    # Calculate start and end points for swipe
    if direction == 'up':
        start_x, start_y = CENTER_X, CENTER_Y + distance
        end_x, end_y = CENTER_X, CENTER_Y - distance
    elif direction == 'down':
        start_x, start_y = CENTER_X, CENTER_Y - distance
        end_x, end_y = CENTER_X, CENTER_Y + distance
    elif direction == 'left':
        start_x, start_y = CENTER_X + distance, CENTER_Y
        end_x, end_y = CENTER_X - distance, CENTER_Y
    elif direction == 'right':
        start_x, start_y = CENTER_X - distance, CENTER_Y
        end_x, end_y = CENTER_X + distance, CENTER_Y
    elif direction == 'up-left':
        start_x, start_y = CENTER_X + distance, CENTER_Y + distance
        end_x, end_y = CENTER_X - distance, CENTER_Y - distance
    elif direction == 'up-right':
        start_x, start_y = CENTER_X - distance, CENTER_Y + distance
        end_x, end_y = CENTER_X + distance, CENTER_Y - distance
    elif direction == 'down-left':
        start_x, start_y = CENTER_X + distance, CENTER_Y - distance
        end_x, end_y = CENTER_X - distance, CENTER_Y + distance
    elif direction == 'down-right':
        start_x, start_y = CENTER_X - distance, CENTER_Y - distance
        end_x, end_y = CENTER_X + distance, CENTER_Y + distance
    else:
        raise ValueError(f"Unknown direction: {direction}")

    # Execute swipe
    cmd = f"input swipe {start_x} {start_y} {end_x} {end_y} 300"
    subprocess.run([ADB, "-s", DEVICE, "shell", cmd],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)  # Wait for pan animation

def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python capture_map_screenshots.py <num_screenshots>")
        print("Example: python capture_map_screenshots.py 15")
        return

    num_screenshots = int(sys.argv[1])

    # Create output directory
    output_dir = Path("map_screenshots")
    output_dir.mkdir(exist_ok=True)

    print(f"Capturing {num_screenshots} screenshots...")

    # Pan pattern: cycle through 8 directions
    directions = ['right', 'down', 'left', 'up', 'down-right', 'down-left', 'up-left', 'up-right']

    for i in range(num_screenshots):
        print(f"[{i+1}/{num_screenshots}] Capturing screenshot...")

        # Capture screenshot
        output_path = output_dir / f"map_{i:03d}.png"
        capture_screenshot(str(output_path))
        print(f"  Saved: {output_path}")

        # Pan to next location (except on last iteration)
        if i < num_screenshots - 1:
            direction = directions[i % len(directions)]
            print(f"  Panning {direction}...")
            pan(direction, distance=300)

    print(f"\nDone! Captured {num_screenshots} screenshots in {output_dir}/")

if __name__ == "__main__":
    main()
