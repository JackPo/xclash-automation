"""
Reinforce Camp (Star) Flow - Click star icon directly to reinforce camp.

Flow:
1. Click star icon at fixed position (same as Royal City star)
2. Look for reinforce button and click it

Usage:
    python scripts/flows/reinforce_camp_star_flow.py
    python scripts/flows/reinforce_camp_star_flow.py --debug
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import cv2
import numpy.typing as npt

from utils.return_to_base_view import return_to_base_view
from utils.template_matcher import match_template

from utils.windows_screenshot_helper import WindowsScreenshotHelper

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

NDArray = npt.NDArray[Any]

# Fixed positions (from template matching results)
STAR_ICON_FALLBACK = (1919, 905)
REINFORCE_BUTTON_CLICK = (1917, 1365)  # On camp popup
HERO_SLOT_1_CLICK = (1467, 1869)  # Leftmost hero slot
MARCH_BUTTON_CLICK = (1924, 1648)  # Same as zombie_attack_flow (from Gemini detection)

# Polling settings
from utils.timings import POLL_INTERVAL, POLL_TIMEOUT_SHORT as POLL_TIMEOUT


def reinforce_camp_star_flow(
    adb: ADBHelper,
    screenshot_helper: WindowsScreenshotHelper | None = None,
    debug: bool = False
) -> bool:
    """
    Click star icon to open camp panel and reinforce.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance
        debug: Enable debug logging

    Returns:
        True if successful, False otherwise
    """
    from utils.windows_screenshot_helper import WindowsScreenshotHelper as WSH
    win = screenshot_helper or WSH()

    try:
        # Step 1: Find and click star icon using template matching
        if debug:
            print("  Step 1: Finding star icon...")
        frame = win.get_screenshot_cv2()
        found, score, pos = match_template(frame, "mark_star_icon_4k.png", threshold=0.15)

        if found and pos:
            if debug:
                print(f"    Star found at {pos}, score={score:.4f}")
            adb.tap(pos[0], pos[1], source="flow:reinforce_camp_star:star_icon")
        else:
            if debug:
                print(f"    Star not found (score={score:.4f}), using fallback {STAR_ICON_FALLBACK}")
            adb.tap(*STAR_ICON_FALLBACK, source="flow:reinforce_camp_star:star_icon")
        time.sleep(1.0)

        # Step 2: Look for reinforce button
        if debug:
            print("  Step 2: Looking for reinforce button...")

        frame = win.get_screenshot_cv2()

        if debug:
            cv2.imwrite("screenshots/debug/reinforce_camp_star_panel.png", frame)
            print("    Saved debug screenshot")

        # Try to find reinforce button
        found, score, pos = match_template(
            frame, "royal_city_reinforce_button_4k.png",
            threshold=0.1
        )

        if debug:
            print(f"    Reinforce button: found={found}, score={score:.4f}, pos={pos}")

        if found and pos:
            if debug:
                print(f"    Clicking reinforce button at {pos}")
            adb.tap(*pos, source="flow:reinforce_camp_star:reinforce_button")
            time.sleep(1.0)

            # Step 3: Click Reinforce button on Reinforce panel
            if debug:
                print("  Step 3: Finding Reinforce button on panel...")

            frame = win.get_screenshot_cv2()
            found, score, pos = match_template(
                frame, "reinforce_panel_button_4k.png",
                search_region=(1600, 1400, 700, 400),  # Constrain to panel area
                threshold=0.1
            )

            if debug:
                print(f"    Reinforce panel button: found={found}, score={score:.4f}, pos={pos}")

            if found and pos:
                adb.tap(*pos, source="flow:reinforce_camp_star:reinforce_panel_button")
            else:
                # Fallback to fixed position
                adb.tap(1914, 1614, source="flow:reinforce_camp_star:reinforce_panel_button")
            time.sleep(1.0)

            # Step 4: Click leftmost hero slot (always slot 1)
            if debug:
                print(f"  Step 4: Clicking leftmost hero at {HERO_SLOT_1_CLICK}...")

            time.sleep(0.5)
            adb.tap(*HERO_SLOT_1_CLICK, source="flow:reinforce_camp_star:hero_slot")
            time.sleep(0.3)

            # Step 5: Find and click March button (use search_region like zombie_attack_flow)
            if debug:
                print("  Step 5: Finding March button...")

            frame = win.get_screenshot_cv2()
            found, score, pos = match_template(
                frame, "march_button_4k.png",
                search_region=(1500, 1400, 900, 500),  # Constrain search area
                threshold=0.05
            )

            if debug:
                print(f"    March button: found={found}, score={score:.4f}, pos={pos}")

            if found and pos:
                adb.tap(*pos, source="flow:reinforce_camp_star:march_button")
            else:
                # Fallback to fixed position
                if debug:
                    print(f"    Using fallback {MARCH_BUTTON_CLICK}")
                adb.tap(*MARCH_BUTTON_CLICK, source="flow:reinforce_camp_star:march_button")

            time.sleep(0.5)
            if debug:
                print("  Reinforce march sent!")
            return True
        else:
            print("  ERROR: Reinforce button not found")
            return False

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return_to_base_view(adb, win, debug=debug)
        return False


if __name__ == "__main__":
    import sys
    import argparse
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from utils.adb_helper import ADBHelper

    parser = argparse.ArgumentParser(description="Click star to reinforce camp")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    print("=== Reinforce Camp (Star) Flow ===")
    print()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    result = reinforce_camp_star_flow(adb, win, debug=args.debug)
    print(f"\nResult: {'SUCCESS' if result else 'FAILED'}")
