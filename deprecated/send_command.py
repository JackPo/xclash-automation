"""
Unified command sender for BlueStacks XClash automation
Sends keyboard commands to BlueStacks (requires window focus)
"""
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
    return windows[0][0] if windows else None

def send_command(command):
    """Send command to BlueStacks

    Args:
        command: 'up', 'down', 'left', 'right', 'zoom_in', 'zoom_out'
    """
    hwnd = find_bluestacks_window()
    if not hwnd:
        print("BlueStacks window not found!")
        return False

    # Bring window to foreground
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.3)

    # Map commands to keys
    if command in ['up', 'down', 'left', 'right']:
        # Arrow keys
        vk_map = {
            'up': win32con.VK_UP,
            'down': win32con.VK_DOWN,
            'left': win32con.VK_LEFT,
            'right': win32con.VK_RIGHT
        }
        vk = vk_map[command]

        win32api.keybd_event(vk, 0, 0, 0)
        time.sleep(0.05)
        win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)

    elif command in ['zoom_in', 'zoom_out']:
        # Shift + A/Z
        key = ord('A') if command == 'zoom_in' else ord('Z')

        win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
        time.sleep(0.05)
        win32api.keybd_event(key, 0, 0, 0)
        time.sleep(0.05)
        win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.05)
        win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
    else:
        print(f"Unknown command: {command}")
        return False

    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python send_command.py <command>")
        print("\nCommands:")
        print("  up, down, left, right  - Pan map")
        print("  zoom_in, zoom_out      - Zoom (Shift+A / Shift+Z)")
        sys.exit(1)

    success = send_command(sys.argv[1].lower())
    if success:
        print(f"Sent: {sys.argv[1]}")
