#!/usr/bin/env python3
"""
Test OCR on a single screenshot to detect castle level numbers.

This script takes a screenshot and runs Tesseract OCR to find castle level
numbers (typically in range 1-30). It's designed to test a single zoom level
and measure how well OCR can detect the numbers.

Usage:
    python test_zoom_ocr.py <screenshot_path>
    python test_zoom_ocr.py zoom_discovery_adb/initial_00.png
"""

import sys
import re
from pathlib import Path
from PIL import Image
import pytesseract

# Configure Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_castle_levels(image_path):
    """
    Run OCR on image and extract castle level numbers.

    Args:
        image_path: Path to screenshot

    Returns:
        dict with:
            - numbers: List of detected numbers (1-30)
            - total_numbers: Count of valid castle level numbers
            - all_text: Full OCR output
            - confidence: Overall OCR confidence
    """
    print(f"\n{'='*60}")
    print(f"Analyzing: {image_path}")
    print(f"{'='*60}")

    # Load image
    img = Image.open(image_path)
    print(f"Image size: {img.size[0]}x{img.size[1]}")

    # Run OCR with detailed data
    ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    # Extract all text for reference
    all_text = pytesseract.image_to_string(img)
    total_chars = len(all_text)

    # Find castle level numbers (1-30)
    castle_levels = []
    confidences = []

    for i, text in enumerate(ocr_data['text']):
        if text.strip():
            # Look for numbers that could be castle levels
            if text.isdigit():
                num = int(text)
                if 1 <= num <= 30:
                    conf = ocr_data['conf'][i]
                    if conf > 0:  # Valid confidence
                        castle_levels.append(num)
                        confidences.append(conf)
                        print(f"  Found level {num:2d} (confidence: {conf:.1f}%)")

    # Calculate statistics
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"{'='*60}")
    print(f"Castle levels detected: {len(castle_levels)}")
    print(f"Numbers found: {sorted(set(castle_levels))}")
    print(f"Average confidence: {avg_confidence:.1f}%")
    print(f"Total OCR characters: {total_chars}")
    print(f"\nCastle level breakdown:")

    # Count occurrences of each level
    level_counts = {}
    for level in castle_levels:
        level_counts[level] = level_counts.get(level, 0) + 1

    for level in sorted(level_counts.keys()):
        count = level_counts[level]
        print(f"  Level {level:2d}: {count} occurrence(s)")

    return {
        'numbers': castle_levels,
        'total_numbers': len(castle_levels),
        'unique_numbers': len(set(castle_levels)),
        'all_text': all_text,
        'total_chars': total_chars,
        'avg_confidence': avg_confidence,
        'level_counts': level_counts,
        'image_size': img.size
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_zoom_ocr.py <screenshot_path>")
        print("\nExample:")
        print("  python test_zoom_ocr.py zoom_discovery_adb/initial_00.png")
        print("  python test_zoom_ocr.py zoom_discovery_adb/zoom_out_10.png")
        sys.exit(1)

    screenshot_path = sys.argv[1]

    # Check if file exists
    if not Path(screenshot_path).exists():
        print(f"ERROR: File not found: {screenshot_path}")
        sys.exit(1)

    # Run OCR analysis
    results = extract_castle_levels(screenshot_path)

    print(f"\n{'='*60}")
    print(f"SUMMARY:")
    print(f"{'='*60}")
    print(f"File: {screenshot_path}")
    print(f"Image Size: {results['image_size'][0]}x{results['image_size'][1]}")
    print(f"Castle Levels Found: {results['total_numbers']}")
    print(f"Unique Levels: {results['unique_numbers']}")
    print(f"OCR Confidence: {results['avg_confidence']:.1f}%")
    print(f"Total Characters: {results['total_chars']}")
    print(f"\nDensity Score: {results['total_numbers']:.1f} castle levels per screenshot")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
