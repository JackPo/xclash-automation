"""Test swiping on the toggle button instead of tapping"""
import sys
sys.path.insert(0, '.')

from button_matcher import ButtonMatcher
from pathlib import Path
import cv2
import subprocess
import time

def capture_screenshot():
    """Capture screenshot from BlueStacks via ADB"""
    adb_path = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
    device = "emulator-5554"
    temp_file = "temp_screenshot.png"

    subprocess.run([adb_path, "-s", device, "shell", "screencap", "/sdcard/temp.png"], capture_output=True)
    subprocess.run([adb_path, "-s", device, "pull", "/sdcard/temp.png", temp_file], capture_output=True)

    return cv2.imread(temp_file)

def swipe(x1, y1, x2, y2, duration_ms=300):
    """Swipe from (x1,y1) to (x2,y2) over duration_ms milliseconds"""
    adb_path = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
    device = "emulator-5554"

    result = subprocess.run(
        [adb_path, "-s", device, "shell", "input", "swipe",
         str(x1), str(y1), str(x2), str(y2), str(duration_ms)],
        capture_output=True
    )

    return result.returncode == 0

def main():
    print("Initializing ButtonMatcher...")
    template_dir = Path(__file__).parent / "templates" / "buttons"
    debug_dir = Path(__file__).parent / "templates" / "debug"
    matcher = ButtonMatcher(template_dir=template_dir, debug_dir=debug_dir, threshold=0.85)

    print("\n=== BEFORE SWIPE ===")
    frame_before = capture_screenshot()
    result_before = matcher.match(frame_before)

    if result_before is None:
        print("ERROR: No button detected!")
        return

    state_before = result_before.label
    x, y = result_before.top_left
    x2, y2 = result_before.bottom_right
    w = x2 - x
    h = y2 - y

    print(f"Current state: {state_before}")
    print(f"Button bounds: ({x}, {y}) to ({x2}, {y2}), size: {w}x{h}")

    # Try swiping from right to left (WORLD to UNION)
    # Start from right side (WORLD area), swipe to left (UNION area)
    center_y = int(y + h * 0.5)
    start_x = int(x + w * 0.7)  # Start from WORLD side
    end_x = int(x + w * 0.3)    # End at UNION side

    print(f"\nAttempt 1: Swiping from ({start_x}, {center_y}) to ({end_x}, {center_y})")
    print("(From WORLD side to UNION side, 300ms duration)")

    if not swipe(start_x, center_y, end_x, center_y, 300):
        print("ERROR: Swipe failed!")
        return

    print("Swipe sent! Waiting 2 seconds...")
    time.sleep(2)

    print("\n=== AFTER SWIPE ===")
    frame_after = capture_screenshot()
    result_after = matcher.match(frame_after)

    if result_after is None:
        print("WARNING: No button detected after swipe")
        return

    state_after = result_after.label
    print(f"State after swipe: {state_after}")

    if state_after != state_before:
        print(f"\nSUCCESS! State changed from {state_before} to {state_after}")
        print("The button requires a SWIPE gesture, not a TAP!")
        return

    # If swipe didn't work, try tapping on the UNION area directly
    print("\n=== Trying direct tap on UNION text/icon ===")
    tap_x = int(x + w * 0.25)
    tap_y = int(y + h * 0.5)

    print(f"Tapping at ({tap_x}, {tap_y})")

    subprocess.run(
        [r"C:\Program Files\BlueStacks_nxt\hd-adb.exe", "-s", "emulator-5554",
         "shell", "input", "tap", str(tap_x), str(tap_y)],
        capture_output=True
    )

    print("Tap sent! Waiting 2 seconds...")
    time.sleep(2)

    frame_after2 = capture_screenshot()
    result_after2 = matcher.match(frame_after2)

    if result_after2:
        state_after2 = result_after2.label
        print(f"State after tap: {state_after2}")

        if state_after2 != state_before:
            print(f"\nSUCCESS with tap! State changed from {state_before} to {state_after2}")
        else:
            print("\nFAILED: Neither swipe nor tap worked")
            print("The button might be disabled or require manual interaction")

if __name__ == "__main__":
    main()
