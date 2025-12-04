"""Extract rally slots with reduced gap - 164 pixels instead of 165."""
import cv2

# Load screenshot
frame = cv2.imread('screenshots/screenshot_20251203_140637.png')

# Known positions
x3 = 1737
x4 = 1902

# Reduced spacing: 164 instead of 165
spacing = 164

# Calculate all 4 X coordinates
x_coords = [
    x3 - spacing * 2,  # Slot 1: 1737 - 328 = 1409
    x3 - spacing,      # Slot 2: 1737 - 164 = 1573
    x3,                # Slot 3: 1737
    x4                 # Slot 4: 1902
]

print(f"Spacing: {spacing} pixels")
print(f"Final X coordinates: {x_coords}")
print()

# Y and size
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
