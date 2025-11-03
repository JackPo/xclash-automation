#!/usr/bin/env python3
"""
Comprehensive test of multiple OCR methods for castle level numbers.
Tests against ground truth from castle_database.csv.
"""

import os
import csv
import time
from pathlib import Path
from PIL import Image
import cv2
import numpy as np

# Ground truth from manual reading
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

results = []

def extract_label_region(image_path):
    """Extract just the number label (bottom ~30% of cutout)"""
    img = Image.open(image_path)
    # Label is in bottom portion
    label_height = 30
    label = img.crop((0, img.height - label_height, img.width, img.height))
    return label

def get_castle_id(filename):
    """Extract castle ID from filename: castle_XXX_x_y.png -> XXX_x_y"""
    stem = Path(filename).stem  # Remove .png
    parts = stem.split('_')  # ['castle', 'XXX', 'x', 'y']
    return f"{parts[1]}_{parts[2]}_{parts[3]}"

# ============================================================================
# METHOD 1: OPTIMIZED TESSERACT
# ============================================================================
def test_tesseract_optimized():
    """Test Tesseract with optimal preprocessing and configs"""
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    print("\n" + "="*60)
    print("METHOD 1: TESSERACT (Optimized)")
    print("="*60)

    correct = 0
    total = 0
    start_time = time.time()

    cutouts_dir = Path("castle_cutouts")

    for cutout_path in sorted(cutouts_dir.glob("castle_*.png")):
        castle_id = get_castle_id(cutout_path.name)
        expected = GROUND_TRUTH[castle_id]

        # Extract label region
        label = extract_label_region(cutout_path)

        # Convert to OpenCV
        img_cv = cv2.cvtColor(np.array(label), cv2.COLOR_RGB2BGR)

        # Scale 6x
        img_cv = cv2.resize(img_cv, None, fx=6, fy=6, interpolation=cv2.INTER_LANCZOS4)

        # Grayscale
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        # Try different PSM modes
        configs = [
            '--psm 10 --oem 3 -c tessedit_char_whitelist=0123456789',  # Single char
            '--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789',   # Single line
            '--psm 8 --oem 3 -c tessedit_char_whitelist=0123456789',   # Single word
            '--psm 6 --oem 3 -c tessedit_char_whitelist=0123456789',   # Block of text
        ]

        detected = None
        for config in configs:
            text = pytesseract.image_to_string(Image.fromarray(gray), config=config).strip()
            if text.isdigit():
                detected = int(text)
                if 1 <= detected <= 30:
                    break

        total += 1
        if detected == expected:
            correct += 1
            print(f"OK {castle_id}: {detected} (correct)")
        else:
            print(f"FAIL {castle_id}: {detected} (expected {expected})")

    elapsed = time.time() - start_time
    accuracy = (correct / total) * 100 if total > 0 else 0

    print(f"\nAccuracy: {correct}/{total} = {accuracy:.1f}%")
    print(f"Time: {elapsed:.2f}s ({elapsed/total:.3f}s per image)")

    results.append({
        'method': 'Tesseract (Optimized)',
        'correct': correct,
        'total': total,
        'accuracy': accuracy,
        'time_total': elapsed,
        'time_per_image': elapsed/total
    })

# ============================================================================
# METHOD 2: PADDLEOCR
# ============================================================================
def test_paddleocr():
    """Test PaddleOCR"""
    try:
        import paddle  # Check for base library
        from paddleocr import PaddleOCR
    except ImportError as e:
        print(f"\nPaddleOCR dependencies missing ({e}). Skipping.")
        return

    print("\n" + "="*60)
    print("METHOD 2: PADDLEOCR")
    print("="*60)

    # Initialize - use default settings
    ocr = PaddleOCR(lang='en')

    correct = 0
    total = 0
    start_time = time.time()

    cutouts_dir = Path("castle_cutouts")

    for cutout_path in sorted(cutouts_dir.glob("castle_*.png")):
        castle_id = get_castle_id(cutout_path.name)
        expected = GROUND_TRUTH[castle_id]

        # Run OCR on full cutout (not just label)
        result = ocr.ocr(str(cutout_path))

        detected = None
        if result and len(result) > 0:
            page_result = result[0]
            rec_texts = page_result.get('rec_texts', [])
            for text in rec_texts:
                # Clean up text
                text_clean = ''.join(c for c in str(text) if c.isdigit())
                if text_clean.isdigit():
                    detected = int(text_clean)
                    if 1 <= detected <= 30:
                        break

        total += 1
        if detected == expected:
            correct += 1
            print(f"OK {castle_id}: {detected} (correct)")
        else:
            print(f"FAIL {castle_id}: {detected} (expected {expected})")

    elapsed = time.time() - start_time
    accuracy = (correct / total) * 100 if total > 0 else 0

    print(f"\nAccuracy: {correct}/{total} = {accuracy:.1f}%")
    print(f"Time: {elapsed:.2f}s ({elapsed/total:.3f}s per image)")

    results.append({
        'method': 'PaddleOCR',
        'correct': correct,
        'total': total,
        'accuracy': accuracy,
        'time_total': elapsed,
        'time_per_image': elapsed/total
    })


# ============================================================================
# METHOD 3: EASYOCR (with unicode fix)
# ============================================================================
def test_easyocr():
    """Test EasyOCR with unicode fix"""
    try:
        # Fix unicode issue
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        import easyocr
    except ImportError:
        print("\nEasyOCR not installed. Skipping.")
        return

    print("\n" + "="*60)
    print("METHOD 3: EASYOCR")
    print("="*60)

    try:
        reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    except Exception as e:
        print(f"EasyOCR initialization failed: {e}")
        return

    correct = 0
    total = 0
    start_time = time.time()

    cutouts_dir = Path("castle_cutouts")

    for cutout_path in sorted(cutouts_dir.glob("castle_*.png")):
        castle_id = get_castle_id(cutout_path.name)
        expected = GROUND_TRUTH[castle_id]

        # Extract label region
        label = extract_label_region(cutout_path)

        # Scale 3x
        scaled = label.resize((label.width * 3, label.height * 3), Image.Resampling.LANCZOS)
        scaled_path = "temp_scaled.png"
        scaled.save(scaled_path)

        # Run OCR
        result = reader.readtext(scaled_path, allowlist='0123456789', detail=1)

        detected = None
        for detection in result:
            text = detection[1].strip()
            if text.isdigit():
                detected = int(text)
                if 1 <= detected <= 30:
                    break

        total += 1
        if detected == expected:
            correct += 1
            print(f"OK {castle_id}: {detected} (correct)")
        else:
            print(f"FAIL {castle_id}: {detected} (expected {expected})")

    elapsed = time.time() - start_time
    accuracy = (correct / total) * 100 if total > 0 else 0

    print(f"\nAccuracy: {correct}/{total} = {accuracy:.1f}%")
    print(f"Time: {elapsed:.2f}s ({elapsed/total:.3f}s per image)")

    results.append({
        'method': 'EasyOCR',
        'correct': correct,
        'total': total,
        'accuracy': accuracy,
        'time_total': elapsed,
        'time_per_image': elapsed/total
    })

    # Cleanup
    if os.path.exists(scaled_path):
        os.remove(scaled_path)

# ============================================================================
# MAIN
# ============================================================================
def main():
    print("COMPREHENSIVE OCR TESTING")
    print("Testing against 32 castle level numbers (ground truth)")
    print("="*60)

    # Test each method
    test_tesseract_optimized()
    test_paddleocr()
    test_easyocr()

    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"{'Method':<25} {'Accuracy':<15} {'Time/Image':<15}")
    print("-"*60)

    for r in results:
        print(f"{r['method']:<25} {r['accuracy']:>6.1f}% ({r['correct']}/{r['total']})  {r['time_per_image']:>8.3f}s")

    # Save results
    with open('ocr_performance.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['method', 'correct', 'total', 'accuracy', 'time_total', 'time_per_image'])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults saved to: ocr_performance.csv")

    # Recommend best
    if results:
        best = max(results, key=lambda x: (x['accuracy'], -x['time_per_image']))
        print(f"\nWINNER: {best['method']} ({best['accuracy']:.1f}% accuracy, {best['time_per_image']:.3f}s per image)")

if __name__ == '__main__':
    main()
