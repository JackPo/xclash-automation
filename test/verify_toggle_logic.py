"""Verify the exact toggle logic for the World/Town button"""
import sys
import time
sys.path.insert(0, '.')

from view_detection import detect_current_view, get_detection_result, ViewState
from find_player import ADBController, Config

def click_at_position(adb, x_frac, description):
    """Click at given fractional position and return new state"""
    result = get_detection_result(adb)
    if not result.match:
        return None

    x, y = result.match.top_left
    w = result.match.bottom_right[0] - x
    h = result.match.bottom_right[1] - y

    click_x = int(x + w * x_frac)
    click_y = int(y + h * 0.5)

    print(f"  {description} (x_frac={x_frac})")
    print(f"  Position: ({click_x}, {click_y})")

    adb.tap(click_x, click_y)
    time.sleep(2.5)

    return detect_current_view(adb)

def main():
    print("="*70)
    print("VERIFY TOGGLE LOGIC")
    print("="*70)
    print("\nTesting which side to click for each state\n")

    config = Config()
    adb = ADBController(config)

    # Test 1: From WORLD, click left (0.25)
    print("\n" + "="*70)
    print("TEST 1: When in WORLD, click LEFT side (0.25)")
    print("="*70)

    current = detect_current_view(adb)
    print(f"Starting state: {current.value}")

    if current != ViewState.WORLD:
        print("Skipping - not in WORLD state")
    else:
        new_state = click_at_position(adb, 0.25, "Click LEFT side")
        print(f"Result: {current.value} → {new_state.value}")

    time.sleep(1)

    # Test 2: From WORLD, click right (0.75)
    print("\n" + "="*70)
    print("TEST 2: When in WORLD, click RIGHT side (0.75)")
    print("="*70)

    current = detect_current_view(adb)
    print(f"Starting state: {current.value}")

    if current != ViewState.WORLD:
        print("Need to reset to WORLD first...")
        # We know clicking 0.75 from TOWN goes to WORLD
        click_at_position(adb, 0.75, "Reset to WORLD")
        current = detect_current_view(adb)

    if current == ViewState.WORLD:
        new_state = click_at_position(adb, 0.75, "Click RIGHT side")
        print(f"Result: {current.value} → {new_state.value}")

    time.sleep(1)

    # Test 3: From TOWN, click left (0.25)
    print("\n" + "="*70)
    print("TEST 3: When in TOWN, click LEFT side (0.25)")
    print("="*70)

    current = detect_current_view(adb)
    print(f"Starting state: {current.value}")

    if current != ViewState.TOWN:
        print("Skipping - not in TOWN state")
    else:
        new_state = click_at_position(adb, 0.25, "Click LEFT side")
        print(f"Result: {current.value} → {new_state.value}")

    time.sleep(1)

    # Test 4: From TOWN, click right (0.75)
    print("\n" + "="*70)
    print("TEST 4: When in TOWN, click RIGHT side (0.75)")
    print("="*70)

    current = detect_current_view(adb)
    print(f"Starting state: {current.value}")

    if current != ViewState.TOWN:
        print("Need to reset to TOWN first...")
        # Click 0.75 from WORLD goes to TOWN
        click_at_position(adb, 0.75, "Reset to TOWN")
        current = detect_current_view(adb)

    if current == ViewState.TOWN:
        new_state = click_at_position(adb, 0.75, "Click RIGHT side")
        print(f"Result: {current.value} → {new_state.value}")

    print("\n" + "="*70)
    print("CONCLUSION")
    print("="*70)
    print("\nBased on test results, determine the toggle logic:")
    print("  - Does clicking LEFT (0.25) always go to one specific state?")
    print("  - Does clicking RIGHT (0.75) always go to one specific state?")
    print("  - Or does clicking toggle based on current state?")

if __name__ == "__main__":
    main()
