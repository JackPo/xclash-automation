import cv2
import numpy as np

img = cv2.imread('templates/debug/testing/roi/button_test_1_20251103_123807_roi.png')
if img is None:
    raise SystemExit('missing roi')

h, w = img.shape[:2]
left = img[:, : w // 2]
right = img[:, w // 2 :]

print('left mean BGR', left.mean(axis=(0, 1)))
print('right mean BGR', right.mean(axis=(0, 1)))
