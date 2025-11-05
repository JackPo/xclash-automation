#!/usr/bin/env python3
import cv2
from pathlib import Path


def main():
    roi_dir = Path("templates/debug/testing/roi")
    for path in sorted(roi_dir.glob("*.png")):
        img = cv2.imread(str(path))
        if img is None:
            continue
        avg_bgr = img.mean(axis=(0, 1))
        h, w = img.shape[:2]
        print(
            f"{path.name}: shape=({h}, {w}) avg_bgr={[round(float(x), 3) for x in avg_bgr]}"
        )


if __name__ == "__main__":
    main()
