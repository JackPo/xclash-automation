from __future__ import annotations

import win32gui
import win32con
import win32api
import time
import sys


def find_bluestacks_window() -> int | None:
    """Find BlueStacks window"""
    windows: list[tuple[int, str]] = []

    def callback(hwnd: int, windows: list[tuple[int, str]]) -> None:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "BlueStacks" in title:
                windows.append((hwnd, title))

    win32gui.EnumWindows(callback, windows)

    if windows:
        print(f"Found: {windows[0][1]}")
        return windows[0][0]
    return None


def send_arrow(direction: str) -> None:
    """Send arrow key to BlueStacks by focusing window and using keybd_event"""
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

    # Bring window to foreground
    print(f"Bringing window to foreground...")
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.3)  # Wait for window to be focused

    # Send key using keybd_event (simulates physical keyboard press)
    print(f"Sending {direction} arrow...")
    win32api.keybd_event(vk, 0, 0, 0)  # Key down
    time.sleep(0.05)
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)  # Key up

    print("Done!")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python send_arrow_proper.py <up|down|left|right>")
        sys.exit(1)

    send_arrow(sys.argv[1].lower())
