#!/usr/bin/env python3
"""
Test OCR on current zoom level screenshot to detect castle numbers.
"""

from PIL import Image, ImageDraw, ImageFont
import pytesseract

# Configure Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def annotate_and_test_ocr(image_path='rightnow.png'):
    """Annotate screenshot and test OCR for castle numbers"""

    img = Image.open(image_path)
    width, height = img.size
    print(f"Image size: {width}x{height}")

    # Define OCR region for castle numbers
    # Exclude: left edge (50px), right minimap (last 400px), top bar (80px), bottom UI (100px)
    left = 50
    top = 80
    right = width - 400  # Exclude minimap area
    bottom = height - 100  # Exclude bottom UI

    print(f"\nOCR Region: ({left}, {top}) to ({right}, {bottom})")
    print(f"Region size: {right-left}x{bottom-top} pixels")

    # Crop to OCR region
    ocr_region = img.crop((left, top, right, bottom))

    # Scale up 4x to make numbers more readable
    new_size = (ocr_region.width * 4, ocr_region.height * 4)
    ocr_region_scaled = ocr_region.resize(new_size, Image.Resampling.LANCZOS)

    print(f"Scaled to: {ocr_region_scaled.width}x{ocr_region_scaled.height}")

    # Run OCR with different config
    print("\nRunning Tesseract OCR...")

    # Try with PSM 6 (uniform block) which works better for small text
    custom_config = r'--psm 6 --oem 3 -c tessedit_char_whitelist=0123456789'
    all_text = pytesseract.image_to_string(ocr_region_scaled, config=custom_config)

    print(f"\nAll OCR text detected (first 500 chars):\n{all_text[:500]}")

    ocr_data = pytesseract.image_to_data(ocr_region_scaled, config=custom_config, output_type=pytesseract.Output.DICT)

    # Debug: print all detected text
    print("\nAll OCR detections:")
    for i, text in enumerate(ocr_data['text']):
        if text.strip():
            conf = ocr_data['conf'][i]
            print(f"  '{text}' - conf: {conf}")

    # Find castle level numbers (1-30)
    castle_levels = []
    for i, text in enumerate(ocr_data['text']):
        if text.strip() and text.isdigit():
            num = int(text)
            if 1 <= num <= 30:
                conf = ocr_data['conf'][i]
                # Accept any confidence, even negative
                x = ocr_data['left'][i]
                y = ocr_data['top'][i]
                castle_levels.append((num, conf, x, y))

    # Sort by number
    castle_levels.sort()

    print(f"\n{'='*60}")
    print(f"CASTLE LEVELS DETECTED: {len(castle_levels)}")
    print(f"{'='*60}")

    # Count occurrences
    level_counts = {}
    for num, conf, x, y in castle_levels:
        level_counts[num] = level_counts.get(num, 0) + 1
        print(f"  Level {num:2d} @ ({x:4d},{y:4d}) - confidence: {conf:.0f}%")

    print(f"\n{'='*60}")
    print("SUMMARY BY LEVEL:")
    print(f"{'='*60}")
    for level in sorted(level_counts.keys()):
        count = level_counts[level]
        marker = " <<<" if level >= 20 else ""
        print(f"  Level {level:2d}: {count:2d} castle(s){marker}")

    # Find level 20+ castles
    level20plus = [num for num, _, _, _ in castle_levels if num >= 20]
    print(f"\n{'='*60}")
    print(f"LEVEL 20+ CASTLES FOUND: {len(level20plus)}")
    print(f"{'='*60}")
    if level20plus:
        print(f"Levels detected: {sorted(set(level20plus))}")
    else:
        print("No level 20+ castles in current view")

    # Create annotated image
    img_annotated = img.copy()
    draw = ImageDraw.Draw(img_annotated)

    # Draw OCR region boundary
    for offset in range(4):
        draw.rectangle(
            [left + offset, top + offset, right - offset, bottom - offset],
            outline='red'
        )

    # Add label
    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except:
        font = None

    draw.text((left + 10, top + 10), "OCR REGION", fill='red', font=font)
    draw.text((left + 10, bottom - 40), f"Detected {len(castle_levels)} castles", fill='yellow', font=font)

    # Mark level 20+ castles on image
    for num, conf, x, y in castle_levels:
        if num >= 20:
            # Draw circle around level 20+ numbers
            abs_x = left + x
            abs_y = top + y
            radius = 30
            for r in range(3):
                draw.ellipse(
                    [abs_x - radius + r, abs_y - radius + r,
                     abs_x + radius - r, abs_y + radius - r],
                    outline='lime'
                )

    # Save annotated image
    output_path = image_path.replace('.png', '_ocr_test.png')
    img_annotated.save(output_path)

    print(f"\n{'='*60}")
    print(f"Annotated image saved: {output_path}")
    print(f"{'='*60}\n")

    return castle_levels

if __name__ == '__main__':
    castle_levels = annotate_and_test_ocr()
