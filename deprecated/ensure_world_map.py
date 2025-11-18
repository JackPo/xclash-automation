#!/usr/bin/env python3
"""
Ensure we're on World map view.
- If button says "World" -> click it (switch to World map)
- If button says "Town" -> already on World map, do nothing
"""

from PIL import Image
import pytesseract
import time
from find_player import ADBController, Config

def ensure_world_map():
    # Setup
    config = Config()
    adb = ADBController(config)
    pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

    # Take screenshot
    print("Taking screenshot...")
    screenshot_path = "screenshot_check.png"
    adb.screenshot(screenshot_path)

    # Open image
    img = Image.open(screenshot_path)
    width, height = img.size

    # Crop lower right corner
    crop_box = (width - 400, height - 200, width, height)
    corner = img.crop(crop_box)
    corner.save("corner_check.png")

    # OCR the corner with PSM 6 (single uniform block)
    print("Checking corner...")
    custom_config = '--psm 6'
    simple_text = pytesseract.image_to_string(corner, config=custom_config)
    print(f"OCR result: '{simple_text.strip()}'")

    ocr_data = pytesseract.image_to_data(corner, config=custom_config, output_type=pytesseract.Output.DICT)

    # Find World or Town
    found_world = False
    found_town = False
    click_x = None
    click_y = None

    n_boxes = len(ocr_data['text'])
    for i in range(n_boxes):
        text = ocr_data['text'][i].strip()
        conf = int(ocr_data['conf'][i])

        if text and conf > 0:  # Show ALL detections
            # Adjust coordinates to full screen
            x = ocr_data['left'][i] + (width - 400)
            y = ocr_data['top'][i] + (height - 200)
            w = ocr_data['width'][i]
            h = ocr_data['height'][i]

            print(f"  [{conf:3d}%] at ({x}, {y}): '{text}'")

            if "WORLD" in text.upper():
                found_world = True
                click_x = x + w // 2
                click_y = y + h // 2
                print(f"  -> Found WORLD button")

            if "TOWN" in text.upper():
                found_town = True
                print(f"  -> Found TOWN button")

    # Decision logic
    if found_world:
        print(f"\n==> Button says 'World' - we're in Town view")
        print(f"==> Clicking at ({click_x}, {click_y}) to switch to World map...")
        adb.tap(click_x, click_y)
        time.sleep(2)
        print("==> Switched to World map!")
        return True

    elif found_town:
        print(f"\n==> Button says 'Town' - already on World map!")
        print("==> No action needed")
        return True

    else:
        print("\n==> ERROR: Could not find World or Town button")
        print("==> Check corner_check.png")
        return False

if __name__ == "__main__":
    success = ensure_world_map()
    exit(0 if success else 1)
