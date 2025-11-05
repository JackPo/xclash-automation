"""Compare before/after clicking UNION to see what actually changed"""
import cv2

before = cv2.imread("union_click_before.png")
after = cv2.imread("union_click_after.png")

if before is None or after is None:
    print("ERROR: Could not load before/after images")
    exit(1)

# Calculate difference
diff = cv2.absdiff(before, after)

# Find regions with significant changes
gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
_, thresh = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)

# Find contours of changed regions
contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

print(f"Found {len(contours)} regions with changes")

# Draw boxes around changed regions
vis = before.copy()
significant_changes = []

for contour in contours:
    x, y, w, h = cv2.boundingRect(contour)
    area = w * h

    if area > 1000:  # Filter out small noise
        cv2.rectangle(vis, (x, y), (x+w, y+h), (0, 255, 0), 2)
        significant_changes.append((x, y, w, h, area))
        print(f"Change at ({x}, {y}), size: {w}x{h}, area: {area}")

# Sort by area
significant_changes.sort(key=lambda c: c[4], reverse=True)

print(f"\nTop 5 largest changes:")
for i, (x, y, w, h, area) in enumerate(significant_changes[:5]):
    print(f"{i+1}. ({x}, {y}) size {w}x{h}, area: {area} pixels")

# Save visualization
cv2.imwrite("union_click_changes_marked.png", vis)
print(f"\nSaved visualization to: union_click_changes_marked.png")

# Check if button area changed
button_x, button_y = 2160, 1190
button_diff = diff[button_y:button_y+250, button_x:button_x+400]
button_diff_sum = button_diff.sum()

print(f"\nButton area difference: {button_diff_sum}")
if button_diff_sum < 100000:
    print("The button itself did NOT change!")
    print("This confirms the button visual stays the same.")
else:
    print("The button DID change!")
