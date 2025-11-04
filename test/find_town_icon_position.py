"""Find the exact position that works for clicking TOWN icon"""
import sys
import time
sys.path.insert(0, '.')

from view_detection import detect_current_view, get_detection_result, ViewState
from find_player import ADBController, Config

def test_town_positions(adb: ADBController):
    """Try many positions on the left side to find TOWN icon click position"""

    print("="*70)
    print("FINDING TOWN ICON CLICK POSITION")
    print("="*70)

    # Make sure we're in WORLD state
    current = detect_current_view(adb)
    if current != ViewState.WORLD:
        print("ERROR: Please start in WORLD state")
        return

    result = get_detection_result(adb)
    if result.match is None:
        print("ERROR: Button not detected")
        return

    x, y = result.match.top_left
    x2, y2 = result.match.bottom_right
    w = x2 - x
    h = y2 - y

    print(f"\nButton bounds: ({x}, {y}) to ({x2}, {y2}), size: {w}x{h}")
    print("Testing various positions on LEFT side (TOWN icon)...\n")

    # Try many positions from far left to center
    test_positions = [
        (0.10, "10% from left"),
        (0.15, "15% from left"),
        (0.20, "20% from left"),
        (0.25, "25% from left"),
        (0.30, "30% from left"),
        (0.35, "35% from left"),
        (0.40, "40% from left"),
    ]

    for x_frac, description in test_positions:
        print(f"Testing {description} (x_frac={x_frac})")

        # Reset to WORLD if needed
        current = detect_current_view(adb)
        if current == ViewState.TOWN:
            print("  Already in TOWN, skipping back to WORLD first...")
            # Click WORLD icon at 75% (we know this works)
            reset_x = int(x + w * 0.75)
            reset_y = int(y + h * 0.5)
            adb.tap(reset_x, reset_y)
            time.sleep(2)

        # Try this position
        click_x = int(x + w * x_frac)
        click_y = int(y + h * 0.5)
        print(f"  Position: ({click_x}, {click_y})")

        adb.tap(click_x, click_y)
        time.sleep(2)

        # Check result
        new_state = detect_current_view(adb)
        print(f"  Result: {new_state.value}")

        if new_state == ViewState.TOWN:
            print(f"\n*** SUCCESS! ***")
            print(f"TOWN icon click works at: {description}")
            print(f"  x_frac: {x_frac}")
            print(f"  Position: ({click_x}, {click_y})")
            return x_frac

        print()

    print("FAILED: None of the positions worked for TOWN icon")
    return None

def main():
    config = Config()
    adb = ADBController(config)

    working_x_frac = test_town_positions(adb)

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print("\nWorking coordinates:")
    print(f"  WORLD icon (right): x_frac=0.75")

    if working_x_frac:
        print(f"  TOWN icon (left): x_frac={working_x_frac}")
    else:
        print(f"  TOWN icon (left): NOT FOUND")

if __name__ == "__main__":
    main()
