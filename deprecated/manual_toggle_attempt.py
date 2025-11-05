from find_player import Config, ADBController
from game_utils import GameHelper

config = Config()
adb = ADBController(config)
helper = GameHelper(adb, config)

match = helper.get_button_match()
print('match:', match)
if not match:
    raise SystemExit('no match')

for frac in [0.15, 0.12, 0.09, 0.06, 0.03]:
    x = int(match.top_left[0] + helper.button_matcher.template_shape[1] * frac)
    y = int(match.top_left[1] + helper.button_matcher.template_shape[0] * 0.75)
    print(f'clicking fraction {frac:.2f} at {(x,y)}')
    helper.adb.tap(x, y)
    import time
    time.sleep(2.0)
    print('state now:', helper.check_world_view())
