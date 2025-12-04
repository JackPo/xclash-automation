"""Extract region around button 2 with 30px margin top/bottom."""
import cv2

# Load screenshot
frame = cv2.imread('screenshots/screenshot_20251203_140637.png')

# Button 2 position from Gemini: (1712, 974) size 234x75
x1 = 1712
y1 = 974
w = 234
h = 75

# Add 30px margin top and bottom
y1_margin = y1 - 30
y2_margin = y1 + h + 30

# Extract region (keep X unchanged)
roi = frame[y1_margin:y2_margin, x1:x1+w]

# Save it
output_path = 'screenshots/rally_region_with_margin.png'
cv2.imwrite(output_path, roi)

print(f"Extracted region:")
print(f"  Original button: ({x1}, {y1}) size {w}x{h}")
print(f"  With margin: ({x1}, {y1_margin}) to ({x1+w}, {y2_margin})")
print(f"  Region size: {w}x{y2_margin - y1_margin}")
print(f"  Saved to: {output_path}")
print(f"\nNow run Gemini on this cropped region")
