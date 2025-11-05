import cv2
import numpy as np

# Read the source image
img = cv2.imread(r'C:\Users\mail\xclash\after_8_zooms.png')
print(f"Source image size: {img.shape}")

# Create a copy for visualization
vis = img.copy()

# Looking at the original image, I can see castles at these approximate pixel locations:
# I'll mark centers and then extract 200x200 boxes around them

castles = [
    # (center_x, center_y, label)
    (205, 145, "C1-Blue"),     # Top-left blue castle
    (390, 105, "C2-Blue-Mid"), # Mid-left blue castle
    (590, 110, "C3-Pink-Top"), # Top pink castle
    (590, 230, "C4-Pink-Bot"), # Bottom pink castle
    (745, 110, "C5-Blue-Top"), # Top-right area blue
    (965, 105, "C6-Blue-Mid"), # Mid-right blue
    (1165, 240, "C7-Blue-R"),  # Right blue castle with 22
]

# Draw all potential castles
for cx, cy, label in castles:
    # Draw center point
    cv2.circle(vis, (cx, cy), 5, (0, 255, 0), -1)
    # Draw bounding box (200x200 centered)
    x1, y1 = cx - 100, cy - 100
    x2, y2 = cx + 100, cy + 100
    cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
    cv2.putText(vis, label, (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

cv2.imwrite(r'C:\Users\mail\xclash\castle_centers.png', vis)
print(f"Saved visualization with {len(castles)} potential castles")
