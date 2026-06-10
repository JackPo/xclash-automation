"""Extract all 4 rally slot positions using calculated X coordinates."""
import cv2

# Load screenshot
frame = cv2.imread('screenshots/screenshot_20251203_140637.png')

# Known X coordinates
x1 = 1737
x2 = 1902

# Calculate spacing
spacing = x2 - x1  # 165 pixels

# Calculate all 4 X coordinates
x_coords = [
    x1,           # 1737
    x2,           # 1902
    x2 + spacing, # 2067
    x2 + spacing * 2  # 2232
]

print(f"X spacing: {spacing} pixels")
print(f"All 4 X coordinates: {x_coords}")
print()

# Use Y from button 1 (best match)
y = 964
w, h = 130, 130

# Extract all 4 positions
for i, x in enumerate(x_coords, 1):
    roi = frame[y:y+h, x:x+w]

    output_path = f'templates/ground_truth/testing/rally_slot_{i}_x{x}_y{y}.png'
    cv2.imwrite(output_path, roi)

    center_x = x + w // 2
    center_y = y + h // 2

    print(f"Slot {i}:")
    print(f"  Position: ({x}, {y})")
    print(f"  Size: {w}x{h}")
    print(f"  Click center: ({center_x}, {center_y})")
    print(f"  Saved to: {output_path}")
    print()
