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

def send_arrow_with_wmchar(direction):
    """Try WM_CHAR instead of WM_KEYDOWN/WM_KEYUP"""
    hwnd = find_bluestacks_window()
    if not hwnd:
        print("BlueStacks window not found!")
        return

    # Arrow keys don't have char codes, but let's try the VK codes anyway
    # Also try WM_SYSCHAR and WM_SYSKEYDOWN
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
    scan_code = win32api.MapVirtualKey(vk, 0)

    # Try multiple message types
    print(f"Sending {direction} arrow using different message types...")

    # Method 1: WM_SYSKEYDOWN + WM_SYSKEYUP (system keys)
    print("  Trying WM_SYSKEYDOWN/WM_SYSKEYUP...")
    lparam_down = 1 | (scan_code << 16) | (1 << 24) | (1 << 29)  # bit 29 = context code
    lparam_up = 1 | (scan_code << 16) | (1 << 24) | (1 << 29) | (1 << 30) | (1 << 31)
    win32api.SendMessage(hwnd, win32con.WM_SYSKEYDOWN, vk, lparam_down)
    time.sleep(0.05)
    win32api.SendMessage(hwnd, win32con.WM_SYSKEYUP, vk, lparam_up)

    time.sleep(0.2)

    # Method 2: Try all child windows with regular WM_KEYDOWN
    print("  Trying to send to ALL windows (parent + children)...")
    def send_to_window(target_hwnd):
        lparam_down = 1 | (scan_code << 16) | (1 << 24)
        lparam_up = 1 | (scan_code << 16) | (1 << 24) | (1 << 30) | (1 << 31)
        win32api.SendMessage(target_hwnd, win32con.WM_KEYDOWN, vk, lparam_down)
        time.sleep(0.01)
        win32api.SendMessage(target_hwnd, win32con.WM_KEYUP, vk, lparam_up)

    # Send to main window
    send_to_window(hwnd)

    # Send to all children
    def enum_callback(child_hwnd, param):
        send_to_window(child_hwnd)

    win32gui.EnumChildWindows(hwnd, enum_callback, None)

    print("Done!")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python send_arrow_wmchar.py <up|down|left|right>")
        sys.exit(1)

    send_arrow_with_wmchar(sys.argv[1].lower())
