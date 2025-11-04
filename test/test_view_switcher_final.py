"""Test the updated ViewSwitcher with simple toggle logic"""
import sys
sys.path.insert(0, '.')

from view_detection import ViewDetector, ViewSwitcher, ViewState
from find_player import ADBController, Config

def main():
    print("="*70)
    print("TESTING UPDATED ViewSwitcher")
    print("="*70)
    print("\nUsing simple toggle logic (x_frac=0.75)\n")

    config = Config()
    adb = ADBController(config)

    detector = ViewDetector()
    switcher = ViewSwitcher(detector, adb)

    # Test 1: Switch to WORLD
    print("\n" + "="*70)
    print("TEST 1: Switch to WORLD")
    print("="*70)
    result1 = switcher.switch_to_view(ViewState.WORLD)
    print(f"Result: {'SUCCESS' if result1 else 'FAILED'}\n")

    # Test 2: Switch to TOWN
    print("="*70)
    print("TEST 2: Switch to TOWN")
    print("="*70)
    result2 = switcher.switch_to_view(ViewState.TOWN)
    print(f"Result: {'SUCCESS' if result2 else 'FAILED'}\n")

    # Test 3: Switch back to WORLD
    print("="*70)
    print("TEST 3: Switch back to WORLD")
    print("="*70)
    result3 = switcher.switch_to_view(ViewState.WORLD)
    print(f"Result: {'SUCCESS' if result3 else 'FAILED'}\n")

    # Summary
    print("="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Switch to WORLD: {'PASS' if result1 else 'FAIL'}")
    print(f"Switch to TOWN: {'PASS' if result2 else 'FAIL'}")
    print(f"Switch back to WORLD: {'PASS' if result3 else 'FAIL'}")

    if all([result1, result2, result3]):
        print("\nALL TESTS PASSED!")
        print("ViewSwitcher is working correctly with simple toggle logic.")
    else:
        print("\nSOME TESTS FAILED")

if __name__ == "__main__":
    main()
