#!/usr/bin/env python3
"""
Extract the bottom-right button region from screenshots for inspection.
"""
from pathlib import Path
import cv2

OUTPUT_DIR = Path("templates/debug/testing/roi")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def extract_roi(path, width=400, height=250):
    img = cv2.imread(str(path))
    if img is None:
        return

    h, w = img.shape[:2]
    x1 = max(0, w - width)
    y1 = max(0, h - height)
    roi = img[y1:, x1:]
    out_path = OUTPUT_DIR / f"{path.stem}_roi.png"
    cv2.imwrite(str(out_path), roi)
    print(f"Saved ROI to {out_path}")


def main():
    images = sorted(Path("templates/debug/testing").glob("*.png"))
    images.append(Path("templates/debug/adb_temp_cli.png"))
    for img_path in images:
        extract_roi(img_path)


if __name__ == "__main__":
    main()
