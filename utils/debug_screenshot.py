"""
Shared debug screenshot utility for all flows.

Usage:
    from utils.debug_screenshot import save_debug_screenshot, DaemonDebugCapture

    # Save with flow name as subdirectory
    save_debug_screenshot(frame, "barracks", "FAIL_step0_panel_not_open")
    # Saves to: templates/debug/barracks/20251209_060553_FAIL_step0_panel_not_open.png

    # For comprehensive daemon debugging:
    debug = DaemonDebugCapture()
    debug.capture(frame, iteration, view_state, "flow_start", "elite_zombie")
"""

from pathlib import Path
from datetime import datetime
import cv2
import os
import time

# Base debug directory
DEBUG_BASE = Path(__file__).parent.parent / "templates" / "debug"

# Daemon debug directory (separate, with auto-cleanup)
DAEMON_DEBUG_BASE = Path(__file__).parent.parent / "screenshots" / "daemon_debug"

# Disk management
MAX_DISK_USAGE_GB = 50
CLEANUP_THRESHOLD_GB = 45
CLEANUP_INTERVAL_SECONDS = 1800  # Check every 30 min


def save_debug_screenshot(frame, flow_name: str, label: str) -> str:
    """
    Save debug screenshot with timestamp and label.

    Args:
        frame: BGR numpy array screenshot
        flow_name: Name of the flow (used as subdirectory, e.g., "barracks", "upgrade", "rally")
        label: Description label for filename (e.g., "FAIL_step0_panel_not_open")

    Returns:
        str: Path to saved file
    """
    # Create subdirectory for this flow
    debug_dir = DEBUG_BASE / flow_name
    debug_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = debug_dir / f"{timestamp}_{label}.png"

    # Save
    cv2.imwrite(str(filepath), frame)

    return str(filepath)


class DaemonDebugCapture:
    """
    Comprehensive debug screenshot capture for daemon.

    Auto-cleans old screenshots to stay within disk budget.
    Captures selectively based on events (view changes, flows, errors).
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.base_dir = DAEMON_DEBUG_BASE
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.last_cleanup = 0
        self.last_view_state = None
        self.capture_count = 0
        self.enabled = True

        # Create today's directory
        self._update_daily_dir()

    def _update_daily_dir(self):
        """Create/update daily subdirectory."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        self.daily_dir = self.base_dir / date_str
        self.daily_dir.mkdir(parents=True, exist_ok=True)

    def _get_disk_usage_gb(self) -> float:
        """Get total disk usage in GB."""
        total = 0
        try:
            for f in self.base_dir.rglob("*.png"):
                total += f.stat().st_size
        except Exception:
            pass
        return total / (1024 ** 3)

    def _cleanup_old(self):
        """Remove oldest screenshots to stay within budget."""
        # Single scan: collect (path, mtime, size) for all files
        files_info = []
        total_bytes = 0
        try:
            for f in self.base_dir.rglob("*.png"):
                stat = f.stat()
                files_info.append((f, stat.st_mtime, stat.st_size))
                total_bytes += stat.st_size
        except Exception:
            pass

        usage_gb = total_bytes / (1024 ** 3)
        if usage_gb < CLEANUP_THRESHOLD_GB:
            return

        print(f"[DEBUG] Disk usage {usage_gb:.1f}GB, cleaning up...")

        # Sort by mtime (oldest first)
        files_info.sort(key=lambda x: x[1])

        removed = 0
        bytes_removed = 0
        target_bytes = int(CLEANUP_THRESHOLD_GB * 0.8 * (1024 ** 3))

        for f, mtime, size in files_info:
            if total_bytes - bytes_removed < target_bytes:
                break
            try:
                f.unlink()
                removed += 1
                bytes_removed += size
            except Exception:
                pass

        # Remove empty dirs
        for d in list(self.base_dir.iterdir()):
            if d.is_dir():
                try:
                    if not any(d.iterdir()):
                        d.rmdir()
                except Exception:
                    pass

        if removed:
            print(f"[DEBUG] Removed {removed} old screenshots ({bytes_removed / (1024**3):.1f}GB)")

    def capture(
        self,
        frame,
        iteration: int,
        view_state: str,
        event: str,
        detail: str = ""
    ) -> str:
        """
        Capture debug screenshot.

        Args:
            frame: CV2 frame
            iteration: Daemon iteration number
            view_state: TOWN/WORLD/CHAT/UNKNOWN
            event: Event type (view_change, flow_start, flow_end, error, recovery, etc.)
            detail: Additional detail (flow name, error message, etc.)

        Returns:
            Path to saved file
        """
        if not self.enabled or frame is None:
            return ""

        # Periodic cleanup check
        now = time.time()
        if now - self.last_cleanup > CLEANUP_INTERVAL_SECONDS:
            self.last_cleanup = now
            self._cleanup_old()

        self._update_daily_dir()

        # Build filename
        ts = datetime.now().strftime("%H%M%S")
        detail_safe = detail.replace(" ", "_").replace("/", "-")[:30] if detail else ""

        if detail_safe:
            filename = f"{ts}_{iteration:05d}_{view_state}_{event}_{detail_safe}.png"
        else:
            filename = f"{ts}_{iteration:05d}_{view_state}_{event}.png"

        filepath = self.daily_dir / filename

        try:
            cv2.imwrite(str(filepath), frame)
            self.capture_count += 1
            return str(filepath)
        except Exception as e:
            print(f"[DEBUG] Failed to save: {e}")
            return ""

    def capture_if_view_changed(
        self,
        frame,
        iteration: int,
        view_state: str
    ) -> str:
        """Capture only if view state changed from last capture."""
        if view_state != self.last_view_state:
            self.last_view_state = view_state
            return self.capture(frame, iteration, view_state, "view_change", f"from_{self.last_view_state or 'init'}")
        return ""


# Singleton accessor
_daemon_debug = None

def get_daemon_debug() -> DaemonDebugCapture:
    """Get singleton daemon debug capture instance."""
    global _daemon_debug
    if _daemon_debug is None:
        _daemon_debug = DaemonDebugCapture()
    return _daemon_debug
