"""Show coordinates and wait for manual click test"""
import sys
sys.path.insert(0, '.')

from button_matcher import ButtonMatcher
from pathlib import Path
import cv2
import subprocess

def capture_screenshot():
    """Capture screenshot from BlueStacks via ADB"""
    adb_path = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
    device = "emulator-5554"
    temp_file = "temp_screenshot.png"

    subprocess.run([adb_path, "-s", device, "shell", "screencap", "/sdcard/temp.png"], capture_output=True)
    subprocess.run([adb_path, "-s", device, "pull", "/sdcard/temp.png", temp_file], capture_output=True)

    return cv2.imread(temp_file)

def main():
    print("Initializing ButtonMatcher...")
    template_dir = Path(__file__).parent / "templates" / "buttons"
    debug_dir = Path(__file__).parent / "templates" / "debug"
    matcher = ButtonMatcher(template_dir=template_dir, debug_dir=debug_dir, threshold=0.85)

    frame = capture_screenshot()
    result = matcher.match(frame)

    if result is None:
        print("ERROR: No button detected!")
        return

    state = result.label
    x, y = result.top_left
    x2, y2 = result.bottom_right
    w = x2 - x
    h = y2 - y

    print(f"\nCurrent state: {state}")
    print(f"Button bounds: ({x}, {y}) to ({x2}, {y2}), size: {w}x{h}")

    # Calculate coordinates for UNION click
    union_x = int(x + w * 0.25)
    union_y = int(y + h * 0.5)

    print(f"\n" + "="*60)
    print("MANUAL TEST INSTRUCTIONS:")
    print("="*60)
    print(f"\n1. The button is currently in {state} mode")
    print(f"2. To switch to UNION mode, you should click at approximately:")
    print(f"   Screen coordinates: ({union_x}, {union_y})")
    print(f"\n3. Manually click on the UNION button (left side with star icon)")
    print(f"4. Then press ENTER here to check if state changed...")

    input("\nPress ENTER after you manually clicked the UNION button: ")

    print("\nCapturing new screenshot...")
    frame_after = capture_screenshot()
    result_after = matcher.match(frame_after)

    if result_after is None:
        print("WARNING: No button detected after manual click")
        return

    state_after = result_after.label
    print(f"State after manual click: {state_after}")

    if state_after != state:
        print(f"\nSUCCESS! Manual click worked - state changed from {state} to {state_after}")
        print("\nThis means the button works, but ADB tap/swipe is NOT working.")
        print("Possible reasons:")
        print("1. Game might be blocking programmatic input")
        print("2. Might need keyboard/mouse input instead of touch")
        print("3. BlueStacks input bridge might have issues")
    else:
        print(f"\nState unchanged (still {state_after})")
        print("Either the manual click didn't register or the button is disabled")

if __name__ == "__main__":
    main()
