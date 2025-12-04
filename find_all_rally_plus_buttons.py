"""Template match the 130x130 rally plus button across entire screenshot."""
import cv2
import numpy as np

# Load screenshot
frame = cv2.imread('screenshots/screenshot_20251203_140637.png')
frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

# Load template
template = cv2.imread('templates/ground_truth/testing/rally_plus_130x130_trim_right.png', cv2.IMREAD_GRAYSCALE)
h, w = template.shape

print(f"Screenshot size: {frame.shape}")
print(f"Template size: {w}x{h}")

# Template match
result = cv2.matchTemplate(frame_gray, template, cv2.TM_SQDIFF_NORMED)

# Find all matches below threshold
threshold = 0.05
matches = []

locations = np.where(result <= threshold)
for pt in zip(*locations[::-1]):  # Switch x and y
    x, y = pt
    score = result[y, x]

    # Check if too close to existing match (avoid duplicates)
    too_close = False
    for mx, my, _ in matches:
        if abs(x - mx) < 50 and abs(y - my) < 50:
            too_close = True
            break

    if not too_close:
        matches.append((x, y, float(score)))

# Sort by score
matches.sort(key=lambda m: m[2])

print(f"\nFound {len(matches)} rally plus buttons (threshold={threshold}):")
for i, (x, y, score) in enumerate(matches, 1):
    center_x = x + w // 2
    center_y = y + h // 2
    print(f"  Button {i}:")
    print(f"    Position: ({x}, {y})")
    print(f"    Score: {score:.6f}")
    print(f"    Click center: ({center_x}, {center_y})")
    print()
