"""Test switching in both directions using the working method"""
import sys
import time
sys.path.insert(0, '.')

from view_detection import detect_current_view, get_detection_result, ViewState
from find_player import ADBController, Config

def switch_view_working_method(adb: ADBController, target_state: ViewState) -> bool:
    """Switch to target state using the proven working method"""

    # Detect current state
    result = get_detection_result(adb)
    print(f"Current state: {result.state.value} (confidence: {result.confidence:.2f})")

    if result.state == target_state:
        print(f"Already in {target_state.value} state")
        return True

    if result.match is None:
        print("ERROR: Button not detected")
        return False

    # Calculate click position
    x, y = result.match.top_left
    x2, y2 = result.match.bottom_right
    w = x2 - x
    h = y2 - y

    if target_state == ViewState.WORLD:
        x_frac = 0.75  # Right side (WORLD icon)
        print(f"Switching to WORLD: clicking RIGHT side (x_frac=0.75)")
    else:
        x_frac = 0.25  # Left side (TOWN icon)
        print(f"Switching to TOWN: clicking LEFT side (x_frac=0.25)")

    click_x = int(x + w * x_frac)
    click_y = int(y + h * 0.5)
    print(f"Click position: ({click_x}, {click_y})")

    # Click
    adb.tap(click_x, click_y)
    time.sleep(2)

    # Verify
    result_after = get_detection_result(adb)
    print(f"After click: {result_after.state.value} (confidence: {result_after.confidence:.2f})")

    if result_after.state == target_state:
        print("SUCCESS!")
        return True
    else:
        print("FAILED: State did not change to target")
        return False

def main():
    print("="*70)
    print("BIDIRECTIONAL SWITCHING TEST")
    print("="*70)
    print("\nTesting switching in both directions using x_frac method:")
    print("  WORLD icon: 75% from left (right side)")
    print("  TOWN icon: 25% from left (left side)\n")

    config = Config()
    adb = ADBController(config)

    # Test 1: Switch to WORLD (if not already)
    print("\n" + "="*70)
    print("TEST 1: Switch to WORLD")
    print("="*70)
    result1 = switch_view_working_method(adb, ViewState.WORLD)

    time.sleep(1)

    # Test 2: Switch to TOWN
    print("\n" + "="*70)
    print("TEST 2: Switch to TOWN")
    print("="*70)
    result2 = switch_view_working_method(adb, ViewState.TOWN)

    time.sleep(1)

    # Test 3: Switch back to WORLD
    print("\n" + "="*70)
    print("TEST 3: Switch back to WORLD")
    print("="*70)
    result3 = switch_view_working_method(adb, ViewState.WORLD)

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Test 1 (to WORLD): {'PASS' if result1 else 'FAIL'}")
    print(f"Test 2 (to TOWN): {'PASS' if result2 else 'FAIL'}")
    print(f"Test 3 (back to WORLD): {'PASS' if result3 else 'FAIL'}")

    if all([result1, result2, result3]):
        print("\nALL TESTS PASSED!")
        print("\nWorking coordinates:")
        print("  WORLD icon (right): x_frac=0.75, y_frac=0.5")
        print("  TOWN icon (left): x_frac=0.25, y_frac=0.5")
    else:
        print("\nSOME TESTS FAILED")

if __name__ == "__main__":
    main()
