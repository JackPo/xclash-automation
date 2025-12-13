"""
Bag Special Tab Flow - Chest claiming from Special tab.

Opens the bag (defaults to Special tab), finds chest tiles using multi-template
matching, and uses them one at a time. Rescans after each use since items shift.

Templates used:
- bag_button_4k.png - Verify bag button present
- bag_tab_4k.png - Verify bag menu opened
- bag_special_tab_active_4k.png - Verify Special tab is active
- bag_chest_special_4k.png - Open chest with blue gems
- bag_golden_chest_4k.png - Golden wooden chest
- bag_green_chest_4k.png - Green crystal chest
- bag_purple_gold_chest_4k.png - Purple crystal chest
- bag_chest_blue_4k.png - Blue/cyan crystal chest
- bag_chest_purple_4k.png - Purple chest with gold trim
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

from scripts.flows.bag_use_item_subflow import use_item_subflow

# Fixed positions (4K resolution)
BAG_BUTTON_REGION = (3679, 1577, 86, 93)
BAG_BUTTON_CLICK = (3732, 1633)

BAG_TAB_REGION = (1352, 32, 1127, 90)

SPECIAL_TAB_REGION = (1525, 2033, 163, 96)  # Same region for active/inactive
SPECIAL_TAB_CLICK = (1602, 2080)  # Only needed if switching from another tab

# Thresholds
CHEST_THRESHOLD = 0.01  # Very strict matching
VERIFICATION_THRESHOLD = 0.01

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "ground_truth"

# Chest templates for Special tab (all variants)
CHEST_TEMPLATES = [
    "bag_chest_special_4k.png",     # Open chest with blue gems
    "bag_golden_chest_4k.png",       # Golden wooden chest
    "bag_green_chest_4k.png",        # Green crystal chest
    "bag_purple_gold_chest_4k.png",  # Purple crystal chest
    "bag_chest_blue_4k.png",         # Blue/cyan crystal chest
    "bag_chest_purple_4k.png",       # Purple chest with gold trim
    "bag_chest_question_4k.png",     # Mystery chest with question mark
]


def _load_template(name: str) -> np.ndarray:
    """Load a template image in grayscale."""
    path = TEMPLATES_DIR / name
    template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if template is None:
        raise FileNotFoundError(f"Template not found: {path}")
    return template


def _load_chest_templates() -> list[tuple[str, np.ndarray]]:
    """Load all chest templates, skip missing ones."""
    templates = []
    for name in CHEST_TEMPLATES:
        path = TEMPLATES_DIR / name
        template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if template is not None:
            templates.append((name, template))
    return templates


def _verify_at_fixed_region(frame_gray: np.ndarray, template: np.ndarray,
                            region: tuple, threshold: float = VERIFICATION_THRESHOLD) -> tuple[bool, float]:
    """Verify template is present at fixed region."""
    x, y, w, h = region
    roi = frame_gray[y:y+h, x:x+w]
    result = cv2.matchTemplate(roi, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, _, _ = cv2.minMaxLoc(result)
    return min_val <= threshold, min_val


def _find_first_chest(frame_gray: np.ndarray, chest_templates: list[tuple[str, np.ndarray]],
                      debug: bool = False) -> tuple[tuple[int, int] | None, float, str | None]:
    """
    Find the first (best matching) chest in the frame using multiple templates.

    Returns:
        ((center_x, center_y), score, template_name) or (None, best_score, None) if not found
    """
    best_match = None
    best_score = 1.0
    best_template_name = None

    for name, template in chest_templates:
        h, w = template.shape
        result = cv2.matchTemplate(frame_gray, template, cv2.TM_SQDIFF_NORMED)
        min_val, _, min_loc, _ = cv2.minMaxLoc(result)

        if debug:
            print(f"    {name}: score={min_val:.4f}")

        if min_val < best_score:
            best_score = min_val
            if min_val <= CHEST_THRESHOLD:
                center_x = min_loc[0] + w // 2
                center_y = min_loc[1] + h // 2
                best_match = (center_x, center_y)
                best_template_name = name

    return best_match, best_score, best_template_name


def bag_special_flow(adb, win=None, debug: bool = False, open_bag: bool = True) -> int:
    """
    Execute the bag special flow to claim all chests from Special tab.

    Rescans after each chest since items shift position when used.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (optional)
        debug: Enable debug output
        open_bag: If True, click bag button first. If False, assume bag is already open.

    Returns:
        Number of chests claimed
    """
    if win is None:
        from utils.windows_screenshot_helper import WindowsScreenshotHelper
        win = WindowsScreenshotHelper()

    # Load templates
    bag_template = _load_template("bag_button_4k.png")
    bag_tab_template = _load_template("bag_tab_4k.png")
    special_tab_active_template = _load_template("bag_special_tab_active_4k.png")
    chest_templates = _load_chest_templates()

    if debug:
        print(f"Loaded {len(chest_templates)} chest templates: {[n for n, _ in chest_templates]}")

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
        time.sleep(1.5)  # Wait for bag to fully load

        # Verify bag opened
        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        is_present, score = _verify_at_fixed_region(frame_gray, bag_tab_template, BAG_TAB_REGION)
        if not is_present:
            if debug:
                print(f"  Bag tab not found - bag didn't open (score={score:.4f})")
            return 0

        if debug:
            print(f"  Bag tab verified - bag is open (score={score:.4f})")

    # Step 2: Verify Special tab is ACTIVE (bag defaults to Special tab)
    if debug:
        print("Step 2: Verifying Special tab is active...")

    frame = win.get_screenshot_cv2()
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    is_active, score = _verify_at_fixed_region(frame_gray, special_tab_active_template, SPECIAL_TAB_REGION)
    if not is_active:
        if debug:
            print(f"  Special tab not active (score={score:.4f}), clicking...")
        # Click Special tab to switch to it
        adb.tap(*SPECIAL_TAB_CLICK)
        time.sleep(0.5)

        # Re-verify
        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        is_active, score = _verify_at_fixed_region(frame_gray, special_tab_active_template, SPECIAL_TAB_REGION)
        if not is_active:
            if debug:
                print(f"  Special tab still not active (score={score:.4f})")
            return 0

    if debug:
        print(f"  Special tab is ACTIVE (score={score:.4f})")

    # Step 3: Loop - find and process chests one at a time, rescan after each
    chest_count = 0
    max_chests = 50

    while chest_count < max_chests:
        if debug:
            print(f"\nScan #{chest_count + 1}: Looking for chests...")

        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        chest_pos, score, matched_template = _find_first_chest(frame_gray, chest_templates, debug=debug)

        if chest_pos is None:
            if debug:
                print(f"  No chest found (best score={score:.4f}), done!")
            break

        cx, cy = chest_pos
        if debug:
            print(f"  Found chest at ({cx}, {cy}), score={score:.4f}, template={matched_template}")

        # Click chest
        if debug:
            print("  Clicking chest...")
        adb.tap(cx, cy)
        time.sleep(0.5)

        # Use the shared subflow for drag/use/back
        success = use_item_subflow(adb, win, debug=debug)
        if not success:
            if debug:
                print("  ERROR: use_item_subflow failed")
            break

        chest_count += 1
        if debug:
            print(f"  Chest #{chest_count} processed!")

    if debug:
        print(f"\nCompleted! Processed {chest_count} chest(s)")

    return chest_count


if __name__ == "__main__":
    import argparse
    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    parser = argparse.ArgumentParser(description="Bag Special Flow - Claim chests from Special tab")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--no-open-bag", action="store_true", help="Don't click bag button (assume already open)")
    args = parser.parse_args()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    count = bag_special_flow(adb, win, debug=args.debug, open_bag=not args.no_open_bag)
    print(f"\nClaimed {count} chest(s)")
