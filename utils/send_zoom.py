from __future__ import annotations

import win32gui
import win32con
import win32api
import time
import sys
from pathlib import Path

try:
    from utils.action_capture import get_action_capture
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    try:
        from utils.action_capture import get_action_capture
    except Exception:
        def get_action_capture():  # type: ignore[misc]
            class _Null:
                def action(self, **_kw):
                    class _C:
                        def __enter__(self_):
                            return self_
                        def __exit__(self_, *a):
                            return False
                    return _C()
            return _Null()


def find_bluestacks_window() -> int | None:
    """Find main BlueStacks window"""
    windows: list[tuple[int, str]] = []

    def callback(hwnd: int, windows: list[tuple[int, str]]) -> None:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "BlueStacks" in title:
                windows.append((hwnd, title))

    win32gui.EnumWindows(callback, windows)

    if windows:
        return windows[0][0]
    return None


def send_zoom(direction: str) -> None:
    """Send zoom command to BlueStacks

    Args:
        direction: 'in' for Shift+A (zoom in), 'out' for Shift+Z (zoom out)
    """
    # Win32 SendInput is REAL Windows input: without marking it, the daemon's
    # own zooms reset system idle and read back as "user active" (recovery
    # then aborts itself and gated actions starve).
    from utils.user_idle_tracker import mark_daemon_action
    mark_daemon_action()
    hwnd = find_bluestacks_window()
    if not hwnd:
        print("BlueStacks window not found!")
        return

    # Map direction to key
    keys = {
        'in': ord('A'),   # Shift+A = zoom in
        'out': ord('Z')   # Shift+Z = zoom out
    }

    if direction not in keys:
        print(f"Unknown direction: {direction}")
        print("Use 'in' for zoom in (Shift+A) or 'out' for zoom out (Shift+Z)")
        return

    vk = keys[direction]

    # Bring window to foreground
    print(f"Bringing BlueStacks to foreground...")
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    time.sleep(0.1)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        # Windows may block foreground switch, but that's OK
        pass
    time.sleep(0.2)

    # Send Shift+A or Shift+Z
    print(f"Sending Shift+{chr(vk)} (zoom {direction})...")

    # Route through action capture (before-shot -> key send -> after-burst).
    with get_action_capture().action(
        action_type="zoom", params={"direction": direction}, source="win32:zoom",
    ):
        # Press Shift
        win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
        time.sleep(0.05)

        # Press A or Z
        win32api.keybd_event(vk, 0, 0, 0)
        time.sleep(0.05)

        # Release A or Z
        win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.05)

        # Release Shift
        win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)

    print("Done!")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python send_zoom.py <in|out>")
        print("  in  = Shift+A (zoom in)")
        print("  out = Shift+Z (zoom out)")
        sys.exit(1)

    send_zoom(sys.argv[1].lower())
