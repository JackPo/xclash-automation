"""
Find TOWN floor tiles using color+variance (same method as safe_grass).
Test on TOWN image (should find floor) and WORLD image (should find NOTHING).
"""
import sys
sys.path.insert(0, "C:\\Users\\mail\\xclash")

import cv2
import numpy as np
from pathlib import Path

TOWN_IMAGE = Path("C:/Users/mail/xclash/screenshots/debug/recent_issue/082553_264_c001674_TOWN_stam113.png")
WORLD_IMAGE = Path("C:/Users/mail/xclash/screenshots/debug/recent_issue/082559_102_c001680_UNKNOWN_stam113.png")

OUTPUT_TOWN = Path("C:/Users/mail/xclash/screenshots/debug/town_floor_detection.png")
OUTPUT_WORLD = Path("C:/Users/mail/xclash/screenshots/debug/world_floor_detection.png")

# TOWN floor tile color range in HSV (grayish-tan stone)
# Hue: 15-35 (tan/beige range)
# Saturation: 10-80 (low saturation - grayish)
# Value: 140-220 (mid-bright - not too dark)
FLOOR_HSV_LOW = np.array([15, 10, 140])
FLOOR_HSV_HIGH = np.array([35, 80, 220])

PATCH_SIZE = 350
MIN_FLOOR_RATIO = 0.90
SCAN_STEP = 80


def find_floor_tiles(frame, debug_name=""):
    """Find floor tiles using color + variance detection."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    floor_mask = cv2.inRange(hsv, FLOOR_HSV_LOW, FLOOR_HSV_HIGH)

    safe_spots = []

    for y in range(0, frame.shape[0] - PATCH_SIZE, SCAN_STEP):
        for x in range(0, frame.shape[1] - PATCH_SIZE, SCAN_STEP):
            patch = frame[y:y+PATCH_SIZE, x:x+PATCH_SIZE]
            patch_mask = floor_mask[y:y+PATCH_SIZE, x:x+PATCH_SIZE]

            floor_ratio = np.sum(patch_mask > 0) / (PATCH_SIZE * PATCH_SIZE)
            if floor_ratio < MIN_FLOOR_RATIO:
                continue

            variance = np.var(patch)
            cx, cy = x + PATCH_SIZE // 2, y + PATCH_SIZE // 2
            safe_spots.append((cx, cy, variance, floor_ratio))

    safe_spots.sort(key=lambda x: x[2])

    print(f"\n{debug_name}:")
    print(f"  Found {len(safe_spots)} floor patches (90%+ floor color, 350px)")
    if safe_spots:
        print(f"  Best: ({safe_spots[0][0]}, {safe_spots[0][1]}) var={safe_spots[0][2]:.0f} floor={safe_spots[0][3]:.0%}")

    return safe_spots, floor_mask


def visualize(frame, safe_spots, floor_mask, output_path, title):
    """Create visualization."""
    output = frame.copy()

    # Overlay floor color mask (blue tint)
    floor_overlay = output.copy()
    floor_overlay[floor_mask > 0] = [255, 200, 150]  # Light blue where floor detected
    output = cv2.addWeighted(output, 0.7, floor_overlay, 0.3, 0)

    # Draw safe spots
    for i, (cx, cy, var, ratio) in enumerate(safe_spots[:30]):
        if i < 10:
            color = (0, 255, 0)  # Green - safest
            radius = 15
        else:
            color = (0, 255, 255)  # Yellow
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

    # Title and legend
    cv2.putText(output, title, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
    cv2.putText(output, f"BLUE TINT = floor color detected", (20, 100),
               cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 200, 150), 2)
    cv2.putText(output, f"GREEN DOTS = {len(safe_spots)} safe floor patches (90%+ floor)", (20, 140),
               cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

    cv2.imwrite(str(output_path), output)
    print(f"  Saved: {output_path}")


def main():
    print("="*60)
    print("TOWN FLOOR DETECTION TEST")
    print("="*60)

    # Test 1: TOWN image - SHOULD find floor tiles
    print("\nLoading TOWN image...")
    town_frame = cv2.imread(str(TOWN_IMAGE))
    town_spots, town_mask = find_floor_tiles(town_frame, "TOWN VIEW")
    visualize(town_frame, town_spots, town_mask, OUTPUT_TOWN, "TOWN - Should find floor")

    # Test 2: WORLD/UNKNOWN image - SHOULD find NOTHING
    print("\nLoading WORLD/UNKNOWN image...")
    world_frame = cv2.imread(str(WORLD_IMAGE))
    world_spots, world_mask = find_floor_tiles(world_frame, "WORLD VIEW (castle popup)")
    visualize(world_frame, world_spots, world_mask, OUTPUT_WORLD, "WORLD - Should find NOTHING")

    print("\n" + "="*60)
    print("SUMMARY:")
    print(f"  TOWN:  {len(town_spots)} safe spots found")
    print(f"  WORLD: {len(world_spots)} safe spots found")
    if len(world_spots) == 0:
        print("  SUCCESS - WORLD correctly matched NOTHING!")
    else:
        print("  PROBLEM - WORLD should have 0 matches!")
    print("="*60)


if __name__ == "__main__":
    main()
