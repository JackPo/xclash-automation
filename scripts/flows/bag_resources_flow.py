"""
Bag Resources Tab Flow - Diamond claiming.

Opens the bag, goes to Resources tab, finds diamond tiles one at a time,
and uses them (drag slider to max, click Use). Rescans after each use
since items shift position.

Templates used:
- bag_button_4k.png - Verify bag button present
- bag_diamond_icon_4k.png - Find diamond tiles (threshold 0.05)
- use_button_4k.png - Verify use dialog opened
- plus_button_4k.png - Verify plus button present
- slider_circle_4k.png - Find slider position to drag
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Add parent dirs to path for imports
_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import cv2
import numpy as np
import numpy.typing as npt

from scripts.flows.bag_use_item_subflow import use_item_subflow

from utils.windows_screenshot_helper import WindowsScreenshotHelper

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

# Fixed positions (4K resolution)
BAG_BUTTON_REGION = (3679, 1596, 72, 77)
BAG_BUTTON_CLICK = (3725, 1624)

RESOURCES_TAB_REGION = (1760, 2045, 120, 70)  # Same region for active/inactive
RESOURCES_TAB_CLICK = (1820, 2080)

BAG_TAB_REGION = (1352, 32, 1127, 90)

# Thresholds
DIAMOND_THRESHOLD = 0.01
VERIFICATION_THRESHOLD = 0.01

# Template paths
TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "ground_truth"


def _load_template(name: str) -> npt.NDArray[Any]:
    """Load a template image in grayscale."""
    path = TEMPLATES_DIR / name
    template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if template is None:
        raise FileNotFoundError(f"Template not found: {path}")
    return template


def _verify_at_fixed_region(
    frame_gray: npt.NDArray[Any],
    template: npt.NDArray[Any],
    region: tuple[int, int, int, int],
    threshold: float = VERIFICATION_THRESHOLD,
) -> tuple[bool, float]:
    """
    Verify template is present at fixed region.

    Returns:
        (is_present, score)
    """
    x, y, w, h = region
    roi = frame_gray[y:y+h, x:x+w]

    result = cv2.matchTemplate(roi, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, _, _ = cv2.minMaxLoc(result)

    return min_val <= threshold, min_val


def _find_first_diamond(
    frame_gray: npt.NDArray[Any],
    template: npt.NDArray[Any],
) -> tuple[tuple[int, int] | None, float]:
    """
    Find the first (best matching) diamond in the frame.

    Returns:
        ((center_x, center_y), score) or (None, score) if not found
    """
    h, w = template.shape
    result = cv2.matchTemplate(frame_gray, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)

    if min_val <= DIAMOND_THRESHOLD:
        center_x = min_loc[0] + w // 2
        center_y = min_loc[1] + h // 2
        return (center_x, center_y), min_val
    return None, min_val


def bag_resources_flow(
    adb: ADBHelper,
    win: WindowsScreenshotHelper | None = None,
    debug: bool = False,
    open_bag: bool = True,
) -> int:
    """
    Execute the bag resources flow to claim all diamonds.

    Rescans after each diamond since items shift position when used.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (optional)
        debug: Enable debug output
        open_bag: If True, click bag button first. If False, assume bag is already open.

    Returns:
        Number of diamonds claimed
    """
    if win is None:
            win = WindowsScreenshotHelper()

    # Load templates
    bag_template = _load_template("bag_button_4k.png")
    bag_tab_template = _load_template("bag_tab_4k.png")
    resources_tab_template = _load_template("bag_resources_tab_4k.png")  # Inactive
    resources_tab_active_template = _load_template("bag_resources_tab_active_4k.png")  # Active
    diamond_template = _load_template("bag_diamond_icon_4k.png")

    # Step 1: Open bag if requested
    if open_bag:
        if debug:
            print("Step 1: Opening bag...")

        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        is_present, score = _verify_at_fixed_region(frame_gray, bag_template, BAG_BUTTON_REGION)
        if not is_present:
            if debug:
                print(f"  Bag button not found (score={score:.4f})")
            return 0

        if debug:
            print(f"  Bag button verified (score={score:.4f}), clicking...")

        adb.tap(*BAG_BUTTON_CLICK)
        time.sleep(1.0)

        # VERIFY: Bag tab visible at top (confirms bag menu opened)
        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        is_present, score = _verify_at_fixed_region(frame_gray, bag_tab_template, BAG_TAB_REGION)
        if not is_present:
            if debug:
                print(f"  Bag tab not found - bag didn't open (score={score:.4f})")
            return 0

        if debug:
            print(f"  Bag tab verified - bag is open (score={score:.4f})")

    # Step 2: Check Resources tab state and activate if needed
    if debug:
        print("Step 2: Checking Resources tab...")

    frame = win.get_screenshot_cv2()
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # First check if Resources tab is already ACTIVE
    is_active, active_score = _verify_at_fixed_region(frame_gray, resources_tab_active_template, RESOURCES_TAB_REGION)
    if is_active:
        if debug:
            print(f"  Resources tab already ACTIVE (score={active_score:.4f})")
    else:
        # Check for INACTIVE Resources tab
        is_present, inactive_score = _verify_at_fixed_region(frame_gray, resources_tab_template, RESOURCES_TAB_REGION)
        if debug:
            print(f"  Resources tab ACTIVE check: score={active_score:.4f}, INACTIVE check: score={inactive_score:.4f}")

        if not is_present:
            if debug:
                print(f"  Resources tab not found (neither active nor inactive)")
            return 0

        # Click inactive tab to activate it
        if debug:
            print(f"  Clicking Resources tab to activate...")
        adb.tap(*RESOURCES_TAB_CLICK)
        time.sleep(0.5)

        # Verify it's now ACTIVE
        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        is_active, active_score = _verify_at_fixed_region(frame_gray, resources_tab_active_template, RESOURCES_TAB_REGION)
        if not is_active:
            if debug:
                print(f"  Resources tab still not active after click (score={active_score:.4f})")
            return 0

        if debug:
            print(f"  Resources tab is now ACTIVE (score={active_score:.4f})")

    # Step 3: Loop - find and process diamonds one at a time, rescan after each
    diamond_count = 0
    max_diamonds = 50  # Safety limit

    while diamond_count < max_diamonds:
        # RESCAN for diamonds (they shift after each use)
        if debug:
            print(f"\nScan #{diamond_count + 1}: Looking for diamonds...")

        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        diamond_pos, score = _find_first_diamond(frame_gray, diamond_template)

        if diamond_pos is None:
            if debug:
                print(f"  No diamond found (best score={score:.4f}), done!")
            break

        dx, dy = diamond_pos
        if debug:
            print(f"  Found diamond at ({dx}, {dy}), score={score:.4f}")

        # Click diamond
        if debug:
            print("  Clicking diamond...")
        adb.tap(dx, dy)
        time.sleep(0.5)

        # Use the shared subflow for drag/use/back
        success = use_item_subflow(adb, win, debug=debug)
        if not success:
            if debug:
                print("  ERROR: use_item_subflow failed")
            break

        diamond_count += 1
        if debug:
            print(f"  Diamond #{diamond_count} processed!")

    if debug:
        print(f"\nCompleted! Processed {diamond_count} diamond(s)")

    return diamond_count


if __name__ == "__main__":
    import argparse
    from utils.adb_helper import ADBHelper

    parser = argparse.ArgumentParser(description="Bag Resources Flow - Claim diamonds")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--no-open-bag", action="store_true", help="Don't click bag button (assume already open)")
    args = parser.parse_args()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    count = bag_resources_flow(adb, win, debug=args.debug, open_bag=not args.no_open_bag)
    print(f"\nClaimed {count} diamond(s)")
