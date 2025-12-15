"""
Hospital Healing Flow - Heal soldiers in 1-hour batches.

After hospital panel is opened, this flow:
1. Finds all soldier rows (by detecting plus buttons)
2. Resets all sliders to zero
3. Fills from top row until healing time reaches ~1 hour
4. Clicks Healing button
5. Returns to base view

Usage:
    python scripts/flows/hospital_healing_flow.py [--max-seconds 3600]
"""

import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.adb_helper import ADBHelper
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.ocr_client import OCRClient
from utils.return_to_base_view import return_to_base_view
from utils.hospital_panel_helper import (
    find_soldier_rows,
    reset_all_sliders,
    drag_slider_to_max_at_y,
    drag_slider_to_position_at_y,
    find_slider_circle_at_y,
    get_healing_time_seconds,
    click_healing_button,
    calculate_slider_x,
    SLIDER_MIN_X,
    SLIDER_MAX_X,
)


def hospital_healing_flow(adb=None, win=None, max_heal_seconds=3600, debug=True):
    """
    Heal soldiers in batches of up to max_heal_seconds.

    Assumes hospital panel is already open.

    Args:
        adb: ADBHelper (created if None)
        win: WindowsScreenshotHelper (created if None)
        max_heal_seconds: Maximum healing time per batch (default 3600 = 1 hour)
        debug: Enable debug output

    Returns:
        bool: True if healing was initiated
    """
    if adb is None:
        adb = ADBHelper()
    if win is None:
        win = WindowsScreenshotHelper()

    ocr = OCRClient()

    print("Hospital Healing Flow")
    print("=" * 50)

    # Step 1: Find all soldier rows
    frame = win.get_screenshot_cv2()
    rows = find_soldier_rows(frame, debug=debug)

    if not rows:
        print("  ERROR: No soldier rows found - is hospital panel open?")
        return False

    print(f"  Found {len(rows)} soldier rows")

    # Step 2: Reset all sliders to zero
    print("\nStep 1: Resetting all sliders to zero...")
    reset_all_sliders(adb, win, rows, debug=debug)
    time.sleep(0.5)

    # Step 3: Check initial healing time (should be 0 or very small)
    frame = win.get_screenshot_cv2()
    initial_time = get_healing_time_seconds(frame, ocr, debug=debug)
    print(f"  Initial healing time: {initial_time}s")

    # Step 4: Fill rows from top until we reach target time
    print(f"\nStep 2: Filling rows to reach ~{max_heal_seconds}s ({max_heal_seconds//3600}h)...")

    current_time = initial_time

    for i, row_y in enumerate(rows):
        print(f"\n  Processing row {i+1} (Y={row_y})...")

        # Drag this row's slider to max
        frame = win.get_screenshot_cv2()
        if not drag_slider_to_max_at_y(adb, frame, row_y, debug=debug):
            print(f"    Could not find slider for row {i+1}, skipping")
            continue

        time.sleep(0.5)

        # Check new healing time
        frame = win.get_screenshot_cv2()
        new_time = get_healing_time_seconds(frame, ocr, debug=debug)
        print(f"    After max: {new_time}s ({new_time//3600}h {(new_time%3600)//60}m)")

        if new_time <= max_heal_seconds:
            # Still under limit, keep this row at max and continue to next
            print(f"    Under limit, keeping at max")
            current_time = new_time
            continue
        else:
            # Over limit - need to binary search for right position
            print(f"    Over limit ({new_time}s > {max_heal_seconds}s), adjusting...")

            # Binary search to find right slider position
            low_ratio = 0.0
            high_ratio = 1.0
            best_ratio = 0.0
            best_time = current_time

            for _ in range(8):  # 8 iterations = ~1% precision
                mid_ratio = (low_ratio + high_ratio) / 2
                target_x = calculate_slider_x(mid_ratio)

                frame = win.get_screenshot_cv2()
                drag_slider_to_position_at_y(adb, frame, row_y, target_x, debug=False)
                time.sleep(0.3)

                frame = win.get_screenshot_cv2()
                test_time = get_healing_time_seconds(frame, ocr, debug=False)

                if debug:
                    print(f"      ratio={mid_ratio:.2f} -> {test_time}s")

                if test_time <= max_heal_seconds:
                    # Can go higher
                    best_ratio = mid_ratio
                    best_time = test_time
                    low_ratio = mid_ratio
                else:
                    # Need to go lower
                    high_ratio = mid_ratio

            # Set to best found ratio
            best_x = calculate_slider_x(best_ratio)
            frame = win.get_screenshot_cv2()
            drag_slider_to_position_at_y(adb, frame, row_y, best_x, debug=debug)
            time.sleep(0.3)

            current_time = best_time
            print(f"    Set to ratio={best_ratio:.2f}, time={current_time}s")

            # Stop processing more rows - we've hit the limit
            break

    # Step 5: Final check and click Healing
    print("\nStep 3: Clicking Healing button...")
    frame = win.get_screenshot_cv2()
    final_time = get_healing_time_seconds(frame, ocr, debug=debug)
    print(f"  Final healing time: {final_time}s ({final_time//3600}h {(final_time%3600)//60}m {final_time%60}s)")

    if final_time == 0:
        print("  No soldiers to heal (time is 0)")
        return False

    click_healing_button(adb, debug=debug)
    time.sleep(1.0)

    # Step 6: Return to base view
    print("\nStep 4: Returning to base view...")
    return_to_base_view(adb, win, debug=debug)

    print("\n" + "=" * 50)
    print("Hospital Healing Flow complete!")
    return True


def main():
    parser = argparse.ArgumentParser(description="Hospital Healing Flow")
    parser.add_argument("--max-seconds", type=int, default=3600,
                        help="Maximum healing time per batch (default: 3600 = 1 hour)")
    parser.add_argument("--debug", action="store_true", default=True,
                        help="Enable debug output")
    args = parser.parse_args()

    hospital_healing_flow(max_heal_seconds=args.max_seconds, debug=args.debug)


if __name__ == "__main__":
    main()
