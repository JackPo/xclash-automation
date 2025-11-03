"""
Adaptively find optimal zoom level by detecting castles
Zooms in/out until we maximize castle count
"""
import cv2
import numpy as np
import subprocess
import time
import win32gui
import win32con
import win32api

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

def send_zoom_command(direction, count=1):
    """Send zoom command N times"""
    hwnd = find_bluestacks_window()
    if not hwnd:
        return False

    for _ in range(count):
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

def capture_and_detect():
    """Capture screenshot and detect castle count"""
    adb = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"

    # Capture screenshot
    subprocess.run([adb, '-s', 'emulator-5554', 'shell', 'screencap', '-p', '/sdcard/temp.png'],
                   capture_output=True)
    subprocess.run([adb, '-s', 'emulator-5554', 'pull', '/sdcard/temp.png', 'temp_adaptive.png'],
                   capture_output=True)

    # Detect castles
    img = cv2.imread('temp_adaptive.png')
    if img is None:
        return 0

    height, width = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    lower_gray = np.array([0, 0, 180])
    upper_gray = np.array([180, 40, 255])
    mask = cv2.inRange(hsv, lower_gray, upper_gray)

    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    castle_count = 0
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)

        if (35 < w < 70 and 35 < h < 70 and
            0.7 < w/h < 1.4 and area > 500 and
            100 < x < width-100 and 100 < y < height-100):
            castle_count += 1

    return castle_count

def find_optimal_zoom():
    """Adaptively find optimal zoom level"""
    print("="*60)
    print("ADAPTIVE ZOOM FINDER")
    print("="*60)

    # Step 1: Zoom all the way OUT
    print("\nStep 1: Zooming all the way OUT...")
    send_zoom_command('out', count=100)
    time.sleep(1)

    # Step 2: Zoom IN until we maximize castle count
    print("\nStep 2: Finding optimal zoom...")

    best_count = 0
    same_count_streak = 0
    step = 0

    while step < 100:
        # Detect current state
        castle_count = capture_and_detect()

        print(f"  Step {step}: {castle_count} castles")

        # Check if we're improving
        if castle_count > best_count:
            best_count = castle_count
            same_count_streak = 0
        elif castle_count == best_count and best_count > 0:
            same_count_streak += 1
        else:
            same_count_streak = 0

        # If castle count is dropping significantly, we passed optimal
        if best_count > 20 and castle_count < best_count * 0.7:
            print(f"\n  Castle count dropped from {best_count} to {castle_count}")
            print(f"  Zooming back out 3 steps...")
            send_zoom_command('out', count=3)
            break

        # If count stable for 3 steps, we're at optimal
        if same_count_streak >= 3 and best_count > 20:
            print(f"\n  Stable at {best_count} castles for 3 steps - OPTIMAL!")
            break

        # Zoom in one step
        send_zoom_command('in', count=1)
        step += 1

    print("\n" + "="*60)
    print(f"OPTIMAL ZOOM REACHED!")
    print(f"Maximum castles detected: {best_count}")
    print(f"Total steps: {step}")
    print("="*60)

    return best_count, step

if __name__ == "__main__":
    print("Make sure you're on the WORLD MAP view!")
    print("Starting in 3 seconds...")
    time.sleep(3)

    best_count, steps = find_optimal_zoom()
