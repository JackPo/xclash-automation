"""Simple test to understand toggle behavior"""
import sys
import time
sys.path.insert(0, '.')

from view_detection import detect_current_view, get_detection_result, ViewState
from find_player import ADBController, Config

def main():
    config = Config()
    adb = ADBController(config)

    print("="*70)
    print("SIMPLE TOGGLE TEST - Just Click 0.75 Repeatedly")
    print("="*70)

    for i in range(6):
        # Detect state
        current = detect_current_view(adb)
        result = get_detection_result(adb)

        print(f"\nRound {i+1}:")
        print(f"  Current state: {current.value}")

        if not result.match:
            print("  ERROR: No match")
            break

        x, y = result.match.top_left
        w = result.match.bottom_right[0] - x
        h = result.match.bottom_right[1] - y

        # Always click 0.75 (right side)
        click_x = int(x + w * 0.75)
        click_y = int(y + h * 0.5)

        print(f"  Clicking at ({click_x}, {click_y}) [x_frac=0.75]")

        adb.tap(click_x, click_y)
        time.sleep(2.5)

        new_state = detect_current_view(adb)
        print(f"  New state: {new_state.value}")

        if i >= 4:  # After 5 clicks, we should see a pattern
            break

    print("\n" + "="*70)
    print("If clicking 0.75 toggles back and forth, it's a simple toggle.")
    print("If clicking 0.75 always goes to the same state, it's state-specific.")
    print("="*70)

if __name__ == "__main__":
    main()
