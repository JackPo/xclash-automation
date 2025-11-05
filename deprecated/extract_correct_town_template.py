"""Extract correct TOWN template from screenshot_town.png"""
import cv2

# Load TOWN screenshot
img = cv2.imread("screenshot_town.png")

if img is None:
    print("ERROR: Could not load screenshot_town.png")
    exit(1)

print(f"Screenshot size: {img.shape[1]}x{img.shape[0]}")

# The button should be at the same location as WORLD: (2160, 1190) to (2560, 1440)
x, y = 2160, 1190
x2, y2 = 2560, 1440

print(f"Extracting button from ({x}, {y}) to ({x2}, {y2})")

# Extract button area
town_button = img[y:y2, x:x2]

print(f"Extracted button size: {town_button.shape[1]}x{town_button.shape[0]}")

# Save as new TOWN template
output_file = "templates/buttons/town_button_template_NEW.png"
cv2.imwrite(output_file, town_button)
print(f"\nSaved NEW TOWN template to: {output_file}")

# Test the match score
result = cv2.matchTemplate(img, town_button, cv2.TM_CCOEFF_NORMED)
min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

print(f"\nNEW TOWN template match score: {max_val:.4f} ({max_val*100:.2f}%)")
print(f"Match location: {max_loc}")

if max_val >= 0.95:
    print("EXCELLENT! New TOWN template matches at 95%+")
else:
    print(f"WARNING: New TOWN template only matches at {max_val*100:.2f}%")

# Compare with old template
old_template = cv2.imread("templates/buttons/town_button_template.png")
if old_template is not None:
    result_old = cv2.matchTemplate(img, old_template, cv2.TM_CCOEFF_NORMED)
    min_val_old, max_val_old, min_loc_old, max_loc_old = cv2.minMaxLoc(result_old)

    print(f"\nOLD TOWN template match score: {max_val_old:.4f} ({max_val_old*100:.2f}%)")
    print(f"\nImprovement: +{(max_val - max_val_old)*100:.2f} percentage points")
