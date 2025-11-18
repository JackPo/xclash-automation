"""
Test castle detection at zoom level 20 using extracted templates.

Validates that castle_scanner.py's CastleDetector can successfully
find castles in zoom_020.png using the newly extracted templates.
"""

import cv2
from castle_scanner import CastleDetector


def main():
    """Test castle detection on zoom_020.png."""
    print("Castle Detection Test - Zoom Level 20")
    print("=" * 60)

    # Initialize detector
    print("Initializing CastleDetector...")
    detector = CastleDetector()
    print(f"  Loaded {len(detector.templates)} templates")
    print()

    # List templates
    print("Templates:")
    for name in detector.templates.keys():
        template = detector.templates[name]
        print(f"  - {name}: {template.shape[1]}x{template.shape[0]} pixels")
    print()

    # Load test frame
    frame_path = "zoom_calibration/zoom_020.png"
    print(f"Loading test frame: {frame_path}")
    frame = cv2.imread(frame_path)

    if frame is None:
        print(f"ERROR: Could not load {frame_path}")
        return

    print(f"  Frame size: {frame.shape[1]}x{frame.shape[0]}")
    print()

    # Detect castles
    print("Detecting castles...")
    castles = detector.find_castles_in_frame(frame, confidence_threshold=0.7)
    print(f"  Found {len(castles)} castles")
    print()

    if not castles:
        print("WARNING: No castles detected!")
        print("This may indicate:")
        print("  1. Templates don't match (wrong scale/appearance)")
        print("  2. Confidence threshold too high")
        print("  3. Deduplication removed all matches")
        print()
        print("Trying with lower threshold (0.5)...")
        castles = detector.find_castles_in_frame(frame, confidence_threshold=0.5)
        print(f"  Found {len(castles)} castles at 0.5 threshold")
        print()

    # Show results
    if castles:
        print("Detected Castles:")
        print("-" * 60)
        for i, castle in enumerate(castles, 1):
            print(f"  {i}. Position: ({castle.x}, {castle.y})")
            print(f"     Confidence: {castle.confidence:.2%}")
            print(f"     Template: {castle.template_used}")
            print()

        # Create visualization
        vis = frame.copy()
        for castle in castles:
            # Draw bounding box (approximate size from template)
            template = detector.templates[castle.template_used]
            w, h = template.shape[1], template.shape[0]

            x1 = castle.x - w // 2
            y1 = castle.y - h // 2
            x2 = castle.x + w // 2
            y2 = castle.y + h // 2

            # Draw rectangle
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Draw center point
            cv2.circle(vis, (castle.x, castle.y), 3, (0, 0, 255), -1)

            # Add confidence label
            label = f"{castle.confidence:.0%}"
            cv2.putText(vis, label, (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX,
                       0.5, (0, 255, 0), 1)

        # Save visualization
        output_path = "temp_template_matching_zoom20.png"
        cv2.imwrite(output_path, vis)
        print(f"Saved visualization: {output_path}")
    else:
        print("No castles detected - cannot create visualization")

    print()
    print("=" * 60)
    print("TEST COMPLETE")


if __name__ == "__main__":
    main()
