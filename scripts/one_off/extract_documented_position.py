"""Extract region at documented plus button position."""
import cv2

# Load screenshot
frame = cv2.imread('screenshots/screenshot_20251203_140637.png')

# Documented position from docs/joining_rallies.md
x, y = 1405, 477
w, h = 127, 132

# Extract region
roi = frame[y:y+h, x:x+w]

# Save it
output_path = 'templates/ground_truth/testing/rally_plus_documented_pos_1405_477.png'
cv2.imwrite(output_path, roi)

print(f"Extracted region at DOCUMENTED position")
print(f"Position: ({x}, {y})")
print(f"Size: {w}x{h}")
print(f"Saved to: {output_path}")

# Now test if the OLD template matches this region
template = cv2.imread('templates/ground_truth/rally_plus_button_4k.png', cv2.IMREAD_GRAYSCALE)
roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

import cv2 as cv
result = cv.matchTemplate(roi_gray, template, cv.TM_SQDIFF_NORMED)
score = float(cv.minMaxLoc(result)[0])

print(f"\nTemplate matching score at documented position: {score:.6f}")
print(f"Threshold: 0.05")
print(f"Match: {'YES' if score <= 0.05 else 'NO'}")
