#!/usr/bin/env python3
"""Detailed test of the town/world toggle detection and switching."""

from find_player import Config, ADBController
from game_utils import GameHelper

config = Config()
adb = ADBController(config)
helper = GameHelper(adb, config)

print("=" * 60)
print("Testing World/Town Toggle Detection")
print("=" * 60)

# Test current state
print("\n1. Checking current state...")
detected, state = helper.check_world_view()
match = helper._last_button_match

print(f"   Detected: {detected}")
print(f"   State: '{state}'")
if match:
    print(f"   Score: {match.score:.3f}")
    print(f"   Label: {match.label}")
    print(f"   Center: {match.center}")
    print(f"   Threshold: {helper.button_matcher.threshold}")
else:
    print("   No match found!")

# Try to toggle
if detected and state in ("WORLD", "TOWN"):
    target_state = "TOWN" if state == "WORLD" else "WORLD"
    print(f"\n2. Attempting to switch from {state} to {target_state}...")
    success = helper.switch_to_view(target_state, max_attempts=2)

    if success:
        print(f"\n✓ Successfully switched to {target_state} view")

        # Verify new state
        print("\n3. Verifying new state...")
        detected2, state2 = helper.check_world_view()
        print(f"   Detected: {detected2}")
        print(f"   State: '{state2}'")

        # Try switching back
        print(f"\n4. Attempting to switch back to {state}...")
        success2 = helper.switch_to_view(state, max_attempts=2)

        if success2:
            print(f"\n✓ Successfully switched back to {state} view")
            print("\n" + "=" * 60)
            print("TOGGLE TEST: SUCCESS ✓")
            print("=" * 60)
        else:
            print(f"\n✗ Failed to switch back to {state}")
    else:
        print(f"\n✗ Failed to switch to {target_state}")
else:
    print("\n✗ Cannot toggle - current state not detected properly")
    print("\nDebug: Check templates/debug/button_match_*.png for captured images")
