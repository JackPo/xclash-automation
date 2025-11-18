#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import numpy as np
import os

crops = [
    ("level_crops/level_00_center_531_369.png", 531, 369),
    ("level_crops/level_01_center_91_1310.png", 91, 1310),
    ("level_crops/level_02_center_1982_190.png", 1982, 190),
    ("level_crops/level_03_center_1422_265.png", 1422, 265),
    ("level_crops/level_04_center_87_1394.png", 87, 1394),
]

os.chdir(r"C:\Users\mail\xclash")

output = []
output.append("=" * 90)
output.append("DETAILED LEVEL CROP ANALYSIS")
output.append("=" * 90)

for crop_path, cx, cy in crops:
    img = cv2.imread(crop_path)
    if img is None:
        continue

    h, w = img.shape[:2]
    filename = os.path.basename(crop_path)

    # Current crop bounds
    current_top = cy + 35
    current_bottom = cy + 60
    current_left = cx - 25
    current_right = cx + 25

    output.append("")
    output.append(filename)
    output.append(f"  Current size: {w}px wide x {h}px tall")
    output.append(f"  Center: ({cx}, {cy})")
    output.append(f"  Current bounds: [{current_top}:{current_bottom}, {current_left}:{current_right}]")

    # Analyze dimensions
    output.append("")
    output.append("  DIMENSION ANALYSIS:")

    if h == 25:
        output.append(f"    Height: FULL (25px captured)")
    elif h < 25:
        missing = 25 - h
        output.append(f"    Height: TRUNCATED! {h}px captured, {missing}px missing")
        output.append(f"    Missing space: {missing}px at bottom")

    if w == 50:
        output.append(f"    Width: FULL (50px captured)")
    elif w < 50:
        missing = 50 - w
        output.append(f"    Width: TRUNCATED! {w}px captured, {missing}px missing")

    # Analyze content
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    non_zero_pixels = np.count_nonzero(gray)
    total_pixels = h * w
    fill_percent = 100 * non_zero_pixels / total_pixels if total_pixels > 0 else 0

    output.append("")
    output.append("  CONTENT ANALYSIS:")
    output.append(f"    Non-zero pixels: {non_zero_pixels}/{total_pixels} ({fill_percent:.1f}%)")

    # Check if content reaches edges
    if h > 1:
        top_row = np.any(gray[0, :] > 50)
        bottom_row = np.any(gray[-1, :] > 50)
        output.append(f"    Has content at top edge: {top_row}")
        output.append(f"    Has content at bottom edge: {bottom_row}")

    if w > 1:
        left_col = np.any(gray[:, 0] > 50)
        right_col = np.any(gray[:, -1] > 50)
        output.append(f"    Has content at left edge: {left_col}")
        output.append(f"    Has content at right edge: {right_col}")

# Write to file
with open("crop_analysis_results.txt", "w") as f:
    f.write("\n".join(output))

print("\n".join(output))
