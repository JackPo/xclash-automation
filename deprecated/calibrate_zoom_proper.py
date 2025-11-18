"""
Properly calibrate zoom levels using keyboard controls
Takes screenshots at each zoom level and measures castle detection accuracy
"""
import cv2
import numpy as np
import subprocess
import time
import win32gui
import win32con
import win32api
from pathlib import Path

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
    """Send zoom command (in or out)"""
    hwnd = find_bluestacks_window()
    if not hwnd:
        return False

    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
    except Exception as e:
        # SetForegroundWindow can fail if Windows rate-limits focus changes
        # Just continue anyway - keys might still work
        time.sleep(0.3)

    key = ord('A') if direction == 'in' else ord('Z')

    win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(key, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.05)
    win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)

    time.sleep(0.5)  # Wait for zoom animation
    return True

def capture_screenshot(output_path):
    """Capture screenshot via ADB"""
    adb = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
    subprocess.run([adb, '-s', 'emulator-5554', 'shell', 'screencap', '-p', '/sdcard/temp.png'],
                   capture_output=True)
    subprocess.run([adb, '-s', 'emulator-5554', 'pull', '/sdcard/temp.png', output_path],
                   capture_output=True)

def detect_castles(image_path):
    """Detect castles and return count + average size"""
    img = cv2.imread(image_path)
    if img is None:
        return 0, 0

    height, width = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Castle color range
    lower_gray = np.array([0, 0, 180])
    upper_gray = np.array([180, 40, 255])
    mask = cv2.inRange(hsv, lower_gray, upper_gray)

    # Clean up
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    castles = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)

        # Filter
        if (35 < w < 70 and 35 < h < 70 and
            0.7 < w/h < 1.4 and area > 500 and
            100 < x < width-100 and 100 < y < height-100):
            castles.append((x, y, w, h))

    if not castles:
        return 0, 0

    avg_size = sum(w*h for x,y,w,h in castles) / len(castles)
    return len(castles), avg_size

def calibrate_zoom():
    """Test zoom levels and find optimal"""
    Path('zoom_calibration').mkdir(exist_ok=True)

    print("="*60)
    print("ZOOM CALIBRATION - Starting from current zoom level")
    print("="*60)

    results = []

    # First, zoom all the way OUT to establish baseline
    print("\nStep 1: Zooming all the way OUT...")
    for i in range(100):  # Zoom out 100 times (many fail, so do lots)
        send_zoom_command('out')
        if (i+1) % 10 == 0:
            print(f"  Zoom out {i+1}/100")

    time.sleep(1)

    # Now test zoom levels by zooming IN step by step
    print("\nStep 2: Testing zoom levels from MIN to MAX zoom...")

    for step in range(100):  # Test 100 zoom steps (lots fail)
        print(f"\nZoom level: {step}")

        # Capture screenshot
        screenshot_path = f'zoom_calibration/zoom_{step:03d}.png'
        capture_screenshot(screenshot_path)

        # Detect castles
        castle_count, avg_size = detect_castles(screenshot_path)

        print(f"  Castles: {castle_count}, Avg size: {avg_size:.0f}px²")

        results.append({
            'step': step,
            'count': castle_count,
            'size': avg_size,
            'path': screenshot_path
        })

        # Zoom in one step for next iteration
        if step < 99:
            send_zoom_command('in')

    # Analyze results
    print("\n" + "="*60)
    print("CALIBRATION RESULTS")
    print("="*60)

    # Find optimal zoom (most castles detected)
    best = max(results, key=lambda x: x['count'])

    print(f"\nBest zoom level: Step {best['step']}")
    print(f"  Castles detected: {best['count']}")
    print(f"  Average size: {best['size']:.0f}px²")

    # Show top 5
    print("\nTop 5 zoom levels:")
    sorted_results = sorted(results, key=lambda x: x['count'], reverse=True)
    for i, r in enumerate(sorted_results[:5], 1):
        print(f"  {i}. Step {r['step']:2d}: {r['count']:2d} castles, {r['size']:4.0f}px²")

    # Save results to CSV
    import csv
    with open('zoom_calibration/results.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['step', 'count', 'size', 'path'])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSaved results to zoom_calibration/results.csv")
    print(f"Saved screenshots to zoom_calibration/")

    return best

if __name__ == "__main__":
    print("Make sure you're on the WORLD MAP view!")
    print("Starting calibration in 3 seconds...")
    time.sleep(3)

    best = calibrate_zoom()
