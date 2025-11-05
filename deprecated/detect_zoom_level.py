"""
Detect current zoom level by measuring castle sizes
Compares current screenshot castle sizes to known reference sizes
"""
import cv2
import numpy as np
import subprocess
from pathlib import Path

def capture_screenshot(output_path='current_zoom_check.png'):
    """Capture screenshot from BlueStacks via ADB"""
    adb = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"

    # Capture and pull screenshot
    subprocess.run([adb, '-s', 'emulator-5554', 'shell', 'screencap', '-p', '/sdcard/temp_zoom.png'],
                   capture_output=True)
    subprocess.run([adb, '-s', 'emulator-5554', 'pull', '/sdcard/temp_zoom.png', output_path],
                   capture_output=True)

    return output_path

def detect_castles_simple(image_path):
    """
    Detect castle icons and return their sizes

    Returns: list of (x, y, width, height) for each castle
    """
    img = cv2.imread(image_path)
    if img is None:
        return []

    height, width = img.shape[:2]

    # Convert to HSV for color detection
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Define range for white/gray castles
    lower_gray = np.array([0, 0, 180])
    upper_gray = np.array([180, 40, 255])

    # Create mask
    mask = cv2.inRange(hsv, lower_gray, upper_gray)

    # Clean up mask
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    castles = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)

        # Filter by size and aspect ratio (same as detect_castles_and_numbers.py)
        if (35 < w < 70 and 35 < h < 70 and
            0.7 < w/h < 1.4 and area > 500 and
            100 < x < width-100 and 100 < y < height-100):
            castles.append((x, y, w, h))

    return castles

def get_average_castle_size(castles):
    """Calculate average castle size from detected castles"""
    if not castles:
        return 0

    sizes = [w * h for x, y, w, h in castles]
    return sum(sizes) / len(sizes)

def detect_zoom_level():
    """
    Detect current zoom level by comparing castle sizes

    Returns: tuple (zoom_level_name, castle_count, avg_size)
    """
    # Capture current screenshot
    print("Capturing screenshot...")
    screenshot = capture_screenshot()

    # Detect castles
    print("Detecting castles...")
    castles = detect_castles_simple(screenshot)
    castle_count = len(castles)
    avg_size = get_average_castle_size(castles)

    print(f"Found {castle_count} castles")
    print(f"Average castle size: {avg_size:.0f} pixels²")

    # Reference sizes from investigation.md analysis
    # zoom_out_10 was found to be optimal (10 castles detected)
    # These are approximate - we'd need to measure actual reference images
    zoom_levels = {
        'initial': (8, 2000),      # ~8 castles, large size
        'zoom_out_10': (10, 1800), # optimal level
        'zoom_out_20': (6, 1600),
        'zoom_out_30': (3, 1400),
    }

    # Find closest match based on castle count (primary) and size (secondary)
    best_match = None
    best_diff = float('inf')

    for level_name, (ref_count, ref_size) in zoom_levels.items():
        # Weight count more heavily than size
        count_diff = abs(castle_count - ref_count) * 100
        size_diff = abs(avg_size - ref_size) / 10 if avg_size > 0 else 1000
        total_diff = count_diff + size_diff

        if total_diff < best_diff:
            best_diff = total_diff
            best_match = level_name

    return best_match, castle_count, avg_size

if __name__ == "__main__":
    level, count, size = detect_zoom_level()
    print(f"\n{'='*50}")
    print(f"Detected zoom level: {level}")
    print(f"Castle count: {count}")
    print(f"Avg castle size: {size:.0f}px²")
    print(f"{'='*50}")
