"""
Draw bounding boxes around well-isolated, well-centered player castles.
"""
import cv2
import numpy as np
from pathlib import Path

def find_player_castles(img, debug=False):
    """
    Find player castles using color-based detection.
    Returns list of (x, y, w, h) bounding boxes.
    """
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Player castle colors - looking for the distinctive blue/purple roof
    # and the surrounding structure colors
    lower_blue = np.array([100, 50, 50])
    upper_blue = np.array([130, 255, 255])

    mask = cv2.inRange(hsv, lower_blue, upper_blue)

    # Morphological operations to clean up the mask
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    if debug:
        cv2.imwrite('debug_castle_mask.png', mask)

    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter contours by area and aspect ratio
    castle_candidates = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 100 or area > 5000:  # Filter by reasonable castle size
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = float(w) / h if h > 0 else 0

        # Castles are roughly square to slightly tall
        if 0.5 < aspect_ratio < 1.5 and w > 10 and h > 10:
            castle_candidates.append((x, y, w, h, area))

    return castle_candidates

def calculate_isolation_score(box, all_boxes, img_shape):
    """
    Calculate how isolated a castle is from others.
    Higher score = more isolated = better.
    """
    x, y, w, h = box
    cx, cy = x + w/2, y + h/2

    min_dist = float('inf')
    for other_box in all_boxes:
        if other_box == box:
            continue
        ox, oy, ow, oh = other_box
        ocx, ocy = ox + ow/2, oy + oh/2
        dist = np.sqrt((cx - ocx)**2 + (cy - ocy)**2)
        min_dist = min(min_dist, dist)

    return min_dist

def calculate_centering_score(box, img_shape):
    """
    Calculate how centered a castle is in the image.
    Higher score = more centered = better.
    """
    h, w = img_shape[:2]
    x, y, bw, bh = box
    cx, cy = x + bw/2, y + bh/2

    # Distance from center
    img_cx, img_cy = w/2, h/2
    dist_from_center = np.sqrt((cx - img_cx)**2 + (cy - img_cy)**2)

    # Normalize by image diagonal
    max_dist = np.sqrt(img_cx**2 + img_cy**2)

    return 1.0 - (dist_from_center / max_dist)

def select_best_castles(candidates, img_shape, n=3):
    """
    Select the N best castles based on isolation and centering.
    """
    if len(candidates) <= n:
        return candidates

    # Calculate scores for each candidate
    scored_candidates = []
    boxes_only = [(x, y, w, h) for x, y, w, h, _ in candidates]

    for i, (x, y, w, h, area) in enumerate(candidates):
        box = (x, y, w, h)
        isolation = calculate_isolation_score(box, boxes_only, img_shape)
        centering = calculate_centering_score(box, img_shape)

        # Combined score (weight isolation more heavily)
        score = isolation * 0.7 + centering * 0.3 + (area / 1000) * 0.1

        scored_candidates.append((score, x, y, w, h))

    # Sort by score descending and take top N
    scored_candidates.sort(reverse=True, key=lambda x: x[0])

    return [(x, y, w, h) for _, x, y, w, h in scored_candidates[:n]]

def create_padded_box(x, y, w, h, padding=20):
    """
    Create a padded bounding box to ensure castle name and level are visible.
    """
    # Add generous padding, especially at the top for the name
    top_pad = padding + 10  # Extra padding at top for player name
    bottom_pad = padding
    left_pad = padding
    right_pad = padding

    new_x = max(0, x - left_pad)
    new_y = max(0, y - top_pad)
    new_w = w + left_pad + right_pad
    new_h = h + top_pad + bottom_pad

    return new_x, new_y, new_w, new_h

def main():
    # Load the image
    input_path = Path('templates/debug/after_8_zooms_small.png')
    output_path = Path('templates/debug/castle_boxes_viz.png')

    if not input_path.exists():
        print(f"Error: Input image not found at {input_path}")
        return

    img = cv2.imread(str(input_path))
    if img is None:
        print(f"Error: Could not load image from {input_path}")
        return

    print(f"Loaded image: {img.shape[1]}x{img.shape[0]}")

    # Find castle candidates
    candidates = find_player_castles(img, debug=True)
    print(f"Found {len(candidates)} castle candidates")

    if len(candidates) == 0:
        print("No castles found!")
        return

    # Select the 3 best castles
    best_castles = select_best_castles(candidates, img.shape, n=3)
    print(f"Selected {len(best_castles)} best castles")

    # Create output image
    output_img = img.copy()

    # Draw boxes and labels
    for i, (x, y, w, h) in enumerate(best_castles, 1):
        # Create padded box
        px, py, pw, ph = create_padded_box(x, y, w, h, padding=25)

        # Ensure box stays within image bounds
        px = max(0, px)
        py = max(0, py)
        pw = min(pw, img.shape[1] - px)
        ph = min(ph, img.shape[0] - py)

        # Draw green bounding box
        cv2.rectangle(output_img, (px, py), (px + pw, py + ph), (0, 255, 0), 2)

        # Draw label
        label = f"C{i}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2

        # Get text size for background
        (text_w, text_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)

        # Draw background for text
        cv2.rectangle(output_img,
                     (px, py - text_h - baseline - 5),
                     (px + text_w + 5, py),
                     (0, 255, 0), -1)

        # Draw text
        cv2.putText(output_img, label, (px + 2, py - 5),
                   font, font_scale, (0, 0, 0), thickness)

        # Print coordinates
        print(f"\nCastle {i} (C{i}):")
        print(f"  Position: x={px}, y={py}")
        print(f"  Size: w={pw}, h={ph}")
        print(f"  Coordinates: ({px}, {py}, {px + pw}, {py + ph})")

    # Save output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), output_img)
    print(f"\nVisualization saved to: {output_path}")
    print(f"Debug mask saved to: debug_castle_mask.png")

if __name__ == '__main__':
    main()
