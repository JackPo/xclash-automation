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

Controlled by config.DEBUG_SCREENSHOTS_ENABLED (default: False)
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING, Any

import cv2
import time

if TYPE_CHECKING:
    import numpy.typing as npt

# Import config flag
try:
    from config import DEBUG_SCREENSHOTS_ENABLED
except ImportError:
    DEBUG_SCREENSHOTS_ENABLED = False

# Base debug directory
DEBUG_BASE = Path(__file__).parent.parent / "templates" / "debug"

# Daemon debug directory (separate, with auto-cleanup)
DAEMON_DEBUG_BASE = Path(__file__).parent.parent / "screenshots" / "daemon_debug"

# Disk management
MAX_DISK_USAGE_GB = 50
CLEANUP_THRESHOLD_GB = 45
CLEANUP_INTERVAL_SECONDS = 1800  # Check every 30 min
MAX_AGE_DAYS = 3  # Delete screenshots older than this

# All screenshot directories to clean
SCREENSHOT_DIRS = [
    Path(__file__).parent.parent / "templates" / "debug",
    Path(__file__).parent.parent / "screenshots" / "debug",
    Path(__file__).parent.parent / "screenshots" / "daemon_debug",
]


def cleanup_old_screenshots(max_age_days: int = MAX_AGE_DAYS) -> int:
    """
    Remove screenshots older than max_age_days from all screenshot directories.

    Call this on daemon startup to prevent disk from filling up.

    Args:
        max_age_days: Maximum age in days (default 3)

    Returns:
        Number of files removed
    """
    cutoff = time.time() - (max_age_days * 24 * 60 * 60)
    removed = 0

    for base_dir in SCREENSHOT_DIRS:
        if not base_dir.exists():
            continue

        try:
            for f in base_dir.rglob("*.png"):
                try:
                    if f.stat().st_mtime < cutoff:
                        f.unlink()
                        removed += 1
                except Exception:
                    pass

            # Remove empty directories
            for d in list(base_dir.rglob("*")):
                if d.is_dir():
                    try:
                        if not any(d.iterdir()):
                            d.rmdir()
                    except Exception:
                        pass
        except Exception:
            pass

    if removed > 0:
        print(f"[CLEANUP] Removed {removed} screenshots older than {max_age_days} days")

    return removed


def save_debug_screenshot(frame: npt.NDArray[Any], flow_name: str, label: str) -> str:
    """
    Save debug screenshot with timestamp and label.

    Args:
        frame: BGR numpy array screenshot
        flow_name: Name of the flow (used as subdirectory, e.g., "barracks", "upgrade", "rally")
        label: Description label for filename (e.g., "FAIL_step0_panel_not_open")

    Returns:
        str: Path to saved file, or empty string if disabled
    """
    if not DEBUG_SCREENSHOTS_ENABLED:
        return ""

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

    _instance: DaemonDebugCapture | None = None
    _initialized: bool
    base_dir: Path
    daily_dir: Path
    last_cleanup: float
    last_view_state: str | None
    capture_count: int
    enabled: bool

    def __new__(cls) -> DaemonDebugCapture:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._initialized = True
        self.base_dir = DAEMON_DEBUG_BASE
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.last_cleanup = 0.0
        self.last_view_state = None
        self.capture_count = 0
        self.enabled = DEBUG_SCREENSHOTS_ENABLED  # Controlled by config

        # Create today's directory
        self._update_daily_dir()

    def _update_daily_dir(self) -> None:
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

    def _cleanup_old(self) -> None:
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
        frame: npt.NDArray[Any] | None,
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
        frame: npt.NDArray[Any] | None,
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
