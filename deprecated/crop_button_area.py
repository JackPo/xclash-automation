"""Crop just the button area from the screenshot"""
import cv2

# Read the full screenshot
img = cv2.imread("test_toggle_before.png")

# Button bounds: (2160, 1190) to (2560, 1440)
padding = 100
x1 = max(0, 2160 - padding)
y1 = max(0, 1190 - padding)
x2 = min(img.shape[1], 2560 + padding)
y2 = min(img.shape[0], 1440 + padding)

cropped = img[y1:y2, x1:x2]

cv2.imwrite("button_area_cropped.png", cropped)
print(f"Cropped button area saved to: button_area_cropped.png")
print(f"Size: {cropped.shape[1]}x{cropped.shape[0]}")
