#!/usr/bin/env python3
"""Simple test of the town/world toggle with adjusted threshold."""

from find_player import Config, ADBController
from game_utils import GameHelper

config = Config()
adb = ADBController(config)
helper = GameHelper(adb, config)

# Lower the threshold since we're getting 0.768
helper.button_matcher.threshold = 0.75

print("=" * 60)
print("Testing World/Town Toggle (threshold: 0.75)")
print("=" * 60)

# Test current state
print("\n1. Checking current state...")
detected, state = helper.check_world_view()
match = helper._last_button_match

print(f"   Detected: {detected}")
print(f"   State: {state}")
if match:
    print(f"   Score: {match.score:.3f}")
    print(f"   Center: {match.center}")

if not detected:
    print("   ERROR: Cannot detect button state")
    exit(1)

# Toggle to opposite state
target_state = "TOWN" if state == "WORLD" else "WORLD"
print(f"\n2. Switching from {state} to {target_state}...")
success = helper.switch_to_view(target_state, max_attempts=2)

if success:
    print(f"   SUCCESS: Switched to {target_state}")

    # Switch back
    print(f"\n3. Switching back to {state}...")
    success2 = helper.switch_to_view(state, max_attempts=2)

    if success2:
        print(f"   SUCCESS: Switched back to {state}")
        print("\n" + "=" * 60)
        print("TOGGLE TEST: PASSED")
        print("=" * 60)
    else:
        print(f"   FAILED: Could not switch back to {state}")
else:
    print(f"   FAILED: Could not switch to {target_state}")
