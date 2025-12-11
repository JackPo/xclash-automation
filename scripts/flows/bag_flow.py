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

# Fixed positions (4K resolution)
BAG_BUTTON_REGION = (3679, 1577, 86, 93)
BAG_BUTTON_CLICK = (3732, 1633)
BAG_TAB_REGION = (1352, 32, 1127, 90)
BACK_BUTTON_CLICK = (1407, 2055)

VERIFICATION_THRESHOLD = 0.1

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "ground_truth"


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

    # Step 3: Run Special tab flow (bag defaults to Special)
    if debug:
        print("\n=== Special Tab ===")
    results["special"] = bag_special_flow(adb, win, debug=debug, open_bag=False)

    # Step 4: Run Hero tab flow
    if debug:
        print("\n=== Hero Tab ===")
    results["hero"] = bag_hero_flow(adb, win, debug=debug, open_bag=False)

    # Step 5: Run Resources tab flow
    if debug:
        print("\n=== Resources Tab ===")
    results["resources"] = bag_resources_flow(adb, win, debug=debug, open_bag=False)

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
