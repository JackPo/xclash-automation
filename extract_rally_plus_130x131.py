"""Extract rally plus button 130x131 (3px less on bottom)."""
import cv2

# Load screenshot
frame = cv2.imread('screenshots/screenshot_20251203_140637.png')

# Position
x1, y1 = 1737, 965
w = 130  # Already has 5px extra on right
h = 131  # 134 - 3

# Extract
roi = frame[y1:y1+h, x1:x1+w]

# Save
output_path = 'templates/ground_truth/testing/rally_plus_button_130x131.png'
cv2.imwrite(output_path, roi)

print(f"Extracted rally plus button 130x131:")
print(f"  Position: ({x1}, {y1})")
print(f"  Size: {w}x{h}")
print(f"  Click center: ({x1 + w//2}, {y1 + h//2})")
print(f"  Saved to: {output_path}")
