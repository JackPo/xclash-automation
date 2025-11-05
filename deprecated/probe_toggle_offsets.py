from find_player import Config, ADBController
from game_utils import GameHelper

config = Config()
adb = ADBController(config)
helper = GameHelper(adb, config)

offsets = [
    (0, 0),
    (-40, 0),
    (-80, 0),
    (-120, 0),
    (-160, 0),
    (-200, 0),
    (0, -40),
    (0, -80),
    (-40, -40),
    (-80, -40),
]

print('Initial state:', helper.check_world_view())
match = helper.get_button_match()
print('Initial match:', match)
if not match:
    raise SystemExit('No button match found')

for dx, dy in offsets:
    target = (match.center[0] + dx, match.center[1] + dy)
    print(f"Testing offset ({dx},{dy}) -> {target}")
    helper.adb.tap(*target)
    impor_time = 1.5
    import time
    time.sleep(impor_time)
    state = helper.check_world_view()
    print('  state:', state)
    if state[0] and state[1] == 'TOWN':
        print('  SUCCESS: Reached Town with this offset')
        break
else:
    print('No offset toggled to Town')

print('Final state:', helper.check_world_view())
