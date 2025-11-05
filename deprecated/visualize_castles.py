import cv2
import numpy as np

# Read the source image
img = cv2.imread(r'C:\Users\mail\xclash\after_8_zooms.png')
print(f"Source image size: {img.shape}")

# Create a copy for visualization
vis = img.copy()

# Based on the image, I can see several castles. Let me mark potential regions
# Image is 1440 height x 2560 width

# Castle candidates (approximate centers and boxes)
# Top-left blue castle
cv2.rectangle(vis, (130, 80), (280, 240), (0, 255, 0), 2)
cv2.putText(vis, "C1", (130, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

# Center-top pink castle
cv2.rectangle(vis, (520, 60), (670, 220), (0, 255, 0), 2)
cv2.putText(vis, "C2", (520, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

# Second pink castle below first
cv2.rectangle(vis, (520, 180), (670, 340), (0, 255, 0), 2)
cv2.putText(vis, "C3", (520, 175), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

# Top-right blue castle
cv2.rectangle(vis, (900, 80), (1050, 240), (0, 255, 0), 2)
cv2.putText(vis, "C4", (900, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

# Right side blue castle with level 22
cv2.rectangle(vis, (1090, 190), (1240, 350), (0, 255, 0), 2)
cv2.putText(vis, "C5", (1090, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

# Bottom center small castle
cv2.rectangle(vis, (570, 630), (690, 760), (0, 255, 0), 2)
cv2.putText(vis, "C6", (570, 625), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

cv2.imwrite(r'C:\Users\mail\xclash\castle_positions.png', vis)
print("Saved visualization to castle_positions.png")
