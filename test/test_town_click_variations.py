"""Test variations for clicking TOWN icon - double-click, longer wait, active side"""
import sys
import time
sys.path.insert(0, '.')

from view_detection import detect_current_view, get_detection_result, ViewState
from find_player import ADBController, Config

def test_variation(adb, description, test_func):
    """Helper to test a variation"""
    print(f"\n{'='*70}")
    print(f"TEST: {description}")
    print(f"{'='*70}")

    # Make sure we start in WORLD
    current = detect_current_view(adb)
    if current == ViewState.TOWN:
        # Switch back to WORLD using known working method
        result = get_detection_result(adb)
        if result.match:
            x, y = result.match.top_left
            w = result.match.bottom_right[0] - x
            h = result.match.bottom_right[1] - y
            adb.tap(int(x + w * 0.75), int(y + h * 0.5))
            time.sleep(2)

    current = detect_current_view(adb)
    print(f"Starting state: {current.value}")

    if current != ViewState.WORLD:
        print("ERROR: Could not start in WORLD state")
        return False

    # Run test
    result = test_func(adb)

    # Check result
    final_state = detect_current_view(adb)
    print(f"Final state: {final_state.value}")

    success = (final_state == ViewState.TOWN)
    print(f"Result: {'SUCCESS' if success else 'FAILED'}")

    return success

def test_click_active_side(adb):
    """Try clicking the active WORLD side (maybe it's a dropdown?)"""
    print("Clicking the ACTIVE WORLD side (right, x_frac=0.75)...")

    result = get_detection_result(adb)
    if not result.match:
        return False

    x, y = result.match.top_left
    w = result.match.bottom_right[0] - x
    h = result.match.bottom_right[1] - y

    click_x = int(x + w * 0.75)
    click_y = int(y + h * 0.5)
    print(f"Position: ({click_x}, {click_y})")

    adb.tap(click_x, click_y)
    time.sleep(3)  # Longer wait

    return True

def test_double_click_left(adb):
    """Try double-clicking the left side"""
    print("Double-clicking LEFT side (x_frac=0.25)...")

    result = get_detection_result(adb)
    if not result.match:
        return False

    x, y = result.match.top_left
    w = result.match.bottom_right[0] - x
    h = result.match.bottom_right[1] - y

    click_x = int(x + w * 0.25)
    click_y = int(y + h * 0.5)
    print(f"Position: ({click_x}, {click_y})")

    adb.tap(click_x, click_y)
    time.sleep(0.1)
    adb.tap(click_x, click_y)
    time.sleep(3)

    return True

def test_long_wait(adb):
    """Try single click with very long wait"""
    print("Single click LEFT side with 5 second wait...")

    result = get_detection_result(adb)
    if not result.match:
        return False

    x, y = result.match.top_left
    w = result.match.bottom_right[0] - x
    h = result.match.bottom_right[1] - y

    click_x = int(x + w * 0.25)
    click_y = int(y + h * 0.5)
    print(f"Position: ({click_x}, {click_y})")

    adb.tap(click_x, click_y)
    time.sleep(5)

    return True

def test_far_left(adb):
    """Try clicking very far left (x_frac=0.05)"""
    print("Clicking FAR LEFT (x_frac=0.05)...")

    result = get_detection_result(adb)
    if not result.match:
        return False

    x, y = result.match.top_left
    w = result.match.bottom_right[0] - x
    h = result.match.bottom_right[1] - y

    click_x = int(x + w * 0.05)
    click_y = int(y + h * 0.5)
    print(f"Position: ({click_x}, {click_y})")

    adb.tap(click_x, click_y)
    time.sleep(3)

    return True

def main():
    print("="*70)
    print("TOWN ICON CLICK VARIATIONS TEST")
    print("="*70)
    print("\nTesting different methods to switch from WORLD to TOWN\n")

    config = Config()
    adb = ADBController(config)

    tests = [
        ("Click Active Side (maybe dropdown?)", test_click_active_side),
        ("Double-Click Left Side", test_double_click_left),
        ("Long Wait (5s) after Left Click", test_long_wait),
        ("Far Left Click (x_frac=0.05)", test_far_left),
    ]

    results = {}

    for name, test_func in tests:
        success = test_variation(adb, name, test_func)
        results[name] = success

        if success:
            print(f"\n*** {name} WORKED! ***")
            break

        time.sleep(1)

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    for name, success in results.items():
        print(f"{name}: {'PASS' if success else 'FAIL'}")

    working = [name for name, success in results.items() if success]

    if working:
        print(f"\nWORKING METHOD: {working[0]}")
    else:
        print("\nNO METHOD WORKED")
        print("\nPossible explanations:")
        print("  1. Game might disable switching from WORLD to TOWN in current game state")
        print("  2. Button might be read-only when in WORLD view")
        print("  3. Might need to close a dialog or perform another action first")
        print("  4. Button design might be one-directional")

if __name__ == "__main__":
    main()
