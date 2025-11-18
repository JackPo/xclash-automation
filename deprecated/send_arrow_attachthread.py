import win32gui
import win32con
import win32api
import win32process
import time
import sys
import ctypes

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

def send_arrow_with_attach_thread(direction):
    """Send arrow key using AttachThreadInput to share input state"""
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

    # Get thread IDs
    current_thread_id = win32api.GetCurrentThreadId()
    target_thread_id, target_process_id = win32process.GetWindowThreadProcessId(hwnd)

    print(f"Current thread ID: {current_thread_id}")
    print(f"Target thread ID: {target_thread_id}")
    print(f"Target process ID: {target_process_id}")

    # Construct lparam for arrow keys (extended key)
    lparam_down = 1 | (scan_code << 16) | (1 << 24)
    lparam_up = 1 | (scan_code << 16) | (1 << 24) | (1 << 30) | (1 << 31)

    # Attach our thread's input to the target thread's input
    print(f"Attaching thread input...")
    attached = ctypes.windll.user32.AttachThreadInput(current_thread_id, target_thread_id, True)

    if not attached:
        error = ctypes.windll.kernel32.GetLastError()
        print(f"AttachThreadInput failed! Error code: {error}")
        # Try anyway
    else:
        print("AttachThreadInput succeeded!")

    try:
        # Now send the message while threads are attached
        print(f"Sending {direction} arrow...")
        result = win32api.SendMessage(hwnd, win32con.WM_KEYDOWN, vk, lparam_down)
        time.sleep(0.05)
        result = win32api.SendMessage(hwnd, win32con.WM_KEYUP, vk, lparam_up)

        error = win32api.GetLastError()
        print(f"SendMessage last error: {error}")
        print("Done!")

    finally:
        # Detach threads
        if attached:
            print("Detaching thread input...")
            ctypes.windll.user32.AttachThreadInput(current_thread_id, target_thread_id, False)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python send_arrow_attachthread.py <up|down|left|right>")
        sys.exit(1)

    send_arrow_with_attach_thread(sys.argv[1].lower())
