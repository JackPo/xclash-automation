import cv2
import numpy as np
world = cv2.imread('templates/buttons/world_button_template.png')
town = cv2.imread('templates/buttons/town_button_template.png')
if world is None or town is None:
    raise SystemExit('missing templates')
diff = cv2.absdiff(world, town)
cv2.imwrite('templates/debug/testing/world_town_diff.png', diff)
print('diff saved, mean', diff.mean())
