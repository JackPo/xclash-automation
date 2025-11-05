"""Test how well the templates match the actual screenshot using raw CV2"""
import cv2
import numpy as np
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
    print(f"Screenshot size: {screenshot.shape[1]}x{screenshot.shape[0]}")

    # Load both templates
    world_template = cv2.imread("templates/buttons/world_button_template.png")
    town_template = cv2.imread("templates/buttons/town_button_template.png")

    print(f"\nWorld template size: {world_template.shape[1]}x{world_template.shape[0]}")
    print(f"Town template size: {town_template.shape[1]}x{town_template.shape[0]}")

    # Try matching both templates
    print("\n" + "="*60)
    print("RAW CV2 TEMPLATE MATCHING:")
    print("="*60)

    # Match WORLD template
    result_world = cv2.matchTemplate(screenshot, world_template, cv2.TM_CCOEFF_NORMED)
    min_val_w, max_val_w, min_loc_w, max_loc_w = cv2.minMaxLoc(result_world)

    print(f"\nWORLD template:")
    print(f"  Best match score: {max_val_w:.4f} ({max_val_w*100:.2f}%)")
    print(f"  Location: {max_loc_w}")

    # Match TOWN template
    result_town = cv2.matchTemplate(screenshot, town_template, cv2.TM_CCOEFF_NORMED)
    min_val_t, max_val_t, min_loc_t, max_loc_t = cv2.minMaxLoc(result_town)

    print(f"\nTOWN template:")
    print(f"  Best match score: {max_val_t:.4f} ({max_val_t*100:.2f}%)")
    print(f"  Location: {max_loc_t}")

    # Draw matches on screenshot
    vis = screenshot.copy()

    # Draw WORLD match
    h_w, w_w = world_template.shape[:2]
    top_left_w = max_loc_w
    bottom_right_w = (top_left_w[0] + w_w, top_left_w[1] + h_w)
    cv2.rectangle(vis, top_left_w, bottom_right_w, (0, 0, 255), 3)  # Red for WORLD
    cv2.putText(vis, f"WORLD: {max_val_w:.4f}", (top_left_w[0], top_left_w[1]-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # Draw TOWN match
    h_t, w_t = town_template.shape[:2]
    top_left_t = max_loc_t
    bottom_right_t = (top_left_t[0] + w_t, top_left_t[1] + h_t)
    cv2.rectangle(vis, top_left_t, bottom_right_t, (255, 0, 0), 3)  # Blue for TOWN
    cv2.putText(vis, f"TOWN: {max_val_t:.4f}", (top_left_t[0], top_left_t[1]-40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

    cv2.imwrite("template_match_comparison.png", vis)
    print(f"\nVisualization saved to: template_match_comparison.png")

    # Also save the cropped button area
    padding = 100
    x = 2160 - padding
    y = 1190 - padding
    x2 = 2560 + padding
    y2 = 1440 + padding
    cropped = vis[max(0,y):min(screenshot.shape[0],y2), max(0,x):min(screenshot.shape[1],x2)]
    cv2.imwrite("template_match_cropped.png", cropped)
    print(f"Cropped view saved to: template_match_cropped.png")

    print("\n" + "="*60)
    print("ANALYSIS:")
    print("="*60)

    if max_val_w >= 0.95:
        print(f"WORLD template: EXCELLENT match ({max_val_w*100:.2f}%)")
    elif max_val_w >= 0.85:
        print(f"WORLD template: GOOD match ({max_val_w*100:.2f}%)")
    elif max_val_w >= 0.70:
        print(f"WORLD template: FAIR match ({max_val_w*100:.2f}%)")
    else:
        print(f"WORLD template: POOR match ({max_val_w*100:.2f}%)")

    if max_val_t >= 0.95:
        print(f"TOWN template: EXCELLENT match ({max_val_t*100:.2f}%)")
    elif max_val_t >= 0.85:
        print(f"TOWN template: GOOD match ({max_val_t*100:.2f}%)")
    elif max_val_t >= 0.70:
        print(f"TOWN template: FAIR match ({max_val_t*100:.2f}%)")
    else:
        print(f"TOWN template: POOR match ({max_val_t*100:.2f}%)")

    print("\nExpected: WORLD should be ~95-100% match since button never changes")
    print(f"Actual: WORLD is {max_val_w*100:.2f}%")

    if max_val_w < 0.90:
        print("\n*** PROBLEM DETECTED! ***")
        print("World template is NOT matching well!")
        print("This means:")
        print("1. The template might be from a different resolution/zoom")
        print("2. The button appearance might have changed")
        print("3. The template might be cropped incorrectly")

if __name__ == "__main__":
    main()
