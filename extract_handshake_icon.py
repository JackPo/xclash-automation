#!/usr/bin/env python3
"""
Extract and test template matching for the shaking hand icon.
"""
import cv2
import numpy as np
from pathlib import Path

# Load the full 4K screenshot
screenshot = cv2.imread('current_screenshot.png')
h, w = screenshot.shape[:2]
print(f"Screenshot size: {w}x{h}")

# Based on LLM analysis, the handshake icon is in lower right
# LLM screenshot is 1920x1080, so coordinates need to be scaled 2x for 4K
# Approximate position from analysis: (1680, 690) in LLM version
# For 4K: multiply by 2 = (3360, 1380)

# Let's extract a region around this area
# Try a larger region first to see what we're working with
center_x_4k = 3360
center_y_4k = 1380

# Extract 400x400 region around the estimated position
region_size = 400
x1 = max(0, center_x_4k - region_size // 2)
y1 = max(0, center_y_4k - region_size // 2)
x2 = min(w, center_x_4k + region_size // 2)
y2 = min(h, center_y_4k + region_size // 2)

region = screenshot[y1:y2, x1:x2]
cv2.imwrite('temp_handshake_region.png', region)
print(f"Extracted region: ({x1}, {y1}) to ({x2}, {y2})")
print(f"Region size: {region.shape[1]}x{region.shape[0]}")

# Try to isolate the icon more precisely
# The icon is peachy/salmon colored and circular
# Let's look at the right edge of the screen more specifically
right_edge_x = w - 150  # 150 pixels from right edge
right_region = screenshot[1200:1600, right_edge_x:w]
cv2.imwrite('temp_right_edge_icons.png', right_region)
print(f"Right edge region: ({right_edge_x}, 1200) to ({w}, 1600)")

# Try to extract just the handshake icon based on color
# Convert to HSV for color-based selection
hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)

# Peachy/salmon color range
# Hue for peachy/salmon: ~0-20 (orange-red range)
lower_peach = np.array([0, 50, 100])
upper_peach = np.array([25, 255, 255])

mask = cv2.inRange(hsv, lower_peach, upper_peach)
cv2.imwrite('temp_handshake_mask.png', mask)

# Find contours in the mask
contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

if contours:
    # Find the largest contour (likely the icon)
    largest_contour = max(contours, key=cv2.contourArea)
    x, y, cw, ch = cv2.boundingRect(largest_contour)

    # Add some padding
    padding = 10
    x = max(0, x - padding)
    y = max(0, y - padding)
    cw = min(region.shape[1] - x, cw + padding * 2)
    ch = min(region.shape[0] - y, ch + padding * 2)

    # Extract the icon
    icon = region[y:y+ch, x:x+cw]
    cv2.imwrite('temp_handshake_icon.png', icon)

    # Calculate actual coordinates in full screenshot
    actual_x = x1 + x
    actual_y = y1 + y

    print(f"\nExtracted icon:")
    print(f"  Size: {cw}x{ch}")
    print(f"  Position in full screenshot: ({actual_x}, {actual_y})")
    print(f"  Center: ({actual_x + cw//2}, {actual_y + ch//2})")

    # Draw rectangle on original
    annotated = screenshot.copy()
    cv2.rectangle(annotated, (actual_x, actual_y), (actual_x + cw, actual_y + ch), (0, 255, 0), 3)
    cv2.imwrite('temp_handshake_annotated.png', annotated)

    # Now test template matching
    print("\nTesting template matching...")
    template = icon
    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    print(f"  Best match score: {max_val:.4f}")
    print(f"  Best match location: {max_loc}")

    # Draw best match
    match_vis = screenshot.copy()
    top_left = max_loc
    bottom_right = (top_left[0] + cw, top_left[1] + ch)
    cv2.rectangle(match_vis, top_left, bottom_right, (0, 0, 255), 3)

    # Also draw ground truth location
    cv2.rectangle(match_vis, (actual_x, actual_y), (actual_x + cw, actual_y + ch), (0, 255, 0), 3)

    cv2.imwrite('temp_handshake_match_result.png', match_vis)

    print("\nFiles created:")
    print("  temp_handshake_region.png - Large region around icon")
    print("  temp_right_edge_icons.png - Right edge of screen")
    print("  temp_handshake_mask.png - Color-based mask")
    print("  temp_handshake_icon.png - Extracted icon template")
    print("  temp_handshake_annotated.png - Annotated with green box")
    print("  temp_handshake_match_result.png - Template matching result")
    print("    Green box = ground truth")
    print("    Red box = best match")
else:
    print("No contours found in peachy color range")
    print("Trying broader search...")

    # Save the right edge for manual inspection
    print("\nSaved temp_right_edge_icons.png for manual inspection")
