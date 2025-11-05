#!/usr/bin/env python3
"""
Test sending keyboard input directly to BlueStacks window
"""

import win32gui
import win32con
import win32api
import time

def find_bluestacks_window():
    """Find BlueStacks window handle"""
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "BlueStacks" in title or "XClash" in title:
                windows.append((hwnd, title))
        return True

    windows = []
    win32gui.EnumWindows(callback, windows)

    if windows:
        print("Found windows:")
        for hwnd, title in windows:
            print(f"  HWND: {hwnd}, Title: {title.encode('utf-8', errors='replace').decode('utf-8')}")
        return windows[0][0]  # Return first matching window
    return None

def send_key_to_window(hwnd, vk_code, with_shift=False):
    """Send a key press to a window

    Args:
        hwnd: Window handle
        vk_code: Virtual key code
        with_shift: Whether to hold Shift key
    """
    # If shift is needed, send shift down first
    if with_shift:
        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_SHIFT, 0)
        time.sleep(0.05)

    # Send key down
    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, 0)
    time.sleep(0.05)

    # Send key up
    win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, 0)
    time.sleep(0.05)

    # If shift was needed, send shift up
    if with_shift:
        win32api.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_SHIFT, 0)
        time.sleep(0.05)

def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_keyboard_input.py find    - Find BlueStacks window")
        print("  python test_keyboard_input.py up      - Send Up Arrow")
        print("  python test_keyboard_input.py down    - Send Down Arrow")
        print("  python test_keyboard_input.py left    - Send Left Arrow")
        print("  python test_keyboard_input.py right   - Send Right Arrow")
        print("  python test_keyboard_input.py in      - Send Shift+A (zoom in)")
        print("  python test_keyboard_input.py out     - Send Shift+Z (zoom out)")
        return

    action = sys.argv[1].lower()

    if action == "find":
        hwnd = find_bluestacks_window()
        if hwnd:
            print(f"\nBlueStacks window found: HWND={hwnd}")
        else:
            print("BlueStacks window not found!")

    elif action == "up":
        hwnd = find_bluestacks_window()
        if not hwnd:
            print("ERROR: BlueStacks window not found!")
            return

        print(f"Sending Up Arrow to HWND {hwnd}...")
        # VK_UP = 0x26
        send_key_to_window(hwnd, 0x26, with_shift=False)
        print("Done!")

    elif action == "down":
        hwnd = find_bluestacks_window()
        if not hwnd:
            print("ERROR: BlueStacks window not found!")
            return

        print(f"Sending Down Arrow to HWND {hwnd}...")
        # VK_DOWN = 0x28
        send_key_to_window(hwnd, 0x28, with_shift=False)
        print("Done!")

    elif action == "left":
        hwnd = find_bluestacks_window()
        if not hwnd:
            print("ERROR: BlueStacks window not found!")
            return

        print(f"Sending Left Arrow to HWND {hwnd}...")
        # VK_LEFT = 0x25
        send_key_to_window(hwnd, 0x25, with_shift=False)
        print("Done!")

    elif action == "right":
        hwnd = find_bluestacks_window()
        if not hwnd:
            print("ERROR: BlueStacks window not found!")
            return

        print(f"Sending Right Arrow to HWND {hwnd}...")
        # VK_RIGHT = 0x27
        send_key_to_window(hwnd, 0x27, with_shift=False)
        print("Done!")

    elif action == "in":
        hwnd = find_bluestacks_window()
        if not hwnd:
            print("ERROR: BlueStacks window not found!")
            return

        print(f"Sending Shift+A to HWND {hwnd}...")
        # A key = 0x41
        send_key_to_window(hwnd, 0x41, with_shift=True)
        print("Done!")

    elif action == "out":
        hwnd = find_bluestacks_window()
        if not hwnd:
            print("ERROR: BlueStacks window not found!")
            return

        print(f"Sending Shift+Z to HWND {hwnd}...")
        # Z key = 0x5A
        send_key_to_window(hwnd, 0x5A, with_shift=True)
        print("Done!")

    else:
        print(f"Unknown action: {action}")

if __name__ == "__main__":
    main()
