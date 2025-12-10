"""
Hero Upgrade Arms Race flow - Check hero tiles for red notification dots and upgrade available heroes.

Triggered during Arms Race "Enhance Hero" event in the last N minutes (configurable),
if user was idle since the START of the Enhance Hero block.

Flow sequence:
1. Click Fing Hero button at (2272, 2038)
2. Wait for hero grid to load
3. Scan 3x4 grid of hero tiles for red notification dots
4. For each tile with red dot:
   a. Click tile
   b. Check if upgrade button is available (green) or unavailable (gray)
   c. If available: click upgrade
   d. Click back to return to hero grid
5. Click back to exit hero grid

Templates:
- Fing Hero button: templates/ground_truth/heroes_button_4k.png (123x177 at 2211,1950)
- Upgrade available: templates/ground_truth/upgrade_button_available_4k.png
- Upgrade unavailable: templates/ground_truth/upgrade_button_unavailable_4k.png
"""

import time

from config import ARMS_RACE_ENHANCE_HERO_MAX_UPGRADES
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.hero_tile_detector import detect_tiles_with_red_dots
from utils.upgrade_button_matcher import UpgradeButtonMatcher
from utils.return_to_base_view import return_to_base_view

# Fing Hero button position
FING_HERO_BUTTON_CLICK = (2272, 2038)

# Back button position (for returning to hero grid after checking a hero)
BACK_BUTTON_CLICK = (1407, 2055)


def hero_upgrade_arms_race_flow(adb, screenshot_helper=None):
    """
    Complete Hero Upgrade Arms Race flow: open heroes -> find tiles with red dots -> upgrade if available.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance (optional)

    Returns:
        True if successful, False otherwise
    """
    win = screenshot_helper if screenshot_helper else WindowsScreenshotHelper()
    upgrade_matcher = UpgradeButtonMatcher()

    # Step 1: Click Fing Hero button
    print(f"    [HERO_UPGRADE] Step 1: Clicking Fing Hero button at {FING_HERO_BUTTON_CLICK}")
    adb.tap(*FING_HERO_BUTTON_CLICK)

    # Step 2: Wait for hero grid to load
    time.sleep(1.5)

    # Step 3: Take screenshot and detect tiles with red dots
    print("    [HERO_UPGRADE] Step 2: Scanning hero grid for red dots...")
    frame = win.get_screenshot_cv2()
    if frame is None:
        print("    [HERO_UPGRADE] Failed to get screenshot")
        return False

    tiles_with_dots = detect_tiles_with_red_dots(frame, debug=True)

    if not tiles_with_dots:
        print("    [HERO_UPGRADE] No tiles with red dots found")
        # Still click back to exit hero grid
        adb.tap(*BACK_BUTTON_CLICK)
        return True

    print(f"    [HERO_UPGRADE] Found {len(tiles_with_dots)} tiles with red dots")

    upgrades_done = 0

    # Step 4: Process each tile with red dot
    for i, tile in enumerate(tiles_with_dots):
        tile_name = tile['name']
        click_pos = tile['click']

        print(f"    [HERO_UPGRADE] Step 3.{i+1}: Processing tile {tile_name}")

        # Click the tile
        print(f"    [HERO_UPGRADE]   Clicking tile at {click_pos}")
        adb.tap(*click_pos)
        time.sleep(1.0)

        # Take screenshot and check upgrade button
        frame = win.get_screenshot_cv2()
        if frame is None:
            print("    [HERO_UPGRADE]   Failed to get screenshot")
            adb.tap(*BACK_BUTTON_CLICK)
            time.sleep(0.5)
            continue

        is_available, avail_score, unavail_score = upgrade_matcher.check_upgrade_available(frame, debug=True)

        if is_available:
            # Click upgrade button
            upgrade_click = upgrade_matcher.get_click_position()
            print(f"    [HERO_UPGRADE]   Upgrade AVAILABLE! Clicking at {upgrade_click}")
            adb.tap(*upgrade_click)
            time.sleep(0.5)
            upgrades_done += 1

            # Check if we've hit the max upgrades
            if upgrades_done >= ARMS_RACE_ENHANCE_HERO_MAX_UPGRADES:
                print(f"    [HERO_UPGRADE]   Reached max upgrades ({ARMS_RACE_ENHANCE_HERO_MAX_UPGRADES}) - returning to base view...")
                return_to_base_view(adb, win, debug=True)
                print(f"    [HERO_UPGRADE] Flow complete - {upgrades_done} upgrade(s) performed")
                return True

            # More upgrades allowed, click back to continue
            print(f"    [HERO_UPGRADE]   Upgrade {upgrades_done}/{ARMS_RACE_ENHANCE_HERO_MAX_UPGRADES} done, clicking back for more...")
            adb.tap(*BACK_BUTTON_CLICK)
            time.sleep(0.5)
        else:
            print(f"    [HERO_UPGRADE]   Upgrade not available (scores: avail={avail_score:.3f}, unavail={unavail_score:.3f})")

        # Click back to return to hero grid
        print(f"    [HERO_UPGRADE]   Clicking back to return to grid")
        adb.tap(*BACK_BUTTON_CLICK)
        time.sleep(0.5)

        # Re-take screenshot for next iteration (grid may have changed)
        frame = win.get_screenshot_cv2()

    # Step 5: Exit hero grid and return to base view
    print(f"    [HERO_UPGRADE] Step 4: Returning to base view...")
    return_to_base_view(adb, win, debug=True)

    print(f"    [HERO_UPGRADE] Flow complete - {upgrades_done} upgrades performed")
    return True
