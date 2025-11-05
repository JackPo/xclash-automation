#!/usr/bin/env python3
"""
Utility script to benchmark World/Town button template matching.

Usage examples:
    python test_button_matching.py --capture 1
    python test_button_matching.py --capture 3 --delay 2
    python test_button_matching.py --images templates/debug/adb_temp_cli.png
"""

import argparse
import time
from datetime import datetime
from pathlib import Path

import cv2

from find_player import Config, ADBController
from game_utils import GameHelper


def capture_frame(helper, output_dir, label):
    """Capture a fresh screenshot via ADB and return (frame, path)."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"{label}_{timestamp}.png"
    helper.adb.screenshot(path)
    frame = cv2.imread(str(path))
    return frame, path if frame is not None else None


def evaluate_frame(helper, frame, source):
    """Run template matching on a frame and print results."""
    if frame is None:
        print(f"[{source}] ERROR: Unable to load image")
        return

    match = helper.button_matcher.match(frame, save_debug=False)
    if not match or match.score < helper.button_matcher.threshold:
        score = match.score if match else 0.0
        print(f"[{source}] NONE | score={score:.3f}")
        return

    print(
        f"[{source}] {match.label:<5} | score={match.score:.3f} "
        f"center={match.center}"
    )


def main():
    parser = argparse.ArgumentParser(description="Test World/Town button template matching.")
    parser.add_argument(
        "--capture",
        type=int,
        default=0,
        help="Number of live captures to run (requires BlueStacks visible).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Delay between captures (seconds).",
    )
    parser.add_argument(
        "--images",
        nargs="*",
        default=[],
        help="Existing image paths to evaluate.",
    )
    parser.add_argument(
        "--label",
        default="button_test",
        help="Base filename label for captured screenshots.",
    )

    args = parser.parse_args()

    config = Config()
    adb = ADBController(config)
    helper = GameHelper(adb, config)

    testing_dir = helper.template_base_dir / "debug" / "testing"
    testing_dir.mkdir(parents=True, exist_ok=True)

    # Evaluate existing images first
    for img_path in args.images:
        path = Path(img_path)
        frame = cv2.imread(str(path))
        evaluate_frame(helper, frame, source=str(path))

    # Run live captures if requested
    for idx in range(args.capture):
        frame, saved_path = capture_frame(helper, testing_dir, f"{args.label}_{idx+1}")
        evaluate_frame(helper, frame, source=str(saved_path))
        if idx < args.capture - 1:
            time.sleep(args.delay)


if __name__ == "__main__":
    main()
