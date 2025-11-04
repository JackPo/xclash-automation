"""Diagnostic tests to find working click method for World/Town button"""
import sys
import time
sys.path.insert(0, '.')

from view_detection import detect_current_view, get_detection_result, ViewState
from find_player import ADBController, Config

def test_center_click(adb: ADBController):
    """Test 1: Click at center of detected button"""
    print("\n" + "="*70)
    print("TEST 1: Click at Center of Button")
    print("="*70)

    # Detect current state
    result_before = get_detection_result(adb)
    print(f"\nBefore: {result_before.state.value} (confidence: {result_before.confidence:.2f})")

    if result_before.match is None:
        print("ERROR: Button not detected!")
        return False

    # Calculate center
    center_x, center_y = result_before.match.center
    print(f"Button center: ({center_x}, {center_y})")
    print(f"Clicking at center...")

    adb.tap(center_x, center_y)
    time.sleep(2)

    # Check if changed
    result_after = get_detection_result(adb)
    print(f"After: {result_after.state.value} (confidence: {result_after.confidence:.2f})")

    if result_after.state != result_before.state:
        print("SUCCESS: State changed by clicking center!")
        return True
    else:
        print("FAILED: State did not change")
        return False

def test_icon_positions(adb: ADBController):
    """Test 2: Click on specific icon positions"""
    print("\n" + "="*70)
    print("TEST 2: Click on Icon Positions (Left and Right)")
    print("="*70)

    # Detect current state
    result = get_detection_result(adb)
    print(f"\nCurrent state: {result.state.value}")

    if result.match is None:
        print("ERROR: Button not detected!")
        return False

    # Get button dimensions
    x, y = result.match.top_left
    x2, y2 = result.match.bottom_right
    w = x2 - x
    h = y2 - y

    print(f"Button bounds: ({x}, {y}) to ({x2}, {y2}), size: {w}x{h}")

    # Determine which icon to click
    if result.state == ViewState.WORLD:
        print("\nCurrently WORLD - will click LEFT side (TOWN icon)")
        x_positions = [
            (0.25, "25% from left"),
            (0.20, "20% from left"),
            (0.30, "30% from left"),
        ]
    elif result.state == ViewState.TOWN:
        print("\nCurrently TOWN - will click RIGHT side (WORLD icon)")
        x_positions = [
            (0.75, "75% from left"),
            (0.80, "80% from left"),
            (0.70, "70% from left"),
        ]
    else:
        print("ERROR: Unknown state")
        return False

    y_frac = 0.5  # Middle vertically

    # Try each position
    for x_frac, description in x_positions:
        print(f"\n  Testing: {description} (x_frac={x_frac})")

        # Calculate position
        click_x = int(x + w * x_frac)
        click_y = int(y + h * y_frac)
        print(f"  Position: ({click_x}, {click_y})")

        # Get state before
        state_before = detect_current_view(adb)

        # Click
        print(f"  Clicking...")
        adb.tap(click_x, click_y)
        time.sleep(2)

        # Check state after
        state_after = detect_current_view(adb)
        print(f"  Before: {state_before.value}, After: {state_after.value}")

        if state_after != state_before:
            print(f"  SUCCESS! Position {description} works!")
            return True
        else:
            print(f"  Failed - state unchanged")

    print("\nFAILED: None of the icon positions worked")
    return False

def test_double_tap(adb: ADBController):
    """Test 3: Try double-tap"""
    print("\n" + "="*70)
    print("TEST 3: Double-Tap at Icon Position")
    print("="*70)

    # Detect current state
    result = get_detection_result(adb)
    print(f"\nCurrent state: {result.state.value}")

    if result.match is None:
        print("ERROR: Button not detected!")
        return False

    # Calculate icon position
    x, y = result.match.top_left
    x2, y2 = result.match.bottom_right
    w = x2 - x
    h = y2 - y

    if result.state == ViewState.WORLD:
        x_frac = 0.25  # TOWN icon on left
        print("Clicking LEFT side (TOWN icon) with double-tap")
    else:
        x_frac = 0.75  # WORLD icon on right
        print("Clicking RIGHT side (WORLD icon) with double-tap")

    click_x = int(x + w * x_frac)
    click_y = int(y + h * 0.5)
    print(f"Position: ({click_x}, {click_y})")

    state_before = detect_current_view(adb)

    # Double tap
    print("Double-tapping...")
    adb.tap(click_x, click_y)
    time.sleep(0.1)
    adb.tap(click_x, click_y)
    time.sleep(2)

    state_after = detect_current_view(adb)
    print(f"Before: {state_before.value}, After: {state_after.value}")

    if state_after != state_before:
        print("SUCCESS: Double-tap worked!")
        return True
    else:
        print("FAILED: Double-tap did not work")
        return False

def test_long_press(adb: ADBController):
    """Test 4: Try long press using swipe with 0 distance"""
    print("\n" + "="*70)
    print("TEST 4: Long Press (1 second) at Icon Position")
    print("="*70)

    # Detect current state
    result = get_detection_result(adb)
    print(f"\nCurrent state: {result.state.value}")

    if result.match is None:
        print("ERROR: Button not detected!")
        return False

    # Calculate icon position
    x, y = result.match.top_left
    x2, y2 = result.match.bottom_right
    w = x2 - x
    h = y2 - y

    if result.state == ViewState.WORLD:
        x_frac = 0.25  # TOWN icon on left
        print("Long-pressing LEFT side (TOWN icon)")
    else:
        x_frac = 0.75  # WORLD icon on right
        print("Long-pressing RIGHT side (WORLD icon)")

    click_x = int(x + w * x_frac)
    click_y = int(y + h * 0.5)
    print(f"Position: ({click_x}, {click_y})")

    state_before = detect_current_view(adb)

    # Long press via swipe with 0 movement
    print("Long-pressing for 1 second...")
    adb.swipe(click_x, click_y, click_x, click_y, 1000)
    time.sleep(2)

    state_after = detect_current_view(adb)
    print(f"Before: {state_before.value}, After: {state_after.value}")

    if state_after != state_before:
        print("SUCCESS: Long press worked!")
        return True
    else:
        print("FAILED: Long press did not work")
        return False

def main():
    print("="*70)
    print("WORLD/TOWN BUTTON CLICK DIAGNOSTICS")
    print("="*70)
    print("\nThis will test different clicking methods to find what works.")
    print("Make sure BlueStacks is running and game is visible.\n")

    # Initialize ADB
    config = Config()
    adb = ADBController(config)

    # Run tests in sequence
    tests = [
        ("Center Click", test_center_click),
        ("Icon Positions", test_icon_positions),
        ("Double-Tap", test_double_tap),
        ("Long Press", test_long_press),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            result = test_func(adb)
            results[test_name] = result

            if result:
                print(f"\n*** {test_name} WORKED! ***")
                print("No need to run remaining tests.")
                break
        except Exception as e:
            print(f"\nERROR in {test_name}: {e}")
            results[test_name] = False

    # Summary
    print("\n" + "="*70)
    print("DIAGNOSTIC SUMMARY")
    print("="*70)

    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")

    working_method = [name for name, result in results.items() if result]

    if working_method:
        print(f"\nWORKING METHOD: {working_method[0]}")
        print("Use this method in ViewSwitcher implementation.")
    else:
        print("\nNO METHOD WORKED")
        print("Possible issues:")
        print("  1. Button might be disabled in current game state")
        print("  2. Game might be blocking ADB input")
        print("  3. Button position detection might be wrong")
        print("  4. Game might require mouse input instead of touch")

if __name__ == "__main__":
    main()
