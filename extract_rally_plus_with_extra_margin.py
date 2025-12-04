"""Extract rally plus button with 5px extra on right and bottom."""
import cv2

# Load screenshot
frame = cv2.imread('screenshots/screenshot_20251203_140637.png')

# Original accurate coordinates
x1, y1 = 1737, 965
w, h = 125, 114

# Add 5px to right and bottom
w_new = w + 5
h_new = h + 5

# Extract
roi = frame[y1:y1+h_new, x1:x1+w_new]

# Save
output_path = 'templates/ground_truth/testing/rally_plus_button_with_margin_130x119.png'
cv2.imwrite(output_path, roi)

print(f"Extracted rally plus button with extra margin:")
print(f"  Position: ({x1}, {y1})")
print(f"  Size: {w_new}x{h_new}")
print(f"  Click center: ({x1 + w_new//2}, {y1 + h_new//2})")
print(f"  Saved to: {output_path}")
