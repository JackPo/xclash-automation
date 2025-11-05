"""Compare template size vs actual detected button size"""
import sys
sys.path.insert(0, '.')

from button_matcher import ButtonMatcher
from pathlib import Path
import cv2
import subprocess

def capture_screenshot():
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

    # Get template size
    template_height, template_width = matcher.template_shape
    print(f"\nTemplate size: {template_width}x{template_height}")

    # Capture and detect
    frame = capture_screenshot()
    result = matcher.match(frame)

    if result is None:
        print("ERROR: No button detected!")
        return

    # Get detected button size
    x, y = result.top_left
    x2, y2 = result.bottom_right
    detected_width = x2 - x
    detected_height = y2 - y

    print(f"Detected button size: {detected_width}x{detected_height}")
    print(f"Detected button bounds: ({x}, {y}) to ({x2}, {y2})")

    print(f"\n{'='*60}")
    print("SIZE COMPARISON:")
    print(f"{'='*60}")
    print(f"Template:  {template_width}x{template_height}")
    print(f"Detected:  {detected_width}x{detected_height}")
    print(f"Difference: {detected_width - template_width}x{detected_height - template_height}")

    if template_width != detected_width or template_height != detected_height:
        print(f"\n*** BUG FOUND! ***")
        print(f"The code is using template size ({template_width}x{template_height})")
        print(f"But the detected button is ({detected_width}x{detected_height})")
        print(f"\nThis means click coordinates are calculated WRONG!")

        # Show the difference in click positions
        print(f"\n{'='*60}")
        print("CLICK COORDINATE COMPARISON (for UNION click at x_frac=0.25):")
        print(f"{'='*60}")

        xf = 0.25
        yf = 0.5

        # Wrong (using template size)
        wrong_x = int(x + template_width * xf)
        wrong_y = int(y + template_height * yf)

        # Correct (using detected size)
        correct_x = int(x + detected_width * xf)
        correct_y = int(y + detected_height * yf)

        print(f"WRONG  (template): ({wrong_x}, {wrong_y})")
        print(f"CORRECT (detected): ({correct_x}, {correct_y})")
        print(f"Difference: ({correct_x - wrong_x}, {correct_y - wrong_y}) pixels off!")
    else:
        print("\nSizes match - this is not the issue")

if __name__ == "__main__":
    main()
