from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.soldier_tile_matcher import get_matcher
import cv2

win = WindowsScreenshotHelper()
frame = win.get_screenshot_cv2()

matcher = get_matcher()

print("Testing soldier tile detection...")
print("=" * 60)

for level in range(3, 9):
    if level not in matcher.templates:
        print(f"Lv{level}: NO TEMPLATE")
        continue

    template = matcher.templates[level]
    result = cv2.matchTemplate(frame, template, cv2.TM_SQDIFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    x, y = min_loc

    print(f"Lv{level}: score={min_val:.6f} at ({x}, {y})")

    if min_val < 0.015:
        print(f"  MATCH (threshold 0.015)")
    elif min_val < 0.03:
        print(f"  CLOSE (would match with 0.03 threshold)")
    else:
        print(f"  NO MATCH")

print("=" * 60)

visible = matcher.find_visible_soldiers(frame)
print(f"\nVisible soldiers with current threshold: {list(visible.keys())}")
