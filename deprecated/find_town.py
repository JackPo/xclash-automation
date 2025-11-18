#!/usr/bin/env python3
"""
Simple script: Find "Town" text in lower right corner.
"""

from PIL import Image
import pytesseract
from find_player import ADBController, Config

def find_town():
    # Setup
    config = Config()
    adb = ADBController(config)
    pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

    # Take screenshot
    print("Taking screenshot...")
    screenshot_path = "screenshot_town.png"
    adb.screenshot(screenshot_path)

    # Open image
    img = Image.open(screenshot_path)
    width, height = img.size

    # Crop lower right corner (last 400x200 pixels)
    crop_box = (width - 400, height - 200, width, height)
    corner = img.crop(crop_box)
    corner.save("corner_town.png")

    print(f"Image size: {width}x{height}")
    print(f"Cropped corner: {crop_box}")

    # OCR the corner
    print("\nRunning OCR on lower right corner...")
    ocr_data = pytesseract.image_to_data(corner, output_type=pytesseract.Output.DICT)

    # Find "Town"
    found = False
    n_boxes = len(ocr_data['text'])
    for i in range(n_boxes):
        text = ocr_data['text'][i].strip()
        conf = int(ocr_data['conf'][i])

        if text and conf > 30:
            # Adjust coordinates back to full screen
            x = ocr_data['left'][i] + (width - 400)
            y = ocr_data['top'][i] + (height - 200)
            w = ocr_data['width'][i]
            h = ocr_data['height'][i]

            print(f"  [{conf:3d}%] at ({x:4d}, {y:4d}): '{text}'")

            if "TOWN" in text.upper() or "WORLD" in text.upper():
                print(f"\n*** FOUND '{text}' ***")
                print(f"    Coordinates: ({x}, {y})")
                print(f"    Size: {w}x{h}")
                print(f"    Confidence: {conf}%")
                print(f"    Center: ({x + w//2}, {y + h//2})")
                found = True

    if not found:
        print("\nTown/World not found. Check corner_town.png")

    print(f"\nScreenshots saved:")
    print(f"  - screenshot_town.png (full)")
    print(f"  - corner_town.png (lower right)")

if __name__ == "__main__":
    find_town()
