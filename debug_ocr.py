#!/usr/bin/env python3
"""
Debug OCR - see exactly what Tesseract detects
"""

from PIL import Image
import pytesseract
from find_player import ADBController, Config

def debug_ocr():
    config = Config()
    adb = ADBController(config)
    pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

    # Take screenshot
    print("Taking screenshot...")
    adb.screenshot("screenshot_debug.png")

    img = Image.open("screenshot_debug.png")
    width, height = img.size

    # Crop lower right
    crop_box = (width - 400, height - 200, width, height)
    corner = img.crop(crop_box)
    corner.save("corner_debug.png")

    print(f"\nImage size: {corner.size}")
    print("\n=== SIMPLE OCR ===")
    text = pytesseract.image_to_string(corner)
    print(repr(text))

    print("\n=== DETAILED OCR ===")
    data = pytesseract.image_to_data(corner, output_type=pytesseract.Output.DICT)

    n_boxes = len(data['text'])
    for i in range(n_boxes):
        txt = data['text'][i]
        conf = int(data['conf'][i])
        if txt.strip():
            x = data['left'][i]
            y = data['top'][i]
            w = data['width'][i]
            h = data['height'][i]
            print(f"[{conf:3d}%] at ({x:4d},{y:4d}) size ({w}x{h}): '{txt}'")

if __name__ == "__main__":
    debug_ocr()
