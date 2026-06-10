"""Extract all 4 rally slot positions - slots 3,4 are at 1737,1902, so 1,2 are to the LEFT."""
import cv2

# Load screenshot
frame = cv2.imread('screenshots/screenshot_20251203_140637.png')

# Known X coordinates (these are slots 3 and 4)
x3 = 1737
x4 = 1902

# Calculate spacing
spacing = x4 - x3  # 165 pixels

# Calculate all 4 X coordinates (go LEFT for slots 1 and 2)
x_coords = [
    x3 - spacing * 2,  # Slot 1: 1737 - 330 = 1407
    x3 - spacing,       # Slot 2: 1737 - 165 = 1572
    x3,                 # Slot 3: 1737
    x4                  # Slot 4: 1902
]

print(f"X spacing: {spacing} pixels")
print(f"All 4 X coordinates: {x_coords}")
print()

# Use Y from button at 1902 (best match)
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
