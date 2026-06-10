"""
Find flat areas by LOW VARIANCE + GRASS COLOR filter.
No template matching - just find uniform green patches.
"""
import sys
sys.path.insert(0, "C:\\Users\\mail\\xclash")

import cv2
import numpy as np
from pathlib import Path

IMAGE_PATH = Path("C:/Users/mail/xclash/screenshots/debug/daemon_frames/220415_864_c009019_WORLD_stam51.png")
OUTPUT_PATH = Path("C:/Users/mail/xclash/screenshots/debug/safe_grass_variance.png")

# Grass color range in HSV (olive green)
# Hue: 30-80 (yellow-green range)
# Saturation: 20-150 (not too gray, not too vivid)
# Value: 80-200 (not too dark, not too bright)
GRASS_HSV_LOW = np.array([30, 20, 80])
GRASS_HSV_HIGH = np.array([80, 150, 200])

PATCH_SIZE = 350  # Size of patch to check variance - bigger = safer distance from castles


def main():
    print(f"Loading...")
    frame = cv2.imread(str(IMAGE_PATH), cv2.IMREAD_COLOR)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    print(f"Image: {frame.shape}")

    output = frame.copy()

    # Create grass color mask
    grass_mask = cv2.inRange(hsv, GRASS_HSV_LOW, GRASS_HSV_HIGH)

    # Show grass color areas
    grass_overlay = output.copy()
    grass_overlay[grass_mask > 0] = [0, 255, 0]  # Green where grass detected
    output = cv2.addWeighted(output, 0.7, grass_overlay, 0.3, 0)

    # Find low-variance patches that are also grass-colored
    step = 80
    safe_spots = []

    for y in range(0, frame.shape[0] - PATCH_SIZE, step):
        for x in range(0, frame.shape[1] - PATCH_SIZE, step):
            patch = frame[y:y+PATCH_SIZE, x:x+PATCH_SIZE]
            patch_mask = grass_mask[y:y+PATCH_SIZE, x:x+PATCH_SIZE]

            # Check if mostly grass colored (>90% of patch)
            grass_ratio = np.sum(patch_mask > 0) / (PATCH_SIZE * PATCH_SIZE)
            if grass_ratio < 0.9:
                continue

            # Calculate variance (lower = flatter)
            variance = np.var(patch)

            cx, cy = x + PATCH_SIZE//2, y + PATCH_SIZE//2
            safe_spots.append((cx, cy, variance, grass_ratio))

    # Sort by variance (lowest first)
    safe_spots.sort(key=lambda x: x[2])

    print(f"Found {len(safe_spots)} grass patches")
    print(f"Variance range: {safe_spots[0][2]:.0f} to {safe_spots[-1][2]:.0f}" if safe_spots else "None")

    # Draw top 30 safest spots
    for i, (cx, cy, var, ratio) in enumerate(safe_spots[:30]):
        # Color by rank: green=safest, yellow=medium
        if i < 10:
            color = (0, 255, 0)
            radius = 15
        else:
            color = (0, 255, 255)
            radius = 10
        cv2.circle(output, (cx, cy), radius, color, -1)
        if i < 5:
            cv2.putText(output, f"var:{var:.0f}", (cx+20, cy),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # Mark safest
    if safe_spots:
        sx, sy, sv, sr = safe_spots[0]
        cv2.circle(output, (sx, sy), 25, (255, 0, 255), 5)
        cv2.putText(output, f"SAFEST var={sv:.0f}", (sx+30, sy),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 255), 2)

    # Legend
    cv2.putText(output, "GREEN TINT = grass color detected", (20, 50),
               cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
    cv2.putText(output, "DOTS = low variance grass patches (safe to click)", (20, 90),
               cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

    cv2.imwrite(str(OUTPUT_PATH), output)
    print(f"\nTop 5 safest spots:")
    for i, (cx, cy, var, ratio) in enumerate(safe_spots[:5]):
        print(f"  {i+1}. ({cx}, {cy}) variance={var:.0f}, grass={ratio:.0%}")
    print(f"\nSaved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
