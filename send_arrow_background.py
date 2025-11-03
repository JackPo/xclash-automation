import win32gui
import win32con
import win32api
import time
import sys

def find_bluestacks_window():
    """Find BlueStacks window"""
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "BlueStacks" in title:
                windows.append((hwnd, title))

    windows = []
    win32gui.EnumWindows(callback, windows)

    if windows:
        print(f"Found: {windows[0][1]}")
        return windows[0][0]
    return None

def send_arrow_background(direction):
    """Send arrow key to BlueStacks WITHOUT focusing window"""
    hwnd = find_bluestacks_window()
    if not hwnd:
        print("BlueStacks window not found!")
        return

    # Map direction to virtual key code
    keys = {
        'up': win32con.VK_UP,
        'down': win32con.VK_DOWN,
        'left': win32con.VK_LEFT,
        'right': win32con.VK_RIGHT
    }

    if direction not in keys:
        print(f"Unknown direction: {direction}")
        return

    vk = keys[direction]

    # Get scan code for the key
    scan_code = win32api.MapVirtualKey(vk, 0)

    # Construct lparam (scan code, repeat count, etc.)
    # Bit 0-15: repeat count (1)
    # Bit 16-23: scan code
    # Bit 24: extended key flag (1 for arrow keys)
    # Bit 29: context code (0)
    # Bit 30: previous key state (0)
    # Bit 31: transition state (0 for down, 1 for up)
    lparam_down = 1 | (scan_code << 16) | (1 << 24)  # Extended key flag for arrows
    lparam_up = 1 | (scan_code << 16) | (1 << 24) | (1 << 30) | (1 << 31)

    print(f"Sending {direction} arrow (background)...")

    # Try SendMessage instead of PostMessage for synchronous delivery
    win32api.SendMessage(hwnd, win32con.WM_KEYDOWN, vk, lparam_down)
    time.sleep(0.05)
    win32api.SendMessage(hwnd, win32con.WM_KEYUP, vk, lparam_up)

    print("Done!")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python send_arrow_background.py <up|down|left|right>")
        sys.exit(1)

    send_arrow_background(sys.argv[1].lower())
