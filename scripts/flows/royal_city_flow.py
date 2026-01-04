"""
Royal City Flow - Attack, Rally, or Scout a Royal City.

Usage:
    python scripts/flows/royal_city_flow.py attack   # Attack with rightmost idle hero
    python scripts/flows/royal_city_flow.py rally    # Rally with rightmost idle hero
    python scripts/flows/royal_city_flow.py scout    # Just scout the city

Assumes Royal City panel is already open (Attack/Rally/Scout buttons visible).
Use go_to_mark_flow first to navigate to the city.
"""

from __future__ import annotations

import sys
import time
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy.typing as npt

from utils.return_to_base_view import return_to_base_view
from utils.template_matcher import match_template
from utils.hero_selector import HeroSelector
from utils.debug_screenshot import save_debug_screenshot
from config import ROYAL_CITY_BUTTON_OFFSETS, ROYAL_CITY_BUTTON_SIZE

from utils.windows_screenshot_helper import WindowsScreenshotHelper

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

logger = logging.getLogger("royal_city_flow")

FLOW_NAME = "royal_city"

# Templates
ATTACK_TEMPLATE = "royal_city_attack_button_4k.png"
RALLY_TEMPLATE = "rally_button_4k.png"  # Has mask
SCOUT_TEMPLATE = "royal_city_scout_button_4k.png"
UNOCCUPIED_TEMPLATE = "royal_city_unoccupied_tab_4k.png"

# March button (reuse from other flows)
MARCH_BUTTON_TEMPLATE = "rally_march_button_4k.png"

# Search region for buttons (center-ish area where panel appears)
BUTTON_SEARCH_REGION = (1300, 1100, 1200, 800)  # x, y, w, h

# Timing
CLICK_DELAY = 0.5
SCREEN_TRANSITION_DELAY = 1.5


def _log(msg: str) -> None:
    logger.info(msg)
    print(f"    [ROYAL_CITY] {msg}")


def _find_attack_button(frame: npt.NDArray[Any]) -> tuple[bool, int, int, float]:
    """Find Attack button using template matching. Returns (found, center_x, center_y, score)."""
    found, score, loc = match_template(
        frame, ATTACK_TEMPLATE,
        search_region=BUTTON_SEARCH_REGION,
        threshold=0.90  # TM_CCORR_NORMED with mask
    )
    if found and loc:
        # CRITICAL: match_template returns CENTER already - don't add half size!
        return True, loc[0], loc[1], score
    return False, 0, 0, score


def _find_button_by_offset(attack_pos: tuple[int, int], button_name: str) -> tuple[int, int] | None:
    """Calculate button position from Attack position using known offsets."""
    offset = ROYAL_CITY_BUTTON_OFFSETS.get(button_name)
    if not offset:
        return None
    w, h = ROYAL_CITY_BUTTON_SIZE
    x = attack_pos[0] + offset[0] + w // 2
    y = attack_pos[1] + offset[1] + h // 2
    return (x, y)


def _is_city_unoccupied(frame: npt.NDArray[Any]) -> bool:
    """Check if Royal City is unoccupied (can't apply titles)."""
    found, score, _ = match_template(
        frame, UNOCCUPIED_TEMPLATE,
        search_region=(1500, 200, 800, 300),
        threshold=0.1  # SQDIFF (no mask) - lower is better
    )
    return found


def _select_rightmost_idle_hero(adb: ADBHelper, win: WindowsScreenshotHelper) -> bool:
    """Select the rightmost idle hero. Returns True if successful."""
    hero_selector = HeroSelector()
    frame = win.get_screenshot_cv2()

    slot = hero_selector.find_rightmost_idle(frame, zz_mode='prefer')
    if slot:
        _log(f"Selecting hero slot {slot['id']} at {slot['click']}")
        adb.tap(*slot['click'])
        time.sleep(CLICK_DELAY)
        return True
    else:
        _log("WARNING: No idle hero found, selecting first slot")
        # Fallback: click first hero slot
        adb.tap(1497, 413)  # First slot position
        time.sleep(CLICK_DELAY)
        return True


def _click_march_button(adb: ADBHelper, win: WindowsScreenshotHelper) -> bool:
    """Find and click the March button. Returns True if successful."""
    frame = win.get_screenshot_cv2()

    # Search for march button in lower portion of screen
    found, score, loc = match_template(
        frame, MARCH_BUTTON_TEMPLATE,
        search_region=(1600, 1400, 800, 400),
        threshold=0.05  # TM_SQDIFF_NORMED
    )

    if found and loc:
        # loc is already CENTER - click directly
        _log(f"Clicking March button at {loc} (score={score:.4f})")
        adb.tap(*loc)
        return True
    else:
        _log(f"March button not found (score={score:.4f}), trying fixed position")
        # Fallback to common march button position
        adb.tap(1912, 1648)
        return True


def royal_city_flow(
    adb: ADBHelper,
    action: str = "scout",
    win: WindowsScreenshotHelper | None = None,
    debug: bool = True
) -> bool:
    """
    Execute Royal City action (attack, rally, or scout).

    Assumes we're at the Royal City location (star visible in center).
    Will click the star to open panel, verify unclaimed, then perform action.

    Args:
        adb: ADBHelper instance
        action: "attack", "rally", or "scout"
        win: WindowsScreenshotHelper (optional)
        debug: Enable debug screenshots

    Returns:
        bool: True if successful
    """
    from utils.windows_screenshot_helper import WindowsScreenshotHelper as WSH

    action = action.lower()
    if action not in ("attack", "rally", "scout"):
        _log(f"ERROR: Invalid action '{action}'. Use attack, rally, or scout.")
        return False

    win = win or WSH()
    _log(f"=== ROYAL CITY {action.upper()} FLOW ===")

    try:
        # Step 1: Find and click the star to open Royal City panel
        _log("Step 1: Finding star to open Royal City panel...")
        frame = win.get_screenshot_cv2()
        if debug:
            save_debug_screenshot(frame, FLOW_NAME, "00_before_click_star")

        # Template match the star
        found, score, loc = match_template(
            frame, "star_single_4k.png",
            search_region=(1400, 600, 1100, 1000),  # Center area
            threshold=0.15  # TM_SQDIFF_NORMED - lower is better
        )
        if not found or loc is None:
            _log(f"ERROR: Star not found (score={score:.4f})")
            return False

        # match_template returns CENTER already, just click it
        _log(f"Star at center {loc}, clicking...")
        adb.tap(*loc)
        time.sleep(SCREEN_TRANSITION_DELAY)

        # Step 2: Take screenshot and verify panel opened
        frame = win.get_screenshot_cv2()
        if debug:
            save_debug_screenshot(frame, FLOW_NAME, "01_after_click_star")

        # Check if city is unoccupied (required for attack/scout)
        if not _is_city_unoccupied(frame):
            _log("ERROR: City is OCCUPIED - cannot attack/scout occupied cities")
            _log("Only UNCLAIMED cities can be attacked/scouted")
            if debug:
                save_debug_screenshot(frame, FLOW_NAME, "01_city_occupied")
            return False

        _log("City is UNCLAIMED - can proceed with action")

        # Find Attack button as reference
        found, attack_x, attack_y, score = _find_attack_button(frame)
        if not found:
            _log(f"ERROR: Attack button not found (score={score:.4f})")
            _log("Is the Royal City panel open?")
            if debug:
                save_debug_screenshot(frame, FLOW_NAME, "01_attack_not_found")
            return False

        attack_pos = (attack_x - ROYAL_CITY_BUTTON_SIZE[0] // 2,
                      attack_y - ROYAL_CITY_BUTTON_SIZE[1] // 2)  # Top-left
        _log(f"Attack button found at center ({attack_x}, {attack_y}), score={score:.4f}")

        # Step 3: Find and click target button via template match
        w, h = ROYAL_CITY_BUTTON_SIZE

        click_pos: tuple[int, int]
        if action == "attack":
            # Already have Attack position from above
            click_pos = (attack_x, attack_y)
            _log(f"Step 3: Clicking ATTACK at {click_pos}")
        elif action == "rally":
            found, score, loc = match_template(
                frame, RALLY_TEMPLATE,
                search_region=BUTTON_SEARCH_REGION,
                threshold=0.90
            )
            if not found or loc is None:
                _log(f"ERROR: Rally button not found (score={score:.4f})")
                return False
            click_pos = loc  # match_template returns CENTER already
            _log(f"Step 3: Rally at center {click_pos}, score={score:.4f}")
        else:  # scout
            found, score, loc = match_template(
                frame, SCOUT_TEMPLATE,
                search_region=BUTTON_SEARCH_REGION,
                threshold=0.90
            )
            if not found or loc is None:
                _log(f"ERROR: Scout button not found (score={score:.4f})")
                return False
            click_pos = loc  # match_template returns CENTER already
            _log(f"Step 3: Scout at center {click_pos}, score={score:.4f}")

        adb.tap(*click_pos)
        time.sleep(SCREEN_TRANSITION_DELAY)

        # Step 3: Handle action-specific logic
        if action == "scout":
            _log("Scout sent!")
            frame = win.get_screenshot_cv2()
            if debug:
                save_debug_screenshot(frame, FLOW_NAME, "02_scout_sent")
            _log("=== ROYAL CITY SCOUT COMPLETE ===")
            return True

        # For attack/rally: need to select hero and march
        frame = win.get_screenshot_cv2()
        if debug:
            save_debug_screenshot(frame, FLOW_NAME, "02_troop_selection")

        # Step 4: Select rightmost idle hero
        _log("Step 3: Selecting rightmost idle hero...")
        if not _select_rightmost_idle_hero(adb, win):
            _log("WARNING: Hero selection may have failed")

        frame = win.get_screenshot_cv2()
        if debug:
            save_debug_screenshot(frame, FLOW_NAME, "03_hero_selected")

        # Step 5: Click March button
        _log("Step 4: Clicking March button...")
        if not _click_march_button(adb, win):
            _log("ERROR: Could not click March button")
            return False

        time.sleep(CLICK_DELAY)
        frame = win.get_screenshot_cv2()
        if debug:
            save_debug_screenshot(frame, FLOW_NAME, "04_march_clicked")

        _log(f"=== ROYAL CITY {action.upper()} COMPLETE ===")
        return True

    except Exception as e:
        _log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        _log("Returning to base view...")
        return_to_base_view(adb, win, debug=False)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Royal City action flow")
    parser.add_argument("action", choices=["attack", "rally", "scout"],
                        help="Action to perform")
    parser.add_argument("--debug", "-d", action="store_true",
                        help="Enable debug screenshots")
    args = parser.parse_args()

    print(f"Royal City {args.action.upper()} Flow")
    print("=" * 50)

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    result = royal_city_flow(adb, args.action, win, debug=args.debug)

    print()
    print(f"Result: {'SUCCESS' if result else 'FAILED'}")
