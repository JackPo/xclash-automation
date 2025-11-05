import cv2
import numpy as np

# Load the screenshot
img = cv2.imread('templates/debug/after_8_zooms.png')
height, width = img.shape[:2]

print(f"Image dimensions: {width}x{height} (width x height)")
print("\nLooking at the image, I can see several castles.")
print("Let me identify complete castles with structure + name + level badge:\n")

# Looking at the screenshot more carefully:
# - Top row has several castles around y=80-170
# - Each castle is roughly 120-140 pixels wide and 100-120 pixels tall (including name and level)

# Let me extract visible complete castles
# Need to include: castle building + player name + level badge
castles = [
    # Castle 1: Left side blue/white castle - needs to go lower to include level badge
    {
        'name': 'castle_complex_1',
        'x': 295,
        'y': 90,
        'width': 150,
        'height': 90
    },
    # Castle 2: Center pink castle - adjust to capture full structure
    {
        'name': 'castle_complex_2',
        'x': 505,
        'y': 50,
        'width': 150,
        'height': 130
    },
    # Castle 3: Right side blue castle - needs adjustment
    {
        'name': 'castle_complex_3',
        'x': 885,
        'y': 105,
        'width': 150,
        'height': 110
    }
]

# Create a copy with rectangles drawn
img_marked = img.copy()
for i, castle in enumerate(castles):
    x, y, w, h = castle['x'], castle['y'], castle['width'], castle['height']
    cv2.rectangle(img_marked, (x, y), (x+w, y+h), (0, 255, 0), 2)
    cv2.putText(img_marked, str(i+1), (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

cv2.imwrite('castle_locations_marked.png', img_marked)
print("Created castle_locations_marked.png with green rectangles showing extraction regions")
print("\nNow extracting the castles...")

# Extract and save each castle
for castle in castles:
    x, y, w, h = castle['x'], castle['y'], castle['width'], castle['height']
    castle_img = img[y:y+h, x:x+w]
    output_path = f"templates/{castle['name']}.png"
    cv2.imwrite(output_path, castle_img)
    print(f"Saved {castle['name']}: ({x},{y}) size {w}x{h}")
