"""
BlueStacks-specific idle detection.

Tracks idle time based on user interaction with the BlueStacks window specifically,
rather than system-wide keyboard/mouse activity.

This means:
- Typing in Chrome does NOT reset BlueStacks idle time
- Clicking in BlueStacks DOES reset BlueStacks idle time
"""

from __future__ import annotations

import ctypes
import time
import win32gui


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]


_detector: BlueStacksIdleDetector | None = None


class BlueStacksIdleDetector:
    """Track idle time specifically for BlueStacks window interactions."""

    BLUESTACKS_TITLE = "BlueStacks App Player"
    INPUT_FRESHNESS_THRESHOLD = 2.0  # seconds - input within this time = "active"

    def __init__(self) -> None:
        self._last_bluestacks_interaction: float = time.time()
        self._bluestacks_hwnd: int | None = None
        self._find_bluestacks_window()

    def _find_bluestacks_window(self) -> None:
        """Find BlueStacks window handle."""
        self._bluestacks_hwnd = win32gui.FindWindow(None, self.BLUESTACKS_TITLE)

    def _get_foreground_hwnd(self) -> int:
        """Get handle of current foreground window."""
        return int(ctypes.windll.user32.GetForegroundWindow())

    def _get_system_idle_seconds(self) -> float:
        """Get system-wide idle time (same as existing idle_detector)."""
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
        millis: int = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return float(millis) / 1000.0

    def _is_bluestacks_foreground(self) -> bool:
        """Check if BlueStacks is the current foreground window."""
        if not self._bluestacks_hwnd:
            self._find_bluestacks_window()
        if not self._bluestacks_hwnd:
            return False
        foreground = self._get_foreground_hwnd()
        return foreground == self._bluestacks_hwnd

    def update(self) -> None:
        """
        Call every daemon iteration to track BlueStacks interactions.

        Updates the last interaction timestamp if:
        1. BlueStacks is the foreground window, AND
        2. User had recent keyboard/mouse input (within INPUT_FRESHNESS_THRESHOLD)
        """
        system_idle = self._get_system_idle_seconds()
        is_foreground = self._is_bluestacks_foreground()

        # If BlueStacks is foreground AND user had recent input, update timestamp
        if is_foreground and system_idle < self.INPUT_FRESHNESS_THRESHOLD:
            self._last_bluestacks_interaction = time.time()

    def get_bluestacks_idle_seconds(self) -> float:
        """Get seconds since last interaction with BlueStacks."""
        return time.time() - self._last_bluestacks_interaction

    def is_bluestacks_foreground(self) -> bool:
        """Public method to check if BlueStacks is currently in foreground."""
        return self._is_bluestacks_foreground()


def get_bluestacks_idle_detector() -> BlueStacksIdleDetector:
    """Get the singleton BlueStacksIdleDetector instance."""
    global _detector
    if _detector is None:
        _detector = BlueStacksIdleDetector()
    return _detector


def get_bluestacks_idle_seconds() -> float:
    """
    Get BlueStacks-specific idle time.

    This also updates the detector, so it's safe to call this
    without explicitly calling update() first.
    """
    detector = get_bluestacks_idle_detector()
    detector.update()
    return detector.get_bluestacks_idle_seconds()


def format_bluestacks_idle_time(seconds: float) -> str:
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
    # Test the detector
    import time as time_module

    print("BlueStacks Idle Detector Test")
    print("=" * 40)
    print("Focus BlueStacks and move mouse to reset idle time")
    print("Focus another window to see idle time increase")
    print("Press Ctrl+C to exit")
    print()

    detector = get_bluestacks_idle_detector()

    try:
        while True:
            detector.update()
            bs_idle = detector.get_bluestacks_idle_seconds()
            sys_idle = detector._get_system_idle_seconds()
            is_fg = detector.is_bluestacks_foreground()

            print(f"BlueStacks FG: {is_fg}, BS Idle: {format_bluestacks_idle_time(bs_idle)}, Sys Idle: {format_bluestacks_idle_time(sys_idle)}", end="\r")
            time_module.sleep(0.5)
    except KeyboardInterrupt:
        print("\nDone.")
