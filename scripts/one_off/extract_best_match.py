"""Extract the best match region and save it."""
import cv2

# Load screenshot
frame = cv2.imread('screenshots/screenshot_20251203_140637.png')

# Best match was at (306, 202) with size 127x132
x, y = 306, 202
w, h = 127, 132

# Extract region
roi = frame[y:y+h, x:x+w]

# Save to ground_truth/testing
output_path = 'templates/ground_truth/testing/rally_plus_best_match_0.077.png'
cv2.imwrite(output_path, roi)

print(f"Extracted best match region")
print(f"Position: ({x}, {y})")
print(f"Size: {w}x{h}")
print(f"Score: 0.077257")
print(f"Saved to: {output_path}")
