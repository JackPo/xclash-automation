#!/usr/bin/env python3
"""
Compute template match scores for stored screenshots (World/Town button region).
"""
from pathlib import Path
import cv2

from game_utils import GameHelper
from find_player import Config, ADBController


def main():
    config = Config()
    adb = ADBController(config)
    helper = GameHelper(adb, config)

    images = sorted(Path("templates/debug/testing").glob("*.png"))
    images.append(Path("templates/debug/adb_temp_cli.png"))

    for path in images:
        frame = cv2.imread(str(path))
        if frame is None:
            continue
        match = helper.button_matcher.match(frame, save_debug=False)
        if not match or match.score < helper.button_matcher.threshold:
            score = match.score if match else 0.0
            print(f"{path} -> NONE (score={score:.3f})")
            continue
        print(f"{path} -> state={match.label} score={match.score:.3f}")


if __name__ == "__main__":
    main()
