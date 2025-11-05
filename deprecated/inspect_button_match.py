import cv2
from pathlib import Path
from button_matcher import ButtonMatcher

matcher = ButtonMatcher(template_dir=Path('templates/buttons'), debug_dir=Path('templates/debug'), threshold=0.85)
frame = cv2.imread('templates/debug/testing/latest_attempt.png')
match = matcher.match(frame, save_debug=False)
print(match)
if match:
    print('shape', matcher.template_shape)
    print('top_left', match.top_left, 'bottom_right', match.bottom_right)
