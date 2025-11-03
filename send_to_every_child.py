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

def send_to_every_child(direction):
    """Try sending arrow key to EVERY child window, one by one"""
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
    scan_code = win32api.MapVirtualKey(vk, 0)

    # Construct lparam for arrow keys
    lparam_down = 1 | (scan_code << 16) | (1 << 24)
    lparam_up = 1 | (scan_code << 16) | (1 << 24) | (1 << 30) | (1 << 31)

    print(f"Enumerating ALL child windows and trying each one...")
    print(f"WATCH BLUESTACKS - tell me if map moves after any attempt!")
    print("=" * 80)

    attempt = 0

    def callback(child_hwnd, param):
        nonlocal attempt
        attempt += 1
        class_name = win32gui.GetClassName(child_hwnd)

        try:
            title = win32gui.GetWindowText(child_hwnd)
            safe_title = title[:30].encode('ascii', errors='replace').decode('ascii') if title else "(no title)"
        except:
            safe_title = "(error)"

        print(f"\nAttempt {attempt}: HWND {child_hwnd} | Class: {class_name} | Title: {safe_title}")

        # Send WM_KEYDOWN + WM_KEYUP to this child
        try:
            win32gui.SendMessage(child_hwnd, win32con.WM_KEYDOWN, vk, lparam_down)
            time.sleep(0.05)
            win32gui.SendMessage(child_hwnd, win32con.WM_KEYUP, vk, lparam_up)
            print(f"  > Sent {direction} arrow to this window")
        except Exception as e:
            print(f"  > ERROR: {e}")

        # Pause to let user observe if map moved
        time.sleep(1.5)

    # Enumerate all child windows
    win32gui.EnumChildWindows(hwnd, callback, None)

    print("\n" + "=" * 80)
    print(f"Finished trying {attempt} child windows.")
    print("Did the map move after any of those attempts? Tell me which number!")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python send_to_every_child.py <up|down|left|right>")
        sys.exit(1)

    send_to_every_child(sys.argv[1].lower())
