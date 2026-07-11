"""
User idle tracker that excludes daemon's own actions.

The problem:
1. Windows GetLastInputInfo() tracks system-wide input
2. BlueStacks captures mouse clicks INTERNALLY - Windows never sees them
3. Daemon's ADB clicks get translated to Windows mouse events by BlueStacks

Solution: Track BOTH system idle AND mouse movement over BlueStacks window.
- If mouse is over BlueStacks and moved recently → user is active
- If system_idle is low AND daemon didn't just click → user is active
- When daemon is about to click, it calls mark_daemon_action()
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

import win32gui


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _has_any_mouse_button_activity() -> bool:
    """
    Check if any primary mouse button is active.

    Uses AsyncKeyState bits:
    - high bit (0x8000): key is currently down
    - low bit (0x0001): key was pressed since last query
    The low bit helps catch fast click taps between daemon polling ticks.
    """
    user32 = ctypes.windll.user32
    vk_codes = (0x01, 0x02, 0x04, 0x05, 0x06)  # LBUTTON, RBUTTON, MBUTTON, XBUTTON1, XBUTTON2
    for vk in vk_codes:
        state = user32.GetAsyncKeyState(vk)
        if state & 0x8001:
            return True
    return False


def _get_system_idle_seconds() -> float:
    """Get raw system idle time from Windows API."""
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
    current_tick = ctypes.windll.kernel32.GetTickCount()
    millis = (current_tick - lii.dwTime) & 0xFFFFFFFF
    return float(millis) / 1000.0


def _get_mouse_position() -> tuple[int, int]:
    """Get current mouse cursor position."""
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)


_bs_hwnd_cache: int | None = None


def _find_bluestacks_window() -> int | None:
    """Find BlueStacks window handle (cached; re-enumerates if stale)."""
    global _bs_hwnd_cache
    if _bs_hwnd_cache is not None and win32gui.IsWindow(_bs_hwnd_cache):
        return _bs_hwnd_cache
    result = []

    def callback(hwnd: int, _: None) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "BlueStacks" in title:
                result.append(hwnd)
        return True

    win32gui.EnumWindows(callback, None)
    _bs_hwnd_cache = result[0] if result else None
    return _bs_hwnd_cache


GA_ROOT = 2


def _is_mouse_over_bluestacks() -> bool:
    """
    Is the cursor ACTUALLY over the BlueStacks window (z-order aware)?

    The old rectangle-only check counted a browser/terminal OVERLAPPING the
    BlueStacks rect as "over the game" - the user reading a dashboard on top
    of BlueStacks pinned user-idle at 0 and starved every gated action.
    """
    hwnd = _find_bluestacks_window()
    if not hwnd:
        return False

    try:
        pt = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        under = ctypes.windll.user32.WindowFromPoint(pt)
        root = ctypes.windll.user32.GetAncestor(under, GA_ROOT)
        return root == hwnd
    except Exception:
        return False


def _is_bluestacks_foreground() -> bool:
    """Is BlueStacks the focused (foreground) window?"""
    hwnd = _find_bluestacks_window()
    if not hwnd:
        return False
    try:
        fg = ctypes.windll.user32.GetForegroundWindow()
        return ctypes.windll.user32.GetAncestor(fg, GA_ROOT) == hwnd
    except Exception:
        return False


class UserIdleTracker:
    """
    Track user idle time, works with BlueStacks.

    BlueStacks captures clicks internally - Windows GetLastInputInfo() never sees them.
    So we also track mouse MOVEMENT over the BlueStacks window.

    If mouse is over BlueStacks and has moved → user is active.
    """

    DAEMON_CLICK_GRACE_PERIOD = 2.0
    ACTIVE_INPUT_THRESHOLD = 3.0

    # Mouse must move at least this many pixels to count as user activity
    MOUSE_MOVE_THRESHOLD = 2

    def __init__(self) -> None:
        self._last_user_activity = time.time()
        self._last_daemon_action = 0.0
        self._prev_system_idle = 0.0
        self._prev_mouse_pos: tuple[int, int] | None = None

    def mark_daemon_action(self) -> None:
        """Call BEFORE the daemon performs a click/action."""
        self._last_daemon_action = time.time()

    def update(self) -> None:
        """
        Update user idle tracking.

        Detects user activity via:
        1. System-wide input (keyboard, mouse outside BlueStacks)
        2. Mouse movement over BlueStacks window (BlueStacks captures clicks internally)
        """
        now = time.time()
        system_idle = _get_system_idle_seconds()
        time_since_daemon_action = now - self._last_daemon_action
        daemon_acted_recently = time_since_daemon_action < self.DAEMON_CLICK_GRACE_PERIOD

        user_is_active = False

        # Method 1: system input counts as GAME activity only when BlueStacks
        # is the focused window. "User active" means input directed AT THE
        # GAME - typing in a terminal/browser on the same machine must NOT
        # freeze the daemon (it pinned idle at 0 for minutes and starved
        # every idle-gated action while the user wasn't touching the game).
        if (
            system_idle < self.ACTIVE_INPUT_THRESHOLD
            and not daemon_acted_recently
            and _is_bluestacks_foreground()
        ):
            user_is_active = True

        # Method 2: Mouse activity over BlueStacks (works even when daemon clicks recently)
        # IMPORTANT: Do not gate this on daemon_acted_recently; otherwise frequent daemon
        # taps can mask real user interaction and cause unwanted recovery clicks.
        mouse_pos = _get_mouse_position()
        mouse_over_bluestacks = _is_mouse_over_bluestacks()

        if self._prev_mouse_pos is not None and mouse_over_bluestacks:
            dx = abs(mouse_pos[0] - self._prev_mouse_pos[0])
            dy = abs(mouse_pos[1] - self._prev_mouse_pos[1])
            mouse_moved = (dx + dy) >= self.MOUSE_MOVE_THRESHOLD
            if mouse_moved:
                user_is_active = True

        # Detect click-without-movement (fast taps or holds).
        # Do not require mouse movement; repeated clicking in place is still user activity.
        if mouse_over_bluestacks and _has_any_mouse_button_activity():
            user_is_active = True

        self._prev_mouse_pos = mouse_pos

        if user_is_active:
            self._last_user_activity = now

        self._prev_system_idle = system_idle

    def get_user_idle_seconds(self) -> float:
        """Get true user idle time (excludes daemon actions)."""
        return time.time() - self._last_user_activity

    def get_system_idle_seconds(self) -> float:
        """Get raw system idle time (for logging/comparison)."""
        return _get_system_idle_seconds()


# Singleton instance
_tracker = None


def get_user_idle_tracker() -> UserIdleTracker:
    """Get the singleton UserIdleTracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = UserIdleTracker()
    return _tracker


def mark_daemon_action() -> None:
    """Convenience function: mark that daemon is about to click."""
    get_user_idle_tracker().mark_daemon_action()


def get_user_idle_seconds() -> float:
    """
    Convenience function: get user idle time (excluding daemon actions).

    Also updates the tracker, so it's safe to call this
    without explicitly calling update() first.
    """
    tracker = get_user_idle_tracker()
    tracker.update()
    return tracker.get_user_idle_seconds()


def format_user_idle_time(seconds: float) -> str:
    """Format idle time as human-readable string (e.g., '2m 30s')."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


if __name__ == "__main__":
    # Test the tracker
    print("User Idle Tracker Test")
    print("=" * 40)
    print("This simulates daemon behavior:")
    print("- Every 3 seconds, daemon 'clicks' (marks action)")
    print("- User idle should accumulate despite daemon clicks")
    print("- Touch keyboard/mouse to reset user idle")
    print("Press Ctrl+C to exit")
    print()

    tracker = get_user_idle_tracker()

    try:
        iteration = 0
        while True:
            iteration += 1

            # Simulate daemon action every 3 seconds
            if iteration % 6 == 0:  # Every 3 seconds (0.5s sleep)
                print(f"[{iteration}] DAEMON CLICK (marking action)")
                tracker.mark_daemon_action()

            tracker.update()
            user_idle = tracker.get_user_idle_seconds()
            sys_idle = tracker.get_system_idle_seconds()

            print(
                f"[{iteration}] user_idle: {format_user_idle_time(user_idle)}, "
                f"sys_idle: {format_user_idle_time(sys_idle)}",
                end="\r"
            )
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nDone.")
