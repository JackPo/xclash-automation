"""
Zoom to target castle size from calibration
Target: 3364px² (from step 25 calibration)
"""
import cv2
import numpy as np
import subprocess
import time
import win32gui
import win32con
import win32api

TARGET_CASTLE_SIZE = 3364  # px² from calibration
TOLERANCE = 200  # Allow ±200px² variance

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

def send_zoom_command(direction):
    """Send single zoom command"""
    hwnd = find_bluestacks_window()
    if not hwnd:
        return False

    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)
    except Exception:
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

def get_castle_size():
    """Get average castle size from current view"""
    adb = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"

    # Capture screenshot
    subprocess.run([adb, '-s', 'emulator-5554', 'shell', 'screencap', '-p', '/sdcard/temp.png'],
                   capture_output=True)
    subprocess.run([adb, '-s', 'emulator-5554', 'pull', '/sdcard/temp.png', 'temp_size_check.png'],
                   capture_output=True)

    # Detect castles
    img = cv2.imread('temp_size_check.png')
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

    castle_sizes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)

        if (35 < w < 70 and 35 < h < 70 and
            0.7 < w/h < 1.4 and area > 500 and
            100 < x < width-100 and 100 < y < height-100):
            castle_sizes.append(w * h)

    if not castle_sizes:
        return 0, 0

    avg_size = sum(castle_sizes) / len(castle_sizes)
    return avg_size, len(castle_sizes)

def zoom_to_target_size():
    """Zoom until castle size matches target"""
    print("="*60)
    print(f"ZOOMING TO TARGET CASTLE SIZE: {TARGET_CASTLE_SIZE}px²")
    print("="*60)

    # Step 1: Zoom all the way OUT
    print("\nZooming all the way OUT (50 steps)...")
    for i in range(50):
        send_zoom_command('out')
        if (i+1) % 10 == 0:
            print(f"  {i+1}/50")

    time.sleep(1)

    # Step 2: Zoom IN until we hit target size
    print(f"\nZooming IN until castle size = {TARGET_CASTLE_SIZE}px²...")

    for step in range(100):
        avg_size, count = get_castle_size()

        if count == 0:
            print(f"  Step {step}: No castles detected (too zoomed out)")
        else:
            diff = avg_size - TARGET_CASTLE_SIZE
            print(f"  Step {step}: {avg_size:.0f}px² ({count} castles) | Diff: {diff:+.0f}px²")

            # Check if we're within tolerance
            if abs(diff) <= TOLERANCE:
                print(f"\n✓ TARGET REACHED!")
                print(f"  Castle size: {avg_size:.0f}px² (target: {TARGET_CASTLE_SIZE}px²)")
                print(f"  Castles visible: {count}")
                print(f"  Steps taken: {step}")
                return True

        # Zoom in one more step
        send_zoom_command('in')

    print("\n✗ Reached max steps without hitting target")
    return False

if __name__ == "__main__":
    print("Make sure you're on the WORLD MAP view!")
    print("Starting in 3 seconds...")
    time.sleep(3)

    zoom_to_target_size()
