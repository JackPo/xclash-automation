"""
Collect training data for castle level and name recognition.
Navigates randomly and collects 300+ samples.

OPTIMAL ZOOM: Viewport area = 56 pixels (this is the area of the yellow rectangle in minimap)
"""

import cv2
import numpy as np
import time
import uuid
from pathlib import Path
from find_player import ADBController, Config
from minimap_navigator import MinimapNavigator
import random

def detect_castles(frame):
    """Detect all castles in the frame using template matching."""
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Load templates
    template_dir = Path('templates/castles')
    templates = []
    for template_path in sorted(template_dir.glob('optimal_zoom_white_*.png')):
        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if template is not None:
            templates.append((template_path.stem, template))

    # Match with threshold 0.965
    threshold = 0.965
    all_matches = []

    for name, template in templates:
        result = cv2.matchTemplate(frame_gray, template, cv2.TM_CCORR_NORMED)
        locations = np.where(result >= threshold)

        for pt in zip(*locations[::-1]):
            score = result[pt[1], pt[0]]
            center_x = pt[0] + template.shape[1] // 2
            center_y = pt[1] + template.shape[0] // 2
            all_matches.append((center_x, center_y, score, name))

    # Deduplicate
    MIN_DISTANCE = 40
    all_matches.sort(key=lambda m: m[2], reverse=True)
    kept = []
    for match in all_matches:
        cx, cy, score, name = match
        is_duplicate = False
        for ex, ey, _, _ in kept:
            distance = np.sqrt((cx - ex)**2 + (cy - ey)**2)
            if distance < MIN_DISTANCE:
                is_duplicate = True
                break
        if not is_duplicate:
            kept.append(match)

    return kept

def random_walk(adb, num_moves=3):
    """Perform random walk using arrow keys."""
    import win32api
    import win32gui

    # Bring BlueStacks to foreground
    hwnd = win32gui.FindWindow(None, "BlueStacks App Player")
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.2)

    # Arrow key codes
    keys = [0x25, 0x26, 0x27, 0x28]  # LEFT, UP, RIGHT, DOWN
    KEYEVENT_KEYUP = 0x0002

    for _ in range(num_moves):
        key = random.choice(keys)
        # Press and release
        win32api.keybd_event(key, 0, 0, 0)
        time.sleep(0.05)
        win32api.keybd_event(key, 0, KEYEVENT_KEYUP, 0)
        time.sleep(0.3)

def main():
    from view_detection import detect_current_view, switch_to_view, ViewState

    config = Config()
    adb = ADBController(config)
    nav = MinimapNavigator()

    # Create output directories
    levels_dir = Path('training_data/levels_raw')
    names_dir = Path('training_data/names_raw')
    levels_dir.mkdir(parents=True, exist_ok=True)
    names_dir.mkdir(parents=True, exist_ok=True)

    print("Starting data collection...")
    print("=" * 50)

    # Step 1: Ensure we're in WORLD view
    print("\n1. Checking current view...")
    current_view = detect_current_view(adb)
    print(f"   Current view: {current_view}")

    if current_view != ViewState.WORLD:
        print("   Switching to WORLD view...")
        switch_to_view(adb, ViewState.WORLD)
        time.sleep(1)
        current_view = detect_current_view(adb)
        print(f"   Now in: {current_view}")

    if current_view != ViewState.WORLD:
        print("   ERROR: Failed to switch to WORLD view!")
        return

    # Step 2: Navigate to optimal zoom (viewport area = 56 pixels)
    print("\n2. Navigating to optimal zoom (viewport area = 56 pixels)...")
    from view_detection import ViewDetector

    view_detector = ViewDetector()
    target_area = 56  # pixels - this is the AREA of the viewport rectangle in minimap

    # Detect current zoom by measuring viewport area
    adb.screenshot('temp_zoom_detect.png')
    frame = cv2.imread('temp_zoom_detect.png')
    minimap_viewport = view_detector._detect_minimap_viewport(frame)

    if minimap_viewport is None:
        print("   ERROR: Could not detect minimap viewport!")
        return

    current_area = minimap_viewport.area
    print(f"   Current viewport area: {current_area} pixels")
    print(f"   Target viewport area: {target_area} pixels")

    # Smaller viewport area = more zoomed IN
    # Larger viewport area = more zoomed OUT
    # So if current < target, we need to zoom OUT
    tolerance = 10  # pixels
    if abs(current_area - target_area) <= tolerance:
        print(f"   Already at optimal zoom!")
    elif current_area < target_area:
        # Need to zoom OUT (make viewport larger)
        print(f"   Zooming OUT to increase viewport area...")
        import subprocess
        while current_area < target_area - tolerance:
            subprocess.run([r'C:\Users\mail\AppData\Local\Programs\Python\Python312\python.exe', 'send_zoom.py', 'out'])
            time.sleep(0.5)
            # Re-check viewport area
            adb.screenshot('temp_zoom_check.png')
            frame = cv2.imread('temp_zoom_check.png')
            minimap_viewport = view_detector._detect_minimap_viewport(frame)
            if minimap_viewport is None:
                print("   ERROR: Lost minimap viewport!")
                break
            current_area = minimap_viewport.area
            print(f"   Current area: {current_area} pixels")
    else:
        # Need to zoom IN (make viewport smaller)
        print(f"   Zooming IN to decrease viewport area...")
        import subprocess
        while current_area > target_area + tolerance:
            subprocess.run([r'C:\Users\mail\AppData\Local\Programs\Python\Python312\python.exe', 'send_zoom.py', 'in'])
            time.sleep(0.5)
            # Re-check viewport area
            adb.screenshot('temp_zoom_check.png')
            frame = cv2.imread('temp_zoom_check.png')
            minimap_viewport = view_detector._detect_minimap_viewport(frame)
            if minimap_viewport is None:
                print("   ERROR: Lost minimap viewport!")
                break
            current_area = minimap_viewport.area
            print(f"   Current area: {current_area} pixels")

    # Verify final zoom level
    time.sleep(1)
    adb.screenshot('temp_zoom_verify.png')
    frame = cv2.imread('temp_zoom_verify.png')
    minimap_viewport = view_detector._detect_minimap_viewport(frame)
    if minimap_viewport:
        final_area = minimap_viewport.area
        print(f"   Final viewport area: {final_area} pixels")
        if abs(final_area - target_area) <= tolerance:
            print(f"   ✓ Successfully reached target zoom!")
        else:
            print(f"   WARNING: Not quite at target (off by {abs(final_area - target_area)} pixels)")

    print("\nTarget: 300+ samples")
    print("=" * 50)

    total_samples = 0
    iteration = 0

    while total_samples < 300:
        iteration += 1
        print(f"\nIteration {iteration}:")

        # Take screenshot
        adb.screenshot('temp_collection.png')
        frame = cv2.imread('temp_collection.png')

        # Detect castles
        castles = detect_castles(frame)
        print(f"  Detected {len(castles)} castles")

        # Extract ROIs for each castle
        timestamp = int(time.time() * 1000)
        for i, (cx, cy, score, template_name) in enumerate(castles):
            unique_id = str(uuid.uuid4())[:8]

            # Extract level ROI (30x50 pixels)
            level_roi = frame[cy+45:cy+75, cx-25:cx+25]
            if level_roi.shape[0] == 30 and level_roi.shape[1] == 50:
                level_filename = f"level_raw_{timestamp}_{unique_id}.png"
                cv2.imwrite(str(levels_dir / level_filename), level_roi)

            # Extract name ROI (20x80 pixels, approximate location)
            name_roi = frame[cy+75:cy+95, cx-40:cx+40]
            if name_roi.shape[0] == 20 and name_roi.shape[1] == 80:
                name_filename = f"name_raw_{timestamp}_{unique_id}.png"
                cv2.imwrite(str(names_dir / name_filename), name_roi)

        total_samples += len(castles)
        print(f"  Total samples collected: {total_samples}/300")

        if total_samples >= 300:
            break

        # Random walk
        num_moves = random.randint(3, 5)
        print(f"  Performing random walk ({num_moves} moves)...")
        random_walk(adb, num_moves)

        # Wait for map to settle
        time.sleep(0.5)

    print("\n" + "=" * 50)
    print(f"Data collection complete!")
    print(f"Total samples: {total_samples}")
    print(f"Level ROIs: {len(list(levels_dir.glob('*.png')))}")
    print(f"Name ROIs: {len(list(names_dir.glob('*.png')))}")
    print("\nNext step: Run label_training_data.py to label samples with image agent")

if __name__ == "__main__":
    main()
