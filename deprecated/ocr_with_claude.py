#!/usr/bin/env python3
"""
OCR castle level numbers using Claude's vision API.
Much more reliable than Tesseract for small game UI text.
"""

import os
import base64
from pathlib import Path
from anthropic import Anthropic

def read_castle_level(image_path):
    """
    Use Claude vision API to read the castle level number from a cutout image.

    Returns: int level number (1-30) or None if not detected
    """
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # Read and encode image
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    #  Create message with image
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_data,
                    },
                },
                {
                    "type": "text",
                    "text": "This is a cutout from a game showing a castle icon with a level number below it. What is the number shown in the white circle/label? Reply with ONLY the number, nothing else."
                }
            ],
        }]
    )

    # Parse response
    text = message.content[0].text.strip()
    try:
        level = int(text)
        if 1 <= level <= 30:
            return level
    except:
        pass

    return None

def main():
    cutouts_dir = Path("castle_cutouts")

    print("Reading castle levels using Claude Vision API...")
    print("="*60)

    results = []

    for cutout_path in sorted(cutouts_dir.glob("castle_*.png")):
        # Parse filename: castle_XXX_x_y.png
        parts = cutout_path.stem.split("_")
        idx = int(parts[1])
        cx = int(parts[2])
        cy = int(parts[3])

        level = read_castle_level(cutout_path)

        if level:
            results.append((idx, level, cx, cy))
            print(f"Castle {idx:03d} @ ({cx},{cy}): Level {level}")
        else:
            print(f"Castle {idx:03d} @ ({cx},{cy}): Could not read")

    print(f"\n{'='*60}")
    print(f"Successfully read {len(results)} out of {len(list(cutouts_dir.glob('castle_*.png')))} castles")

    # Find level 20+
    level20plus = [r for r in results if r[1] >= 20]
    if level20plus:
        print(f"\n{'='*60}")
        print(f"LEVEL 20+ CASTLES FOUND: {len(level20plus)}")
        print(f"{'='*60}")
        for idx, level, cx, cy in level20plus:
            print(f"  Castle {idx:03d}: Level {level} @ ({cx},{cy})")

if __name__ == '__main__':
    main()
