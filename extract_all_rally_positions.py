"""Extract all 4 rally plus button positions from Gemini response."""

# Gemini's raw response:
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

print("All 4 rally slot plus button positions:\n")

for i, detection in enumerate(raw_detections, 1):
    x1_norm, y1_norm, x2_norm, y2_norm = detection["box_2d"]

    # Convert to pixel coordinates
    x1 = int(x1_norm * scale_x)
    y1 = int(y1_norm * scale_y)
    x2 = int(x2_norm * scale_x)
    y2 = int(y2_norm * scale_y)

    w = x2 - x1
    h = y2 - y1

    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2

    print(f"Slot {i}:")
    print(f"  Position: ({x1}, {y1})")
    print(f"  Size: {w}x{h}")
    print(f"  Center (click): ({center_x}, {center_y})")
    print()

# Calculate staggering
print("Staggering analysis:")
positions = []
for detection in raw_detections:
    x1_norm, y1_norm, x2_norm, y2_norm = detection["box_2d"]
    x1 = int(x1_norm * scale_x)
    y1 = int(y1_norm * scale_y)
    positions.append((x1, y1))

x_coords = [p[0] for p in positions]
y_coords = [p[1] for p in positions]

print(f"X coordinates: {x_coords}")
print(f"Y coordinates: {y_coords}")

if len(set(x_coords)) == 1:
    print(f"X is FIXED at {x_coords[0]}")
else:
    print(f"X varies")

y_diffs = [y_coords[i+1] - y_coords[i] for i in range(len(y_coords)-1)]
print(f"Y spacing between slots: {y_diffs}")
