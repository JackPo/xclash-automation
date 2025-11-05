#!/usr/bin/env python3
"""
Test PaddleOCR rec-only mode with proper preprocessing.
Extract white pill label, apply Otsu thresholding, then recognize.
"""

import cv2
import numpy as np
from pathlib import Path
from PIL import Image
from paddleocr import TextRecognition
import time

# Ground truth
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

def extract_pill_label(image_path, debug=False):
    """
    Extract and preprocess the label region from bottom of castle cutout.
    Simpler approach: just extract bottom region and preprocess.
    """
    # Load image
    img = cv2.imread(str(image_path))
    if img is None:
        return None

    # Extract bottom 30 pixels (where label is)
    height = img.shape[0]
    label_region = img[height-30:height, :]

    # Convert to grayscale
    gray = cv2.cvtColor(label_region, cv2.COLOR_BGR2GRAY)

    # Apply Otsu thresholding to separate text from background
    # THRESH_BINARY_INV makes text white, background black
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Invert so text is black on white (standard for OCR)
    processed = cv2.bitwise_not(binary)

    if debug:
        # Save intermediate steps
        cv2.imwrite('debug_label_gray.png', gray)
        cv2.imwrite('debug_label_binary.png', binary)
        cv2.imwrite('debug_label_processed.png', processed)

    return processed

def test_paddle_rec_only():
    """Test PaddleOCR in rec-only mode on all castle cutouts"""

    print("="*60)
    print("PADDLEOCR REC-ONLY MODE TEST")
    print("="*60)

    # Initialize TextRecognition (rec-only mode)
    print("\nInitializing TextRecognition (rec-only mode)...")
    ocr = TextRecognition()

    correct = 0
    total = 0
    start_time = time.time()

    cutouts_dir = Path("castle_cutouts")

    for cutout_path in sorted(cutouts_dir.glob("castle_*.png")):
        # Get castle ID
        parts = cutout_path.stem.split('_')
        castle_id = f"{parts[1]}_{parts[2]}_{parts[3]}"
        expected = GROUND_TRUTH[castle_id]

        # Extract and preprocess pill label
        pill = extract_pill_label(cutout_path, debug=(castle_id == '001_1098_1198'))

        if pill is None:
            print(f"FAIL {castle_id}: No pill extracted (expected {expected})")
            total += 1
            continue

        # Scale up the pill 6x for better OCR recognition
        pill_scaled = cv2.resize(pill, None, fx=6, fy=6, interpolation=cv2.INTER_LANCZOS4)

        # Save preprocessed pill temporarily
        temp_path = "temp_pill.png"
        cv2.imwrite(temp_path, pill_scaled)

        # Run text recognition
        result = ocr.predict(temp_path)

        detected = None
        if result and len(result) > 0:
            text = str(result[0]['rec_text'])
            # Clean up - extract digits only
            text_clean = ''.join(c for c in text if c.isdigit())
            if text_clean.isdigit():
                detected = int(text_clean)
                if not (1 <= detected <= 30):
                    detected = None

        total += 1
        if detected == expected:
            correct += 1
            print(f"OK {castle_id}: {detected}")
        else:
            print(f"FAIL {castle_id}: {detected} (expected {expected})")

    elapsed = time.time() - start_time
    accuracy = (correct / total) * 100 if total > 0 else 0

    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"{'='*60}")
    print(f"Accuracy: {correct}/{total} = {accuracy:.1f}%")
    print(f"Time: {elapsed:.2f}s ({elapsed/total:.3f}s per image)")
    print(f"Method: PaddleOCR rec-only + preprocessing")

    return accuracy

if __name__ == '__main__':
    accuracy = test_paddle_rec_only()
