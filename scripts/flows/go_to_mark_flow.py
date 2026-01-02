"""
Go to Marked Location Flow - Navigate to first marked Special location.

Flow (with verification at each step):
1. Match search button -> click -> verify search panel opened (Mark tab visible)
2. Click Mark tab at FIXED position -> verify Mark tab is active
3. Match Special sub-tab -> click -> verify Go button visible
4. Match Go button -> click

Templates:
- search_button_4k.png (with mask) - magnifying glass on left sidebar
- search_mark_tab_active_4k.png / search_mark_tab_inactive_4k.png
- search_special_tab_active_4k.png
- go_button_4k.png
"""

import time
from pathlib import Path

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.view_state_detector import go_to_world
from utils.return_to_base_view import return_to_base_view
from utils.template_matcher import match_template, match_template_fixed, has_mask

# Thresholds - different for masked vs non-masked templates
SQDIFF_THRESHOLD = 0.1   # For non-masked templates (lower=better)
CCORR_THRESHOLD = 0.95   # For masked templates (higher=better)
POLL_TIMEOUT = 3.0
POLL_INTERVAL = 0.3

# Fixed position for Mark tab (rightmost tab in search panel)
MARK_TAB_POS = (2206, 1047)      # Top-left of Mark tab region
MARK_TAB_SIZE = (265, 99)        # Size of tab template
MARK_TAB_CLICK = (2338, 1096)    # Center click position


def _get_threshold(template_name: str) -> float:
    """Get appropriate threshold based on whether template has a mask."""
    return CCORR_THRESHOLD if has_mask(template_name) else SQDIFF_THRESHOLD


def _poll_for_template(win, template_name, timeout=POLL_TIMEOUT, threshold=None, debug=False):
    """Poll until template matches or timeout. Returns (found, score, pos, frame)."""
    # Use appropriate threshold for masked vs non-masked templates
    if threshold is None:
        threshold = _get_threshold(template_name)

    start = time.time()
    last_score = 1.0
    while time.time() - start < timeout:
        frame = win.get_screenshot_cv2()
        found, score, pos = match_template(frame, template_name, threshold=threshold)
        last_score = score
        if found:
            if debug:
                print(f"    Found {template_name}: score={score:.4f}, pos={pos}")
            return True, score, pos, frame
        time.sleep(POLL_INTERVAL)
    if debug:
        print(f"    Timeout waiting for {template_name}: last_score={last_score:.4f}")
    return False, last_score, None, None


def _poll_for_mark_tab_fixed(win, timeout=POLL_TIMEOUT, debug=False):
    """Poll for Mark tab at FIXED position. Returns (found, is_active, score, frame)."""
    start = time.time()
    while time.time() - start < timeout:
        frame = win.get_screenshot_cv2()

        # Check inactive first
        found, score, _ = match_template_fixed(
            frame, "search_mark_tab_inactive_4k.png",
            MARK_TAB_POS, MARK_TAB_SIZE, threshold=SQDIFF_THRESHOLD
        )
        if found:
            if debug:
                print(f"    Mark tab INACTIVE at fixed pos: score={score:.4f}")
            return True, False, score, frame

        # Check active
        found, score, _ = match_template_fixed(
            frame, "search_mark_tab_active_4k.png",
            MARK_TAB_POS, MARK_TAB_SIZE, threshold=SQDIFF_THRESHOLD
        )
        if found:
            if debug:
                print(f"    Mark tab ACTIVE at fixed pos: score={score:.4f}")
            return True, True, score, frame

        time.sleep(POLL_INTERVAL)

    if debug:
        print(f"    Timeout waiting for Mark tab at fixed position")
    return False, False, 1.0, None


def go_to_mark_flow(adb, screenshot_helper=None, debug=False):
    """
    Navigate to first marked Special location.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance
        debug: Enable debug logging

    Returns:
        True if successful, False otherwise
    """
    win = screenshot_helper or WindowsScreenshotHelper()

    try:
        # Step 0: Go to WORLD view first
        if debug:
            print("  Step 0: Going to WORLD view...")
        go_to_world(adb)
        time.sleep(0.5)

        # Step 1: Find and click search button
        if debug:
            print("  Step 1: Finding search button...")
        frame = win.get_screenshot_cv2()
        found, score, pos = match_template(frame, "search_button_4k.png", threshold=_get_threshold("search_button_4k.png"))
        if debug:
            print(f"    Search button: found={found}, score={score:.4f}, pos={pos}")

        if not found:
            print("  ERROR: Search button not found")
            return False

        if debug:
            print(f"    Clicking search button at {pos}")
        adb.tap(*pos)
        time.sleep(0.5)

        # Verify: Poll for Mark tab at FIXED position (proves search panel opened)
        if debug:
            print("    Verifying search panel opened (looking for Mark tab at fixed position)...")
        found, is_active, score, frame = _poll_for_mark_tab_fixed(win, debug=debug)
        if not found:
            print("  ERROR: Search panel did not open (Mark tab not found at fixed position)")
            return False

        # Step 2: Click Mark tab at FIXED position (if not already active)
        if is_active:
            if debug:
                print(f"  Step 2: Mark tab already active, skipping click")
        else:
            if debug:
                print(f"  Step 2: Clicking Mark tab at FIXED position {MARK_TAB_CLICK}")
            adb.tap(*MARK_TAB_CLICK)
            time.sleep(0.5)

            # Verify: Poll for Mark tab to become active at fixed position
            if debug:
                print("    Verifying Mark tab is active...")
            found, is_active, score, frame = _poll_for_mark_tab_fixed(win, debug=debug)
            if not found or not is_active:
                print("  ERROR: Mark tab did not become active")
                return False

        # Step 3: Find and click Special sub-tab
        if debug:
            print("  Step 3: Finding Special sub-tab...")
        # Special tab should now be visible
        found, score, special_pos = match_template(frame, "search_special_tab_active_4k.png", threshold=_get_threshold("search_special_tab_active_4k.png"))
        if debug:
            print(f"    Special tab: found={found}, score={score:.4f}, pos={special_pos}")

        if not found:
            print("  ERROR: Special sub-tab not found")
            return False

        if debug:
            print(f"    Clicking Special tab at {special_pos}")
        adb.tap(*special_pos)
        time.sleep(0.5)

        # Step 4: Find and click Go button
        if debug:
            print("  Step 4: Finding Go button...")
        found, score, go_pos, frame = _poll_for_template(
            win, "go_button_4k.png", debug=debug
        )
        if not found:
            print("  ERROR: Go button not found (no marked Special location?)")
            return False

        if debug:
            print(f"    Clicking Go button at {go_pos}")
        adb.tap(*go_pos)
        time.sleep(2.0)  # Wait for navigation

        if debug:
            print("  Go to mark complete!")
        return True

    except Exception as e:
        print(f"  ERROR: {e}")
        return_to_base_view(adb, win, debug=debug)
        return False


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from utils.adb_helper import ADBHelper

    print("=== Go to Mark Flow Test ===")
    print()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    result = go_to_mark_flow(adb, win, debug=True)
    print(f"\nResult: {'SUCCESS' if result else 'FAILED'}")
