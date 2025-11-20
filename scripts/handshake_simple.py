#!/usr/bin/env python3
"""
Simple handshake clicker - runs once, checks and clicks if present.
Run this in a loop (e.g., Windows Task Scheduler every 3 seconds).
"""
import sys
import cv2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.adb_helper import ADBHelper
from utils.handshake_icon_matcher import HandshakeIconMatcher


def main():
    try:
        # Initialize
        adb = ADBHelper()
        matcher = HandshakeIconMatcher(
            threshold=0.99,
            debug_dir=Path('templates/debug')
        )

        # Take screenshot
        full_path, _ = adb.take_screenshot('temp_handshake.png', scale_for_llm=False)
        frame = cv2.imread(full_path)

        # Check for handshake
        is_present, score = matcher.is_present(frame, save_debug=False)

        if is_present:
            print(f"[+] Handshake detected (score={score:.4f}) - Clicking...")
            # Click at fixed center position
            adb.tap(3165, 1843)
            return 0
        else:
            print(f"[-] No handshake (score={score:.4f})")
            return 1

    except Exception as e:
        print(f"ERROR: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
