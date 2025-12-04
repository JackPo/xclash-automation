"""Extract all 3 square rally plus buttons from Gemini."""
import cv2

# Load screenshot
frame = cv2.imread('screenshots/screenshot_20251203_140637.png')

# Gemini's raw response:
raw_detections = [
    {"box_2d": [223, 495, 281, 529]},
    {"box_2d": [446, 451, 507, 486]},
    {"box_2d": [446, 495, 507, 529]}
]

# Image size
image_width = 3840
image_height = 2160

# Scale factor
scale_x = image_width / 1000.0
scale_y = image_height / 1000.0

for i, detection in enumerate(raw_detections, 1):
    x1_norm, y1_norm, x2_norm, y2_norm = detection["box_2d"]

    # Convert to pixels
    x1 = int(x1_norm * scale_x)
    y1 = int(y1_norm * scale_y)
    x2 = int(x2_norm * scale_x)
    y2 = int(y2_norm * scale_y)

    w = x2 - x1
    h = y2 - y1

    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2

    # Extract
    roi = frame[y1:y2, x1:x2]

    # Save
    output_path = f'templates/ground_truth/testing/rally_square_button_{i}_pos{x1}_{y1}.png'
    cv2.imwrite(output_path, roi)

    print(f"Button {i}:")
    print(f"  Position: ({x1}, {y1})")
    print(f"  Size: {w}x{h}")
    print(f"  Center (click): ({center_x}, {center_y})")
    print(f"  Saved to: {output_path}")
    print()
