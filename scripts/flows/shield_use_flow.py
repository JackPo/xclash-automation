"""
Shield Use Flow - Activate a shield from the bag Special tab.

Opens bag, navigates to Special tab, finds the shield, clicks it,
clicks Use button to activate, then closes bag.

Shield templates:
- bag_shield_8hr_4k.png (green background)
- bag_shield_12hr_4k.png (blue background)
- bag_shield_24hr_4k.png (purple background)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.template_matcher import match_template
from utils.ui_helpers import click_back
from utils.current_state import update_shield_inventory, get_shield_inventory

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

# Fixed positions (4K resolution) - same as shield_inventory_flow
BAG_BUTTON_REGION = (3659, 1556, 132, 127)
BAG_BUTTON_CLICK = (3725, 1624)

BAG_TAB_REGION = (1352, 32, 1127, 90)

# Bag content region - search for items within this area
BAG_CONTENT_REGION = (1337, 137, 1161, 1871)

SPECIAL_TAB_REGION = (1480, 2000, 230, 150)

# Use button region (appears when clicking an item)
USE_BUTTON_REGION = (1750, 1400, 350, 300)

# Thresholds
SHIELD_THRESHOLD = 0.08
VERIFICATION_THRESHOLD = 0.02
USE_BUTTON_THRESHOLD = 0.1

# Shield templates
SHIELD_TEMPLATES = {
    "8hr": "bag_shield_8hr_4k.png",
    "12hr": "bag_shield_12hr_4k.png",
    "24hr": "bag_shield_24hr_4k.png",
}


def shield_use_flow(
    adb: ADBHelper,
    shield_type: str,
    win: WindowsScreenshotHelper | None = None,
    debug: bool = False,
    force: bool = False,
) -> dict:
    """
    Use/activate a shield from the bag.

    Args:
        adb: ADBHelper instance
        shield_type: "8hr", "12hr", or "24hr"
        win: WindowsScreenshotHelper instance (optional)
        debug: Enable debug output
        force: If True, use shield even if one is already active

    Returns:
        Dict with success status and message
    """
    if shield_type not in SHIELD_TEMPLATES:
        return {"success": False, "error": f"Invalid shield type: {shield_type}"}

    if win is None:
        win = WindowsScreenshotHelper()

    template_name = SHIELD_TEMPLATES[shield_type]

    if debug:
        print(f"Shield Use Flow - {shield_type}")
        print("=" * 50)

    # Step 0: Check if shield is already active
    if not force:
        if debug:
            print("Step 0: Checking if shield already active...")

        frame = win.get_screenshot_cv2()
        from utils.shield_active_matcher import is_shield_active
        shield_active, shield_score = is_shield_active(frame, debug=debug)

        if shield_active:
            if debug:
                print(f"  Shield already active (score={shield_score:.4f}) - skipping")
            return {
                "success": False,
                "error": "Shield already active",
                "shield_already_active": True,
                "score": shield_score
            }

        if debug:
            print(f"  No active shield detected (score={shield_score:.4f})")

    # Step 1: Open bag
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
        return {"success": False, "error": "Bag button not visible"}

    if debug:
        print(f"  Bag button found (score={score:.4f}), clicking...")

    adb.tap(*BAG_BUTTON_CLICK, source="flow:shield_use:open_bag")
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
        return {"success": False, "error": "Failed to open bag"}

    if debug:
        print(f"  Bag opened (score={score:.4f})")

    # Step 2: Navigate to Special tab
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
            click_back(adb)
            return {"success": False, "error": "Special tab not found"}

        if debug:
            print(f"  Clicking Special tab at {tab_center}...")
        adb.tap(*tab_center, source="flow:shield_use:activate_special_tab")
        time.sleep(0.5)

    if debug:
        print("  Special tab active")

    # Step 3: Find and click shield
    if debug:
        print(f"Step 3: Finding {shield_type} shield...")

    frame = win.get_screenshot_cv2()

    found, score, center = match_template(
        frame, template_name,
        search_region=BAG_CONTENT_REGION,
        threshold=SHIELD_THRESHOLD
    )

    if debug:
        print(f"  Shield match: found={found}, score={score:.4f}, center={center}")

    if not found or center is None:
        if debug:
            print(f"  Shield {shield_type} not found in bag")
        click_back(adb)
        return {"success": False, "error": f"Shield {shield_type} not found in bag"}

    if debug:
        print(f"  Clicking shield at {center}...")
    adb.tap(*center, source="flow:shield_use:click_shield")
    time.sleep(0.8)

    # Step 4: Click Use button
    if debug:
        print("Step 4: Clicking Use button...")

    frame = win.get_screenshot_cv2()

    use_found, use_score, use_pos = match_template(
        frame, "use_button_4k.png",
        search_region=USE_BUTTON_REGION,
        threshold=USE_BUTTON_THRESHOLD
    )

    if debug:
        print(f"  Use button: found={use_found}, score={use_score:.4f}, pos={use_pos}")

    if not use_found or use_pos is None:
        if debug:
            print("  Use button not found - maybe item dialog didn't open")
        click_back(adb)
        time.sleep(0.3)
        click_back(adb)
        return {"success": False, "error": "Use button not found"}

    if debug:
        print(f"  Clicking Use at {use_pos}...")
    adb.tap(*use_pos, source="flow:shield_use:use_button")
    time.sleep(1.0)

    # Step 5: Close dialogs and bag
    if debug:
        print("Step 5: Closing bag...")

    # Click back multiple times to ensure we exit all dialogs
    for i in range(3):
        click_back(adb)
        time.sleep(0.4)

        frame = win.get_screenshot_cv2()
        # Check if bag is still visible
        is_bag, _, _ = match_template(
            frame, "bag_tab_4k.png",
            search_region=BAG_TAB_REGION,
            threshold=VERIFICATION_THRESHOLD
        )
        if not is_bag:
            break

    # Final back to ensure we're out
    click_back(adb)
    time.sleep(0.3)

    # Step 6: Update inventory count
    if debug:
        print("Step 6: Updating inventory...")

    # Decrement the shield count in state
    current = get_shield_inventory()
    new_count = current.get(shield_type, 1)
    if new_count is not None and new_count > 0:
        new_count -= 1

    # Update with decremented value
    update_shield_inventory(
        shields_8hr=new_count if shield_type == "8hr" else current.get("8hr"),
        shields_12hr=new_count if shield_type == "12hr" else current.get("12hr"),
        shields_24hr=new_count if shield_type == "24hr" else current.get("24hr"),
    )

    if debug:
        print("=" * 50)
        print(f"SUCCESS: {shield_type} shield activated!")

    return {"success": True, "shield_type": shield_type, "message": f"{shield_type} shield activated"}


if __name__ == "__main__":
    import argparse
    from utils.adb_helper import ADBHelper

    parser = argparse.ArgumentParser(description="Shield Use Flow - Activate a shield")
    parser.add_argument("shield_type", choices=["8hr", "12hr", "24hr"], help="Shield duration")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--force", action="store_true", help="Use shield even if one is already active")
    args = parser.parse_args()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    result = shield_use_flow(adb, args.shield_type, win, debug=args.debug, force=args.force)
    print(f"\nResult: {result}")
