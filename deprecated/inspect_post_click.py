import cv2
import numpy as np
from pathlib import Path

path = Path("templates/debug/testing/post_click.png")
img = cv2.imread(str(path))
if img is None:
    print("missing screenshot")
    raise SystemExit

print("shape:", img.shape)
# Save ROI around bottom right for inspection
h, w = img.shape[:2]
roi = img[h - 400 : h, w - 400 : w]
cv2.imwrite("templates/debug/testing/post_click_roi.png", roi)
print("saved ROI to templates/debug/testing/post_click_roi.png")
