from find_player import Config, ADBController
from game_utils import GameHelper
config = Config()
adb = ADBController(config)
helper = GameHelper(adb, config)
match = helper.button_matcher.match_from_adb(adb)
print('match', match)
if match and match.score >= helper.button_matcher.threshold:
    print('state', match.label)
else:
    print('below threshold')
