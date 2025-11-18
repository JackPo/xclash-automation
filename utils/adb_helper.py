#!/usr/bin/env python3
"""
ADB Helper - Centralized ADB management for XClash automation.

Provides robust device detection, connection management, and screenshot utilities.
Automatically saves both full-resolution and LLM-friendly scaled screenshots.

Usage:
    python adb_helper.py screenshot <output_path>
    python adb_helper.py check

    # From Python code:
    from adb_helper import ADBHelper
    adb = ADBHelper()
    full_path, llm_path = adb.take_screenshot("screenshot.png")
"""

import subprocess
import time
import sys
import argparse
from pathlib import Path
from PIL import Image
import io


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
    EXPECTED_RESOLUTION = (3840, 2160)  # 4K

    def __init__(self, auto_connect=True):
        """
        Initialize ADB helper.

        Args:
            auto_connect: If True, automatically find and connect to device
        """
        self.device = None

        if auto_connect:
            self.ensure_connected()

    def _run_adb(self, args, capture_output=True, check=False):
        """
        Execute ADB command.

        Args:
            args: List of command arguments
            capture_output: Whether to capture stdout/stderr
            check: Whether to raise exception on non-zero exit

        Returns:
            Tuple of (success, stdout, stderr)
        """
        cmd = [self.ADB_PATH]
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
                result = subprocess.run(cmd, check=check)
                return result.returncode == 0, "", ""
        except subprocess.CalledProcessError as e:
            return False, e.stdout if hasattr(e, 'stdout') else "", e.stderr if hasattr(e, 'stderr') else str(e)

    def find_device(self):
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

    def ensure_connected(self):
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

    def take_screenshot(self, output_path, scale_for_llm=True, llm_scale=0.5):
        """
        Capture screenshot from device.

        Saves both full-resolution and optionally an LLM-friendly scaled version.
        Uses exec-out screencap for direct binary capture (no device temp files).

        Args:
            output_path: Path to save full-resolution screenshot
            scale_for_llm: If True, also save scaled version for LLM viewing
            llm_scale: Scale factor for LLM version (default 0.5 = 50%)

        Returns:
            Tuple of (full_path, llm_path) where llm_path is None if scale_for_llm=False

        Raises:
            RuntimeError: If ADB connection fails or screenshot capture fails
        """
        if not self.ensure_connected():
            raise RuntimeError("No ADB device connected. Is BlueStacks running?")

        output_path = Path(output_path)

        # Capture screenshot using exec-out (direct binary to stdout)
        # This avoids creating temp files on the device
        cmd = [self.ADB_PATH, "-s", self.device, "exec-out", "screencap", "-p"]

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

            llm_path = None
            if scale_for_llm:
                # Load image and create scaled version
                img = Image.open(io.BytesIO(result.stdout))

                # Calculate scaled dimensions
                width, height = img.size
                new_width = int(width * llm_scale)
                new_height = int(height * llm_scale)

                # Scale with high-quality resampling
                img_scaled = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Save with _llm suffix
                llm_path = output_path.parent / f"{output_path.stem}_llm{output_path.suffix}"
                img_scaled.save(llm_path, optimize=True)

            return str(output_path), str(llm_path) if llm_path else None

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Screenshot capture failed: {e.stderr.decode() if e.stderr else str(e)}")

    def tap(self, x, y):
        """
        Tap at screen coordinates.

        Args:
            x: X coordinate (0-3840 for 4K)
            y: Y coordinate (0-2160 for 4K)
        """
        if not self.ensure_connected():
            raise RuntimeError("No ADB device connected")

        self._run_adb(["shell", "input", "tap", str(x), str(y)])

    def swipe(self, x1, y1, x2, y2, duration=300):
        """
        Swipe gesture.

        Args:
            x1, y1: Start coordinates
            x2, y2: End coordinates
            duration: Swipe duration in milliseconds
        """
        if not self.ensure_connected():
            raise RuntimeError("No ADB device connected")

        self._run_adb([
            "shell", "input", "swipe",
            str(x1), str(y1), str(x2), str(y2), str(duration)
        ])

    def get_screen_size(self):
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


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="ADB Helper - Screenshot and device management utility"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Screenshot command
    screenshot_parser = subparsers.add_parser("screenshot", help="Take screenshot")
    screenshot_parser.add_argument("output", help="Output path for screenshot")
    screenshot_parser.add_argument(
        "--no-scale",
        action="store_true",
        help="Don't create LLM-friendly scaled version"
    )

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

            full_path, llm_path = adb.take_screenshot(
                args.output,
                scale_for_llm=not args.no_scale
            )

            print(f"Full resolution: {full_path}")
            if llm_path:
                print(f"LLM version: {llm_path}")

            sys.exit(0)

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
