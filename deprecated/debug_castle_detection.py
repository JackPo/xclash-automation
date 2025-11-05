"""Debug castle detection to see what's being found"""
import cv2
import numpy as np

def debug_detect_castles(image_path='current_zoom_check.png'):
    img = cv2.imread(image_path)
    if img is None:
        print(f"ERROR: Could not load {image_path}")
        return

    height, width = img.shape[:2]
    print(f"Image loaded: {width}x{height}")

    # Convert to HSV
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Castle color range
    lower_gray = np.array([0, 0, 180])
    upper_gray = np.array([180, 40, 255])

    mask = cv2.inRange(hsv, lower_gray, upper_gray)

    # Clean up
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"Found {len(contours)} total contours")

    # Check all contours (not just filtered ones)
    valid_count = 0
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)

        # Check against filters
        size_ok = (35 < w < 70 and 35 < h < 70)
        aspect_ok = (0.7 < w/h < 1.4) if h > 0 else False
        area_ok = area > 500
        margin_ok = (100 < x < width-100 and 100 < y < height-100)

        if size_ok and aspect_ok and area_ok and margin_ok:
            valid_count += 1

        # Print first few for debugging
        if valid_count <= 5:
            print(f"  Contour: x={x}, y={y}, w={w}, h={h}, area={area:.0f}")
            print(f"    size_ok={size_ok}, aspect_ok={aspect_ok}, area_ok={area_ok}, margin_ok={margin_ok}")

    print(f"\nValid castles after filtering: {valid_count}")

    # Save debug image with mask
    cv2.imwrite('debug_mask.png', mask)
    print(f"Saved mask to debug_mask.png")

if __name__ == "__main__":
    debug_detect_castles()
