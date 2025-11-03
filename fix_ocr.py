#!/usr/bin/env python3
"""
Fix OCR with preprocessing
"""

from PIL import Image, ImageEnhance, ImageOps
import pytesseract
from find_player import ADBController, Config

def fix_ocr():
    config = Config()
    adb = ADBController(config)
    pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

    # Take screenshot
    print("Taking screenshot...")
    adb.screenshot("screenshot_fix.png")

    img = Image.open("screenshot_fix.png")
    width, height = img.size

    # Crop lower right
    crop_box = (width - 400, height - 200, width, height)
    corner = img.crop(crop_box)
    corner.save("corner_original.png")

    print(f"Original size: {corner.size}")

    # Try different preprocessing
    tests = [
        ("original", corner),
        ("grayscale", corner.convert('L')),
        ("contrast_2x", ImageEnhance.Contrast(corner.convert('L')).enhance(2)),
        ("contrast_3x", ImageEnhance.Contrast(corner.convert('L')).enhance(3)),
        ("sharpness_2x", ImageEnhance.Sharpness(corner.convert('L')).enhance(2)),
    ]

    for name, test_img in tests:
        test_img.save(f"test_{name}.png")

        print(f"\n=== TEST: {name} ===")

        # Try different PSM modes
        for psm in [3, 6, 7, 11]:
            custom_config = f'--psm {psm}'
            text = pytesseract.image_to_string(test_img, config=custom_config)
            text = text.strip()
            if text:
                print(f"  PSM {psm}: '{text}'")
                if "WORLD" in text.upper() or "TOWN" in text.upper():
                    print(f"  *** FOUND IT with {name} + PSM {psm} ***")

if __name__ == "__main__":
    fix_ocr()
