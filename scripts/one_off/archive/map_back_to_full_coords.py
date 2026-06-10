"""Map cropped region coordinates back to full screenshot."""

# Cropped region info
crop_x_offset = 1712
crop_y_offset = 944  # y1 - 30

# Gemini detection in cropped region
local_x1 = 25
local_y1 = 21
local_w = 125
local_h = 114

# Map back to full screenshot
full_x1 = crop_x_offset + local_x1
full_y1 = crop_y_offset + local_y1
full_x2 = full_x1 + local_w
full_y2 = full_y1 + local_h

center_x = (full_x1 + full_x2) // 2
center_y = (full_y1 + full_y2) // 2

print("Rally plus button coordinates in FULL screenshot:")
print(f"  Position: ({full_x1}, {full_y1})")
print(f"  Size: {local_w}x{local_h}")
print(f"  Center (click): ({center_x}, {center_y})")
