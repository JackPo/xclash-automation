#!/usr/bin/env python3
"""
Handshake Icon Auto-Clicker Loop (Windows Screenshot Path)

Uses Windows API screenshots for 50x faster capture vs ADB.
Runs continuously, checking for handshake icon every 3 seconds.
Press Ctrl+C to stop.

Performance:
- ADB path: ~2.7s screenshot + 0.16s load + 3s sleep = ~5.9s/iteration
- Windows path: ~0.05s screenshot + 3s sleep = ~3.05s/iteration

Usage:
    python run_handshake_loop_windows.py [--interval SECONDS]
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
        description="Handshake icon auto-clicker loop (Windows screenshot path)"
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=3.0,
        help="Check interval in seconds (default: 3.0)"
    )

    args = parser.parse_args()

    print(f"Starting handshake auto-clicker [WINDOWS PATH] (checking every {args.interval}s)")
    print("Using Windows API screenshots for 50x faster capture")
    print("Press Ctrl+C to stop")
    print("="*60)

    try:
        # Initialize ADB (only needed for clicking)
        adb = ADBHelper()
        print(f"Connected to device: {adb.device}")

        # Initialize Windows screenshot helper
        windows_helper = WindowsScreenshotHelper()
        print("Windows screenshot helper initialized")

        # Initialize handshake matcher
        matcher = HandshakeIconMatcher(
            threshold=0.05,  # TM_SQDIFF_NORMED: lower = better match, threshold is MAX difference
            debug_dir=Path('templates/debug')
        )

        iteration = 0
        total_screenshot_time = 0
        total_match_time = 0

        while True:
            iteration += 1
            print(f"\n[Iteration {iteration}] {time.strftime('%H:%M:%S')}")

            try:
                # Take screenshot using Windows API (FAST!)
                screenshot_start = time.time()
                frame = windows_helper.get_screenshot_cv2()
                screenshot_time = time.time() - screenshot_start
                total_screenshot_time += screenshot_time

                # Check if handshake is present at FIXED location
                match_start = time.time()
                is_present, score = matcher.is_present(frame)
                match_time = time.time() - match_start
                total_match_time += match_time

                if is_present:
                    print(f"  [CLICK] Icon detected! Diff={score:.4f} at fixed position (3165, 1843)")
                    matcher.click(adb)
                else:
                    print(f"  [SKIP] Icon not present (diff={score:.4f} > 0.05)")

                # Print timing stats
                print(f"  [TIMING] Screenshot: {screenshot_time*1000:.1f}ms, Match: {match_time*1000:.1f}ms")

            except Exception as e:
                print(f"  [ERROR] {e}")
                import traceback
                traceback.print_exc()

            # Wait for next iteration
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n\n" + "="*60)
        print("Stopped by user")
        if iteration > 0:
            avg_screenshot = (total_screenshot_time / iteration) * 1000
            avg_match = (total_match_time / iteration) * 1000
            print(f"\nAverage timings over {iteration} iterations:")
            print(f"  Screenshot: {avg_screenshot:.1f}ms")
            print(f"  Matching:   {avg_match:.1f}ms")
            print(f"  Total:      {avg_screenshot + avg_match:.1f}ms (+ {args.interval}s sleep)")
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
