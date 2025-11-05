import time
from find_player import Config, ADBController
from game_utils import GameHelper
from button_matcher import ButtonMatcher
from pathlib import Path
import cv2

config = Config()
adb = ADBController(config)
helper = GameHelper(adb, config)
matcher = helper.button_matcher

match = helper.get_button_match()
print('match:', match)

if not match:
    raise SystemExit('no match')

fractions = [0.15]
for frac in fractions:
    x = int(match.top_left[0] + matcher.template_shape[1] * frac)
    y = int(match.top_left[1] + matcher.template_shape[0] * 0.75)
    print('click:', (x, y))
    helper.adb.tap(x, y)
    time.sleep(1.0)
    # capture screenshot to inspect
    tmp = Path('templates/debug/testing/post_click.png')
    adb.screenshot(tmp)
    frame = cv2.imread(str(tmp))
    m2 = matcher.match(frame, save_debug=False)
    print('post match:', m2)
    state = helper.check_world_view()
    print('state after click:', state)
