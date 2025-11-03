#!/usr/bin/env python3
"""
Test EasyOCR with different scaling factors (no Otsu).
Find optimal scaling for best accuracy.
"""

import cv2
import numpy as np
from pathlib import Path
from PIL import Image
import time
import easyocr

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

def extract_label_region(image_path):
    """Extract just the number label (bottom ~30px of cutout)"""
    img = Image.open(image_path)
    label_height = 30
    label = img.crop((0, img.height - label_height, img.width, img.height))
    return label

def test_scale(scale_factor, reader):
    """Test EasyOCR with a specific scaling factor"""

    correct = 0
    total = 0
    cutouts_dir = Path("castle_cutouts")

    for cutout_path in sorted(cutouts_dir.glob("castle_*.png")):
        parts = cutout_path.stem.split('_')
        castle_id = f"{parts[1]}_{parts[2]}_{parts[3]}"
        expected = GROUND_TRUTH[castle_id]

        # Extract label region
        label = extract_label_region(cutout_path)

        # Scale
        scaled = label.resize((label.width * scale_factor, label.height * scale_factor), Image.Resampling.LANCZOS)
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

    accuracy = (correct / total) * 100 if total > 0 else 0
    return correct, total, accuracy

def main():
    print("="*60)
    print("EASYOCR SCALING FACTOR OPTIMIZATION")
    print("="*60)

    # Initialize EasyOCR once
    print("\nInitializing EasyOCR...")
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)

    # Test different scaling factors
    scales = [2, 3, 4, 5, 6, 8, 10]

    results = []

    for scale in scales:
        print(f"\nTesting scale {scale}x...")
        start_time = time.time()
        correct, total, accuracy = test_scale(scale, reader)
        elapsed = time.time() - start_time

        results.append({
            'scale': scale,
            'correct': correct,
            'total': total,
            'accuracy': accuracy,
            'time': elapsed
        })

        print(f"  Accuracy: {correct}/{total} = {accuracy:.1f}%")
        print(f"  Time: {elapsed:.2f}s")

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"{'Scale':<10} {'Accuracy':<20} {'Time':<10}")
    print("-"*60)

    for r in results:
        print(f"{r['scale']}x{'':<8} {r['accuracy']:>6.1f}% ({r['correct']}/{r['total']}){'':<6} {r['time']:>6.2f}s")

    # Find best
    best = max(results, key=lambda x: x['accuracy'])
    print(f"\nBEST: {best['scale']}x scaling = {best['accuracy']:.1f}% accuracy")

if __name__ == '__main__':
    main()
