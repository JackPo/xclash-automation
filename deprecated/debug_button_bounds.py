import cv2
from pathlib import Path
from button_matcher import ButtonMatcher

matcher = ButtonMatcher(template_dir=Path('templates/buttons'), debug_dir=Path('templates/debug'), threshold=0.85)
images = [
    ('latest_attempt', 'templates/debug/testing/latest_attempt.png'),
    ('button_test_1', 'templates/debug/testing/button_test_1_20251103_123807.png'),
]
for name, path in images:
    frame = cv2.imread(path)
    match = matcher.match(frame, save_debug=False)
    if match:
        print(name, match)
    else:
        print(name, 'no match')
