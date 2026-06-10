"""Extract new plus button from Windows screenshot and test both templates."""
import cv2
import sys
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load the Windows screenshot
frame = cv2.imread('screenshots/screenshot_20251203_140637.png')
if frame is None:
    print("ERROR: Could not load screenshot")
    exit(1)

print(f"Screenshot size: {frame.shape}")

# Extract region at X=1405, trying different Y positions to find the plus button
# Based on the search range, let's try Y positions in the rally list
X = 1405
W = 127
H = 132

# Try multiple Y positions to find where the plus button actually is
test_positions = range(400, 1800, 50)

print("\nSearching for plus button location...")
print("Extracting samples and checking if they look like plus buttons\n")

# Load old template for comparison
old_template_path = Path("templates/ground_truth/rally_plus_button_4k.png")
old_template = cv2.imread(str(old_template_path), cv2.IMREAD_GRAYSCALE)

frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

best_match_y = None
best_match_score = 1.0

for y in test_positions:
    # Extract ROI
    roi = frame_gray[y:y+H, X:X+W]

    if roi.shape[0] != H or roi.shape[1] != W:
        continue

    # Test against old template
    result = cv2.matchTemplate(roi, old_template, cv2.TM_SQDIFF_NORMED)
    score = float(cv2.minMaxLoc(result)[0])

    if score < best_match_score:
        best_match_score = score
        best_match_y = y

print(f"Best match with OLD template: Y={best_match_y}, score={best_match_score:.6f}")
print(f"Threshold: 0.05")
print(f"OLD template {'WORKS' if best_match_score <= 0.05 else 'FAILS'}\n")

if best_match_y is None:
    print("Could not find any reasonable match. Need manual Y coordinate.")
    exit(1)

# Extract new template from best match location
print(f"Extracting NEW template from Y={best_match_y}...")
new_template = frame[best_match_y:best_match_y+H, X:X+W]

# Save new template
new_template_path = Path("templates/ground_truth/rally_plus_button_4k_WINDOWS.png")
cv2.imwrite(str(new_template_path), new_template)
print(f"Saved NEW template to: {new_template_path}")

# Now test NEW template against the same screenshot
new_template_gray = cv2.cvtColor(new_template, cv2.COLOR_BGR2GRAY)

print("\nTesting NEW template against same screenshot...")
test_y = best_match_y
roi = frame_gray[test_y:test_y+H, X:X+W]
result = cv2.matchTemplate(roi, new_template_gray, cv2.TM_SQDIFF_NORMED)
score = float(cv2.minMaxLoc(result)[0])

print(f"NEW template at Y={test_y}: score={score:.6f}")
print(f"NEW template {'WORKS (score should be ~0.0)' if score <= 0.05 else 'FAILS'}")

# Visual comparison
print("\n" + "="*70)
print("COMPARISON:")
print(f"OLD template score: {best_match_score:.6f} ({'PASS' if best_match_score <= 0.05 else 'FAIL'})")
print(f"NEW template score: {score:.6f} ({'PASS' if score <= 0.05 else 'FAIL'})")
print("="*70)

if best_match_score > 0.05 and score <= 0.05:
    print("\n✓ CONFIRMED: Old template was from ADB screenshot, new one from Windows works!")
    print(f"Replace old template with: {new_template_path}")
elif best_match_score <= 0.05:
    print("\n✗ OLD template already works fine. Problem is elsewhere.")
else:
    print("\n? Both templates fail. Issue is different.")
