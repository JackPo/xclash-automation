"""
Windows idle time detector.

Uses Windows API to check how long since last keyboard/mouse input.
"""
import ctypes


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]


def get_idle_seconds() -> float:
    """
    Get the number of seconds since last user input (keyboard/mouse).

    Returns:
        Seconds since last input activity.
    """
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
    millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
    return millis / 1000.0


def format_idle_time(seconds: float) -> str:
    """
    Format idle time as human-readable string.

    Args:
        seconds: Idle time in seconds

    Returns:
        Formatted string like "2m 30s" or "1h 5m"
    """
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


def is_user_idle(min_seconds: float = 300) -> bool:
    """
    Check if user has been idle for at least min_seconds.

    Args:
        min_seconds: Minimum idle time threshold (default 5 minutes)

    Returns:
        True if user has been idle for at least min_seconds.
    """
    return get_idle_seconds() >= min_seconds
