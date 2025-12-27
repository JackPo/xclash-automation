"""
Hospital Healing Flow - Heal soldiers in 1-hour batches.

After hospital panel is opened, this flow:
1. Finds all soldier rows (by detecting plus buttons)
2. Resets all sliders to zero
3. Fills from bottom row (highest level) until healing time reaches ~1 hour
4. Clicks Healing button
5. Returns to base view

Usage:
    python scripts/flows/hospital_healing_flow.py [--max-seconds 3600]
"""

import sys
import time
import argparse
import cv2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.adb_helper import ADBHelper
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.ocr_client import OCRClient
from utils.return_to_base_view import return_to_base_view
from utils.hospital_panel_helper import (
    find_plus_buttons,
    reset_all_sliders,
    drag_slider_to_max,
    drag_slider_to_min,
    drag_slider_to_position,
    get_healing_time_seconds,
    click_healing_button,
    calculate_slider_x,
    scroll_panel_down,
    MAX_SAFE_HEAL_SECONDS,
    get_slider_y,
)


def hospital_healing_flow(adb=None, win=None, max_heal_seconds=3600, debug=True):
    """
    Heal soldiers in batches of up to max_heal_seconds.

    Assumes hospital panel is already open.
    Processes rows from BOTTOM to TOP (highest level soldiers first).
    Includes 90-minute safety check to prevent accidental long heals.

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

    # Step 0: Verify hospital panel is open by checking header
    print("\nStep 0: Verifying hospital panel is open...")
    frame = win.get_screenshot_cv2()
    header_template_path = Path(__file__).parent.parent.parent / "templates" / "ground_truth" / "hospital_header_4k.png"
    header_template = cv2.imread(str(header_template_path), cv2.IMREAD_GRAYSCALE)
    if header_template is None:
        print("  WARNING: Could not load hospital_header_4k.png - skipping verification")
    else:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(gray, header_template, cv2.TM_SQDIFF_NORMED)
        min_val, _, min_loc, _ = cv2.minMaxLoc(result)
        if min_val > 0.1:
            print(f"  ERROR: Hospital panel NOT open (header score={min_val:.4f})")
            return False
        print(f"  OK - Hospital panel verified (header score={min_val:.4f})")

    # Step 1: Find soldier rows (detects plus buttons)
    print("\nStep 1: Finding soldier rows...")
    frame = win.get_screenshot_cv2()
    buttons = find_plus_buttons(frame, debug=debug)

    if not buttons:
        print("  ERROR: No soldier rows found - is hospital panel open?")
        return False

    print(f"  Found {len(buttons)} soldier rows")

    # Step 2: Reset all sliders to zero
    print("\nStep 2: Resetting all sliders to zero...")
    reset_all_sliders(adb, win, buttons, debug=debug)
    time.sleep(0.5)

    # Step 3: Check initial healing time (should be 0 or very small)
    frame = win.get_screenshot_cv2()
    initial_time = get_healing_time_seconds(frame, ocr, debug=debug)
    print(f"  Initial healing time: {initial_time}s")

    # Step 4: Fill rows from BOTTOM to TOP (highest level soldiers first)
    print(f"\nStep 3: Filling rows BOTTOM-TO-TOP to reach ~{max_heal_seconds}s ({max_heal_seconds//3600}h)...")
    print(f"  (Processing highest level soldiers first)")

    current_time = initial_time

    # Process rows in REVERSE order (bottom to top = highest level first)
    for i, (plus_x, plus_y, score) in enumerate(reversed(buttons)):
        row_num = len(buttons) - i  # For display: bottom row is highest number
        slider_y = get_slider_y(plus_y)
        print(f"\n  Processing row {row_num} (Y={slider_y}, bottom-to-top order)...")

        # Drag this row's slider to max
        frame = win.get_screenshot_cv2()
        if not drag_slider_to_max(adb, frame, plus_x, plus_y, debug=debug):
            print(f"    Could not find slider for row {row_num}, skipping")
            continue

        time.sleep(0.5)

        # Check new healing time
        frame = win.get_screenshot_cv2()
        new_time = get_healing_time_seconds(frame, ocr, debug=debug)
        print(f"    After max: {new_time}s ({new_time//3600}h {(new_time%3600)//60}m)")

        # SAFETY CHECK: OCR sanity - if we maxed a slider but time is still 0, something is wrong
        if new_time == 0 and current_time == 0:
            print(f"    WARNING: OCR returned 0 after maxing slider - possible OCR failure")
            # Continue anyway, but log the warning

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
                target_x = calculate_slider_x(plus_x, mid_ratio)

                frame = win.get_screenshot_cv2()
                drag_slider_to_position(adb, frame, plus_x, plus_y, target_x, debug=False)
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
            best_x = calculate_slider_x(plus_x, best_ratio)
            frame = win.get_screenshot_cv2()
            drag_slider_to_position(adb, frame, plus_x, plus_y, best_x, debug=debug)
            time.sleep(0.3)

            current_time = best_time
            print(f"    Set to ratio={best_ratio:.2f}, time={current_time}s")

            # Stop processing more rows - we've hit the limit
            break

    # Step 5: Final check and click Healing
    print("\nStep 4: Final verification and clicking Healing button...")
    frame = win.get_screenshot_cv2()
    final_time = get_healing_time_seconds(frame, ocr, debug=debug)
    print(f"  Final healing time: {final_time}s ({final_time//3600}h {(final_time%3600)//60}m {final_time%60}s)")

    # Final safety check
    if final_time > MAX_SAFE_HEAL_SECONDS:
        print(f"  ERROR: Final time {final_time}s exceeds safety limit! NOT clicking Heal.")
        return_to_base_view(adb, win, debug=debug)
        return False

    if final_time == 0:
        print("  No soldiers to heal (time is 0)")
        return False

    click_healing_button(adb, debug=debug)
    time.sleep(1.0)

    # Step 6: Return to base view
    print("\nStep 5: Returning to base view...")
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
