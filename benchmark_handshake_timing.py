#!/usr/bin/env python3
"""
Benchmark handshake loop timing to identify bottleneck.
"""
import time
import cv2
from pathlib import Path
from adb_helper import ADBHelper
from handshake_icon_matcher import HandshakeIconMatcher


def main():
    print("Benchmarking handshake loop components...")
    print("=" * 60)

    # Initialize
    adb = ADBHelper()
    matcher = HandshakeIconMatcher(threshold=0.99, debug_dir=Path('templates/debug'))

    # Run 5 iterations and measure each component
    for i in range(5):
        print(f"\nIteration {i+1}/5:")

        # Measure screenshot capture
        start = time.time()
        full_path, _ = adb.take_screenshot('temp_benchmark.png', scale_for_llm=False)
        screenshot_time = time.time() - start
        print(f"  Screenshot: {screenshot_time:.3f}s")

        # Measure image load
        start = time.time()
        frame = cv2.imread(full_path)
        load_time = time.time() - start
        print(f"  Image load: {load_time:.3f}s")

        # Measure template matching
        start = time.time()
        is_present, score = matcher.is_present(frame, save_debug=False)
        match_time = time.time() - start
        print(f"  Matching:   {match_time:.3f}s (score={score:.4f})")

        # Total for this iteration (excluding sleep)
        total = screenshot_time + load_time + match_time
        print(f"  TOTAL:      {total:.3f}s")

        time.sleep(1.0)  # Small delay between iterations

    print("\n" + "=" * 60)
    print("Benchmark complete")


if __name__ == "__main__":
    main()
