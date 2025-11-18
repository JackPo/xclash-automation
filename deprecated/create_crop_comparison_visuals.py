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

# Create a visual comparison showing what needs to be captured
for crop_path, cx, cy in crops:
    img = cv2.imread(crop_path)
    if img is None:
        continue

    h, w = img.shape[:2]
    filename = os.path.basename(crop_path)

    # Create visualization showing the problem and solution
    # We'll make a tall image showing current vs needed bounds

    # Visualization height = what we need to capture (50px) + some padding
    vis_height = 80
    vis_width = 100

    vis = np.ones((vis_height, vis_width, 3), dtype=np.uint8) * 255  # White background

    # Draw center line (red)
    center_y = 40
    cv2.line(vis, (0, center_y), (vis_width, center_y), (0, 0, 255), 1)

    # Current crop bounds (blue)
    current_top = 15
    current_bottom = current_top + h
    cv2.rectangle(vis, (10, current_top), (90, current_bottom), (255, 0, 0), 2)
    cv2.putText(vis, f"Current: {h}px", (5, current_top-3), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 0, 0), 1)

    # Recommended bounds (green)
    recommended_top = 5
    recommended_bottom = recommended_top + 50
    cv2.rectangle(vis, (10, recommended_top), (90, recommended_bottom), (0, 255, 0), 2)
    cv2.putText(vis, f"Recommended: 50px", (5, recommended_top-3), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)

    # Draw missing space if applicable (in red)
    if h < 25:
        missing = 25 - h
        cv2.rectangle(vis, (10, current_bottom), (90, current_bottom + missing), (0, 0, 255), 2)
        cv2.putText(vis, f"Missing: {missing}px", (5, current_bottom + missing + 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)

    # Save visualization
    output_name = f"vis_{filename}"
    cv2.imwrite(output_name, vis)
    print(f"Created: {output_name}")

print("\nVisualizations created!")
print("\nTo view results, open the generated 'vis_level_*.png' files")
print("\nColor coding:")
print("  BLUE   = Current crop (may be truncated)")
print("  GREEN  = Recommended crop (50px safe zone)")
print("  RED    = Missing pixels (only for level_04)")
