"""
Faction Trials Flow - Manual flow for faction trials battles.

This is a manually triggered flow (not daemon-automated).
Navigate to the Faction Trials screen first, then run this script.

Sequence (repeated up to 20 times):
1. Verify Challenge button present, click it
2. Verify Deploy button present, click it
3. Verify camcorder icon (battle screen), click back button
4. Repeat until no buttons found or 20 iterations
5. Return to base view

Run manually:
    python scripts/flows/faction_trials_flow.py
"""
import sys
import time
from pathlib import Path

_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import cv2
import numpy as np

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.adb_helper import ADBHelper
from utils.return_to_base_view import return_to_base_view

# Fixed positions (4K resolution)
CHALLENGE_BUTTON_REGION = (1543, 1976, 361, 130)
CHALLENGE_BUTTON_CLICK = (1723, 2041)

DEPLOY_BUTTON_REGION = (1950, 1976, 377, 145)
DEPLOY_BUTTON_CLICK = (2138, 2048)

CAMCORDER_ICON_REGION = (1355, 1853, 115, 119)
BACK_BUTTON_CLICK = (1407, 2055)

# Templates
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "ground_truth"

# Threshold for template matching
THRESHOLD = 0.1


def _load_template(name: str) -> np.ndarray | None:
    """Load template image in grayscale."""
    path = TEMPLATES_DIR / name
    if not path.exists():
        print(f"  ERROR: Template not found: {path}")
        return None
    return cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)


def _check_at_region(frame_gray: np.ndarray, template: np.ndarray,
                     region: tuple, threshold: float = THRESHOLD) -> tuple[bool, float]:
    """Check if template is present at fixed region."""
    x, y, w, h = region
    roi = frame_gray[y:y+h, x:x+w]

    # Handle size mismatch
    th, tw = template.shape
    if roi.shape[0] < th or roi.shape[1] < tw:
        return False, 1.0

    result = cv2.matchTemplate(roi, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, _, _ = cv2.minMaxLoc(result)
    return min_val <= threshold, min_val


def faction_trials_flow(adb=None, win=None, max_iterations: int = 20, debug: bool = True) -> int:
    """
    Execute faction trials flow.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        max_iterations: Maximum number of battles (default 20)
        debug: Enable debug output

    Returns:
        Number of battles completed
    """
    if adb is None:
        adb = ADBHelper()
    if win is None:
        win = WindowsScreenshotHelper()

    # Load templates
    challenge_template = _load_template("challenge_button_4k.png")
    deploy_template = _load_template("deploy_button_4k.png")
    camcorder_template = _load_template("camcorder_icon_4k.png")

    if any(t is None for t in [challenge_template, deploy_template, camcorder_template]):
        print("ERROR: Missing templates")
        return 0

    battles_completed = 0

    for i in range(max_iterations):
        if debug:
            print(f"\n=== Battle {i + 1}/{max_iterations} ===")

        # Step 1: Check for Challenge button
        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        is_present, score = _check_at_region(frame_gray, challenge_template, CHALLENGE_BUTTON_REGION)
        if debug:
            print(f"  Challenge button: {'found' if is_present else 'not found'} (score={score:.4f})")

        if not is_present:
            if debug:
                print("  Challenge button not found, ending flow")
            break

        # Click Challenge
        if debug:
            print(f"  Clicking Challenge at {CHALLENGE_BUTTON_CLICK}")
        adb.tap(*CHALLENGE_BUTTON_CLICK)
        time.sleep(1.5)

        # Step 2: Check for Deploy button
        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        is_present, score = _check_at_region(frame_gray, deploy_template, DEPLOY_BUTTON_REGION)
        if debug:
            print(f"  Deploy button: {'found' if is_present else 'not found'} (score={score:.4f})")

        if not is_present:
            if debug:
                print("  Deploy button not found, ending flow")
            break

        # Click Deploy
        if debug:
            print(f"  Clicking Deploy at {DEPLOY_BUTTON_CLICK}")
        adb.tap(*DEPLOY_BUTTON_CLICK)
        time.sleep(2.0)  # Wait for battle to start

        # Step 3: Check for camcorder icon (battle screen)
        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        is_present, score = _check_at_region(frame_gray, camcorder_template, CAMCORDER_ICON_REGION)
        if debug:
            print(f"  Camcorder icon: {'found' if is_present else 'not found'} (score={score:.4f})")

        if not is_present:
            if debug:
                print("  Camcorder icon not found, ending flow")
            break

        # Click back button to exit battle
        if debug:
            print(f"  Clicking back button at {BACK_BUTTON_CLICK}")
        adb.tap(*BACK_BUTTON_CLICK)
        time.sleep(1.5)

        battles_completed += 1
        if debug:
            print(f"  Battle {battles_completed} completed!")

    # Return to base view
    if debug:
        print(f"\n=== Returning to base view ===")
    return_to_base_view(adb, win, debug=debug)

    if debug:
        print(f"\n=== Faction Trials Flow Complete: {battles_completed} battles ===")

    return battles_completed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Faction Trials Flow - Manual faction trials battles")
    parser.add_argument("--max", type=int, default=20, help="Maximum battles (default 20)")
    parser.add_argument("--quiet", action="store_true", help="Disable debug output")
    args = parser.parse_args()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    count = faction_trials_flow(adb, win, max_iterations=args.max, debug=not args.quiet)
    print(f"\nCompleted {count} battles")
