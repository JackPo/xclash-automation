#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import os
import sys

os.chdir(r"C:\Users\mail\xclash")

crops = [
    "level_crops/level_00_center_531_369.png",
    "level_crops/level_01_center_91_1310.png",
    "level_crops/level_02_center_1982_190.png",
    "level_crops/level_03_center_1422_265.png",
    "level_crops/level_04_center_87_1394.png",
]

print("=" * 80)
print("LEVEL CROP IMAGE ANALYSIS")
print("=" * 80)

for crop_path in crops:
    try:
        img = cv2.imread(crop_path)
        if img is None:
            print(f"\n{crop_path}: Could not read image")
            continue

        h, w = img.shape[:2]
        filename = os.path.basename(crop_path)

        # Extract center coordinates from filename
        # Format: level_00_center_531_369.png
        parts = filename.replace(".png", "").split("_")
        cx = int(parts[3])
        cy = int(parts[4])

        print(f"\n{filename}")
        print(f"  Actual dimensions: {w}px wide x {h}px tall")
        print(f"  Expected crop: 50px wide x 25px tall")
        print(f"  Center point: ({cx}, {cy})")
        print(f"  Crop extraction: frame[{cy}+35:{cy}+60, {cx}-25:{cx}+25]")
        print(f"  Which equals: frame[{cy+35}:{cy+60}, {cx-25}:{cx+25}]")

    except Exception as e:
        print(f"{crop_path}: Error - {e}")

