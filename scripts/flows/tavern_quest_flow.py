"""
Tavern Quest Flow - Claim completed quests from My Quests tab.

Entry: Assumes Tavern is already open.
Exit: Back to base view.

Tab Detection:
- tavern_my_quests_active_4k.png → My Quests is active
- tavern_ally_quests_active_4k.png → Ally Quests is active

My Quests:
- Column-restricted Claim button detection (X: 2100-2500, full Y)
- Click each Claim button found
- Scroll and repeat until no more Claim buttons
"""
from __future__ import annotations

import sys
from pathlib import Path

_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import cv2
import numpy as np
import time
import logging

from utils.adb_helper import ADBHelper
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.return_to_base_view import return_to_base_view

logger = logging.getLogger(__name__)

# Template paths
TEMPLATE_DIR = "templates/ground_truth"
MY_QUESTS_ACTIVE_TEMPLATE = f"{TEMPLATE_DIR}/tavern_my_quests_active_4k.png"
ALLY_QUESTS_ACTIVE_TEMPLATE = f"{TEMPLATE_DIR}/tavern_ally_quests_active_4k.png"
CLAIM_BUTTON_TEMPLATE = f"{TEMPLATE_DIR}/claim_button_4k.png"

# Tab regions and click positions (4K)
MY_QUESTS_TAB_REGION = (1505, 723, 299, 65)  # x, y, w, h
ALLY_QUESTS_TAB_REGION = (2054, 723, 299, 65)
MY_QUESTS_CLICK = (1654, 755)
ALLY_QUESTS_CLICK = (2203, 755)

# Claim button detection - column restricted
CLAIM_X_START = 2100
CLAIM_X_END = 2500
CLAIM_THRESHOLD = 0.02  # Strict threshold to avoid false positives

# Scroll parameters
SCROLL_START_Y = 1800  # Bottom of quest list
SCROLL_END_Y = 1000    # Top of quest list
SCROLL_X = 1920        # Center X
SCROLL_DURATION = 300  # ms


def load_template_gray(path: str) -> np.ndarray:
    """Load template as grayscale."""
    template = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if template is None:
        raise FileNotFoundError(f"Template not found: {path}")
    return template


def check_tab_active(frame_gray: np.ndarray, template: np.ndarray, region: tuple) -> tuple[bool, float]:
    """Check if a tab is active by matching template in region."""
    x, y, w, h = region
    roi = frame_gray[y:y+h, x:x+w]

    # Resize template if needed
    if roi.shape != template.shape:
        template_resized = cv2.resize(template, (roi.shape[1], roi.shape[0]))
    else:
        template_resized = template

    result = cv2.matchTemplate(roi, template_resized, cv2.TM_SQDIFF_NORMED)
    score = result[0, 0]

    return score < 0.02, score  # Active if score < 0.02


def find_claim_buttons(frame_gray: np.ndarray, template: np.ndarray) -> list[tuple[int, int]]:
    """
    Find all Claim buttons by scanning column (X: 2100-2500, full Y).
    Returns list of (x, y) click positions.
    """
    # Extract column ROI
    column_roi = frame_gray[:, CLAIM_X_START:CLAIM_X_END]

    result = cv2.matchTemplate(column_roi, template, cv2.TM_SQDIFF_NORMED)

    # Find all matches below threshold
    locations = np.where(result < CLAIM_THRESHOLD)

    if len(locations[0]) == 0:
        return []

    # Get template dimensions for click center calculation
    th, tw = template.shape[:2]

    # Collect all match positions with scores
    matches = []
    for y, x in zip(locations[0], locations[1]):
        score = result[y, x]
        # Convert back to full frame coordinates
        full_x = CLAIM_X_START + x + tw // 2
        full_y = y + th // 2
        matches.append((full_x, full_y, score))

    # Sort by Y position
    matches.sort(key=lambda m: m[1])

    # Non-maximum suppression - keep distinct Y positions (min spacing 100px)
    filtered = []
    min_spacing = 100

    for full_x, full_y, score in matches:
        # Check if this Y is far enough from all kept positions
        is_distinct = True
        for _, kept_y in filtered:
            if abs(full_y - kept_y) < min_spacing:
                is_distinct = False
                break

        if is_distinct:
            filtered.append((full_x, full_y))

    return filtered


def is_in_tavern(frame_gray: np.ndarray) -> tuple[bool, str]:
    """
    Verify we're in Tavern by checking if either tab template matches.
    Returns (is_in_tavern, active_tab) where active_tab is 'my_quests', 'ally_quests', or None.
    """
    my_quests_active_template = load_template_gray(MY_QUESTS_ACTIVE_TEMPLATE)
    ally_quests_active_template = load_template_gray(ALLY_QUESTS_ACTIVE_TEMPLATE)
    my_quests_inactive_template = load_template_gray(f"{TEMPLATE_DIR}/tavern_my_quests_4k.png")
    ally_quests_inactive_template = load_template_gray(f"{TEMPLATE_DIR}/tavern_ally_quests_4k.png")

    # Check My Quests region for either active or inactive template
    my_active, my_active_score = check_tab_active(frame_gray, my_quests_active_template, MY_QUESTS_TAB_REGION)
    my_inactive, my_inactive_score = check_tab_active(frame_gray, my_quests_inactive_template, MY_QUESTS_TAB_REGION)

    # Check Ally Quests region for either active or inactive template
    ally_active, ally_active_score = check_tab_active(frame_gray, ally_quests_active_template, ALLY_QUESTS_TAB_REGION)
    ally_inactive, ally_inactive_score = check_tab_active(frame_gray, ally_quests_inactive_template, ALLY_QUESTS_TAB_REGION)

    logger.debug(f"Tab scores - My active:{my_active_score:.4f} inactive:{my_inactive_score:.4f}, "
                 f"Ally active:{ally_active_score:.4f} inactive:{ally_inactive_score:.4f}")

    # Must have at least one tab matching (active or inactive) in each position
    my_quests_visible = my_active or my_inactive
    ally_quests_visible = ally_active or ally_inactive

    if not (my_quests_visible and ally_quests_visible):
        return False, None

    # Determine which tab is active
    if my_active:
        return True, "my_quests"
    elif ally_active:
        return True, "ally_quests"
    else:
        # Both inactive? Shouldn't happen but default to my_quests
        return True, "my_quests"


def run_my_quests_flow(adb: ADBHelper, win: WindowsScreenshotHelper, debug: bool = False) -> int:
    """
    Claim all completed quests from My Quests tab.
    Returns number of claims made.
    """
    logger.info("Starting My Quests claim flow")

    # Load templates
    my_quests_active_template = load_template_gray(MY_QUESTS_ACTIVE_TEMPLATE)
    claim_template = load_template_gray(CLAIM_BUTTON_TEMPLATE)

    total_claims = 0
    no_claims_count = 0
    max_no_claims = 2  # Stop after 2 consecutive scrolls with no claims

    while no_claims_count < max_no_claims:
        # Take screenshot
        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # FIRST: Verify we're in Tavern
        in_tavern, active_tab = is_in_tavern(frame_gray)
        if not in_tavern:
            logger.warning("Not in Tavern! Aborting My Quests flow.")
            return total_claims

        # Check if My Quests tab is active
        if active_tab != "my_quests":
            logger.info(f"My Quests tab not active (active={active_tab}), clicking to switch")
            adb.tap(*MY_QUESTS_CLICK)
            time.sleep(0.5)
            continue

        # Find Claim buttons
        claim_buttons = find_claim_buttons(frame_gray, claim_template)

        if debug:
            logger.debug(f"Found {len(claim_buttons)} Claim buttons")

        if not claim_buttons:
            logger.info("No Claim buttons found, scrolling...")
            no_claims_count += 1

            # Scroll down
            adb.swipe(SCROLL_X, SCROLL_START_Y, SCROLL_X, SCROLL_END_Y, SCROLL_DURATION)
            time.sleep(0.5)
            continue

        # Reset no_claims counter since we found buttons
        no_claims_count = 0

        # Click FIRST Claim button only (congratulations popup appears after each)
        x, y = claim_buttons[0]
        logger.info(f"Clicking Claim at ({x}, {y})")
        adb.tap(x, y)
        time.sleep(0.5)  # Wait for congratulations popup
        total_claims += 1

        # Click back button to dismiss congratulations popup
        logger.info("Clicking back button to dismiss popup")
        adb.tap(1407, 2055)  # Back button position
        time.sleep(1.0)  # Wait longer for popup to fully dismiss

    logger.info(f"My Quests flow complete. Total claims: {total_claims}")
    return total_claims


def run_tavern_quest_flow(adb: ADBHelper = None, win: WindowsScreenshotHelper = None, debug: bool = False) -> dict:
    """
    Main tavern quest flow.
    Assumes Tavern is already open.

    Returns dict with claim counts.
    """
    if adb is None:
        adb = ADBHelper()
    if win is None:
        win = WindowsScreenshotHelper()

    results = {
        "my_quests_claims": 0,
        "ally_quests_claims": 0,
    }

    # Run My Quests flow
    results["my_quests_claims"] = run_my_quests_flow(adb, win, debug)

    # Ally Quests flow - TBD by user
    # More complex logic, not just clicking all Assist buttons
    logger.info("Ally Quests flow not implemented yet (TBD)")

    # Return to base view
    logger.info("Returning to base view")
    return_to_base_view(adb, win, debug=debug)

    return results


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    parser = argparse.ArgumentParser(description="Tavern Quest Flow")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--my-quests-only", action="store_true", help="Only run My Quests flow")
    args = parser.parse_args()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    if args.my_quests_only:
        claims = run_my_quests_flow(adb, win, debug=args.debug)
        print(f"My Quests claims: {claims}")
    else:
        results = run_tavern_quest_flow(adb, win, debug=args.debug)
        print(f"Results: {results}")
