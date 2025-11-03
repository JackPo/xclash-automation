"""
Smart zoom setup using Town/World reset trick
1. Ensure we can detect World/Town button (zoom in if needed)
2. Switch to Town (resets zoom to default)
3. Switch back to World (now at known baseline)
4. Zoom out 5 times from baseline
5. Fine-tune to exact target castle size (3364px²)
"""
import cv2
import numpy as np
import subprocess
import time
import win32gui
import win32con
import win32api
from PIL import Image
import pytesseract

# Configuration
ADB = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
DEVICE = "emulator-5554"
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# UI coordinates (from game_utils.py)
WORLD_TOGGLE_X = 2350  # Right side
WORLD_TOGGLE_Y = 1350  # Bottom

# Target castle size from calibration
TARGET_SIZE = 3364  # px²
TOLERANCE = 200  # ±200px²

def find_bluestacks_window():
    """Find main BlueStacks window"""
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "BlueStacks" in title:
                windows.append((hwnd, title))
    windows = []
    win32gui.EnumWindows(callback, windows)
    return windows[0][0] if windows else None

def send_zoom(direction, count=1):
    """Send zoom command via keyboard"""
    hwnd = find_bluestacks_window()
    if not hwnd:
        return False

    for _ in range(count):
        try:
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.2)
        except:
            time.sleep(0.2)

        key = ord('A') if direction == 'in' else ord('Z')
        win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
        time.sleep(0.05)
        win32api.keybd_event(key, 0, 0, 0)
        time.sleep(0.05)
        win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.05)
        win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.3)
    return True

def adb_click(x, y):
    """Click at coordinates via ADB"""
    subprocess.run([ADB, '-s', DEVICE, 'shell', 'input', 'tap', str(x), str(y)],
                   capture_output=True)

def capture_screenshot():
    """Capture screenshot via ADB"""
    subprocess.run([ADB, '-s', DEVICE, 'shell', 'screencap', '-p', '/sdcard/temp.png'],
                   capture_output=True)
    subprocess.run([ADB, '-s', DEVICE, 'pull', '/sdcard/temp.png', 'temp_zoom_setup.png'],
                   capture_output=True)
    return 'temp_zoom_setup.png'

def detect_world_town_button():
    """Detect if World/Town button is visible via OCR"""
    screenshot = capture_screenshot()
    img = Image.open(screenshot)

    # Crop lower-right corner
    width, height = img.size
    crop_box = (width - 400, height - 250, width, height)
    corner = img.crop(crop_box)

    # OCR
    text = pytesseract.image_to_string(corner).upper()

    is_world = "WORLD" in text
    is_town = "TOWN" in text

    return is_world or is_town, text

def get_castle_size():
    """Get average castle size from current screenshot"""
    screenshot = capture_screenshot()
    img = cv2.imread(screenshot)
    if img is None:
        return 0, 0

    height, width = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    lower_gray = np.array([0, 0, 180])
    upper_gray = np.array([180, 40, 255])
    mask = cv2.inRange(hsv, lower_gray, upper_gray)

    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    sizes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)

        if (35 < w < 70 and 35 < h < 70 and
            0.7 < w/h < 1.4 and area > 500 and
            100 < x < width-100 and 100 < y < height-100):
            sizes.append(w * h)

    if not sizes:
        return 0, 0

    avg_size = sum(sizes) / len(sizes)
    return avg_size, len(sizes)

def setup_optimal_zoom():
    """Main function to setup optimal zoom"""
    print("="*60)
    print("SMART ZOOM SETUP")
    print("="*60)

    # Step 1: Ensure World/Town button is visible
    print("\n[1/5] Detecting World/Town button...")
    detected, text = detect_world_town_button()

    if not detected:
        print("  Button not visible. Zooming in to make UI bigger...")
        send_zoom('in', count=3)
        time.sleep(1)
        detected, text = detect_world_town_button()

        if not detected:
            print(f"\nERROR: Cannot detect World/Town button!")
            print(f"  OCR text found: '{text}'")
            print("  Make sure you're on the WORLD MAP view")
            return False

    # Step 2: Switch to Town (resets zoom)
    print("\n[2/5] Switching to Town view (zoom reset)...")
    adb_click(WORLD_TOGGLE_X, WORLD_TOGGLE_Y)
    time.sleep(2)  # Wait for view change

    # Step 3: Switch back to World (now at baseline zoom)
    print("\n[3/5] Switching back to World view (baseline zoom)...")
    adb_click(WORLD_TOGGLE_X, WORLD_TOGGLE_Y)
    time.sleep(2)

    # Step 4: Zoom out 3 times from baseline (was 5, too far)
    print("\n[4/5] Zooming out 3 times from baseline...")
    send_zoom('out', count=3)
    time.sleep(1)

    # Step 5: Fine-tune to target size
    print(f"\n[5/5] Fine-tuning to target size ({TARGET_SIZE}px²)...")

    for iteration in range(20):  # Increased from 10 to 20
        avg_size, count = get_castle_size()

        if count == 0:
            print(f"  Iteration {iteration+1}: No castles detected, zooming out...")
            send_zoom('out', count=1)
            continue

        diff = avg_size - TARGET_SIZE
        print(f"  Iteration {iteration+1}: {avg_size:.0f}px² ({count} castles) | Diff: {diff:+.0f}px²")

        # Check if within tolerance
        if abs(diff) <= TOLERANCE:
            print(f"\nOPTIMAL ZOOM REACHED!")
            print(f"  Castle size: {avg_size:.0f}px² (target: {TARGET_SIZE}px²)")
            print(f"  Castles visible: {count}")
            print(f"  Iterations: {iteration+1}")
            return True

        # Adjust zoom
        if diff < 0:  # Castles too small, need to zoom IN (get closer)
            send_zoom('in', count=1)
        else:  # Castles too big, need to zoom OUT (get farther)
            send_zoom('out', count=1)

    print("\nWARNING: Reached max iterations")
    avg_size, count = get_castle_size()
    print(f"Final: {avg_size:.0f}px² ({count} castles)")
    return False

if __name__ == "__main__":
    print("Make sure BlueStacks is visible!")
    print("Starting in 3 seconds...")
    time.sleep(3)

    success = setup_optimal_zoom()

    print("\n" + "="*60)
    if success:
        print("SUCCESS: Optimal zoom configured!")
    elif success is False:
        print("FAILED: Could not setup zoom (check error above)")
        exit(1)
    else:
        print("COMPLETED: Close to optimal (max iterations reached)")
    print("="*60)
