import cv2
import numpy as np
world = cv2.imread('templates/buttons/world_button_template.png')
town = cv2.imread('templates/buttons/town_button_template.png')
diff = cv2.absdiff(world, town)
h, w = diff.shape[:2]
left = diff[:, : w // 2]
right = diff[:, w // 2 :]
print('left mean', left.mean(axis=(0,1)))
print('right mean', right.mean(axis=(0,1)))
