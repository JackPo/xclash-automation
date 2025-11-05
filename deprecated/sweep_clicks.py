from find_player import Config, ADBController
from game_utils import GameHelper
import time

config = Config()
adb = ADBController(config)
helper = GameHelper(adb, config)
match = helper.get_button_match()
print('initial match', match)
fractions = [
    (0.5, 0.5), (0.1, 0.5), (0.9, 0.5),
    (0.2, 0.7), (0.8, 0.7),
    (0.2, 0.3), (0.8, 0.3)
]
for xf, yf in fractions:
    match = helper.get_button_match()
    print('match before click', match)
    if not match:
        break
    x = int(match.top_left[0] + helper.button_matcher.template_shape[1] * xf)
    y = int(match.top_left[1] + helper.button_matcher.template_shape[0] * yf)
    print(f'clicking {xf:.2f}, {yf:.2f} -> {(x,y)}')
    helper.adb.tap(x, y)
    time.sleep(2)
    print('state:', helper.check_world_view())
