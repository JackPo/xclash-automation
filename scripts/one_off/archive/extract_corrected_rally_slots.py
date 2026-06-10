"""Extract rally slots with corrected X offsets: -2 for slot 1, -1 for slot 2."""
import cv2

# Load screenshot
frame = cv2.imread('screenshots/screenshot_20251203_140637.png')

# Corrected X coordinates (MINUS not plus)
x_coords = [
    1407 - 2,  # Slot 1: 1405
    1572 - 1,  # Slot 2: 1571
    1737,      # Slot 3: 1737 (unchanged)
    1902       # Slot 4: 1902 (unchanged)
]

print(f"Corrected X coordinates: {x_coords}")
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
