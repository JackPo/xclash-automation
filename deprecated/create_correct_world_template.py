"""Create correct WORLD template from current screenshot"""
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
    print("Capturing screenshot...")
    screenshot = capture_screenshot()

    # The WORLD button is at (2160, 1190) to (2560, 1440)
    x, y = 2160, 1190
    x2, y2 = 2560, 1440

    print(f"Extracting WORLD button from ({x}, {y}) to ({x2}, {y2})")

    # Extract the button area
    world_button = screenshot[y:y2, x:x2]

    print(f"Extracted button size: {world_button.shape[1]}x{world_button.shape[0]}")

    # Save as new template
    output_file = "templates/buttons/world_button_template_NEW.png"
    cv2.imwrite(output_file, world_button)
    print(f"\nSaved NEW WORLD template to: {output_file}")

    # Test the match score with this new template
    result = cv2.matchTemplate(screenshot, world_button, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    print(f"\nNEW template match score: {max_val:.4f} ({max_val*100:.2f}%)")
    print(f"Match location: {max_loc}")

    if max_val >= 0.95:
        print("\n✓ EXCELLENT! New template matches at 95%+")
        print("This should be the correct template!")
    else:
        print(f"\n✗ WARNING: Even new template only matches at {max_val*100:.2f}%")
        print("There might be compression or other issues")

    # Also check old template
    old_template = cv2.imread("templates/buttons/world_button_template.png")
    result_old = cv2.matchTemplate(screenshot, old_template, cv2.TM_CCOEFF_NORMED)
    min_val_old, max_val_old, min_loc_old, max_loc_old = cv2.minMaxLoc(result_old)

    print(f"\nOLD template match score: {max_val_old:.4f} ({max_val_old*100:.2f}%)")

    print("\n" + "="*60)
    print("COMPARISON:")
    print("="*60)
    print(f"OLD template (world_button_template.png): {max_val_old*100:.2f}%")
    print(f"NEW template (extracted from current screenshot): {max_val*100:.2f}%")
    print(f"Improvement: +{(max_val - max_val_old)*100:.2f} percentage points")

if __name__ == "__main__":
    main()
