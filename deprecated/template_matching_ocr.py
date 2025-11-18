#!/usr/bin/env python3
"""
Template matching OCR for castle level numbers.
Uses OpenCV template matching with digit templates extracted from game UI.
"""

import cv2
import numpy as np
from pathlib import Path
from PIL import Image

# Ground truth for testing
GROUND_TRUTH = {
    '000_1643_1221': 13, '001_1098_1198': 3, '002_1943_1082': 3, '003_1841_1082': 5,
    '004_1572_1082': 3, '005_1705_1013': 4, '006_831_989': 4, '007_1134_922': 3,
    '008_1701_899': 3, '009_1267_854': 10, '010_1566_831': 3, '011_437_823': 7,
    '012_936_809': 3, '013_1200_787': 5, '014_836_787': 4, '015_1829_765': 15,
    '016_969_743': 3, '017_738_743': 3, '018_774_678': 3, '019_1136_656': 3,
    '020_941_547': 3, '021_1494_526': 5, '022_1944_420': 4, '023_172_378': 4,
    '024_1909_356': 2, '025_1138_356': 4, '026_817_336': 3, '027_1807_211': 5,
    '028_1203_191': 3, '029_980_191': 4, '030_1867_109': 3, '031_160_109': 5,
}

# Template sources (castle_id: expected_digits_string)
TEMPLATE_SOURCES = {
    0: ('026_817_336', 17, 8),   # Has '3'
    1: ('015_1829_765', 12, 8),  # Has '15' - extract '1'
    2: ('024_1909_356', 17, 8),  # Has '2'
    3: ('001_1098_1198', 17, 8),  # Has '3'
    4: ('005_1705_1013', 17, 8),  # Has '4'
    5: ('003_1841_1082', 17, 8),  # Has '5'
    # 6: Need to find
    7: ('011_437_823', 17, 8),   # Has '7'
    # 8: Need to find
    # 9: Need to find
}

def extract_label_region(image_path):
    """Extract just the number label (bottom portion)"""
    img = Image.open(image_path)
    label_height = 30
    label = img.crop((0, img.height - label_height, img.width, img.height))
    return np.array(label)

def create_digit_templates():
    """Create templates for digits 0-9 by extracting from known samples"""
    templates = {}
    cutouts_dir = Path("castle_cutouts")

    print("Creating digit templates...")

    # For each digit, extract template from a known good sample
    for digit in [0, 1, 2, 3, 4, 5, 7]:
        if digit not in TEMPLATE_SOURCES:
            continue

        castle_id, x_offset, width = TEMPLATE_SOURCES[digit]
        castle_file = None

        # Find the file
        for f in cutouts_dir.glob(f"castle_*{castle_id}.png"):
            castle_file = f
            break

        if not castle_file:
            print(f"  Warning: Could not find sample for digit {digit}")
            continue

        # Extract label region
        label = extract_label_region(castle_file)

        # Convert to grayscale
        gray = cv2.cvtColor(label, cv2.COLOR_RGB2GRAY)

        # Extract the digit region (manually specified)
        digit_template = gray[:, x_offset:x_offset+width]

        templates[digit] = digit_template

        # Save template for inspection
        cv2.imwrite(f'template_{digit}.png', digit_template)
        print(f"  Created template for digit {digit}: {digit_template.shape}")

    # For missing digits, create synthetic or use best guess
    # Digit 1 from '15' (castle 015)
    if 1 not in templates:
        castle_file = None
        for f in cutouts_dir.glob(f"castle_*015_1829_765.png"):
            castle_file = f
            break
        if castle_file:
            label = extract_label_region(castle_file)
            gray = cv2.cvtColor(label, cv2.COLOR_RGB2GRAY)
            digit_template = gray[:, 12:18]  # Extract '1' from '15'
            templates[1] = digit_template
            cv2.imwrite(f'template_1.png', digit_template)
            print(f"  Created template for digit 1: {digit_template.shape}")

    # Digit 0 from '10' (castle 009)
    if 0 not in templates:
        castle_file = None
        for f in cutouts_dir.glob(f"castle_*009_1267_854.png"):
            castle_file = f
            break
        if castle_file:
            label = extract_label_region(castle_file)
            gray = cv2.cvtColor(label, cv2.COLOR_RGB2GRAY)
            digit_template = gray[:, 20:28]  # Extract '0' from '10'
            templates[0] = digit_template
            cv2.imwrite(f'template_0.png', digit_template)
            print(f"  Created template for digit 0: {digit_template.shape}")

    return templates

def match_digit(image_gray, templates, method=cv2.TM_CCOEFF_NORMED):
    """Find best matching digit for an image region"""
    best_digit = -1
    best_score = -1

    for digit, template in templates.items():
        # Try multiple scales
        for scale in [0.8, 0.9, 1.0, 1.1, 1.2]:
            h, w = template.shape
            new_h, new_w = int(h * scale), int(w * scale)

            if new_h > image_gray.shape[0] or new_w > image_gray.shape[1]:
                continue

            resized_template = cv2.resize(template, (new_w, new_h))

            # Template matching
            result = cv2.matchTemplate(image_gray, resized_template, method)
            _, max_val, _, _ = cv2.minMaxLoc(result)

            if max_val > best_score:
                best_score = max_val
                best_digit = digit

    return best_digit, best_score

def recognize_number(image_path, templates):
    """Recognize 1-2 digit number from castle cutout"""
    # Extract label region
    label = extract_label_region(image_path)
    gray = cv2.cvtColor(label, cv2.COLOR_RGB2GRAY)

    # Apply threshold to isolate black digits
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)

    # Find contours (each digit should be a contour)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter and sort contours left to right
    digit_contours = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        # Filter out noise (too small or at edges)
        if w > 4 and h > 8 and x > 2 and x + w < gray.shape[1] - 2:
            digit_contours.append((x, y, w, h))

    # Sort left to right
    digit_contours.sort(key=lambda c: c[0])

    if not digit_contours:
        return None, 0

    # Recognize each digit
    digits = []
    confidences = []

    for x, y, w, h in digit_contours:
        # Extract digit region with some padding
        x1 = max(0, x - 2)
        x2 = min(gray.shape[1], x + w + 2)
        y1 = max(0, y - 2)
        y2 = min(gray.shape[0], y + h + 2)

        digit_img = gray[y1:y2, x1:x2]

        # Match against templates
        digit, confidence = match_digit(digit_img, templates)

        if digit != -1:
            digits.append(digit)
            confidences.append(confidence)

    if not digits:
        return None, 0

    # Combine digits into number
    number = 0
    for d in digits:
        number = number * 10 + d

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    return number, avg_confidence

def test_template_matching():
    """Test template matching on all castle cutouts"""
    print("\n" + "="*60)
    print("TEMPLATE MATCHING OCR TEST")
    print("="*60)

    # Create templates
    templates = create_digit_templates()

    if not templates:
        print("ERROR: No templates created!")
        return

    print(f"\nCreated {len(templates)} digit templates")
    print(f"Testing on 32 castle cutouts...\n")

    cutouts_dir = Path("castle_cutouts")
    correct = 0
    total = 0

    for cutout_path in sorted(cutouts_dir.glob("castle_*.png")):
        # Get castle ID
        stem = cutout_path.stem
        parts = stem.split('_')
        castle_id = f"{parts[1]}_{parts[2]}_{parts[3]}"
        expected = GROUND_TRUTH[castle_id]

        # Recognize number
        detected, confidence = recognize_number(cutout_path, templates)

        total += 1
        if detected == expected:
            correct += 1
            print(f"OK {castle_id}: {detected} (confidence: {confidence:.2f})")
        else:
            print(f"FAIL {castle_id}: {detected} (expected {expected}, confidence: {confidence:.2f})")

    accuracy = (correct / total) * 100 if total > 0 else 0

    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"{'='*60}")
    print(f"Accuracy: {correct}/{total} = {accuracy:.1f}%")
    print(f"Method: Template Matching (OpenCV)")

    return accuracy

if __name__ == '__main__':
    import time
    start = time.time()
    accuracy = test_template_matching()
    elapsed = time.time() - start
    print(f"Time: {elapsed:.2f}s ({elapsed/32:.3f}s per image)")
