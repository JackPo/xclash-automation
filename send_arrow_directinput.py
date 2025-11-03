import win32gui
import win32con
import win32api
import ctypes
import time
import sys

# Define INPUT structure for SendInput
PUL = ctypes.POINTER(ctypes.c_ulong)

class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]

class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                ("mi", MouseInput),
                ("hi", HardwareInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]

# Constants
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

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

def send_arrow_with_sendinput_scancode(direction):
    """Send arrow key using SendInput with scancodes (DirectInput compatible)"""
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

    # Get hardware scan code
    scan_code = win32api.MapVirtualKey(vk, 0)

    print(f"Sending {direction} arrow using SendInput with scancode {scan_code}...")
    print(f"Target window: {win32gui.GetWindowText(hwnd)}")

    # Create input structures
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()

    # Key down - use SCANCODE flag and EXTENDEDKEY for arrows
    ii_.ki = KeyBdInput(0, scan_code, KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY, 0, ctypes.pointer(extra))
    input_down = Input(ctypes.c_ulong(INPUT_KEYBOARD), ii_)

    # Key up - OR the KEYUP flag with SCANCODE and EXTENDEDKEY
    ii_.ki = KeyBdInput(0, scan_code, KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0, ctypes.pointer(extra))
    input_up = Input(ctypes.c_ulong(INPUT_KEYBOARD), ii_)

    # Send the input
    ctypes.windll.user32.SendInput(1, ctypes.pointer(input_down), ctypes.sizeof(input_down))
    time.sleep(0.05)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(input_up), ctypes.sizeof(input_up))

    print("Done!")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python send_arrow_directinput.py <up|down|left|right>")
        sys.exit(1)

    send_arrow_with_sendinput_scancode(sys.argv[1].lower())
