#!/usr/bin/env python3
"""
Check screenshots for minimap/global map presence.

This script examines screenshots to detect if a minimap (global map) is visible
in the upper right corner. The minimap would be useful for coordinate tracking
when panning around the map to find castles.

Usage:
    python check_minimap.py
    python check_minimap.py --image zoom_discovery_adb/zoom_out_30.png
"""

import argparse
from pathlib import Path
from PIL import Image, ImageDraw
import pytesseract

# Configure Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def check_upper_right_for_minimap(image_path, show_region=False):
    """
    Check upper right corner for minimap indicators.

    The minimap typically:
    - Located in upper right corner
    - Shows a small overview of the global map
    - May have coordinate text (X:xxx Y:yyy)
    - Has distinctive visual patterns (roads, territories, etc.)

    Args:
        image_path: Path to screenshot
        show_region: If True, save a cropped version of the region being checked

    Returns:
        dict with findings
    """
    img = Image.open(image_path)
    width, height = img.size

    # Define upper right region (top-right 20% of screen)
    # Typical minimap location
    region_width = int(width * 0.20)  # 20% of screen width
    region_height = int(height * 0.20)  # 20% of screen height
    left = width - region_width
    top = 0
    right = width
    bottom = region_height

    # Extract upper right corner
    upper_right = img.crop((left, top, right, bottom))

    # Run OCR on this region to look for map-related text
    text = pytesseract.image_to_string(upper_right)

    # Look for coordinate patterns or map-related keywords
    has_coordinates = ('X:' in text or 'Y:' in text or
                      'x:' in text or 'y:' in text)
    has_map_keywords = any(keyword in text.lower() for keyword in
                          ['map', 'kingdom', 'world', 'alliance'])

    # Analyze colors in the region (minimaps often have distinct color patterns)
    # Convert to RGB if needed
    if upper_right.mode != 'RGB':
        upper_right = upper_right.convert('RGB')

    # Sample pixels to detect if there's a distinct map-like pattern
    pixels = list(upper_right.getdata())
    unique_colors = len(set(pixels))
    avg_brightness = sum(sum(p) for p in pixels) / (len(pixels) * 3)

    # Save cropped region if requested
    if show_region:
        region_path = Path(image_path).parent / f"{Path(image_path).stem}_upper_right.png"

        # Draw a red border around the region we checked on the original image
        img_copy = img.copy()
        draw = ImageDraw.Draw(img_copy)
        draw.rectangle([left, top, right, bottom], outline='red', width=5)

        debug_path = Path(image_path).parent / f"{Path(image_path).stem}_minimap_check.png"
        img_copy.save(debug_path)

        upper_right.save(region_path)
        print(f"  Saved region to: {region_path}")
        print(f"  Saved annotated image to: {debug_path}")

    return {
        'has_coordinates': has_coordinates,
        'has_map_keywords': has_map_keywords,
        'unique_colors': unique_colors,
        'avg_brightness': avg_brightness,
        'ocr_text': text.strip(),
        'region': (left, top, right, bottom)
    }

def main():
    parser = argparse.ArgumentParser(description='Check for minimap in screenshots')
    parser.add_argument('--image', help='Single image to check')
    parser.add_argument('--dir', default='zoom_discovery_adb',
                       help='Directory to scan (default: zoom_discovery_adb)')
    parser.add_argument('--show-region', action='store_true',
                       help='Save cropped region images for visual inspection')
    args = parser.parse_args()

    if args.image:
        # Check single image
        images = [Path(args.image)]
    else:
        # Check all screenshots in directory
        screenshot_dir = Path(args.dir)
        if not screenshot_dir.exists():
            print(f"ERROR: Directory not found: {screenshot_dir}")
            return

        images = sorted(screenshot_dir.glob('*.png'))

    if not images:
        print("ERROR: No images found")
        return

    print(f"Checking {len(images)} screenshot(s) for minimap presence")
    print(f"{'='*70}\n")

    minimap_candidates = []

    for img_path in images:
        print(f"Checking {img_path.name}...")

        try:
            result = check_upper_right_for_minimap(img_path, args.show_region)

            # Scoring system to identify likely minimap presence
            score = 0
            if result['has_coordinates']:
                score += 3
                print(f"  [+3] Found coordinates in upper right")
            if result['has_map_keywords']:
                score += 2
                print(f"  [+2] Found map-related keywords")
            if result['unique_colors'] > 100:
                score += 1
                print(f"  [+1] Rich color variety ({result['unique_colors']} colors)")

            if result['ocr_text']:
                print(f"  OCR Text: {result['ocr_text'][:100]}")

            print(f"  Minimap Score: {score}/6")

            if score >= 2:
                minimap_candidates.append({
                    'filename': img_path.name,
                    'score': score,
                    'result': result
                })
                print(f"  >>> POSSIBLE MINIMAP DETECTED <<<")

            print()

        except Exception as e:
            print(f"  ERROR: {e}\n")

    print(f"\n{'='*70}")
    print("MINIMAP DETECTION SUMMARY")
    print(f"{'='*70}\n")

    if minimap_candidates:
        print(f"Found {len(minimap_candidates)} screenshot(s) with possible minimap:\n")
        for candidate in sorted(minimap_candidates, key=lambda x: x['score'], reverse=True):
            print(f"  {candidate['filename']}")
            print(f"    Score: {candidate['score']}/6")
            if candidate['result']['ocr_text']:
                print(f"    Text: {candidate['result']['ocr_text'][:100]}")
            print()

        print("\nRECOMMENDATION: Review these images manually to confirm minimap presence")
    else:
        print("No minimap detected in any screenshots.")
        print("\nPOSSIBLE REASONS:")
        print("  1. Minimap doesn't exist in this game")
        print("  2. Minimap is hidden or toggleable via UI button")
        print("  3. Minimap appears only in specific game modes")
        print("  4. Need to zoom out further to see minimap")
        print("\nFALLBACK STRATEGY:")
        print("  Use grid-based navigation (already implemented in find_level20.py)")

    print(f"\n{'='*70}\n")

if __name__ == '__main__':
    main()
