import win32api
import win32con
import time
import sys

def send_arrow_keybd_event_no_focus(direction):
    """Use keybd_event WITHOUT SetForegroundWindow"""

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

    print(f"Sending {direction} arrow using keybd_event (NO SetForegroundWindow)")
    print("This will send keyboard input to the CURRENTLY FOCUSED window")
    print("If BlueStacks is in background, keyboard goes to your current window instead")
    print()

    # Send key using keybd_event WITHOUT bringing any window to foreground
    win32api.keybd_event(vk, 0, 0, 0)  # Key down
    time.sleep(0.05)
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)  # Key up

    print("Done! Did BlueStacks map pan? Or did the key go to your current window?")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_keybd_event_background.py <up|down|left|right>")
        sys.exit(1)

    send_arrow_keybd_event_no_focus(sys.argv[1].lower())
