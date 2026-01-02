"""
Soldier Speedup Flow - Speed up soldier training using Quick Speedup.

Pre-condition: Barrack is in TRAINING state (stopwatch visible)

Flow:
1. Click barrack bubble
2. Verify Soldier Training panel opened (header + Speed Up button)
3. Click Speed Up button
4. Verify Speed Up panel opened (dark header + Quick Speedup button)
5. Click Quick Speedup button
6. Click Confirm button
7. Return to base view

Templates:
- soldier_training_header_4k.png - (1678, 315) 480x54
- speed_up_button_4k.png - (1728, 1393) 372x144, click (1914, 1465)
- quick_speedup_button_4k.png - X=1728, Y=variable, 372x136
- confirm_button_4k.png - click (1912, 1289)
"""

import time
from pathlib import Path

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.return_to_base_view import return_to_base_view
from utils.template_matcher import match_template

# Template paths
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "ground_truth"

# Fixed positions (4K)
SOLDIER_TRAINING_HEADER_POS = (1678, 315)
SOLDIER_TRAINING_HEADER_SIZE = (480, 54)

SPEED_UP_BUTTON_POS = (1728, 1393)
SPEED_UP_BUTTON_SIZE = (372, 144)
SPEED_UP_BUTTON_CLICK = (1914, 1465)

SPEED_UP_HEADER_X = 1758
SPEED_UP_HEADER_SIZE = (334, 71)

QUICK_SPEEDUP_X = 1728
QUICK_SPEEDUP_SIZE = (372, 136)

CONFIRM_BUTTON_CLICK = (1912, 1289)

# Thresholds
THRESHOLD = 0.05


def soldier_speedup_flow(adb, barrack_click_pos, screenshot_helper=None, debug=False):
    """
    Speed up soldier training at a barrack.

    Args:
        adb: ADBHelper instance
        barrack_click_pos: (x, y) position to click barrack bubble
        screenshot_helper: WindowsScreenshotHelper instance
        debug: Enable debug logging

    Returns:
        True if successful, False otherwise
    """
    win = screenshot_helper or WindowsScreenshotHelper()

    try:
        # Step 1: Click barrack bubble
        if debug:
            print(f"  Step 1: Clicking barrack at {barrack_click_pos}")
        adb.tap(*barrack_click_pos)
        time.sleep(1.0)

        # Step 2: Verify Soldier Training panel
        if debug:
            print("  Step 2: Verifying Soldier Training panel...")
        frame = win.get_screenshot_cv2()

        header_ok, header_score, _ = match_template(
            frame,
            "soldier_training_header_4k.png",
            search_region=(*SOLDIER_TRAINING_HEADER_POS, *SOLDIER_TRAINING_HEADER_SIZE),
            threshold=THRESHOLD
        )
        speedup_ok, speedup_score, _ = match_template(
            frame,
            "speed_up_button_4k.png",
            search_region=(*SPEED_UP_BUTTON_POS, *SPEED_UP_BUTTON_SIZE),
            threshold=THRESHOLD
        )

        if debug:
            print(f"    Header: {header_ok} ({header_score:.4f})")
            print(f"    Speed Up button: {speedup_ok} ({speedup_score:.4f})")

        if not (header_ok and speedup_ok):
            print("  ERROR: Soldier Training panel not detected")
            return False

        # Step 3: Click Speed Up button
        if debug:
            print(f"  Step 3: Clicking Speed Up button at {SPEED_UP_BUTTON_CLICK}")
        adb.tap(*SPEED_UP_BUTTON_CLICK)
        time.sleep(0.8)

        # Step 4: Verify Speed Up panel (search Y for Quick Speedup)
        if debug:
            print("  Step 4: Verifying Speed Up panel...")
        frame = win.get_screenshot_cv2()

        # Search in vertical strip at fixed X
        search_region = (QUICK_SPEEDUP_X, 1500, QUICK_SPEEDUP_SIZE[0], 600)
        quick_ok, quick_score, quick_loc = match_template(
            frame,
            "quick_speedup_button_4k.png",
            search_region=search_region,
            threshold=THRESHOLD
        )
        quick_y = quick_loc[1] - QUICK_SPEEDUP_SIZE[1] // 2 if quick_loc else None

        if debug:
            print(f"    Quick Speedup: {quick_ok} ({quick_score:.4f}, y={quick_y})")

        if not quick_ok:
            print("  ERROR: Quick Speedup button not found")
            return False

        # Step 5: Click Quick Speedup button (quick_loc is already center)
        quick_click_x, quick_click_y = quick_loc
        if debug:
            print(f"  Step 5: Clicking Quick Speedup at ({quick_click_x}, {quick_click_y})")
        adb.tap(quick_click_x, quick_click_y)
        time.sleep(0.5)

        # Step 6: Click Confirm button
        if debug:
            print(f"  Step 6: Clicking Confirm at {CONFIRM_BUTTON_CLICK}")
        adb.tap(*CONFIRM_BUTTON_CLICK)
        time.sleep(0.5)

        if debug:
            print("  Speedup complete!")
        return True

    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    finally:
        return_to_base_view(adb, win, debug=debug)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from utils.adb_helper import ADBHelper
    from config import BARRACKS_POSITIONS

    print("=== Soldier Speedup Flow Test ===")
    print("This flow requires a TRAINING barrack (stopwatch visible)")
    print()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    # Default to barrack 0
    barrack_idx = 0
    if len(sys.argv) > 1:
        barrack_idx = int(sys.argv[1])

    # Calculate click position
    bx, by = BARRACKS_POSITIONS[barrack_idx]
    click_pos = (bx + 40, by + 43)

    print(f"Using barrack {barrack_idx} at {BARRACKS_POSITIONS[barrack_idx]}")
    print(f"Click position: {click_pos}")
    print()

    result = soldier_speedup_flow(adb, click_pos, win, debug=True)
    print(f"\nResult: {'SUCCESS' if result else 'FAILED'}")
