"""Template match the OLD ADB template across ENTIRE screenshot."""
import cv2
import sys
import numpy as np
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load screenshot
frame = cv2.imread('screenshots/screenshot_20251203_140637.png')
if frame is None:
    print("ERROR: Could not load screenshot")
    exit(1)

print(f"Screenshot size: {frame.shape}")

# Load OLD ADB template
template_path = Path("templates/ground_truth/rally_plus_button_4k.png")
template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)

if template is None:
    print(f"ERROR: Could not load template from {template_path}")
    exit(1)

print(f"Template size: {template.shape}")

# Convert to grayscale
frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

# Template match ENTIRE image
print("\nSearching ENTIRE image for plus button...")
result = cv2.matchTemplate(frame_gray, template, cv2.TM_SQDIFF_NORMED)

# Find ALL matches below threshold
threshold = 0.15  # Higher threshold to catch more candidates
matches = []

h, w = template.shape
min_distance = 50  # Minimum distance between matches

# Get all locations below threshold
locations = np.where(result <= threshold)

for pt in zip(*locations[::-1]):  # Switch x and y
    x, y = pt
    score = result[y, x]

    # Check if too close to existing match
    too_close = False
    for mx, my, _ in matches:
        if abs(x - mx) < min_distance and abs(y - my) < min_distance:
            too_close = True
            break

    if not too_close:
        matches.append((x, y, float(score)))

# Sort by score (best first)
matches.sort(key=lambda m: m[2])

print(f"\nFound {len(matches)} potential matches (threshold={threshold}):")
for i, (x, y, score) in enumerate(matches[:20]):  # Show top 20
    print(f"  {i+1}. pos=({x}, {y}), score={score:.6f}")

if matches:
    best_x, best_y, best_score = matches[0]
    print(f"\nBest match: ({best_x}, {best_y}) with score={best_score:.6f}")
    print(f"Template size: {w}x{h}")
    print(f"Click position would be: ({best_x + w//2}, {best_y + h//2})")
else:
    print("\nNO MATCHES FOUND even with threshold 0.15")

    # Find absolute best match regardless of threshold
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    print(f"\nAbsolute best match anywhere:")
    print(f"  Position: {min_loc}")
    print(f"  Score: {min_val:.6f}")
