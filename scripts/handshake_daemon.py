#!/usr/bin/env python3
"""
Icon Auto-Clicker Daemon

Runs continuously, checking for clickable icons every 3 seconds.
Currently detects:
- Handshake icon (Union button)
- Treasure map icon (bouncing scroll on barracks)

Press Ctrl+C to stop.

Usage:
    python handshake_daemon.py [--interval SECONDS]
"""

import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.adb_helper import ADBHelper
from utils.handshake_icon_matcher import HandshakeIconMatcher
from utils.treasure_map_matcher import TreasureMapMatcher
from utils.windows_screenshot_helper import WindowsScreenshotHelper


def main():
    parser = argparse.ArgumentParser(
        description="Icon auto-clicker daemon (handshake + treasure map)"
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=3.0,
        help="Check interval in seconds (default: 3.0)"
    )

    args = parser.parse_args()

    print(f"Starting icon auto-clicker daemon (checking every {args.interval}s)")
    print("Detecting: Handshake icon, Treasure map icon")
    print("Press Ctrl+C to stop")
    print("="*60)

    try:
        # Initialize ADB
        adb = ADBHelper()
        print(f"Connected to device: {adb.device}")

        # Initialize matchers
        debug_dir = Path('templates/debug')

        handshake_matcher = HandshakeIconMatcher(
            threshold=0.05,  # TM_SQDIFF_NORMED: lower = better match
            debug_dir=debug_dir
        )
        print(f"Handshake matcher loaded: {handshake_matcher.template_path}")

        treasure_matcher = TreasureMapMatcher(
            threshold=0.05,  # TM_SQDIFF_NORMED: lower = better match
            debug_dir=debug_dir
        )
        print(f"Treasure map matcher loaded: {treasure_matcher.template_path}")

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

                # Check handshake icon
                handshake_present, handshake_score = handshake_matcher.is_present(frame)
                if handshake_present:
                    print(f"  [HANDSHAKE] Detected! diff={handshake_score:.4f} -> CLICKING (3165, 1843)")
                    handshake_matcher.click(adb)
                else:
                    print(f"  [HANDSHAKE] Not present (diff={handshake_score:.4f})")

                # Check treasure map icon
                treasure_present, treasure_score = treasure_matcher.is_present(frame)
                if treasure_present:
                    print(f"  [TREASURE]  Detected! diff={treasure_score:.4f} -> CLICKING (2175, 1621)")
                    treasure_matcher.click(adb)
                else:
                    print(f"  [TREASURE]  Not present (diff={treasure_score:.4f})")

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
