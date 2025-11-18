"""
Extract castle templates from zoom_020.png for zoom level 20 detection.

Uses existing HSV color filtering to detect castles, then extracts them
as templates for use in castle_scanner.py
"""

import cv2
import numpy as np
from pathlib import Path

# HSV color ranges for castle detection (from castle_matcher.py)
LOWER_PINK = np.array([140, 30, 30])
UPPER_PINK = np.array([170, 255, 255])

MIN_CASTLE_AREA = 500  # Minimum pixels for a valid castle at zoom 20
MAX_CASTLE_AREA = 5000  # Maximum pixels for a valid castle at zoom 20
MIN_ASPECT_RATIO = 0.5  # width/height minimum
MAX_ASPECT_RATIO = 2.0  # width/height maximum


def detect_castles(frame):
    """
    Detect castles in frame using HSV color filtering.

    Returns:
        List of (x, y, w, h) bounding boxes
    """
    # Convert to HSV
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Create mask for pink castles
    mask = cv2.inRange(hsv, LOWER_PINK, UPPER_PINK)

    # Morphological operations to clean up mask
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter contours
    valid_boxes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h

        # Check area constraints
        if area < MIN_CASTLE_AREA or area > MAX_CASTLE_AREA:
            continue

        # Check aspect ratio
        aspect_ratio = w / h if h > 0 else 0
        if aspect_ratio < MIN_ASPECT_RATIO or aspect_ratio > MAX_ASPECT_RATIO:
            continue

        valid_boxes.append((x, y, w, h))

    return valid_boxes


def extract_templates(frame, boxes, output_dir, max_templates=10):
    """
    Extract castle templates from frame.

    Args:
        frame: Source image
        boxes: List of (x, y, w, h) bounding boxes
        output_dir: Directory to save templates
        max_templates: Maximum number of templates to extract
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Sort by area (largest first) to get diverse samples
    boxes_with_area = [(x, y, w, h, w*h) for x, y, w, h in boxes]
    boxes_with_area.sort(key=lambda b: b[4], reverse=True)

    # Select diverse templates (varying sizes)
    selected = []
    for i, (x, y, w, h, area) in enumerate(boxes_with_area):
        if len(selected) >= max_templates:
            break

        # Check if this size is significantly different from already selected
        is_unique_size = True
        for _, _, sw, sh in selected:
            size_diff = abs((w * h) - (sw * sh)) / (sw * sh)
            if size_diff < 0.3:  # Less than 30% size difference
                is_unique_size = False
                break

        if is_unique_size or len(selected) < 3:  # Always take first 3
            selected.append((x, y, w, h))

    # Extract and save templates
    saved = []
    for i, (x, y, w, h) in enumerate(selected):
        # Add padding around castle
        padding = 5
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(frame.shape[1], x + w + padding)
        y2 = min(frame.shape[0], y + h + padding)

        # Extract castle region
        castle = frame[y1:y2, x1:x2]

        # Save template
        template_name = f"zoom20_castle_{i+1:02d}.png"
        template_path = output_dir / template_name
        cv2.imwrite(str(template_path), castle)

        saved.append({
            'name': template_name,
            'size': f"{castle.shape[1]}x{castle.shape[0]}",
            'position': f"({x}, {y})"
        })

        print(f"Extracted: {template_name} - {castle.shape[1]}x{castle.shape[0]} pixels at ({x}, {y})")

    return saved


def visualize_detections(frame, boxes, output_path):
    """Draw bounding boxes on frame and save visualization."""
    vis = frame.copy()

    for i, (x, y, w, h) in enumerate(boxes):
        # Draw rectangle
        cv2.rectangle(vis, (x, y), (x+w, y+h), (0, 255, 0), 2)

        # Add label
        label = f"C{i+1}"
        cv2.putText(vis, label, (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    cv2.imwrite(output_path, vis)
    print(f"Saved visualization: {output_path}")


def main():
    """Main extraction workflow."""
    print("Castle Template Extraction - Zoom Level 20")
    print("=" * 60)

    # Load zoom_020.png
    frame_path = "zoom_calibration/zoom_020.png"
    frame = cv2.imread(frame_path)

    if frame is None:
        print(f"ERROR: Could not load {frame_path}")
        return

    print(f"Loaded: {frame_path} ({frame.shape[1]}x{frame.shape[0]})")
    print()

    # Detect castles
    print("Detecting castles...")
    boxes = detect_castles(frame)
    print(f"Found {len(boxes)} castles")
    print()

    if not boxes:
        print("ERROR: No castles detected!")
        return

    # Extract templates
    print("Extracting templates...")
    output_dir = "templates/castles"
    templates = extract_templates(frame, boxes, output_dir, max_templates=10)
    print()

    # Create visualization
    print("Creating visualization...")
    visualize_detections(frame, boxes, "temp_castle_detection_zoom20.png")
    print()

    # Summary
    print("=" * 60)
    print(f"EXTRACTION COMPLETE")
    print(f"  Detected: {len(boxes)} castles")
    print(f"  Extracted: {len(templates)} templates")
    print(f"  Location: {output_dir}/")
    print()
    print("Templates:")
    for t in templates:
        print(f"  - {t['name']}: {t['size']} at {t['position']}")


if __name__ == "__main__":
    main()
