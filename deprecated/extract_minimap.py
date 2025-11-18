"""
Extract the mini-map from upper-right corner of the game screen
The mini-map shows zoom level via yellow marker position/size
"""
import cv2
import numpy as np
import sys

def find_minimap_region(screenshot_path):
    """
    Find and extract the mini-map from upper-right corner
    The mini-map is a square region in the upper-right
    """
    img = cv2.imread(screenshot_path)
    if img is None:
        print(f"Error: Could not read {screenshot_path}")
        return None

    h, w = img.shape[:2]
    print(f"Screenshot size: {w}x{h}")

    # The mini-map is in the upper-right corner
    # Based on typical UI layout, it's usually within:
    # - Right 15% of screen width
    # - Top 15% of screen height

    # Let's try a few different crop regions and show them
    # User can tell us which one is correct

    regions = [
        # (name, x, y, width, height) - all as fractions of screen size
        ("Region 1: Top-right 200x200", 0.92, 0.01, 0.078, 0.14),
        ("Region 2: Top-right 180x180", 0.93, 0.02, 0.07, 0.125),
        ("Region 3: Top-right 220x220", 0.91, 0.01, 0.086, 0.153),
        ("Region 4: Top-right 160x160", 0.94, 0.03, 0.0625, 0.111),
    ]

    crops = []
    for i, (name, x_frac, y_frac, w_frac, h_frac) in enumerate(regions):
        x = int(x_frac * w)
        y = int(y_frac * h)
        crop_w = int(w_frac * w)
        crop_h = int(h_frac * h)

        # Ensure we don't go out of bounds
        x = max(0, min(x, w - crop_w))
        y = max(0, min(y, h - crop_h))

        crop = img[y:y+crop_h, x:x+crop_w]
        crops.append((name, crop, (x, y, crop_w, crop_h)))

        print(f"\n{name}")
        print(f"  Position: ({x}, {y})")
        print(f"  Size: {crop_w}x{crop_h}")

        # Save crop
        output_file = f"minimap_candidate_{i+1}.png"
        cv2.imwrite(output_file, crop)
        print(f"  Saved: {output_file}")

    # Also try to detect the mini-map by looking for a square border
    # The mini-map usually has a distinct border/frame
    print("\n" + "="*60)
    print("Attempting automatic detection...")

    # Look in upper-right quadrant
    search_region = img[0:int(h*0.2), int(w*0.75):w]
    gray = cv2.cvtColor(search_region, cv2.COLOR_BGR2GRAY)

    # Try edge detection to find the square border
    edges = cv2.Canny(gray, 50, 150)
    cv2.imwrite("minimap_edge_detection.png", edges)
    print("Saved edge detection: minimap_edge_detection.png")

    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Look for square-ish contours
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        area = cv2.contourArea(contour)
        if area < 1000:  # Too small
            continue

        # Get bounding rectangle
        x, y, cw, ch = cv2.boundingRect(contour)

        # Check if roughly square
        aspect_ratio = cw / ch if ch > 0 else 0
        if 0.8 < aspect_ratio < 1.2 and area > 10000:
            print(f"\nFound potential mini-map:")
            print(f"  Position: ({x + int(w*0.75)}, {y})")
            print(f"  Size: {cw}x{ch}")
            print(f"  Aspect ratio: {aspect_ratio:.2f}")

            # Extract this region
            actual_x = x + int(w*0.75)
            actual_y = y
            minimap_auto = img[actual_y:actual_y+ch, actual_x:actual_x+cw]
            cv2.imwrite("minimap_auto_detected.png", minimap_auto)
            print(f"  Saved: minimap_auto_detected.png")
            break

    print("\n" + "="*60)
    print("Cropped multiple candidate regions.")
    print("Please check the output files and tell me which one")
    print("shows the mini-map correctly.")
    print("="*60)

if __name__ == "__main__":
    screenshot = sys.argv[1] if len(sys.argv) > 1 else "current_game_state.png"
    find_minimap_region(screenshot)
