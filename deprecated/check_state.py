from find_player import Config, ADBController
from game_utils import GameHelper
config = Config()
adb = ADBController(config)
helper = GameHelper(adb, config)
print(helper.check_world_view())
