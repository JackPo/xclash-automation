"""Extract the actual rally plus button template."""
import cv2

# Load screenshot
frame = cv2.imread('screenshots/screenshot_20251203_140637.png')

# Accurate coordinates from Gemini
x1, y1 = 1737, 965
w, h = 125, 114

# Extract
roi = frame[y1:y1+h, x1:x1+w]

# Save to ground_truth/testing
output_path = 'templates/ground_truth/testing/rally_plus_button_accurate_1737_965.png'
cv2.imwrite(output_path, roi)

print(f"Extracted accurate rally plus button:")
print(f"  Position: ({x1}, {y1})")
print(f"  Size: {w}x{h}")
print(f"  Click center: ({x1 + w//2}, {y1 + h//2})")
print(f"  Saved to: {output_path}")
