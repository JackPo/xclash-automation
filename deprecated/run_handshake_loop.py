#!/usr/bin/env python3
"""
Handshake Icon Auto-Clicker Loop

Runs continuously, checking for handshake icon every 3 seconds.
Press Ctrl+C to stop.

Usage:
    python run_handshake_loop.py [--interval SECONDS]
"""

import sys
import time
import argparse
from pathlib import Path

from adb_helper import ADBHelper
from handshake_icon_matcher import HandshakeIconMatcher
from windows_screenshot_helper import WindowsScreenshotHelper


def main():
    parser = argparse.ArgumentParser(
        description="Handshake icon auto-clicker loop"
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=3.0,
        help="Check interval in seconds (default: 3.0)"
    )

    args = parser.parse_args()

    print(f"Starting handshake auto-clicker (checking every {args.interval}s)")
    print("Press Ctrl+C to stop")
    print("="*60)

    try:
        # Initialize ADB
        adb = ADBHelper()
        print(f"Connected to device: {adb.device}")

        # Initialize handshake matcher
        matcher = HandshakeIconMatcher(
            threshold=0.05,  # TM_SQDIFF_NORMED: lower = better match, threshold is MAX difference
            debug_dir=Path('templates/debug')
        )

        # Initialize Windows screenshot helper
        windows_helper = WindowsScreenshotHelper()
        print("Windows screenshot helper initialized")

        iteration = 0
        while True:
            iteration += 1
            print(f"\n[Iteration {iteration}] {time.strftime('%H:%M:%S')}")

            try:
                # Take screenshot using Windows API (FAST!)
                frame = windows_helper.get_screenshot_cv2()

                # Check if handshake is present at FIXED location
                is_present, score = matcher.is_present(frame)

                if is_present:
                    print(f"  [CLICK] Icon detected! Diff={score:.4f} at fixed position (3165, 1843)")
                    matcher.click(adb)
                else:
                    print(f"  [SKIP] Icon not present (diff={score:.4f} > 0.05)")

            except Exception as e:
                print(f"  [ERROR] {e}")

            # Wait for next iteration
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n\nStopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
