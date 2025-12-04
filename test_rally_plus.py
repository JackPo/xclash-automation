"""Test rally plus button matcher on screenshot_20251203_140637.png"""
import cv2
import sys
from pathlib import Path
from utils.rally_plus_matcher import RallyPlusMatcher

# Set UTF-8 encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load screenshot
frame = cv2.imread('screenshots/screenshot_20251203_140637.png')
if frame is None:
    print("ERROR: Could not load screenshot")
    exit(1)

print(f"Screenshot size: {frame.shape}")

matcher = RallyPlusMatcher()
print(f"Threshold: {matcher.threshold}")
print(f"Search Y range: {matcher.SEARCH_Y_START} to {matcher.SEARCH_Y_END}")
print(f"Fixed X: {matcher.PLUS_BUTTON_X}")
print(f"Button size: {matcher.PLUS_BUTTON_WIDTH}x{matcher.PLUS_BUTTON_HEIGHT}")

# Find all plus buttons
plus_buttons = matcher.find_all_plus_buttons(frame)

print(f"\nFound {len(plus_buttons)} plus button(s)")
for i, (x, y, score) in enumerate(plus_buttons):
    print(f"  Button {i}: pos=({x}, {y}), score={score:.6f}")

if not plus_buttons:
    print("\nNO PLUS BUTTONS FOUND!")
    print("Debugging - checking template matching scores...")

    # Load template
    template_dir = Path(__file__).parent / "templates" / "ground_truth"
    template_path = template_dir / "rally_plus_button_4k.png"
    template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)

    if template is None:
        print(f"ERROR: Could not load template from {template_path}")
        exit(1)

    print(f"Template size: {template.shape}")

    # Convert frame to grayscale
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Check a few sample Y positions
    test_y_positions = [500, 700, 900, 1100, 1300, 1500]
    print(f"\nSampling scores at different Y positions (X={matcher.PLUS_BUTTON_X}):")

    best_score = 1.0
    best_y = 0

    for y in test_y_positions:
        roi = frame_gray[
            y : y + matcher.PLUS_BUTTON_HEIGHT,
            matcher.PLUS_BUTTON_X : matcher.PLUS_BUTTON_X + matcher.PLUS_BUTTON_WIDTH
        ]

        if roi.shape[0] == matcher.PLUS_BUTTON_HEIGHT and roi.shape[1] == matcher.PLUS_BUTTON_WIDTH:
            result = cv2.matchTemplate(roi, template, cv2.TM_SQDIFF_NORMED)
            score = float(cv2.minMaxLoc(result)[0])
            status = "MATCH!" if score <= matcher.threshold else "no match"
            print(f"  Y={y}: score={score:.6f} ({status})")

            if score < best_score:
                best_score = score
                best_y = y

    print(f"\nBest score overall: {best_score:.6f} at Y={best_y}")
    print(f"Threshold: {matcher.threshold}")
    print(f"Best score is {'BELOW (would match)' if best_score <= matcher.threshold else 'ABOVE (no match)'} threshold")
