#!/usr/bin/env python3
from pathlib import Path
import cv2

paths = [Path("templates/debug/adb_temp_cli.png")]
paths += sorted(Path("templates/debug/testing").glob("*.png"))

for p in paths:
    img = cv2.imread(str(p))
    if img is None:
        continue
    h, w = img.shape[:2]
    print(f"{p} shape=({h},{w})")
