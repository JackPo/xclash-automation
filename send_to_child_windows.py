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

def find_child_by_class(parent_hwnd, target_class):
    """Find child window by class name"""
    found = []

    def callback(hwnd, param):
        class_name = win32gui.GetClassName(hwnd)
        if class_name == target_class:
            found.append(hwnd)

    win32gui.EnumChildWindows(parent_hwnd, callback, None)
    return found[0] if found else None

def send_arrow_to_child(direction, target_class=None):
    """Send arrow key to child window"""
    parent = find_bluestacks_window()
    if not parent:
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
    scan_code = win32api.MapVirtualKey(vk, 0)

    # Construct lparam for arrow keys (extended key)
    lparam_down = 1 | (scan_code << 16) | (1 << 24)
    lparam_up = 1 | (scan_code << 16) | (1 << 24) | (1 << 30) | (1 << 31)

    # If target_class specified, find that child
    if target_class:
        child_hwnd = find_child_by_class(parent, target_class)
        if not child_hwnd:
            print(f"Child window with class '{target_class}' not found!")
            return
        print(f"Sending {direction} to child class: {target_class} (HWND: {child_hwnd})")
        target_hwnd = child_hwnd
    else:
        # Try all child windows
        print(f"Sending {direction} to all child windows...")
        children = []
        def callback(hwnd, param):
            class_name = win32gui.GetClassName(hwnd)
            children.append((hwnd, class_name))
        win32gui.EnumChildWindows(parent, callback, None)

        for child_hwnd, class_name in children:
            print(f"  Trying: {class_name} (HWND: {child_hwnd})")
            win32api.SendMessage(child_hwnd, win32con.WM_KEYDOWN, vk, lparam_down)
            time.sleep(0.05)
            win32api.SendMessage(child_hwnd, win32con.WM_KEYUP, vk, lparam_up)
        print("Done!")
        return

    # Send to specific target
    win32api.SendMessage(target_hwnd, win32con.WM_KEYDOWN, vk, lparam_down)
    time.sleep(0.05)
    win32api.SendMessage(target_hwnd, win32con.WM_KEYUP, vk, lparam_up)
    print("Done!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python send_to_child_windows.py <direction> [class_name]")
        print("Example: python send_to_child_windows.py right")
        print("         python send_to_child_windows.py right BlueStacksApp")
        sys.exit(1)

    direction = sys.argv[1].lower()
    target_class = sys.argv[2] if len(sys.argv) > 2 else None

    send_arrow_to_child(direction, target_class)
