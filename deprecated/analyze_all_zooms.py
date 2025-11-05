#!/usr/bin/env python3
"""
Analyze all zoom screenshots to find optimal zoom level for castle scanning.

This script processes all screenshots in zoom_discovery_adb/ directory and
determines which zoom level provides the best balance of:
1. Castle density (more castles visible)
2. OCR accuracy (reliable number detection)
3. Confidence scores (high confidence readings)

Usage:
    python analyze_all_zooms.py
    python analyze_all_zooms.py --output zoom_analysis.csv
"""

import argparse
import csv
from pathlib import Path
from PIL import Image
import pytesseract

# Configure Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def analyze_screenshot(image_path):
    """
    Analyze a single screenshot for castle level numbers.

    Args:
        image_path: Path to screenshot

    Returns:
        dict with analysis results
    """
    img = Image.open(image_path)

    # Run OCR with detailed data
    ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    # Find castle level numbers (1-30)
    castle_levels = []
    confidences = []

    for i, text in enumerate(ocr_data['text']):
        if text.strip() and text.isdigit():
            num = int(text)
            if 1 <= num <= 30:
                conf = ocr_data['conf'][i]
                if conf > 0:  # Valid confidence
                    castle_levels.append(num)
                    confidences.append(conf)

    # Calculate statistics
    total_text = pytesseract.image_to_string(img)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    return {
        'filename': image_path.name,
        'castle_count': len(castle_levels),
        'unique_castles': len(set(castle_levels)),
        'avg_confidence': avg_confidence,
        'total_chars': len(total_text),
        'castle_levels': castle_levels
    }

def parse_zoom_level(filename):
    """
    Extract zoom level from filename.

    Examples:
        initial_00.png -> 0
        zoom_out_10.png -> 10
        zoom_in_05.png -> -5
    """
    name = filename.lower().replace('.png', '')

    if name.startswith('initial'):
        return 0
    elif 'zoom_out' in name:
        parts = name.split('_')
        return int(parts[-1]) if parts[-1].isdigit() else 0
    elif 'zoom_in' in name:
        parts = name.split('_')
        return -int(parts[-1]) if parts[-1].isdigit() else 0
    else:
        return 0

def main():
    parser = argparse.ArgumentParser(description='Analyze zoom screenshots')
    parser.add_argument('--output', default='zoom_analysis.csv',
                       help='Output CSV file (default: zoom_analysis.csv)')
    parser.add_argument('--dir', default='zoom_discovery_adb',
                       help='Directory with screenshots (default: zoom_discovery_adb)')
    args = parser.parse_args()

    # Find all PNG screenshots
    screenshot_dir = Path(args.dir)
    if not screenshot_dir.exists():
        print(f"ERROR: Directory not found: {screenshot_dir}")
        return

    screenshots = sorted(screenshot_dir.glob('*.png'))
    if not screenshots:
        print(f"ERROR: No PNG files found in {screenshot_dir}")
        return

    print(f"Found {len(screenshots)} screenshots to analyze")
    print(f"{'='*70}")

    results = []

    for screenshot in screenshots:
        print(f"Analyzing {screenshot.name}... ", end='', flush=True)

        try:
            data = analyze_screenshot(screenshot)
            zoom_level = parse_zoom_level(screenshot.name)

            result = {
                'zoom_level': zoom_level,
                'filename': data['filename'],
                'castle_count': data['castle_count'],
                'unique_castles': data['unique_castles'],
                'avg_confidence': round(data['avg_confidence'], 1),
                'total_chars': data['total_chars'],
                'density_score': data['castle_count']  # Could weight by confidence
            }

            results.append(result)
            print(f"OK ({result['castle_count']} castles, {result['avg_confidence']:.1f}% conf)")

        except Exception as e:
            print(f"ERROR: {e}")

    # Sort by zoom level
    results.sort(key=lambda x: x['zoom_level'])

    # Write CSV
    output_file = Path(args.output)
    with open(output_file, 'w', newline='') as f:
        if results:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

    print(f"\n{'='*70}")
    print(f"Analysis complete! Results saved to: {output_file}")
    print(f"{'='*70}\n")

    # Print summary statistics
    print("ZOOM LEVEL ANALYSIS SUMMARY")
    print(f"{'='*70}")
    print(f"{'Zoom Level':<12} {'Castles':<10} {'Unique':<10} {'Confidence':<12} {'Chars':<8}")
    print(f"{'-'*70}")

    for r in results:
        zoom_str = f"{r['zoom_level']:+d}" if r['zoom_level'] != 0 else "initial"
        print(f"{zoom_str:<12} {r['castle_count']:<10} {r['unique_castles']:<10} "
              f"{r['avg_confidence']:<12.1f} {r['total_chars']:<8}")

    # Find optimal zoom level
    print(f"\n{'='*70}")
    print("RECOMMENDATIONS")
    print(f"{'='*70}")

    # Best density (most castles per screenshot)
    best_density = max(results, key=lambda x: x['castle_count'])
    print(f"Best Density: {best_density['filename']} "
          f"({best_density['castle_count']} castles)")

    # Best confidence
    best_confidence = max(results, key=lambda x: x['avg_confidence'])
    print(f"Best Confidence: {best_confidence['filename']} "
          f"({best_confidence['avg_confidence']:.1f}%)")

    # Best balance (high castle count + good confidence)
    # Weight: 70% density, 30% confidence
    for r in results:
        r['balanced_score'] = (r['castle_count'] * 0.7) + (r['avg_confidence'] / 100 * 10 * 0.3)

    best_balanced = max(results, key=lambda x: x['balanced_score'])
    print(f"Best Balance: {best_balanced['filename']} "
          f"({best_balanced['castle_count']} castles, {best_balanced['avg_confidence']:.1f}% conf)")

    print(f"\n{'='*70}")
    print(f"RECOMMENDED ZOOM LEVEL: {best_balanced['filename']}")
    print(f"  - Castle Count: {best_balanced['castle_count']}")
    print(f"  - Confidence: {best_balanced['avg_confidence']:.1f}%")
    print(f"  - Zoom Level: {best_balanced['zoom_level']:+d}")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()
