"""
Reinforce Camp Flow - Navigate to a marked camp location and reinforce it.

Flow (similar to go_to_mark but clicks second-from-top Go button):
1. Click search button -> verify search panel opened (Mark tab visible)
2. Click Mark tab at FIXED position -> verify Mark tab is active
3. Click Special sub-tab -> verify Go buttons visible
4. Find ALL Go buttons, click the SECOND from top

Usage:
    python scripts/flows/reinforce_camp_flow.py
    python scripts/flows/reinforce_camp_flow.py --debug
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np
import numpy.typing as npt

from utils.view_state_detector import go_to_world
from utils.return_to_base_view import return_to_base_view
from utils.template_matcher import match_template, has_mask

from utils.windows_screenshot_helper import WindowsScreenshotHelper

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

# Type alias for numpy arrays
NDArray = npt.NDArray[Any]

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "ground_truth"

# Thresholds - all SQDIFF (lower=better)
SQDIFF_THRESHOLD = 0.1   # For non-masked templates
MASKED_THRESHOLD = 0.05  # For masked templates (stricter)
POLL_TIMEOUT = 3.0
POLL_INTERVAL = 0.3

# Fixed position for Mark tab (rightmost tab in search panel)
MARK_TAB_POS: tuple[int, int] = (2206, 1047)
MARK_TAB_SIZE: tuple[int, int] = (265, 99)
MARK_TAB_CLICK: tuple[int, int] = (2338, 1096)
MARK_TAB_REGION: tuple[int, int, int, int] = (
    MARK_TAB_POS[0], MARK_TAB_POS[1], MARK_TAB_SIZE[0], MARK_TAB_SIZE[1]
)


def _get_threshold(template_name: str) -> float:
    """Get appropriate threshold based on whether template has a mask."""
    return MASKED_THRESHOLD if has_mask(template_name) else SQDIFF_THRESHOLD


def _poll_for_template(
    win: WindowsScreenshotHelper,
    template_name: str,
    timeout: float = POLL_TIMEOUT,
    threshold: float | None = None,
    debug: bool = False
) -> tuple[bool, float, tuple[int, int] | None, NDArray | None]:
    """Poll until template matches or timeout. Returns (found, score, pos, frame)."""
    if threshold is None:
        threshold = _get_threshold(template_name)

    start = time.time()
    last_score = 1.0
    frame: NDArray | None = None
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
    return False, last_score, None, frame


def _poll_for_mark_tab_fixed(
    win: WindowsScreenshotHelper,
    timeout: float = POLL_TIMEOUT,
    debug: bool = False
) -> tuple[bool, bool, float, NDArray | None]:
    """Poll for Mark tab at FIXED position. Returns (found, is_active, score, frame)."""
    start = time.time()
    frame: NDArray | None = None
    while time.time() - start < timeout:
        frame = win.get_screenshot_cv2()

        # Check inactive first
        found, score, _ = match_template(
            frame, "search_mark_tab_inactive_4k.png",
            search_region=MARK_TAB_REGION, threshold=SQDIFF_THRESHOLD
        )
        if found:
            if debug:
                print(f"    Mark tab INACTIVE at fixed pos: score={score:.4f}")
            return True, False, score, frame

        # Check active
        found, score, _ = match_template(
            frame, "search_mark_tab_active_4k.png",
            search_region=MARK_TAB_REGION, threshold=SQDIFF_THRESHOLD
        )
        if found:
            if debug:
                print(f"    Mark tab ACTIVE at fixed pos: score={score:.4f}")
            return True, True, score, frame

        time.sleep(POLL_INTERVAL)

    if debug:
        print("    Timeout waiting for Mark tab at fixed position")
    return False, False, 1.0, frame


def find_all_go_buttons(
    frame: NDArray,
    debug: bool = False
) -> list[tuple[int, int, float]]:
    """
    Find ALL Go button positions in the frame.

    Returns:
        List of (x, y, score) tuples sorted by Y (top to bottom)
    """
    template_path = TEMPLATE_DIR / "go_button_4k.png"
    template = cv2.imread(str(template_path))
    if template is None:
        if debug:
            print("    ERROR: Could not load go_button_4k.png")
        return []

    # Template match
    result = cv2.matchTemplate(frame, template, cv2.TM_SQDIFF_NORMED)
    h, w = template.shape[:2]

    # Find all matches below threshold
    threshold = 0.1
    locations = np.where(result < threshold)

    # Convert to list of (x, y, score)
    matches: list[tuple[int, int, float]] = []
    for y, x in zip(*locations):
        score = float(result[y, x])
        center_x = x + w // 2
        center_y = y + h // 2
        matches.append((center_x, center_y, score))

    if not matches:
        if debug:
            print("    No Go buttons found")
        return []

    # Deduplicate - keep best score within 50px
    deduplicated: list[tuple[int, int, float]] = []
    for x, y, score in matches:
        is_dup = False
        for i, (dx, dy, ds) in enumerate(deduplicated):
            if abs(x - dx) < 50 and abs(y - dy) < 50:
                if score < ds:
                    deduplicated[i] = (x, y, score)
                is_dup = True
                break
        if not is_dup:
            deduplicated.append((x, y, score))

    # Sort by Y (top to bottom)
    deduplicated.sort(key=lambda m: m[1])

    if debug:
        print(f"    Found {len(deduplicated)} Go buttons:")
        for i, (x, y, score) in enumerate(deduplicated):
            print(f"      {i+1}. ({x}, {y}) score={score:.4f}")

    return deduplicated


def reinforce_camp_flow(
    adb: ADBHelper,
    screenshot_helper: WindowsScreenshotHelper | None = None,
    debug: bool = False
) -> bool:
    """
    Navigate to marked camp (second Go button) and prepare to reinforce.

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
        # Step 0: Go to WORLD view first
        if debug:
            print("  Step 0: Going to WORLD view...")
        go_to_world(adb)
        time.sleep(0.5)

        # Step 1: Find and click search button
        if debug:
            print("  Step 1: Finding search button...")
        frame = win.get_screenshot_cv2()

        # Try all search button variants
        found = False
        pos = None
        for template_name in ["search_button_4k.png", "search_button_4k_v2.png", "search_button_ice_4k.png"]:
            found, score, pos = match_template(frame, template_name, threshold=_get_threshold(template_name))
            if debug:
                print(f"    {template_name}: found={found}, score={score:.4f}")
            if found:
                break

        if not found or pos is None:
            print("  ERROR: Search button not found")
            return False

        if debug:
            print(f"    Clicking search button at {pos}")
        adb.tap(pos[0], pos[1], source="flow:reinforce_camp:search_button")
        time.sleep(0.5)

        # Verify: Poll for Mark tab at FIXED position
        if debug:
            print("    Verifying search panel opened...")
        found, is_active, score, _ = _poll_for_mark_tab_fixed(win, debug=debug)
        if not found:
            print("  ERROR: Search panel did not open")
            return False

        # Step 2: Click Mark tab at FIXED position (if not already active)
        if is_active:
            if debug:
                print(f"  Step 2: Mark tab already active, skipping click")
        else:
            if debug:
                print(f"  Step 2: Clicking Mark tab at FIXED position {MARK_TAB_CLICK}")
            adb.tap(MARK_TAB_CLICK[0], MARK_TAB_CLICK[1], source="flow:reinforce_camp:mark_tab")
            time.sleep(0.5)

            # Verify Mark tab active
            found, is_active, score, _ = _poll_for_mark_tab_fixed(win, debug=debug)
            if not found or not is_active:
                print("  ERROR: Mark tab did not become active")
                return False

        # Step 3: Find and click Special sub-tab
        if debug:
            print("  Step 3: Finding Special sub-tab...")
        frame = win.get_screenshot_cv2()
        found, score, special_pos = match_template(
            frame, "search_special_tab_active_4k.png",
            threshold=_get_threshold("search_special_tab_active_4k.png")
        )
        if debug:
            print(f"    Special tab: found={found}, score={score:.4f}, pos={special_pos}")

        if not found or special_pos is None:
            print("  ERROR: Special sub-tab not found")
            return False

        if debug:
            print(f"    Clicking Special tab at {special_pos}")
        adb.tap(special_pos[0], special_pos[1], source="flow:reinforce_camp:special_tab")
        time.sleep(0.5)

        # Step 4: Find ALL Go buttons, click SECOND from bottom
        if debug:
            print("  Step 4: Finding all Go buttons...")

        # Wait for buttons to appear
        time.sleep(0.3)
        frame = win.get_screenshot_cv2()

        # Save debug screenshot
        if debug:
            cv2.imwrite("screenshots/debug/reinforce_camp_go_buttons.png", frame)
            print("    Saved debug screenshot")

        go_buttons = find_all_go_buttons(frame, debug=debug)

        if len(go_buttons) < 2:
            print(f"  ERROR: Need at least 2 Go buttons, found {len(go_buttons)}")
            return False

        # Get second from TOP (index 1)
        target_x, target_y, target_score = go_buttons[1]

        if debug:
            print(f"    Clicking SECOND from top Go button at ({target_x}, {target_y})")
        adb.tap(target_x, target_y, source="flow:reinforce_camp:go_button")
        time.sleep(2.0)  # Wait for navigation

        if debug:
            print("  Reinforce camp navigation complete!")
        return True

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

    parser = argparse.ArgumentParser(description="Navigate to marked camp and reinforce")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    print("=== Reinforce Camp Flow ===")
    print()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    result = reinforce_camp_flow(adb, win, debug=args.debug)
    print(f"\nResult: {'SUCCESS' if result else 'FAILED'}")
