#!/usr/bin/env python3
"""
Navigate to a specific zoom level and capture screenshot.

Usage:
    python goto_zoom_level.py 35
    python goto_zoom_level.py 35 --annotate
"""

import sys
import time
import subprocess
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Configuration
ADB_PATH = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
DEVICE = "emulator-5554"

def zoom_out_once():
    """Zoom out one step using minitouch pinch-in gesture"""
    commands = """d 0 12800 9216 50
d 1 19968 9216 50
c
w 15
m 0 13952 9216 50
m 1 18816 9216 50
c
w 15
m 0 15104 9216 50
m 1 17664 9216 50
c
w 15
u 0
u 1
c
"""

    cmd = [ADB_PATH, "-s", DEVICE, "shell", "/data/local/tmp/minitouch -i"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        proc.communicate(input=commands, timeout=2)
    except:
        proc.kill()

def zoom_out_steps(num_steps):
    """Zoom out by repeating pinch gesture"""
    print(f"Zooming out {num_steps} steps...")
    for i in range(num_steps):
        zoom_out_once()
        time.sleep(1.5)  # Wait for animation and minitouch to reset
        print(f"  Step {i+1}/{num_steps} complete")
    print("Zoom complete!")

def take_screenshot(output_path="current_zoom.png"):
    """Take screenshot and save locally."""
    print(f"Taking screenshot...")

    # Capture screenshot on device
    subprocess.run([ADB_PATH, "-s", DEVICE, "shell", "screencap", "-p", "/sdcard/temp_zoom.png"],
                   capture_output=True)

    # Pull to local
    subprocess.run([ADB_PATH, "-s", DEVICE, "pull", "/sdcard/temp_zoom.png", output_path],
                   capture_output=True)

    print(f"Screenshot saved: {output_path}")
    return output_path

def annotate_screenshot(image_path):
    """Annotate screenshot with OCR region boundaries"""
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)

    # Define OCR region (central game area, excluding UI)
    # Based on analysis of zoom_out_35.png:
    # - Exclude top bar (resources)
    # - Exclude left sidebar (UI buttons)
    # - Exclude right sidebar (events)
    # - Exclude bottom bar (navigation/chat)

    width, height = img.size

    # OCR region for castle numbers only
    left = int(width * 0.08)    # 200px @ 2560 width
    top = int(height * 0.10)     # 144px @ 1440 height
    right = int(width * 0.51)    # 1300px @ 2560 width
    bottom = int(height * 0.49)  # 706px @ 1440 height

    # Draw thick red rectangle
    for offset in range(5):
        draw.rectangle(
            [left + offset, top + offset, right - offset, bottom - offset],
            outline='red'
        )

    # Add labels
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except:
        font = None

    draw.text((left + 10, top + 10), "OCR REGION", fill='red', font=font)
    draw.text((left + 10, bottom - 50), f"{right-left}x{bottom-top}px", fill='red', font=font)

    # Also mark corners with coordinates
    draw.text((left, top - 30), f"({left},{top})", fill='yellow', font=font)
    draw.text((right - 150, bottom + 10), f"({right},{bottom})", fill='yellow', font=font)

    # Save annotated version
    annotated_path = image_path.replace('.png', '_annotated.png')
    img.save(annotated_path)

    print(f"\nAnnotated screenshot saved: {annotated_path}")
    print(f"\nOCR REGION COORDINATES:")
    print(f"  Left:   {left}px")
    print(f"  Top:    {top}px")
    print(f"  Right:  {right}px")
    print(f"  Bottom: {bottom}px")
    print(f"  Size:   {right-left}x{bottom-top} pixels")

    return annotated_path

def main():
    parser = argparse.ArgumentParser(description='Navigate to specific zoom level')
    parser.add_argument('zoom_level', type=int, help='Zoom level (e.g., 35 for zoom_out_35)')
    parser.add_argument('--annotate', action='store_true', help='Annotate screenshot with OCR region')
    parser.add_argument('--output', default='zoom35_live.png', help='Output filename')
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"Navigating to Zoom Level {args.zoom_level}")
    print(f"{'='*60}\n")

    # Check ADB connection
    print("Checking ADB connection...")
    result = subprocess.run([ADB_PATH, "devices"], capture_output=True, text=True)
    if DEVICE not in result.stdout:
        print(f"ERROR: Device {DEVICE} not found")
        print("Make sure BlueStacks is running")
        return
    print("OK - Connected to BlueStacks\n")

    # Zoom to target level
    zoom_out_steps(args.zoom_level)

    # Wait for UI to settle
    print("\nWaiting for UI to settle...")
    time.sleep(2)

    # Take screenshot
    print()
    screenshot_path = take_screenshot(args.output)

    # Annotate if requested
    if args.annotate:
        print()
        annotated_path = annotate_screenshot(screenshot_path)
        print(f"\n{'='*60}")
        print("NEXT STEPS:")
        print(f"{'='*60}")
        print(f"1. Review annotated screenshot: {annotated_path}")
        print(f"2. Verify OCR region captures all castle levels")
        print(f"3. Use these coordinates in OCR scripts")

    print(f"\n{'='*60}")
    print("Complete!")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
