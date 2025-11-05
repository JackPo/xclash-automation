import cv2
import numpy as np

# Load the screenshot
img = cv2.imread('templates/debug/after_8_zooms.png')

if img is None:
    print("ERROR: Could not load image!")
    exit(1)

print(f"Image shape: {img.shape}")

# Define castle extraction regions (x, y, width, height)
# Each region should include: castle structure + player name + level badge
# Image is 1440x2560 (height x width)
castles = [
    # Castle 1: Top-left area blue/white castle
    {
        'name': 'castle_complex_1',
        'x': 120,
        'y': 170,
        'width': 160,
        'height': 80
    },
    # Castle 2: Center-top pink castle
    {
        'name': 'castle_complex_2',
        'x': 500,
        'y': 50,
        'width': 160,
        'height': 130
    },
    # Castle 3: Right area blue/white castle
    {
        'name': 'castle_complex_3',
        'x': 1090,
        'y': 180,
        'width': 160,
        'height': 120
    }
]

# Extract and save each castle
for castle in castles:
    x, y, w, h = castle['x'], castle['y'], castle['width'], castle['height']

    # Extract the region
    castle_img = img[y:y+h, x:x+w]

    # Save the template
    output_path = f"templates/{castle['name']}.png"
    cv2.imwrite(output_path, castle_img)

    print(f"Extracted {castle['name']}: position ({x}, {y}), size ({w}x{h})")
    print(f"  Saved to: {output_path}")
    print(f"  Extracted shape: {castle_img.shape}")

print("\nAll castles extracted successfully!")
