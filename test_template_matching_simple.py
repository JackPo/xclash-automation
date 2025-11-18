"""
Simple template matching test without PaddleOCR initialization.
Tests if our zoom20 templates can detect castles using pure OpenCV.
"""

import cv2
import numpy as np
from pathlib import Path


def test_template_matching():
    """Test template matching on zoom_020.png."""
    print("Simple Template Matching Test")
    print("=" * 60)

    # Load frame
    frame_path = "zoom_calibration/zoom_020.png"
    frame = cv2.imread(frame_path)
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    print(f"Frame: {frame.shape[1]}x{frame.shape[0]}")
    print()

    # Load templates
    template_dir = Path("templates/castles")
    templates = []

    for template_path in sorted(template_dir.glob("zoom20_*.png")):
        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if template is not None:
            templates.append((template_path.stem, template))
            print(f"Loaded: {template_path.stem} ({template.shape[1]}x{template.shape[0]})")

    print()

    # Test each template
    all_matches = []

    for name, template in templates:
        print(f"Testing template: {name}")

        # Match using TM_CCORR_NORMED (same as castle_scanner.py)
        result = cv2.matchTemplate(frame_gray, template, cv2.TM_CCORR_NORMED)

        # Find matches above threshold
        threshold = 0.7
        locations = np.where(result >= threshold)

        matches = []
        for pt in zip(*locations[::-1]):
            score = result[pt[1], pt[0]]
            center_x = pt[0] + template.shape[1] // 2
            center_y = pt[1] + template.shape[0] // 2
            matches.append((center_x, center_y, score, name, template.shape))

        print(f"  Found {len(matches)} matches at threshold {threshold}")

        if matches:
            # Sort by score
            matches.sort(key=lambda m: m[2], reverse=True)
            print(f"  Top 3 scores: {[f'{m[2]:.2%}' for m in matches[:3]]}")

        all_matches.extend(matches)
        print()

    # Deduplicate (remove overlapping matches)
    print("Deduplicating matches...")
    MIN_DISTANCE = 50

    # Sort by confidence
    all_matches.sort(key=lambda m: m[2], reverse=True)

    kept = []
    for match in all_matches:
        cx, cy, score, name, shape = match

        # Check if too close to existing match
        is_duplicate = False
        for existing in kept:
            ex, ey = existing[0], existing[1]
            distance = np.sqrt((cx - ex)**2 + (cy - ey)**2)
            if distance < MIN_DISTANCE:
                is_duplicate = True
                break

        if not is_duplicate:
            kept.append(match)

    print(f"  {len(all_matches)} total matches -> {len(kept)} after deduplication")
    print()

    # Show final results
    if kept:
        print("Final Detected Castles:")
        print("-" * 60)
        for i, (cx, cy, score, name, shape) in enumerate(kept, 1):
            print(f"  {i}. Position: ({cx}, {cy})")
            print(f"     Confidence: {score:.2%}")
            print(f"     Template: {name}")
            print()

        # Create visualization
        vis = frame.copy()
        for cx, cy, score, name, shape in kept:
            w, h = shape[1], shape[0]
            x1 = cx - w // 2
            y1 = cy - h // 2
            x2 = cx + w // 2
            y2 = cy + h // 2

            # Draw box
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Draw center
            cv2.circle(vis, (cx, cy), 3, (0, 0, 255), -1)

            # Add label
            label = f"{score:.0%}"
            cv2.putText(vis, label, (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX,
                       0.5, (0, 255, 0), 1)

        output_path = "temp_simple_template_test.png"
        cv2.imwrite(output_path, vis)
        print(f"Saved: {output_path}")
    else:
        print("No castles detected!")
        print("Try lowering threshold or extracting more diverse templates")

    print()
    print("=" * 60)
    print(f"TEST COMPLETE: {len(kept)} castles detected")


if __name__ == "__main__":
    test_template_matching()
