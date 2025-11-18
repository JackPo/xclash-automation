import win32gui
import win32con
import win32api
import time
import sys

def find_bluestacks_window():
    """Find main BlueStacks window"""
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "BlueStacks" in title:
                windows.append((hwnd, title))

    windows = []
    win32gui.EnumWindows(callback, windows)

    if windows:
        return windows[0][0]
    return None

def send_zoom(direction):
    """Send zoom command to BlueStacks

    Args:
        direction: 'in' for Shift+A (zoom in), 'out' for Shift+Z (zoom out)
    """
    hwnd = find_bluestacks_window()
    if not hwnd:
        print("BlueStacks window not found!")
        return

    # Map direction to key
    keys = {
        'in': ord('A'),   # Shift+A = zoom in
        'out': ord('Z')   # Shift+Z = zoom out
    }

    if direction not in keys:
        print(f"Unknown direction: {direction}")
        print("Use 'in' for zoom in (Shift+A) or 'out' for zoom out (Shift+Z)")
        return

    vk = keys[direction]

    # Bring window to foreground
    print(f"Bringing BlueStacks to foreground...")
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    time.sleep(0.1)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except:
        # Windows may block foreground switch, but that's OK
        pass
    time.sleep(0.2)

    # Send Shift+A or Shift+Z
    print(f"Sending Shift+{chr(vk)} (zoom {direction})...")

    # Press Shift
    win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
    time.sleep(0.05)

    # Press A or Z
    win32api.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)

    # Release A or Z
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.05)

    # Release Shift
    win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)

    print("Done!")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python send_zoom.py <in|out>")
        print("  in  = Shift+A (zoom in)")
        print("  out = Shift+Z (zoom out)")
        sys.exit(1)

    send_zoom(sys.argv[1].lower())
