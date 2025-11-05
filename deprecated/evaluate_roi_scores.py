#!/usr/bin/env python3
import cv2
from pathlib import Path
from find_player import Config, ADBController
from game_utils import GameHelper

def main():
    config = Config()
    adb = ADBController(config)
    helper = GameHelper(adb, config)

    roi_dir = Path('templates/debug/testing/roi')
    image_paths = sorted(roi_dir.glob('*.png'))

    for path in image_paths:
        img = cv2.imread(str(path))
        if img is None:
            continue
        match = helper.button_matcher.match(img, save_debug=False)
        label = path.name
        if match and match.score >= helper.button_matcher.threshold:
            print(f"{label}: {match.label} score={match.score:.3f}")
        elif match:
            print(f"{label}: NONE score={match.score:.3f}")
        else:
            print(f"{label}: NONE score=0.000")

if __name__ == '__main__':
    main()
