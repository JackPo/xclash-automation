import cv2
import numpy as np
from pathlib import Path
for name in ['button_test_1_20251103_123807_roi.png', 'latest_attempt_roi.png']:
    path = Path('templates/debug/testing/roi') / name
    img = cv2.imread(str(path))
    if img is None:
        print(name, 'missing')
        continue
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 170, 255, cv2.THRESH_BINARY)
    ys, xs = np.where(thresh > 0)
    print(name, 'width', img.shape[1], 'height', img.shape[0])
    if len(xs) == 0:
        print('  no bright areas')
        continue
    print('  x range', xs.min(), xs.max(), 'mean', xs.mean())
    print('  y range', ys.min(), ys.max(), 'mean', ys.mean())
