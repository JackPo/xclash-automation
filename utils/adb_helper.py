#!/usr/bin/env python3
"""
ADB Helper - Centralized ADB management for XClash automation.

Provides robust device detection, connection management, and screenshot utilities.

Usage:
    python adb_helper.py screenshot <output_path>
    python adb_helper.py check

    # From Python code:
    from adb_helper import ADBHelper
    adb = ADBHelper()
    adb.take_screenshot("screenshot.png")
"""
from __future__ import annotations

import subprocess
import time
import sys
import argparse
import logging
from pathlib import Path
from typing import Callable

try:
    from utils.action_capture import get_action_capture
except ImportError:
    # Allow direct invocation (python utils/adb_helper.py) where 'utils' isn't a package.
    sys.path.insert(0, str(Path(__file__).parent.parent))
    try:
        from utils.action_capture import get_action_capture
    except Exception:  # last-resort no-op so ADB actions never break
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

# Module-level click logger for debugging all tap actions
_click_logger: logging.Logger | None = None


def _get_click_logger() -> logging.Logger:
    """Get or create the click audit logger."""
    global _click_logger
    if _click_logger is None:
        _click_logger = logging.getLogger("click_audit")
        _click_logger.setLevel(logging.DEBUG)
        # Prevent propagation to root logger (no stdout spam)
        _click_logger.propagate = False

        # Only add handler if not already present (prevent duplicates)
        if not _click_logger.handlers:
            log_dir = Path(__file__).parent.parent / "logs"
            log_dir.mkdir(exist_ok=True)
            handler = logging.FileHandler(log_dir / "clicks.log")
            handler.setFormatter(logging.Formatter(
                "%(asctime)s.%(msecs)03d | %(message)s",
                datefmt="%H:%M:%S"
            ))
            _click_logger.addHandler(handler)
    return _click_logger


class ADBHelper:
    """
    Centralized ADB controller with automatic device detection and management.

    Features:
    - Auto-detects active BlueStacks device (prioritizes emulator-XXXX)
    - Validates connection before operations
    - Screenshot capture with automatic scaling for LLM viewing
    - Simple tap/swipe methods for UI interaction
    """

    ADB_PATH = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"

    def __init__(self, auto_connect: bool = True, on_action: Callable[[], None] | None = None) -> None:
        """
        Initialize ADB helper.

        Args:
            auto_connect: If True, automatically find and connect to device
            on_action: Optional callback to invoke before each tap/swipe action.
                       Used by UserIdleTracker to track daemon actions.
        """
        self.device: str | None = None
        self._on_action = on_action

        if auto_connect:
            self.ensure_connected()

    def _run_adb(self, args: list[str], capture_output: bool = True, check: bool = False) -> tuple[bool, str, str]:
        """
        Execute ADB command.

        Args:
            args: List of command arguments
            capture_output: Whether to capture stdout/stderr
            check: Whether to raise exception on non-zero exit

        Returns:
            Tuple of (success, stdout, stderr)
        """
        cmd: list[str] = [self.ADB_PATH]
        if self.device:
            cmd.extend(["-s", self.device])
        cmd.extend(args)

        try:
            if capture_output:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=check
                )
                return True, result.stdout, result.stderr
            else:
                run_result = subprocess.run(cmd, check=check)
                return run_result.returncode == 0, "", ""
        except subprocess.CalledProcessError as e:
            stdout = e.stdout if hasattr(e, 'stdout') and e.stdout else ""
            stderr = e.stderr if hasattr(e, 'stderr') and e.stderr else str(e)
            return False, stdout, stderr

    def find_device(self) -> str | None:
        """
        Find active BlueStacks device.

        Uses the proven detection logic from setup_bluestacks.py:
        1. Restart ADB server for clean state
        2. Check for emulator-XXXX devices (stable)
        3. Fall back to IP port connections (may go offline)

        Returns:
            Device ID string or None if not found
        """
        # Restart ADB server for clean state
        self._run_adb(["kill-server"], capture_output=False)
        time.sleep(0.5)
        self._run_adb(["start-server"], capture_output=False)
        time.sleep(1.0)

        # Check for emulator-XXXX devices FIRST (these are stable)
        success, stdout, _ = self._run_adb(["devices"])
        if success and "emulator-" in stdout:
            lines = stdout.strip().split('\n')[1:]  # Skip header
            for line in lines:
                if "\tdevice" in line and "emulator-" in line:
                    device = line.split()[0]
                    return device

        # Fall back to IP ports (may go offline)
        ports = [5556, 5555, 5554, 5557, 5558]
        for port in ports:
            success, _, _ = self._run_adb(["connect", f"127.0.0.1:{port}"])
            if success:
                time.sleep(0.5)
                success, stdout, _ = self._run_adb(["devices"])
                if f"127.0.0.1:{port}\tdevice" in stdout:
                    return f"127.0.0.1:{port}"

        return None

    def ensure_connected(self) -> bool:
        """
        Ensure ADB connection is active. Reconnects if needed.

        Returns:
            True if connected, False otherwise
        """
        # If we have a device, verify it's still online
        if self.device:
            success, stdout, _ = self._run_adb(["get-state"])
            if success and "device" in stdout:
                return True

        # Need to find/reconnect
        self.device = self.find_device()
        if self.device:
            return True

        return False

    def take_screenshot(self, output_path: str | Path) -> str:
        """
        Capture screenshot from device.

        Uses exec-out screencap for direct binary capture (no device temp files).

        Args:
            output_path: Path to save screenshot

        Returns:
            Path to saved screenshot

        Raises:
            RuntimeError: If ADB connection fails or screenshot capture fails
        """
        if not self.ensure_connected():
            raise RuntimeError("No ADB device connected. Is BlueStacks running?")

        output_path = Path(output_path)

        # Capture screenshot using exec-out (direct binary to stdout)
        # This avoids creating temp files on the device
        device_str = self.device if self.device else ""
        cmd = [self.ADB_PATH, "-s", device_str, "exec-out", "screencap", "-p"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=True
            )

            # result.stdout contains raw PNG bytes
            if not result.stdout:
                raise RuntimeError("Screenshot capture returned empty data")

            # Save full resolution
            output_path.write_bytes(result.stdout)

            return str(output_path)

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Screenshot capture failed: {e.stderr.decode() if e.stderr else str(e)}")

    def tap(self, x: int, y: int, source: str = "unknown", before_frame: object | None = None) -> None:
        """
        Tap at screen coordinates.

        Args:
            x: X coordinate (0-3840 for 4K)
            y: Y coordinate (0-2160 for 4K)
            source: Identifier for what initiated this click (for debugging audit trail)
            before_frame: Optional pre-captured frame to reuse as the capture
                          before-shot (avoids an extra screenshot grab).
        """
        if not self.ensure_connected():
            raise RuntimeError("No ADB device connected")

        # Log click to dedicated audit file
        logger = _get_click_logger()
        logger.debug(f"TAP ({x:4d}, {y:4d}) | {source}")

        # Route through the action-capture layer (before-shot -> send -> after-burst).
        with get_action_capture().action(
            action_type="tap", params={"x": x, "y": y},
            source=source, device=self.device, before_frame=before_frame,
        ):
            # Notify tracker before action (for idle detection)
            if self._on_action:
                self._on_action()

            self._run_adb(["shell", "input", "tap", str(x), str(y)])

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300,
              source: str = "unknown") -> None:
        """
        Swipe gesture.

        Args:
            x1, y1: Start coordinates
            x2, y2: End coordinates
            duration: Swipe duration in milliseconds
            source: Identifier for what initiated this swipe (audit trail)
        """
        if not self.ensure_connected():
            raise RuntimeError("No ADB device connected")

        logger = _get_click_logger()
        logger.debug(f"SWIPE ({x1:4d},{y1:4d})->({x2:4d},{y2:4d}) d={duration} | {source}")

        with get_action_capture().action(
            action_type="swipe",
            params={"x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration": duration},
            source=source, device=self.device,
        ):
            # Notify tracker before action (for idle detection)
            if self._on_action:
                self._on_action()

            self._run_adb([
                "shell", "input", "swipe",
                str(x1), str(y1), str(x2), str(y2), str(duration)
            ])

    def key_event(self, keycode: int, source: str = "unknown") -> None:
        """
        Send a key event.

        Args:
            keycode: Android keycode (e.g., 20 for DPAD_DOWN, 19 for DPAD_UP)
            source: Identifier for what initiated this key event (audit trail)
        """
        if not self.ensure_connected():
            raise RuntimeError("No ADB device connected")

        logger = _get_click_logger()
        logger.debug(f"KEY {keycode} | {source}")

        with get_action_capture().action(
            action_type="key_event", params={"keycode": keycode},
            source=source, device=self.device,
        ):
            if self._on_action:
                self._on_action()

            self._run_adb(["shell", "input", "keyevent", str(keycode)])

    def get_screen_size(self) -> tuple[int, int] | None:
        """
        Get current screen resolution.

        Returns:
            Tuple of (width, height) or None if failed
        """
        if not self.ensure_connected():
            return None

        success, stdout, _ = self._run_adb(["shell", "wm", "size"])
        if success:
            # Parse "Physical size: 3840x2160" or "Override size: 3840x2160"
            for line in stdout.split('\n'):
                if 'size:' in line.lower():
                    parts = line.split(':')
                    if len(parts) > 1:
                        res = parts[-1].strip()
                        if 'x' in res:
                            w, h = res.split('x')
                            return (int(w), int(h))

        return None

    def kill_other_apps(self, keep_package: str = "com.xman.na.gp") -> list[str]:
        """
        Force-stop all non-essential apps except the game.

        Kills BlueStacks bloatware (Game Center, etc.) while keeping
        system apps and the game running.

        Args:
            keep_package: Package name to keep running (default: game)

        Returns:
            List of package names that were killed
        """
        if not self.ensure_connected():
            return []

        # Packages to always kill (BlueStacks bloatware)
        kill_list = [
            "com.bluestacks.gamecenter",
            "com.bluestacks.filemanager",
            "com.bluestacks.settings",
            "com.android.vending",  # Play Store
        ]

        # Get running activities to find more packages
        success, stdout, _ = self._run_adb([
            "shell", "dumpsys", "activity", "activities"
        ])

        if success:
            import re
            # Find all package names in TaskRecord entries
            for match in re.finditer(r'TaskRecord\{[^}]+ A=([a-zA-Z0-9_.]+)', stdout):
                pkg = match.group(1)
                # Skip system apps and the game
                if pkg.startswith("com.android."):
                    continue
                if pkg.startswith("com.uncube."):  # BlueStacks launcher - keep
                    continue
                if pkg == keep_package:
                    continue
                if pkg not in kill_list:
                    kill_list.append(pkg)

        # Kill each package
        killed = []
        for pkg in kill_list:
            success, _, _ = self._run_adb(["shell", "am", "force-stop", pkg])
            if success:
                killed.append(pkg)

        return killed


def main() -> None:
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="ADB Helper - Screenshot and device management utility"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Screenshot command
    screenshot_parser = subparsers.add_parser("screenshot", help="Take screenshot")
    screenshot_parser.add_argument("output", help="Output path for screenshot")

    # Check command
    subparsers.add_parser("check", help="Check ADB connection status")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        adb = ADBHelper()

        if args.command == "check":
            if adb.device:
                print(f"Connected to device: {adb.device}")
                size = adb.get_screen_size()
                if size:
                    print(f"Screen resolution: {size[0]}x{size[1]}")
                sys.exit(0)
            else:
                print("ERROR: No device connected")
                print("Make sure BlueStacks is running")
                sys.exit(1)

        elif args.command == "screenshot":
            print(f"Capturing screenshot from {adb.device}...")

            path = adb.take_screenshot(args.output)

            print(f"Saved: {path}")

            sys.exit(0)

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
