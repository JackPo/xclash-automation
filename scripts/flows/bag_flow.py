"""
Bag Flow - Main orchestrator for all bag tab flows.

Opens the bag and runs all 3 subflows:
1. Special tab - chests
2. Hero tab - chests
3. Resources tab - diamonds

Then closes bag and returns to base view.
Triggered by 5-minute idle (same as union gifts/donation).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import cv2
import numpy as np

from scripts.flows.bag_special_flow import bag_special_flow
from scripts.flows.bag_hero_flow import bag_hero_flow
from scripts.flows.bag_resources_flow import bag_resources_flow
from utils.return_to_base_view import return_to_base_view
from utils.view_state_detector import go_to_town

# Fixed positions (4K resolution)
BAG_BUTTON_REGION = (3679, 1577, 86, 93)
BAG_BUTTON_CLICK = (3732, 1633)
BAG_TAB_REGION = (1352, 32, 1127, 90)
BACK_BUTTON_CLICK = (1407, 2055)

VERIFICATION_THRESHOLD = 0.01

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "ground_truth"

# Active tab templates - match all, lowest score = current tab
ACTIVE_TAB_TEMPLATES = {
    "special": "bag_special_tab_active_4k.png",
    "resources": "bag_resources_tab_active_4k.png",
    "hero": "bag_hero_tab_active_4k.png",
}

# Tab click positions (4K)
TAB_CLICK_POSITIONS = {
    "special": (1602, 2080),
    "resources": (1827, 2076),
    "hero": (2257, 2078),
}


def _load_template(name: str) -> np.ndarray:
    """Load a template image in grayscale."""
    path = TEMPLATES_DIR / name
    template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if template is None:
        raise FileNotFoundError(f"Template not found: {path}")
    return template


def _verify_at_fixed_region(frame_gray: np.ndarray, template: np.ndarray,
                            region: tuple, threshold: float = VERIFICATION_THRESHOLD) -> tuple[bool, float]:
    """Verify template is present at fixed region."""
    x, y, w, h = region
    roi = frame_gray[y:y+h, x:x+w]
    result = cv2.matchTemplate(roi, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, _, _ = cv2.minMaxLoc(result)
    return min_val <= threshold, min_val


def detect_active_tab(frame_gray: np.ndarray, debug: bool = False) -> str | None:
    """
    Detect which bag tab is currently active by matching all active templates.

    Returns the tab name with lowest score that passes threshold, or None.
    """
    best_tab = None
    best_score = 1.0

    for tab_name, template_name in ACTIVE_TAB_TEMPLATES.items():
        template = _load_template(template_name)
        result = cv2.matchTemplate(frame_gray, template, cv2.TM_SQDIFF_NORMED)
        min_val, _, _, _ = cv2.minMaxLoc(result)

        if debug:
            print(f"    {tab_name}: {min_val:.4f}")

        if min_val < best_score and min_val <= VERIFICATION_THRESHOLD:
            best_score = min_val
            best_tab = tab_name

    return best_tab


def switch_to_tab(adb, win, target_tab: str, debug: bool = False) -> bool:
    """
    Switch to the specified tab if not already there.

    Returns True if successfully on target tab.
    """
    frame = win.get_screenshot_cv2()
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    current_tab = detect_active_tab(frame_gray, debug=debug)

    if current_tab == target_tab:
        if debug:
            print(f"  Already on {target_tab} tab")
        return True

    if target_tab not in TAB_CLICK_POSITIONS:
        if debug:
            print(f"  Unknown tab: {target_tab}")
        return False

    if debug:
        print(f"  Current tab: {current_tab}, switching to {target_tab}...")

    adb.tap(*TAB_CLICK_POSITIONS[target_tab])
    time.sleep(0.5)

    # Verify switch
    frame = win.get_screenshot_cv2()
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    new_tab = detect_active_tab(frame_gray, debug=debug)

    if new_tab == target_tab:
        if debug:
            print(f"  Switched to {target_tab} tab")
        return True
    else:
        if debug:
            print(f"  Failed to switch, still on {new_tab}")
        return False


def bag_flow(adb, win=None, debug: bool = False) -> dict:
    """
    Execute the main bag flow - opens bag and runs all 3 subflows.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (optional)
        debug: Enable debug output

    Returns:
        dict with counts: {"special": N, "hero": N, "resources": N}
    """
    if win is None:
        from utils.windows_screenshot_helper import WindowsScreenshotHelper
        win = WindowsScreenshotHelper()

    results = {"special": 0, "hero": 0, "resources": 0}

    # Load templates
    bag_template = _load_template("bag_button_4k.png")
    bag_tab_template = _load_template("bag_tab_4k.png")

    # Step 0: Navigate to TOWN (bag button only visible in TOWN view)
    if debug:
        print("Step 0: Navigating to TOWN...")
    go_to_town(adb, debug=debug)
    time.sleep(0.5)

    # Step 1: Verify bag button visible (confirms we're in TOWN)
    if debug:
        print("Step 1: Verifying bag button...")

    frame = win.get_screenshot_cv2()
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    is_present, score = _verify_at_fixed_region(frame_gray, bag_template, BAG_BUTTON_REGION)
    if not is_present:
        if debug:
            print(f"  Bag button not found (score={score:.4f})")
        return results

    if debug:
        print(f"  Bag button verified (score={score:.4f})")

    # Step 2: Click bag button
    if debug:
        print("Step 2: Opening bag...")

    adb.tap(*BAG_BUTTON_CLICK)
    time.sleep(1.5)

    # Verify bag opened
    frame = win.get_screenshot_cv2()
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    is_present, score = _verify_at_fixed_region(frame_gray, bag_tab_template, BAG_TAB_REGION)
    if not is_present:
        if debug:
            print(f"  Bag tab not found - bag didn't open (score={score:.4f})")
        return_to_base_view(adb, win, debug=debug)
        return results

    if debug:
        print(f"  Bag opened (score={score:.4f})")

    # Step 3: Run Special tab flow
    if debug:
        print("\n=== Special Tab ===")
    if switch_to_tab(adb, win, "special", debug=debug):
        results["special"] = bag_special_flow(adb, win, debug=debug, open_bag=False)
    else:
        if debug:
            print("  Failed to switch to Special tab")

    # Step 4: Run Hero tab flow
    if debug:
        print("\n=== Hero Tab ===")
    if switch_to_tab(adb, win, "hero", debug=debug):
        results["hero"] = bag_hero_flow(adb, win, debug=debug, open_bag=False)
    else:
        if debug:
            print("  Failed to switch to Hero tab")

    # Step 5: Run Resources tab flow
    if debug:
        print("\n=== Resources Tab ===")
    if switch_to_tab(adb, win, "resources", debug=debug):
        results["resources"] = bag_resources_flow(adb, win, debug=debug, open_bag=False)
    else:
        if debug:
            print("  Failed to switch to Resources tab")

    # Step 6: Close bag and return to base view
    if debug:
        print("\nStep 6: Closing bag...")

    adb.tap(*BACK_BUTTON_CLICK)
    time.sleep(0.5)

    return_to_base_view(adb, win, debug=debug)

    if debug:
        print(f"\n=== Bag Flow Complete ===")
        print(f"Special: {results['special']}, Hero: {results['hero']}, Resources: {results['resources']}")

    return results


if __name__ == "__main__":
    import argparse
    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    parser = argparse.ArgumentParser(description="Bag Flow - Claim from all bag tabs")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    results = bag_flow(adb, win, debug=args.debug)
    print(f"\nResults: Special={results['special']}, Hero={results['hero']}, Resources={results['resources']}")
