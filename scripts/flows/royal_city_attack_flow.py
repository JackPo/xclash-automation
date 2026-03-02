"""
Royal City Reinforce Flow - Navigate to Royal City and reinforce it.

Uses template matching for reliable detection.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.adb_helper import ADBHelper
from utils.template_matcher import match_template
from utils.return_to_base_view import return_to_base_view
from utils.hero_selector import HeroSelector
from scripts.flows.go_to_mark_flow import go_to_mark_flow

# Templates
STAR_ICON_TEMPLATE = "mark_star_icon_4k.png"
UNOCCUPIED_TEMPLATE = "royal_city_unoccupied_tab_4k.png"
REINFORCE_BUTTON_TEMPLATE = "royal_city_reinforce_button_4k.png"
REINFORCE_PANEL_HEADER_TEMPLATE = "reinforce_panel_header_4k.png"
REINFORCE_CONFIRM_BUTTON_TEMPLATE = "reinforce_confirm_button_4k.png"
MARCH_BUTTON_TEMPLATE = "march_button_4k.png"

# Fixed positions (4K)
ROYAL_CITY_CLICK_POS = (1920, 900)  # Center of screen after go_to_mark

# Thresholds
TEMPLATE_THRESHOLD = 0.05

# Timeouts
POLL_TIMEOUT = 10.0
POLL_INTERVAL = 0.3


def royal_city_attack_flow(
    adb: ADBHelper,
    win: WindowsScreenshotHelper | None = None,
    debug: bool = True,
) -> bool:
    """
    Navigate to Royal City and reinforce it.

    Steps:
    1. go_to_mark -> centers Royal City
    2. Verify star icon visible (confirms location)
    3. Click fixed position to open city panel
    4. Poll for Unoccupied template (panel opened)
    5. Template match Reinforce button and click
    6. Poll for troop panel / March button
    7. Click March

    Returns:
        True if successful, False otherwise
    """
    win = win or WindowsScreenshotHelper()

    if debug:
        print("=== ROYAL CITY REINFORCE FLOW ===")
        print()

    try:
        # Step 1: Navigate to marked Royal City
        if debug:
            print("Step 1: Navigating to Royal City via go_to_mark...")
        if not go_to_mark_flow(adb, win, debug=debug):
            if debug:
                print("  ERROR: Failed to navigate to Royal City")
            return False

        time.sleep(1.0)

        # Step 2: Verify star icon visible
        if debug:
            print("Step 2: Verifying star icon at marked location...")

        frame = win.get_screenshot_cv2()
        found, score, pos = match_template(frame, STAR_ICON_TEMPLATE, threshold=TEMPLATE_THRESHOLD)

        if not found:
            if debug:
                print(f"  WARNING: Star icon not found (score={score:.4f}), proceeding anyway...")
        else:
            if debug:
                print(f"  Star icon found at {pos}, score={score:.4f}")

        # Step 3: Click fixed position to open city panel
        if debug:
            print(f"Step 3: Clicking Royal City at fixed position {ROYAL_CITY_CLICK_POS}...")

        adb.tap(*ROYAL_CITY_CLICK_POS, source="flow:royal_city:click_city")
        time.sleep(1.5)

        # Step 4: Poll for Unoccupied template (panel opened)
        if debug:
            print("Step 4: Waiting for city panel to open (Unoccupied tab)...")

        panel_opened = False
        start_time = time.time()

        while time.time() - start_time < POLL_TIMEOUT:
            frame = win.get_screenshot_cv2()
            found, score, pos = match_template(frame, UNOCCUPIED_TEMPLATE, threshold=TEMPLATE_THRESHOLD)

            if found:
                if debug:
                    print(f"  Panel opened! Unoccupied tab at {pos}, score={score:.4f}")
                panel_opened = True
                break

            time.sleep(POLL_INTERVAL)

        if not panel_opened:
            if debug:
                print("  ERROR: City panel did not open (Unoccupied tab not found)")
            return False

        # Step 5: Find and click hexagonal Reinforce button
        if debug:
            print("Step 5: Finding hexagonal Reinforce button...")

        frame = win.get_screenshot_cv2()
        found, score, pos = match_template(frame, REINFORCE_BUTTON_TEMPLATE, threshold=TEMPLATE_THRESHOLD)

        if not found:
            if debug:
                print(f"  ERROR: Reinforce button not found (score={score:.4f})")
            return False

        if debug:
            print(f"  Reinforce button at {pos}, score={score:.4f}")
            print(f"  Clicking Reinforce...")

        adb.tap(*pos, source="flow:royal_city:click_reinforce")
        time.sleep(1.5)

        # Step 6: Poll for Reinforce panel header
        if debug:
            print("Step 6: Waiting for Reinforce panel (header)...")

        panel_opened = False
        start_time = time.time()

        while time.time() - start_time < POLL_TIMEOUT:
            frame = win.get_screenshot_cv2()
            found, score, pos = match_template(frame, REINFORCE_PANEL_HEADER_TEMPLATE, threshold=TEMPLATE_THRESHOLD)

            if found:
                if debug:
                    print(f"  Reinforce panel opened! Header at {pos}, score={score:.4f}")
                panel_opened = True
                break

            time.sleep(POLL_INTERVAL)

        if not panel_opened:
            if debug:
                print("  ERROR: Reinforce panel did not open")
            return False

        # Step 7: Find and click Reinforce confirm button
        if debug:
            print("Step 7: Finding Reinforce confirm button...")

        frame = win.get_screenshot_cv2()
        found, score, pos = match_template(frame, REINFORCE_CONFIRM_BUTTON_TEMPLATE, threshold=TEMPLATE_THRESHOLD)

        if not found:
            if debug:
                print(f"  ERROR: Reinforce confirm button not found (score={score:.4f})")
            return False

        if debug:
            print(f"  Confirm button at {pos}, score={score:.4f}")
            print(f"  Clicking confirm...")

        adb.tap(*pos, source="flow:royal_city:click_confirm")
        time.sleep(1.5)

        # Step 8: Poll for March button (troop panel opened)
        if debug:
            print("Step 8: Waiting for troop panel (March button)...")

        march_found = False
        march_pos = None
        start_time = time.time()

        while time.time() - start_time < POLL_TIMEOUT:
            frame = win.get_screenshot_cv2()
            found, score, pos = match_template(frame, MARCH_BUTTON_TEMPLATE, threshold=TEMPLATE_THRESHOLD)

            if found:
                if debug:
                    print(f"  March button found at {pos}, score={score:.4f}")
                march_found = True
                march_pos = pos
                break

            time.sleep(POLL_INTERVAL)

        if not march_found:
            if debug:
                print("  ERROR: March button not found")
            return False

        # Step 9: Select rightmost idle hero
        if debug:
            print("Step 9: Selecting rightmost idle hero...")

        hero_selector = HeroSelector()
        frame = win.get_screenshot_cv2()
        slot = hero_selector.find_rightmost_idle(frame, zz_mode='prefer')

        if slot:
            if debug:
                print(f"  Found hero slot {slot['id']} at {slot['click']}")
            adb.tap(*slot['click'], source="flow:royal_city:select_hero")
            time.sleep(0.5)
        else:
            if debug:
                print("  WARNING: No idle hero found, using first slot")
            adb.tap(1497, 413, source="flow:royal_city:select_hero_fallback")
            time.sleep(0.5)

        # Step 10: Click March
        if debug:
            print("Step 10: Clicking March to dispatch troops...")

        adb.tap(*march_pos, source="flow:royal_city:click_march")
        time.sleep(1.0)

        if debug:
            print()
            print("=== ROYAL CITY REINFORCE COMPLETE ===")

        return True

    except Exception as e:
        if debug:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
        return False

    finally:
        if debug:
            print("Returning to base view...")
        return_to_base_view(adb, win, debug=False)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Reinforce Royal City")
    parser.add_argument("--debug", "-d", action="store_true", default=True, help="Enable debug output")
    args = parser.parse_args()

    print("Royal City Reinforce Flow")
    print("=" * 50)
    print()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    result = royal_city_attack_flow(adb, win, debug=args.debug)

    print()
    print(f"Result: {'SUCCESS' if result else 'FAILED'}")
