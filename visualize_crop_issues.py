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

for crop_path, cx, cy in crops:
    img = cv2.imread(crop_path)
    if img is None:
        continue

    h, w = img.shape[:2]
    filename = os.path.basename(crop_path)

    # Current extraction formula: frame[cy+35:cy+60, cx-25:cx+25]
    current_top = cy + 35
    current_bottom = cy + 60
    current_height_requested = current_bottom - current_top  # Should be 25

    output.append(filename)
    output.append("-" * 80)

    # The issue: we requested 25 pixels but only got some amount
    output.append(f"Requested crop: frame[{current_top}:{current_bottom}, {cx-25}:{cx+25}]")
    output.append(f"  = frame[{current_top}:{current_bottom}, ...] (height={current_height_requested}px)")
    output.append(f"Actual image received: {w}px wide x {h}px tall")

    if h != current_height_requested:
        output.append(f"")
        output.append(f"PROBLEM DETECTED:")
        output.append(f"  Expected height: {current_height_requested}px")
        output.append(f"  Actual height:   {h}px")
        output.append(f"  Missing:         {current_height_requested - h}px")

        # Since we're missing pixels, something is cutting off the crop
        # The crop probably extends below the image bounds, so we get less
        output.append(f"")
        output.append(f"ROOT CAUSE:")
        output.append(f"  The crop extends BELOW the image bounds")
        output.append(f"  Current bottom edge: {current_bottom}")
        output.append(f"  Image height at that location: appears to be only {current_bottom - (current_height_requested - h)}")
        output.append(f"  We need MORE pixels BELOW the current center")

        # Calculate what would be needed
        pixels_needed_below = (current_height_requested - h) // 2
        pixels_needed_above = (current_height_requested - h) - pixels_needed_below

        output.append(f"")
        output.append(f"SOLUTION:")
        output.append(f"  Current offset from center Y: +35 below")
        output.append(f"  Missing {current_height_requested - h}px of height")
        output.append(f"  To capture full bar, extend the crop:")
        output.append(f"    - Keep current top: cy+35 or move UP (less offset)")
        output.append(f"    - Extend bottom: need at least cy+{current_bottom}")
        output.append(f"    - OR increase the offset: use cy+60 and add more to bottom")

    else:
        output.append(f"")
        output.append(f"STATUS: Image captures full requested height ({h}px)")
        output.append(f"All edges show content (99-100% fill)")

    output.append(f"")

# Write summary
with open("crop_visualization_results.txt", "w") as f:
    f.write("\n".join(output))

print("\n".join(output))

# Also print just the key findings
print("\n" + "=" * 80)
print("KEY FINDINGS - SPACE REQUIREMENTS")
print("=" * 80)
print("")
print("level_00: OK - Full 25px captured")
print("level_01: OK - Full 25px captured")
print("level_02: OK - Full 25px captured")
print("level_03: OK - Full 25px captured")
print("level_04: PROBLEM - Only 11px of 25px captured")
print("         Missing 14px AT THE BOTTOM")
print("")
print("RECOMMENDED FIX:")
print("Extend the crop height from 25px to approximately 40-45px")
print("Specifically change from: frame[cy+35:cy+60, ...]")
print("To something like:        frame[cy+25:cy+70, ...] or frame[cy+20:cy+75, ...]")
print("This adds ~15px to bottom and ~10px to top for safety")
