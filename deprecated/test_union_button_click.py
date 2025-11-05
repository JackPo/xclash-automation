"""Test clicking directly on the UNION button icon"""
import cv2
import subprocess
import time

def capture_screenshot():
    adb_path = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
    device = "emulator-5554"
    temp_file = "temp_screenshot.png"

    subprocess.run([adb_path, "-s", device, "shell", "screencap", "/sdcard/temp.png"], capture_output=True)
    subprocess.run([adb_path, "-s", device, "pull", "/sdcard/temp.png", temp_file], capture_output=True)

    return cv2.imread(temp_file)

def click_at(x, y):
    adb_path = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
    device = "emulator-5554"

    result = subprocess.run(
        [adb_path, "-s", device, "shell", "input", "tap", str(x), str(y)],
        capture_output=True
    )

    return result.returncode == 0

def main():
    # Button bounds: (2160, 1190) to (2560, 1440), size 400x250
    # UNION is on the left half, WORLD is on the right half

    # Try clicking on the center of the UNION icon (roughly left quarter of the button)
    union_click_x = 2160 + 100  # 100 pixels from left edge = 2260
    union_click_y = 1190 + 125  # Middle of button height = 1315

    print("Testing UNION button click")
    print(f"Button bounds: (2160, 1190) to (2560, 1440)")
    print(f"UNION click position: ({union_click_x}, {union_click_y})")
    print(f"  (This is 100px from left edge, middle height)")

    print("\nCapturing BEFORE screenshot...")
    before = capture_screenshot()

    # Check what's at the click position
    print(f"\nPixel color at click position: {before[union_click_y, union_click_x]}")

    print(f"\nClicking at ({union_click_x}, {union_click_y})...")
    if not click_at(union_click_x, union_click_y):
        print("ERROR: Click failed!")
        return

    print("Waiting 1.5 seconds...")
    time.sleep(1.5)

    print("Capturing AFTER screenshot...")
    after = capture_screenshot()

    # Simple pixel difference check
    diff = cv2.absdiff(before, after)
    total_diff = diff.sum()

    print(f"\nPixel difference sum: {total_diff}")

    if total_diff > 1000000:  # Arbitrary threshold
        print("Screen changed significantly - button might have worked!")
        cv2.imwrite("union_click_before.png", before)
        cv2.imwrite("union_click_after.png", after)
        cv2.imwrite("union_click_diff.png", diff)
        print("Saved: union_click_before.png, union_click_after.png, union_click_diff.png")
    else:
        print("Screen did not change - button click had no effect")

    # Also try alternative positions
    print("\n" + "="*60)
    print("Trying alternative UNION button positions...")
    print("="*60)

    alternatives = [
        (2160 + 50, 1190 + 125, "50px from left, middle"),  # More left
        (2160 + 150, 1190 + 125, "150px from left, middle"),  # More right
        (2160 + 100, 1190 + 100, "100px from left, upper"),  # More up
        (2160 + 100, 1190 + 150, "100px from left, lower"),  # More down
    ]

    for alt_x, alt_y, desc in alternatives:
        print(f"\nTrying: ({alt_x}, {alt_y}) - {desc}")
        before_alt = capture_screenshot()
        click_at(alt_x, alt_y)
        time.sleep(1.0)
        after_alt = capture_screenshot()
        diff_alt = cv2.absdiff(before_alt, after_alt).sum()
        print(f"  Difference: {diff_alt}")
        if diff_alt > 1000000:
            print(f"  SUCCESS! This position worked!")
            break

if __name__ == "__main__":
    main()
