"""Test actual button clicking with before/after screenshots"""
import sys
sys.path.insert(0, '.')

from button_matcher import ButtonMatcher
from pathlib import Path
import cv2
import numpy as np
import subprocess
import time

def capture_screenshot():
    """Capture screenshot from BlueStacks via ADB"""
    adb_path = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
    device = "emulator-5554"

    temp_file = "temp_screenshot.png"

    # Capture to device
    result = subprocess.run(
        [adb_path, "-s", device, "shell", "screencap", "/sdcard/temp.png"],
        capture_output=True
    )
    if result.returncode != 0:
        print(f"ERROR: Failed to capture screenshot: {result.stderr.decode()}")
        return None

    # Pull from device
    result = subprocess.run(
        [adb_path, "-s", device, "pull", "/sdcard/temp.png", temp_file],
        capture_output=True
    )
    if result.returncode != 0:
        print(f"ERROR: Failed to pull screenshot: {result.stderr.decode()}")
        return None

    # Read image
    frame = cv2.imread(temp_file)
    return frame

def click_at(x, y):
    """Click at specific coordinates via ADB"""
    adb_path = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
    device = "emulator-5554"

    result = subprocess.run(
        [adb_path, "-s", device, "shell", "input", "tap", str(x), str(y)],
        capture_output=True
    )

    if result.returncode != 0:
        print(f"ERROR: Failed to click: {result.stderr.decode()}")
        return False

    return True

def main():
    print("Initializing ButtonMatcher...")
    template_dir = Path(__file__).parent / "templates" / "buttons"
    debug_dir = Path(__file__).parent / "templates" / "debug"
    matcher = ButtonMatcher(template_dir=template_dir, debug_dir=debug_dir, threshold=0.85)

    print("\n=== BEFORE CLICK ===")
    print("Capturing screenshot...")
    frame_before = capture_screenshot()
    if frame_before is None:
        print("ERROR: Could not capture screenshot")
        return

    print("Detecting button state...")
    result_before = matcher.match(frame_before)

    if result_before is None:
        print("ERROR: No button detected!")
        return

    state_before = result_before.label
    score_before = result_before.score
    x, y = result_before.top_left
    x2, y2 = result_before.bottom_right
    w = x2 - x
    h = y2 - y

    print(f"Current state: {state_before} (score: {score_before:.3f})")
    print(f"Button bounds: ({x}, {y}) to ({x2}, {y2}), size: {w}x{h}")

    # Save before screenshot
    cv2.imwrite("test_toggle_before.png", frame_before)
    print("Saved: test_toggle_before.png")

    # Calculate click coordinates based on current state
    if state_before == "WORLD":
        # Click left side to switch to TOWN
        print("\nSwitching from WORLD to TOWN...")
        print("Trying click positions on LEFT side:")
        x_fracs = [0.18, 0.1, 0.02]
        y_fracs = [0.7, 0.8, 0.6]
    else:  # TOWN
        # Click right side to switch to WORLD
        print("\nSwitching from TOWN to WORLD...")
        print("Trying click positions on RIGHT side:")
        x_fracs = [0.82, 0.9, 0.98]
        y_fracs = [0.7, 0.8, 0.6]

    # Try each click position
    for i, (xf, yf) in enumerate(zip(x_fracs, y_fracs)):
        click_x = int(x + w * xf)
        click_y = int(y + h * yf)

        print(f"\nAttempt {i+1}: Clicking at ({click_x}, {click_y}) - x_frac={xf}, y_frac={yf}")

        if not click_at(click_x, click_y):
            print("  Click failed!")
            continue

        print("  Click sent! Waiting 0.5s for UI to update...")
        time.sleep(0.5)

        # Check if state changed
        frame_after = capture_screenshot()
        if frame_after is None:
            print("  ERROR: Could not capture screenshot after click")
            continue

        result_after = matcher.match(frame_after)
        if result_after is None:
            print("  WARNING: No button detected after click")
            continue

        state_after = result_after.label
        score_after = result_after.score

        print(f"  State after click: {state_after} (score: {score_after:.3f})")

        if state_after != state_before:
            print(f"\n✓ SUCCESS! State changed from {state_before} to {state_after}")

            # Save after screenshot
            cv2.imwrite("test_toggle_after.png", frame_after)
            print("Saved: test_toggle_after.png")

            print(f"\nSummary:")
            print(f"  Before: {state_before} (score: {score_before:.3f})")
            print(f"  After: {state_after} (score: {score_after:.3f})")
            print(f"  Click position: ({click_x}, {click_y})")
            print(f"  Click fractional offsets: x={xf}, y={yf}")
            return
        else:
            print(f"  State unchanged (still {state_after})")

    print("\n✗ FAILED: None of the click attempts changed the button state")
    print("All click positions were:")
    for i, (xf, yf) in enumerate(zip(x_fracs, y_fracs)):
        click_x = int(x + w * xf)
        click_y = int(y + h * yf)
        print(f"  {i+1}. ({click_x}, {click_y}) - x_frac={xf}, y_frac={yf}")

if __name__ == "__main__":
    main()
