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

def enumerate_all_windows_recursive(hwnd, level=0):
    """Recursively enumerate ALL nested child windows"""
    all_windows = [(hwnd, level)]

    def callback(child_hwnd, param):
        # Add this child
        param.append((child_hwnd, level + 1))
        # Recursively enumerate its children
        grandchildren = enumerate_all_windows_recursive(child_hwnd, level + 1)
        param.extend(grandchildren)

    children = []
    win32gui.EnumChildWindows(hwnd, callback, children)

    return children

def send_to_every_window_recursive(direction):
    """Try sending arrow key to EVERY window recursively"""
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

    print(f"Recursively enumerating ALL windows (nested children)...")
    print(f"WATCH BLUESTACKS - tell me if map moves after any attempt!")
    print("=" * 80)

    # Get all windows recursively
    all_windows = [(hwnd, 0)] + enumerate_all_windows_recursive(hwnd, 0)

    print(f"Found {len(all_windows)} windows total (including nested)")
    print("=" * 80)

    for attempt, (target_hwnd, level) in enumerate(all_windows, 1):
        class_name = win32gui.GetClassName(target_hwnd)

        try:
            title = win32gui.GetWindowText(target_hwnd)
            safe_title = title[:30].encode('ascii', errors='replace').decode('ascii') if title else "(no title)"
        except:
            safe_title = "(error)"

        indent = "  " * level
        print(f"\n{indent}Attempt {attempt} (Level {level}): HWND {target_hwnd}")
        print(f"{indent}  Class: {class_name} | Title: {safe_title}")

        # Send WM_KEYDOWN + WM_KEYUP
        try:
            win32gui.SendMessage(target_hwnd, win32con.WM_KEYDOWN, vk, lparam_down)
            time.sleep(0.05)
            win32gui.SendMessage(target_hwnd, win32con.WM_KEYUP, vk, lparam_up)
            print(f"{indent}  > Sent {direction} arrow")
        except Exception as e:
            print(f"{indent}  > ERROR: {str(e)[:50]}")

        # Pause to let user observe
        time.sleep(1.0)

    print("\n" + "=" * 80)
    print(f"Finished trying {len(all_windows)} windows.")
    print("Did the map move after any of those attempts? Tell me which number!")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python send_to_every_child_recursive.py <up|down|left|right>")
        sys.exit(1)

    send_to_every_window_recursive(sys.argv[1].lower())
