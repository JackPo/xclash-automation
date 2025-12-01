"""
Hero Upgrade Arms Race flow - Check hero tiles for red notification dots and upgrade available heroes.

Triggered at 2:00 AM Pacific if user was continuously idle for 3h 45m before that time.

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

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.hero_tile_detector import detect_tiles_with_red_dots
from utils.upgrade_button_matcher import UpgradeButtonMatcher
from .back_from_chat_flow import back_from_chat_flow

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

            # Click back repeatedly until we reach town/world view
            print(f"    [HERO_UPGRADE]   Upgrade clicked - clicking back until town/world view")
            from utils.view_state_detector import detect_view, ViewState
            for _ in range(10):  # Max 10 back clicks
                time.sleep(0.5)
                frame = win.get_screenshot_cv2()
                view_state, _ = detect_view(frame)
                if view_state in (ViewState.TOWN, ViewState.WORLD):
                    print(f"    [HERO_UPGRADE]   Reached {view_state.value} view")
                    break
                print(f"    [HERO_UPGRADE]   Clicking back...")
                adb.tap(*BACK_BUTTON_CLICK)

            print(f"    [HERO_UPGRADE] Flow complete - {upgrades_done} upgrade performed")
            return True
        else:
            print(f"    [HERO_UPGRADE]   Upgrade not available (scores: avail={avail_score:.3f}, unavail={unavail_score:.3f})")

        # Click back to return to hero grid
        print(f"    [HERO_UPGRADE]   Clicking back to return to grid")
        adb.tap(*BACK_BUTTON_CLICK)
        time.sleep(0.5)

        # Re-take screenshot for next iteration (grid may have changed)
        frame = win.get_screenshot_cv2()

    # Step 5: Exit hero grid
    print(f"    [HERO_UPGRADE] Step 4: Exiting hero grid")
    adb.tap(*BACK_BUTTON_CLICK)
    time.sleep(0.5)

    # Use back_from_chat_flow to ensure we're back to main view
    back_from_chat_flow(adb, win)

    print(f"    [HERO_UPGRADE] Flow complete - {upgrades_done} upgrades performed")
    return True
