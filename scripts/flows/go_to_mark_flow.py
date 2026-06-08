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
from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy.typing as npt

from utils.view_state_detector import go_to_world
from utils.return_to_base_view import return_to_base_view
from utils.template_matcher import match_template, has_mask

from utils.windows_screenshot_helper import WindowsScreenshotHelper

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

# Type alias for numpy arrays
NDArray = npt.NDArray[Any]

# Thresholds - all SQDIFF (lower=better)
SQDIFF_THRESHOLD = 0.1   # For non-masked templates
MASKED_THRESHOLD = 0.05  # For masked templates (stricter)
POLL_TIMEOUT = 4.5
POLL_INTERVAL = 0.3
ARRIVAL_TIMEOUT = 8.0

# Fixed position for Mark tab (rightmost tab in search panel)
MARK_TAB_POS: tuple[int, int] = (2206, 1047)      # Top-left of Mark tab region
MARK_TAB_SIZE: tuple[int, int] = (265, 99)        # Size of tab template
MARK_TAB_CLICK: tuple[int, int] = (2338, 1096)    # Center click position
# Combined search region for template matching (x, y, w, h)
MARK_TAB_REGION: tuple[int, int, int, int] = (
    MARK_TAB_POS[0], MARK_TAB_POS[1], MARK_TAB_SIZE[0], MARK_TAB_SIZE[1]
)
# Go button should be matched only inside search panel to avoid false positives
# on the bottom-right world/town toggle.
GO_BUTTON_SEARCH_REGION: tuple[int, int, int, int] = (2000, 800, 900, 900)
SEARCH_BUTTON_SEARCH_REGION: tuple[int, int, int, int] = (0, 1400, 260, 420)
ARRIVAL_STAR_SEARCH_REGION: tuple[int, int, int, int] = (1400, 600, 1100, 1000)
SEARCH_BUTTON_V2_THRESHOLD = 0.02
SEARCH_BUTTON_FALLBACK_CLICK: tuple[int, int] = (78, 1498)
ARRIVAL_STAR_THRESHOLD = 0.06
ARRIVAL_STAR_SINGLE_THRESHOLD = 0.10


def _get_threshold(template_name: str) -> float:
    """Get appropriate threshold based on whether template has a mask."""
    return MASKED_THRESHOLD if has_mask(template_name) else SQDIFF_THRESHOLD


def _poll_for_template(
    win: WindowsScreenshotHelper,
    template_name: str,
    search_region: tuple[int, int, int, int] | None = None,
    timeout: float = POLL_TIMEOUT,
    threshold: float | None = None,
    debug: bool = False
) -> tuple[bool, float, tuple[int, int] | None, NDArray | None]:
    """Poll until template matches or timeout. Returns (found, score, pos, frame)."""
    # Use appropriate threshold for masked vs non-masked templates
    if threshold is None:
        threshold = _get_threshold(template_name)

    start = time.time()
    last_score = 1.0
    frame: NDArray | None = None
    while time.time() - start < timeout:
        frame = win.get_screenshot_cv2()
        found, score, pos = match_template(
            frame,
            template_name,
            search_region=search_region,
            threshold=threshold
        )
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


def _poll_for_arrival_star(
    win: WindowsScreenshotHelper,
    timeout: float = ARRIVAL_TIMEOUT,
    debug: bool = False
) -> tuple[bool, str | None, float, tuple[int, int] | None]:
    """Poll for marked-city star icon to confirm Go navigation completed."""
    start = time.time()
    best_score = 1.0
    best_template: str | None = None
    best_pos: tuple[int, int] | None = None

    while time.time() - start < timeout:
        frame = win.get_screenshot_cv2()

        found, score, pos = match_template(
            frame,
            "mark_star_icon_4k.png",
            search_region=ARRIVAL_STAR_SEARCH_REGION,
            threshold=ARRIVAL_STAR_THRESHOLD,
        )
        if score < best_score:
            best_score = score
            best_template = "mark_star_icon_4k.png"
            best_pos = pos
        if found:
            if debug:
                print(f"    Arrival verified via mark_star_icon_4k.png: score={score:.4f}, pos={pos}")
            return True, "mark_star_icon_4k.png", score, pos

        found, score, pos = match_template(
            frame,
            "star_single_4k.png",
            search_region=ARRIVAL_STAR_SEARCH_REGION,
            threshold=ARRIVAL_STAR_SINGLE_THRESHOLD,
        )
        if score < best_score:
            best_score = score
            best_template = "star_single_4k.png"
            best_pos = pos
        if found:
            if debug:
                print(f"    Arrival verified via star_single_4k.png: score={score:.4f}, pos={pos}")
            return True, "star_single_4k.png", score, pos

        time.sleep(POLL_INTERVAL)

    if debug:
        print(
            "    Arrival star not detected within timeout: "
            f"best_template={best_template}, best_score={best_score:.4f}, best_pos={best_pos}"
        )
    return False, best_template, best_score, best_pos


def go_to_mark_flow(
    adb: ADBHelper,
    screenshot_helper: WindowsScreenshotHelper | None = None,
    debug: bool = False
) -> bool:
    """
    Navigate to first marked Special location.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance
        debug: Enable debug logging

    Returns:
        True if successful, False otherwise
    """
    # Import here to avoid circular imports at module level
    from utils.windows_screenshot_helper import WindowsScreenshotHelper as WSH
    win = screenshot_helper or WSH()

    try:
        # Step 0: Go to WORLD view first
        if debug:
            print("  Step 0: Going to WORLD view...")
        if not go_to_world(adb):
            print("  ERROR: Failed to reach WORLD view before go_to_mark")
            return False
        time.sleep(0.5)

        # Step 1: Find and click search button (try both template variants)
        if debug:
            print("  Step 1: Finding search button...")
        # If search panel is already open, don't toggle it closed.
        found, is_active, score, _ = _poll_for_mark_tab_fixed(win, timeout=0.8, debug=False)
        if found:
            search_opened = True
            if debug:
                state = "active" if is_active else "inactive"
                print(f"    Search panel already open (Mark tab {state}, score={score:.4f})")
        else:
            search_opened = False

        frame = win.get_screenshot_cv2()
        search_candidates: list[tuple[float, tuple[int, int], str]] = []
        candidate_specs = [
            ("search_button_4k.png", 0.20, "v1"),
            ("search_button_4k_v2.png", 0.20, "v2"),
            ("search_button_ice_4k.png", 0.20, "ice"),
        ]
        for template_name, probe_threshold, label in candidate_specs:
            found, score, pos = match_template(
                frame,
                template_name,
                search_region=SEARCH_BUTTON_SEARCH_REGION,
                threshold=probe_threshold,
            )
            if debug:
                print(f"    Search button ({label}): found={found}, score={score:.4f}, pos={pos}")
            if pos is not None:
                search_candidates.append((score, pos, label))

        # Prefer lower-score detections, then fixed known coordinates.
        search_candidates.sort(key=lambda item: item[0])
        search_clicks: list[tuple[tuple[int, int], str]] = []
        seen: set[tuple[int, int]] = set()
        for score, pos, label in search_candidates:
            if score > 0.12 or pos in seen:
                continue
            seen.add(pos)
            search_clicks.append((pos, f"template_{label}_{score:.4f}"))
        for fallback in (SEARCH_BUTTON_FALLBACK_CLICK, (125, 1576)):
            if fallback not in seen:
                search_clicks.append((fallback, "fallback"))

        if not search_opened:
            is_active = False
            for click_pos, reason in search_clicks:
                if debug:
                    print(f"    Clicking search button candidate {click_pos} ({reason})")
                    print("    Verifying search panel opened (Mark tab detection in panel region)...")
                adb.tap(click_pos[0], click_pos[1], source="flow:go_to_mark:search_button")
                time.sleep(0.5)
                found, is_active, score, _ = _poll_for_mark_tab_fixed(win, debug=debug)
                if found:
                    search_opened = True
                    break
        else:
            # Refresh active/inactive state for Step 2 behavior.
            found, is_active, score, _ = _poll_for_mark_tab_fixed(win, timeout=1.2, debug=debug)
            if not found:
                search_opened = False

        if not search_opened:
            print("  ERROR: Search panel did not open (Mark tab not found in panel region)")
            return False

        # Step 2: Click Mark tab at FIXED position (if not already active)
        if is_active:
            if debug:
                print(f"  Step 2: Mark tab already active, skipping click")
        else:
            if debug:
                print(f"  Step 2: Clicking Mark tab at {MARK_TAB_CLICK}")
            adb.tap(MARK_TAB_CLICK[0], MARK_TAB_CLICK[1], source="flow:go_to_mark:mark_tab")
            time.sleep(0.5)

            # Verify: Poll for Mark tab to become active at fixed position
            if debug:
                print("    Verifying Mark tab is active...")
            found, is_active, score, _ = _poll_for_mark_tab_fixed(win, debug=debug)
            if not found or not is_active:
                print("  ERROR: Mark tab did not become active")
                return False

        # Step 3: Find and click Special sub-tab
        if debug:
            print("  Step 3: Finding Special sub-tab...")
        # Special tab should now be visible
        # Take fresh screenshot since frame from poll could be stale or None
        frame = win.get_screenshot_cv2()
        found, score, special_pos = match_template(frame, "search_special_tab_active_4k.png", threshold=_get_threshold("search_special_tab_active_4k.png"))
        if debug:
            print(f"    Special tab: found={found}, score={score:.4f}, pos={special_pos}")

        if not found or special_pos is None:
            print("  ERROR: Special sub-tab not found")
            return False

        if debug:
            print(f"    Clicking Special tab at {special_pos}")
        adb.tap(special_pos[0], special_pos[1], source="flow:go_to_mark:special_tab")
        time.sleep(0.5)

        # Step 4: Find and click Go button
        if debug:
            print("  Step 4: Finding Go button...")
        found, score, go_pos, _ = _poll_for_template(
            win, "go_button_4k.png", search_region=GO_BUTTON_SEARCH_REGION, debug=debug
        )
        if not found or go_pos is None:
            print("  ERROR: Go button not found (no marked Special location?)")
            return False

        if debug:
            print(f"    Clicking Go button at {go_pos}")
        adb.tap(go_pos[0], go_pos[1], source="flow:go_to_mark:go_button")
        time.sleep(1.0)

        # Verify destination arrival before returning success.
        if debug:
            print("    Verifying arrival at marked location (star icon)...")
        arrived, template_name, star_score, star_pos = _poll_for_arrival_star(win, debug=debug)
        if not arrived:
            print(
                "  ERROR: Go completed but marked-location arrival not verified "
                f"(best={template_name}, score={star_score:.4f}, pos={star_pos})"
            )
            return False

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
