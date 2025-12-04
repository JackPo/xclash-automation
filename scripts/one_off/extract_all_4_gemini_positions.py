"""Extract all 4 rally plus button positions that Gemini detected."""
import cv2

# Load screenshot
frame = cv2.imread('screenshots/joining_team.png')

# Gemini's raw response with all 4 detections:
raw_detections = [
    {"box_2d": [286, 268, 340, 294], "label": "plus button"},
    {"box_2d": [286, 300, 340, 326], "label": "plus button"},
    {"box_2d": [286, 332, 340, 358], "label": "plus button"},
    {"box_2d": [286, 364, 340, 390], "label": "plus button"}
]

# Image size
image_width = 3840
image_height = 2160

# Scale factor (normalized 0-1000 to pixels)
scale_x = image_width / 1000.0
scale_y = image_height / 1000.0

for i, detection in enumerate(raw_detections, 1):
    x1_norm, y1_norm, x2_norm, y2_norm = detection["box_2d"]

    # Convert to pixel coordinates
    x1 = int(x1_norm * scale_x)
    y1 = int(y1_norm * scale_y)
    x2 = int(x2_norm * scale_x)
    y2 = int(y2_norm * scale_y)

    w = x2 - x1
    h = y2 - y1

    # Extract region
    roi = frame[y1:y2, x1:x2]

    # Save it
    output_path = f'templates/ground_truth/testing/rally_plus_gemini_slot_{i}_pos_{x1}_{y1}.png'
    cv2.imwrite(output_path, roi)

    print(f"Slot {i}:")
    print(f"  Position: ({x1}, {y1})")
    print(f"  Size: {w}x{h}")
    print(f"  Saved to: {output_path}")
    print()
