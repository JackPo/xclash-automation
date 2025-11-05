"""Test a single click on the button with extended wait time"""
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

def click_at(x, y):
    """Click at specific coordinates via ADB"""
    adb_path = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
    device = "emulator-5554"

    result = subprocess.run(
        [adb_path, "-s", device, "shell", "input", "tap", str(x), str(y)],
        capture_output=True
    )

    return result.returncode == 0

def main():
    print("Initializing ButtonMatcher...")
    template_dir = Path(__file__).parent / "templates" / "buttons"
    debug_dir = Path(__file__).parent / "templates" / "debug"
    matcher = ButtonMatcher(template_dir=template_dir, debug_dir=debug_dir, threshold=0.85)

    print("\n=== BEFORE CLICK ===")
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

    # Try clicking in the center of the shield (UNION) area - around 30% from left
    click_x = int(x + w * 0.30)
    click_y = int(y + h * 0.5)

    print(f"\nClicking at ({click_x}, {click_y}) - center of shield area")
    print("(x_frac=0.30, y_frac=0.50)")

    if not click_at(click_x, click_y):
        print("ERROR: Click failed!")
        return

    print("Click sent! Waiting 2 seconds for animation...")
    time.sleep(2)

    print("\n=== AFTER CLICK ===")
    frame_after = capture_screenshot()
    result_after = matcher.match(frame_after)

    if result_after is None:
        print("WARNING: No button detected after click")
        return

    state_after = result_after.label
    print(f"State after click: {state_after}")

    if state_after != state_before:
        print(f"\nSUCCESS! State changed from {state_before} to {state_after}")
    else:
        print(f"\nFAILED: State unchanged (still {state_after})")
        print("\nPossible issues:")
        print("1. Button might not be responsive to ADB tap")
        print("2. Might need drag/swipe instead of tap")
        print("3. Coordinates might be slightly off")
        print("4. Game might be in a state where button is disabled")

if __name__ == "__main__":
    main()
