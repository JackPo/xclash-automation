"""Compare the button area in WORLD vs TOWN screenshots to see what actually changes"""
import cv2
import numpy as np

# Load both screenshots
world_img = cv2.imread("screenshot_check.png")
town_img = cv2.imread("screenshot_town.png")

if world_img is None or town_img is None:
    print("ERROR: Could not load screenshots")
    exit(1)

# Extract button areas
x, y = 2160, 1190
x2, y2 = 2560, 1440

world_button = world_img[y:y2, x:x2]
town_button = town_img[y:y2, x:x2]

# Save for visual comparison
cv2.imwrite("comparison_world_button.png", world_button)
cv2.imwrite("comparison_town_button.png", town_button)

# Calculate pixel difference
diff = cv2.absdiff(world_button, town_button)
diff_sum = diff.sum()
total_pixels = world_button.shape[0] * world_button.shape[1] * world_button.shape[2]
avg_diff_per_pixel = diff_sum / total_pixels

print("="*70)
print("BUTTON AREA COMPARISON: WORLD vs TOWN")
print("="*70)
print(f"\nButton size: {world_button.shape[1]}x{world_button.shape[0]}")
print(f"Total pixel difference: {diff_sum:,.0f}")
print(f"Average difference per pixel: {avg_diff_per_pixel:.2f}")

if avg_diff_per_pixel < 1.0:
    print("\nRESULT: Buttons are IDENTICAL (or near-identical)")
    print("The button visual does NOT change between WORLD and TOWN states!")
else:
    print(f"\nRESULT: Buttons have {avg_diff_per_pixel:.2f} avg difference per pixel")

# Find where differences occur
gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
_, thresh = cv2.threshold(gray_diff, 10, 255, cv2.THRESH_BINARY)
changed_pixels = cv2.countNonZero(thresh)
total_button_pixels = thresh.shape[0] * thresh.shape[1]
percent_changed = (changed_pixels / total_button_pixels) * 100

print(f"\nPixels with difference > 10: {changed_pixels}/{total_button_pixels} ({percent_changed:.2f}%)")

if changed_pixels > 0:
    # Highlight differences
    diff_vis = world_button.copy()
    diff_vis[thresh > 0] = [0, 0, 255]  # Mark differences in red
    cv2.imwrite("comparison_diff_highlighted.png", diff_vis)
    print("Saved difference visualization to: comparison_diff_highlighted.png")

# Now compare full screenshots to see what DOES change
full_diff = cv2.absdiff(world_img, town_img)
gray_full_diff = cv2.cvtColor(full_diff, cv2.COLOR_BGR2GRAY)
_, full_thresh = cv2.threshold(gray_full_diff, 30, 255, cv2.THRESH_BINARY)

# Find contours of changed regions
contours, _ = cv2.findContours(full_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

print(f"\n" + "="*70)
print("FULL SCREENSHOT COMPARISON")
print("="*70)
print(f"Found {len(contours)} regions with significant changes")

significant_changes = []
for contour in contours:
    x_c, y_c, w_c, h_c = cv2.boundingRect(contour)
    area = w_c * h_c
    if area > 5000:  # Filter small changes
        significant_changes.append((x_c, y_c, w_c, h_c, area))

significant_changes.sort(key=lambda c: c[4], reverse=True)

print(f"\nTop 10 largest changed regions:")
for i, (x_c, y_c, w_c, h_c, area) in enumerate(significant_changes[:10]):
    print(f"{i+1}. Position: ({x_c}, {y_c}), Size: {w_c}x{h_c}, Area: {area:,} pixels")

# Mark changes on visualization
vis = world_img.copy()
for x_c, y_c, w_c, h_c, area in significant_changes[:10]:
    cv2.rectangle(vis, (x_c, y_c), (x_c+w_c, y_c+h_c), (0, 255, 0), 3)
    cv2.putText(vis, f"{area//1000}K", (x_c, y_c-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

cv2.imwrite("comparison_full_changes.png", vis)
print("\nSaved full screenshot changes to: comparison_full_changes.png")

print("\n" + "="*70)
print("CONCLUSION")
print("="*70)
print("The button in the lower-right corner does NOT change.")
print("To detect WORLD vs TOWN state, we need to look at OTHER parts of the screen.")
