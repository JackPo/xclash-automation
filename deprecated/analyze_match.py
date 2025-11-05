from pathlib import Path
import cv2
from button_matcher import ButtonMatcher

frame_path = Path('templates/debug/testing/debug_btn_1_20251103_162924.png')
frame = cv2.imread(str(frame_path))
matcher = ButtonMatcher(template_dir=Path('templates/buttons'), debug_dir=Path('templates/debug'), threshold=0.85)
match = matcher.match(frame, save_debug=False)
print('match:', match)
if match:
    print('label:', match.label, 'score:', match.score)
