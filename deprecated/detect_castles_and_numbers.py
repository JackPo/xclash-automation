#!/usr/bin/env python3
"""
Detect castle icons and extract number labels for OCR.

This approach:
1. Detects white/gray castle icons using color thresholding
2. Extracts the number region below each castle
3. OCRs each number cutout individually for better accuracy
"""

import cv2
import numpy as np
from PIL import Image
import pytesseract
from pathlib import Path

# Configure Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def detect_castles(image_path='rightnow.png', debug=True):
    """
    Detect castle icons using color-based detection.

    Returns: list of (x, y, width, height) bounding boxes for each castle
    """
    # Load image
    img = cv2.imread(image_path)
    if img is None:
        print(f"ERROR: Could not load {image_path}")
        return []

    height, width = img.shape[:2]
    print(f"Image size: {width}x{height}")

    # Convert to HSV for better color detection
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Define range for white/gray castles - stricter range
    # Castles are very light gray/white with low saturation
    lower_gray = np.array([0, 0, 180])  # Higher value threshold
    upper_gray = np.array([180, 40, 255])  # Lower saturation threshold

    # Create mask for castle colors
    mask = cv2.inRange(hsv, lower_gray, upper_gray)

    # Apply morphological operations to clean up mask
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter contours by size (castles should be roughly 35-70 pixels wide)
    castle_boxes = []
    EDGE_MARGIN = 100  # Ignore detections within 100px of screen edge

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)

        # Filter out edge cases - castles shouldn't be at screen edges
        if x < EDGE_MARGIN or y < EDGE_MARGIN:
            continue
        if x + w > width - EDGE_MARGIN or y + h > height - EDGE_MARGIN:
            continue

        # Stricter filtering - castles are more square and consistent size
        if 35 <= w <= 70 and 35 <= h <= 70:
            # Must be more square
            aspect_ratio = float(w) / h
            if 0.7 <= aspect_ratio <= 1.4:
                # Must have decent area (not just a tiny speck)
                if cv2.contourArea(contour) > 500:
                    castle_boxes.append((x, y, w, h))

    print(f"\nDetected {len(castle_boxes)} potential castles")

    if debug:
        # Save debug image showing detected castles
        debug_img = img.copy()
        for x, y, w, h in castle_boxes:
            cv2.rectangle(debug_img, (x, y), (x+w, y+h), (0, 255, 0), 2)

        debug_path = image_path.replace('.png', '_castle_detection.png')
        cv2.imwrite(debug_path, debug_img)
        print(f"Debug image saved: {debug_path}")

    return castle_boxes

def extract_number_cutouts(image_path, castle_boxes, output_dir='castle_cutouts'):
    """
    Extract the number region below each castle.

    Returns: list of (cutout_image, x, y, castle_index)
    """
    # Load original image
    img = Image.open(image_path)

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    cutouts = []

    for idx, (cx, cy, cw, ch) in enumerate(castle_boxes):
        # Define cutout region: castle + number label below
        # Start at TOP of castle, extend down to include full label
        num_x = cx - 5   # Extend left slightly
        num_y = cy       # Start at TOP of castle
        num_w = cw + 10  # Extend width
        num_h = ch + 50  # Castle height + label below

        # Ensure coordinates are within image bounds
        num_x = max(0, num_x)
        num_y = max(0, num_y)
        num_x2 = min(img.width, num_x + num_w)
        num_y2 = min(img.height, num_y + num_h)

        # Extract cutout
        cutout = img.crop((num_x, num_y, num_x2, num_y2))

        # Save only the original cutout
        cutout_path = output_path / f"castle_{idx:03d}_{cx}_{cy}.png"
        cutout.save(cutout_path)

        cutouts.append((cutout, cx, cy, idx))

    print(f"\nExtracted {len(cutouts)} number cutouts to {output_dir}/")

    return cutouts

def ocr_number_cutouts(cutouts):
    """
    Run OCR on each number cutout.

    Returns: list of (level, confidence, x, y, castle_index)
    """
    results = []

    print(f"\nRunning OCR on {len(cutouts)} cutouts...")

    for cutout_img, cx, cy, idx in cutouts:
        # Scale up 4x for OCR (but don't save it)
        scaled = cutout_img.resize(
            (cutout_img.width * 4, cutout_img.height * 4),
            Image.Resampling.LANCZOS
        )

        # PSM 8 for single word/number
        config = r'--psm 8 --oem 3 -c tessedit_char_whitelist=0123456789'

        try:
            text = pytesseract.image_to_string(scaled, config=config).strip()

            # Try to parse as number
            if text and text.isdigit():
                level = int(text)
                if 1 <= level <= 30:
                    # Get confidence
                    data = pytesseract.image_to_data(scaled, config=config, output_type=pytesseract.Output.DICT)
                    confidences = [c for c in data['conf'] if c > 0]
                    avg_conf = sum(confidences) / len(confidences) if confidences else 0

                    results.append((level, avg_conf, cx, cy, idx))
                    print(f"  Castle {idx:03d} @ ({cx},{cy}): Level {level} ({avg_conf:.0f}% conf)")
        except Exception as e:
            pass  # Skip failed OCR attempts

    print(f"\nSuccessfully OCR'd {len(results)} castle levels")

    return results

def main():
    image_path = 'rightnow.png'

    print("="*60)
    print("CASTLE DETECTION AND LEVEL EXTRACTION")
    print("="*60)

    # Step 1: Detect castles
    castle_boxes = detect_castles(image_path, debug=True)

    if not castle_boxes:
        print("\nNo castles detected! Try adjusting detection parameters.")
        return

    # Step 2: Extract number cutouts
    cutouts = extract_number_cutouts(image_path, castle_boxes)

    # Step 3: OCR each cutout
    results = ocr_number_cutouts(cutouts)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY:")
    print(f"{'='*60}")
    print(f"Total castles detected: {len(castle_boxes)}")
    print(f"Successfully read levels: {len(results)}")
    print(f"Success rate: {len(results)/len(castle_boxes)*100:.1f}%")

    # Find level 20+
    level20plus = [r for r in results if r[0] >= 20]
    if level20plus:
        print(f"\n{'='*60}")
        print(f"LEVEL 20+ CASTLES FOUND: {len(level20plus)}")
        print(f"{'='*60}")
        for level, conf, cx, cy, idx in level20plus:
            print(f"  Castle {idx:03d}: Level {level} @ ({cx},{cy}) - {conf:.0f}% confidence")

if __name__ == '__main__':
    main()
