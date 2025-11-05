import cv2
from pathlib import Path
for path in sorted(Path('.').glob('template_*.png')):
    img = cv2.imread(str(path))
    if img is None:
        continue
    h, w = img.shape[:2]
    print(f"{path.name}: ({h}, {w})")
