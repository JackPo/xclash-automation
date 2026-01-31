"""
Shield Inventory Flow - Read shield counts from bag Special tab.

Opens bag, navigates to Special tab, matches shield templates (8hr, 12hr, 24hr),
extracts counts via OCR, and updates current_state.json.

Shield templates (no count number, just the icon):
- bag_shield_8hr_4k.png (green background)
- bag_shield_12hr_4k.png (blue background)
- bag_shield_24hr_4k.png (purple background)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import numpy.typing as npt

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.template_matcher import match_template
from utils.ui_helpers import click_back
from utils.ocr_client import OCRClient
from utils.current_state import update_shield_inventory

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

# Fixed positions (4K resolution) - same as bag_special_flow
BAG_BUTTON_REGION = (3659, 1556, 132, 127)
BAG_BUTTON_CLICK = (3725, 1624)

BAG_TAB_REGION = (1352, 32, 1127, 90)

# Bag content region - search for items within this area
BAG_CONTENT_REGION = (1337, 137, 1161, 1871)

SPECIAL_TAB_REGION = (1480, 2000, 230, 150)

# Thresholds
SHIELD_THRESHOLD = 0.08  # Shield matching threshold
VERIFICATION_THRESHOLD = 0.02

# Shield templates (icon only, no count number)
# Template size: 230x189
SHIELD_TEMPLATES = {
    "8hr": "bag_shield_8hr_4k.png",
    "12hr": "bag_shield_12hr_4k.png",
    "24hr": "bag_shield_24hr_4k.png",
}

# Full tile extraction around template match
# Template is 230x189 (cropped icon without count)
# Full bag item tile is ~240x250, we extract slightly larger to ensure count is captured
TILE_HALF_WIDTH = 125   # Half width of full tile
TILE_HALF_HEIGHT = 130  # Half height of full tile (extra for count at bottom)


def _extract_shield_count(
    frame: npt.NDArray[Any],
    center: tuple[int, int],
    ocr: OCRClient,
    debug: bool = False,
) -> int | None:
    """
    Extract the count number for a shield at the given position.

    Extracts the FULL item tile and sends to OCR for better accuracy.

    Args:
        frame: Screenshot
        center: Center position of matched template
        ocr: OCR client
        debug: Enable debug output

    Returns:
        Count as integer, or None if OCR fails
    """
    cx, cy = center
    h, w = frame.shape[:2]

    # Calculate full tile region centered on match, with extra space below for count
    x1 = max(0, cx - TILE_HALF_WIDTH)
    y1 = max(0, cy - TILE_HALF_HEIGHT + 20)  # Shift down slightly to include count
    x2 = min(w, cx + TILE_HALF_WIDTH)
    y2 = min(h, cy + TILE_HALF_HEIGHT + 30)  # Extra space below for count number

    tile_region = (x1, y1, x2 - x1, y2 - y1)

    if debug:
        print(f"    Full tile region: {tile_region}")

    try:
        count = ocr.extract_number(frame, region=tile_region)
        return count
    except Exception as e:
        if debug:
            print(f"    OCR error: {e}")
        return None


def shield_inventory_flow(
    adb: ADBHelper,
    win: WindowsScreenshotHelper | None = None,
    debug: bool = False,
    open_bag: bool = True,
) -> dict[str, int | None]:
    """
    Read shield inventory from bag Special tab.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (optional)
        debug: Enable debug output
        open_bag: If True, click bag button first. If False, assume bag is open.

    Returns:
        Dict with shield counts: {"8hr": N, "12hr": N, "24hr": N}
    """
    if win is None:
        win = WindowsScreenshotHelper()

    ocr = OCRClient()
    result: dict[str, int | None] = {"8hr": None, "12hr": None, "24hr": None}

    if debug:
        print("Shield Inventory Flow")
        print("=" * 50)

    # Step 1: Open bag if requested
    if open_bag:
        if debug:
            print("Step 1: Opening bag...")

        frame = win.get_screenshot_cv2()

        is_present, score, _ = match_template(
            frame, "bag_button_4k.png",
            search_region=BAG_BUTTON_REGION,
            threshold=0.1
        )
        if not is_present:
            if debug:
                print(f"  Bag button not found (score={score:.4f})")
            return result

        if debug:
            print(f"  Bag button found (score={score:.4f}), clicking...")

        adb.tap(*BAG_BUTTON_CLICK, source="flow:shield_inventory:open_bag")
        time.sleep(1.5)

        # Verify bag opened
        frame = win.get_screenshot_cv2()
        is_present, score, _ = match_template(
            frame, "bag_tab_4k.png",
            search_region=BAG_TAB_REGION,
            threshold=VERIFICATION_THRESHOLD
        )
        if not is_present:
            if debug:
                print(f"  Bag tab not found (score={score:.4f})")
            return result

        if debug:
            print(f"  Bag opened (score={score:.4f})")

    # Step 2: Check Special tab and activate if needed
    if debug:
        print("Step 2: Checking Special tab...")

    frame = win.get_screenshot_cv2()

    _, active_score, _ = match_template(
        frame, "bag_special_tab_active_4k.png",
        search_region=SPECIAL_TAB_REGION,
        threshold=1.0
    )
    _, inactive_score, tab_center = match_template(
        frame, "bag_special_tab_4k.png",
        search_region=SPECIAL_TAB_REGION,
        threshold=1.0
    )

    if debug:
        print(f"  Tab scores: active={active_score:.4f}, inactive={inactive_score:.4f}")

    is_active = active_score < inactive_score

    if not is_active:
        if tab_center is None:
            if debug:
                print("  Special tab not found")
            if open_bag:
                click_back(adb)
            return result

        if debug:
            print(f"  Clicking Special tab at {tab_center}...")
        adb.tap(*tab_center, source="flow:shield_inventory:activate_special_tab")
        time.sleep(0.5)
        frame = win.get_screenshot_cv2()

    if debug:
        print("  Special tab active")

    # Step 3: Match each shield template and OCR count
    if debug:
        print("Step 3: Scanning for shields...")

    frame = win.get_screenshot_cv2()

    for shield_type, template_name in SHIELD_TEMPLATES.items():
        found, score, center = match_template(
            frame, template_name,
            search_region=BAG_CONTENT_REGION,
            threshold=SHIELD_THRESHOLD
        )

        if debug:
            print(f"  {shield_type} shield ({template_name}): found={found}, score={score:.4f}")

        if found and center:
            count = _extract_shield_count(frame, center, ocr, debug=debug)
            result[shield_type] = count
            if debug:
                print(f"    Count: {count}")
        else:
            if debug:
                print(f"    Not found in bag")

    # Step 4: Update current state
    if debug:
        print("Step 4: Updating state...")

    update_shield_inventory(
        shields_8hr=result["8hr"],
        shields_12hr=result["12hr"],
        shields_24hr=result["24hr"],
    )

    if debug:
        print(f"  Saved: {result}")

    # Step 5: Close bag if we opened it
    if open_bag:
        if debug:
            print("Step 5: Closing bag...")
        click_back(adb)
        time.sleep(0.3)

    if debug:
        print("=" * 50)
        print(f"Result: {result}")

    return result


if __name__ == "__main__":
    import argparse
    from utils.adb_helper import ADBHelper

    parser = argparse.ArgumentParser(description="Shield Inventory Flow - Read shield counts")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--no-open-bag", action="store_true", help="Don't click bag button")
    args = parser.parse_args()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    result = shield_inventory_flow(adb, win, debug=args.debug, open_bag=not args.no_open_bag)
    print(f"\nShield Inventory: {result}")
