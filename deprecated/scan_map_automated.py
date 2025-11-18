"""
Automated map scanner using zoom + pan controls
Scans the map in a grid pattern and captures castle data
"""
import cv2
import numpy as np
import subprocess
import time
import win32gui
import win32con
import win32api
from pathlib import Path
import csv
from datetime import datetime

# Configuration
ADB = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
DEVICE = "emulator-5554"
GRID_WIDTH = 10  # Scan 10 positions horizontally
GRID_HEIGHT = 10  # Scan 10 positions vertically
PAN_DELAY = 1.0  # Seconds to wait after panning for map to settle

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

def send_arrow(direction):
    """Send arrow key command"""
    hwnd = find_bluestacks_window()
    if not hwnd:
        return False

    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)
    except:
        time.sleep(0.2)

    vk_map = {
        'up': win32con.VK_UP,
        'down': win32con.VK_DOWN,
        'left': win32con.VK_LEFT,
        'right': win32con.VK_RIGHT
    }
    vk = vk_map[direction]

    win32api.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(PAN_DELAY)  # Wait for map to settle

    return True

def capture_screenshot(output_path):
    """Capture screenshot via ADB"""
    subprocess.run([ADB, '-s', DEVICE, 'shell', 'screencap', '-p', '/sdcard/temp.png'],
                   capture_output=True)
    subprocess.run([ADB, '-s', DEVICE, 'pull', '/sdcard/temp.png', output_path],
                   capture_output=True)

def detect_castles(image_path):
    """Detect castles in screenshot and return their info"""
    img = cv2.imread(image_path)
    if img is None:
        return []

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

        # Filter for castle-sized objects
        if (35 < w < 70 and 35 < h < 70 and
            0.7 < w/h < 1.4 and area > 500 and
            100 < x < width-100 and 100 < y < height-100):
            castles.append({
                'x': x,
                'y': y,
                'width': w,
                'height': h,
                'area': w * h
            })

    return castles

def scan_map():
    """Main scanning function"""
    print("="*60)
    print("AUTOMATED MAP SCANNER")
    print("="*60)
    print(f"Grid size: {GRID_WIDTH} x {GRID_HEIGHT}")
    print(f"Total positions: {GRID_WIDTH * GRID_HEIGHT}")
    print()

    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"map_scan_{timestamp}")
    output_dir.mkdir(exist_ok=True)

    # Initialize CSV for castle data
    csv_path = output_dir / "castle_data.csv"
    csv_file = open(csv_path, 'w', newline='')
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(['grid_x', 'grid_y', 'castle_count', 'avg_size',
                         'castle_x', 'castle_y', 'castle_w', 'castle_h', 'castle_area'])

    total_castles = 0
    positions_scanned = 0

    # Scan in snake pattern
    for row in range(GRID_HEIGHT):
        # Determine direction based on row (snake pattern)
        if row % 2 == 0:
            # Even rows: scan left to right
            col_range = range(GRID_WIDTH)
            direction = 'right'
        else:
            # Odd rows: scan right to left
            col_range = range(GRID_WIDTH)
            direction = 'left'

        for col in col_range:
            positions_scanned += 1
            print(f"\n[{positions_scanned}/{GRID_WIDTH * GRID_HEIGHT}] Position ({col}, {row})")

            # Capture screenshot
            screenshot_path = output_dir / f"scan_{row:02d}_{col:02d}.png"
            capture_screenshot(str(screenshot_path))

            # Detect castles
            castles = detect_castles(str(screenshot_path))
            castle_count = len(castles)
            total_castles += castle_count

            if castle_count > 0:
                avg_size = sum(c['area'] for c in castles) / castle_count
                print(f"  Castles: {castle_count}, Avg size: {avg_size:.0f}px²")

                # Write each castle to CSV
                for castle in castles:
                    csv_writer.writerow([
                        col, row, castle_count, avg_size,
                        castle['x'], castle['y'],
                        castle['width'], castle['height'], castle['area']
                    ])
            else:
                print(f"  Castles: 0")

            # Pan to next position (except on last position)
            if col < GRID_WIDTH - 1:
                send_arrow(direction)

        # Move down one row (except on last row)
        if row < GRID_HEIGHT - 1:
            print(f"\n  Moving to next row...")
            send_arrow('down')

    csv_file.close()

    # Summary
    print("\n" + "="*60)
    print("SCAN COMPLETE!")
    print("="*60)
    print(f"Positions scanned: {positions_scanned}")
    print(f"Total castles found: {total_castles}")
    print(f"Average castles per position: {total_castles / positions_scanned:.1f}")
    print(f"\nData saved to: {output_dir}")
    print(f"  Screenshots: {positions_scanned} images")
    print(f"  Castle data: {csv_path}")
    print("="*60)

if __name__ == "__main__":
    print("PREREQUISITES:")
    print("  1. BlueStacks must be visible (not minimized)")
    print("  2. Game should be on WORLD MAP view")
    print("  3. Run setup_optimal_zoom.py first to set correct zoom level")
    print("\nStarting scan in 5 seconds...")
    time.sleep(5)

    scan_map()
