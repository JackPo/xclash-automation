#!/usr/bin/env python3
"""
Test sending keyboard input to BlueStacks - trying child windows and SendMessage
"""

import win32gui
import win32con
import win32api
import time

def find_bluestacks_windows():
    """Find all BlueStacks related windows including children"""
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            if "BlueStacks" in title or "XClash" in title or class_name:
                windows.append((hwnd, title, class_name))
        return True

    windows = []
    win32gui.EnumWindows(callback, windows)

    # Also get child windows of BlueStacks main window
    bluestacks_hwnd = None
    for hwnd, title, _ in windows:
        if "BlueStacks App Player" in title:
            bluestacks_hwnd = hwnd
            break

    if bluestacks_hwnd:
        def enum_child_callback(hwnd, windows):
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            windows.append((hwnd, title, class_name))
            return True

        child_windows = []
        win32gui.EnumChildWindows(bluestacks_hwnd, enum_child_callback, child_windows)
        windows.extend(child_windows)

    return windows

def send_key_sendmessage(hwnd, vk_code, with_shift=False):
    """Send key using SendMessage instead of PostMessage"""
    if with_shift:
        win32api.SendMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_SHIFT, 0)
        time.sleep(0.05)

    win32api.SendMessage(hwnd, win32con.WM_KEYDOWN, vk_code, 0)
    time.sleep(0.05)
    win32api.SendMessage(hwnd, win32con.WM_KEYUP, vk_code, 0)
    time.sleep(0.05)

    if with_shift:
        win32api.SendMessage(hwnd, win32con.WM_KEYUP, win32con.VK_SHIFT, 0)
        time.sleep(0.05)

def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_keyboard_input2.py list   - List all BlueStacks windows")
        print("  python test_keyboard_input2.py in     - Send Shift+A to all windows")
        print("  python test_keyboard_input2.py out    - Send Shift+Z to all windows")
        return

    action = sys.argv[1].lower()

    windows = find_bluestacks_windows()

    if action == "list":
        print(f"Found {len(windows)} windows:")
        for hwnd, title, class_name in windows:
            try:
                print(f"  HWND: {hwnd:10d}, Class: {class_name:30s}, Title: {title}")
            except UnicodeEncodeError:
                print(f"  HWND: {hwnd:10d}, Class: {class_name:30s}, Title: [Unicode error]")

    elif action == "in":
        print(f"Sending Shift+A to {len(windows)} windows using SendMessage...")
        for hwnd, title, class_name in windows:
            print(f"  -> HWND {hwnd} ({class_name})")
            try:
                send_key_sendmessage(hwnd, 0x41, with_shift=True)
            except Exception as e:
                print(f"     ERROR: {e}")
        print("Done!")

    elif action == "out":
        print(f"Sending Shift+Z to {len(windows)} windows using SendMessage...")
        for hwnd, title, class_name in windows:
            print(f"  -> HWND {hwnd} ({class_name})")
            try:
                send_key_sendmessage(hwnd, 0x5A, with_shift=True)
            except Exception as e:
                print(f"     ERROR: {e}")
        print("Done!")

    else:
        print(f"Unknown action: {action}")

if __name__ == "__main__":
    main()
