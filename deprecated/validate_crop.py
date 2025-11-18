#!/usr/bin/env python3
"""
Validator helper: Crop and save for validation
"""
import sys
from PIL import Image

if len(sys.argv) < 6:
    print("Usage: python validate_crop.py <input> <x> <y> <w> <h>")
    sys.exit(1)

input_path = sys.argv[1]
x = int(sys.argv[2])
y = int(sys.argv[3])
w = int(sys.argv[4])
h = int(sys.argv[5])

img = Image.open(input_path)
cropped = img.crop((x, y, x + w, y + h))
cropped.save('temp_validation_crop.png')
print(f"Cropped {w}x{h} region from ({x}, {y}) to temp_validation_crop.png")
print(f"Image size: {cropped.size}")
