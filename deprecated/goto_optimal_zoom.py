"""
Navigate to optimal zoom level for castle detection
Based on calibration: 100 zoom outs, then 25 zoom ins = 30 castles visible
"""
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

def send_zoom_command(direction):
    """Send zoom command (in or out)"""
    hwnd = find_bluestacks_window()
    if not hwnd:
        return False

    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
    except Exception:
        time.sleep(0.3)

    key = ord('A') if direction == 'in' else ord('Z')

    win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(key, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.05)
    win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)

    time.sleep(0.5)
    return True

def goto_optimal_zoom():
    """Navigate to optimal zoom level (30 castles visible)"""
    print("="*60)
    print("NAVIGATING TO OPTIMAL ZOOM LEVEL")
    print("="*60)

    # Step 1: Zoom all the way OUT
    print("\nStep 1: Zooming all the way OUT (100 steps)...")
    for i in range(100):
        send_zoom_command('out')
        if (i+1) % 10 == 0:
            print(f"  Zoomed out {i+1}/100")

    time.sleep(1)

    # Step 2: Zoom IN to optimal level (25 steps = 30 castles)
    print("\nStep 2: Zooming IN to optimal level (25 steps)...")
    for i in range(25):
        send_zoom_command('in')
        if (i+1) % 5 == 0:
            print(f"  Zoomed in {i+1}/25")

    print("\n" + "="*60)
    print("REACHED OPTIMAL ZOOM!")
    print("Expected: ~30 castles visible")
    print("="*60)

if __name__ == "__main__":
    print("Make sure you're on the WORLD MAP view!")
    print("Starting in 3 seconds...")
    time.sleep(3)

    goto_optimal_zoom()
