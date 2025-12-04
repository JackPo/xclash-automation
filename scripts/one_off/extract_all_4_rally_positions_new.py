"""Extract all 4 rally positions using 166 pixel spacing from new screenshot."""
import cv2

# Load new screenshot
frame = cv2.imread('screenshots/screenshot_20251203_215140.png')

# Detected positions (from template matching)
# Button 2: X=1570
# Button 1: X=1737 (spacing from button 2: 167)
# Button 3: X=1902 (spacing from button 1: 165)

# Use 166 pixel average spacing
spacing = 166

# Calculate all 4 X coordinates
# Button 1 is at 1737, go LEFT by 166 to get the leftmost
x_coords = [
    1570 - 166,  # Slot 1 (leftmost): 1404
    1570,        # Slot 2: 1570
    1737,        # Slot 3: 1737
    1902         # Slot 4: 1902
]

print(f"Spacing: {spacing} pixels")
print(f"All 4 X coordinates: {x_coords}")
print()

# Y coordinate (ALL THE SAME)
y = 474
w, h = 130, 130

# Verify actual spacings
print(f"Actual spacings:")
print(f"  Slot 1 to 2: {x_coords[1] - x_coords[0]}")
print(f"  Slot 2 to 3: {x_coords[2] - x_coords[1]}")
print(f"  Slot 3 to 4: {x_coords[3] - x_coords[2]}")
print()

# Extract all 4 positions
for i, x in enumerate(x_coords, 1):
    roi = frame[y:y+h, x:x+w]

    output_path = f'templates/ground_truth/testing/rally_new_slot_{i}_x{x}_y{y}.png'
    cv2.imwrite(output_path, roi)

    center_x = x + w // 2
    center_y = y + h // 2

    print(f"Slot {i}:")
    print(f"  Position: ({x}, {y})")
    print(f"  Size: {w}x{h}")
    print(f"  Click center: ({center_x}, {center_y})")
    print(f"  Saved to: {output_path}")
    print()

print("\n=== FINAL DOCUMENTATION ===")
print(f"Rally slot Y coordinate: {y} (FIXED)")
print(f"Rally slot X coordinates: {x_coords}")
print(f"Rally slot spacing: ~166 pixels (varies 165-167)")
print(f"Rally slot size: 130x130 pixels")
