import cv2
import numpy as np
from pathlib import Path
img = np.full((250, 400, 3), 200, dtype=np.uint8)
path = Path('templates/debug/testing/roi/blank.png')
path.parent.mkdir(parents=True, exist_ok=True)
cv2.imwrite(str(path), img)
print(path)
