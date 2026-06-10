"""
Royal City Title Management Flow - Apply kingdom titles.

Pre-condition: At marked Royal City location (star icon visible)

Usage:
    python scripts/flows/title_management_flow.py minister_of_science
    python scripts/flows/title_management_flow.py marshall --no-return

Flow:
1. Click star icon → Poll for Royal City header
2. Click Manage → Poll for Royal City Management header
3. Click Title Assignment → Poll for Kingdom Title header
4. Click desired title → Poll for title detail header
5. Click Apply
6. (Optional) Return to base view
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy.typing as npt

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.adb_helper import ADBHelper
from utils.return_to_base_view import return_to_base_view
# go_to_world no longer needed - go_to_mark_flow handles view switching
from utils.template_matcher import match_template

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "ground_truth"
DATA_DIR = Path(__file__).parent.parent.parent / "data"

# Load title data
with open(DATA_DIR / "kingdom_titles.json") as f:
    TITLE_DATA = json.load(f)

# Fixed click positions (4K)
STAR_ICON_CLICK = (1919, 905)
ROYAL_CITY_CENTER_CLICK = (1919, 1005)
STAR_SEARCH_REGION = (1400, 600, 1100, 1000)
MANAGE_BUTTON_CLICK = (2230, 881)        # Position on OTHER Royal Cities
MANAGE_BUTTON_CLICK_OWN = (2230, 731)    # Position on YOUR Royal City (has Reinforce/Garrison buttons)
TITLE_ASSIGNMENT_CLICK = (1650, 976)
APPLY_BUTTON_CLICK = (1914, 1844)

# Template search regions for validation
# Keep X fixed to panel column; allow Y to vary because panel vertical placement shifts.
ROYAL_CITY_HEADER_SEARCH_POS = (1463, 300)
ROYAL_CITY_HEADER_SEARCH_SIZE = (902, 420)

ROYAL_CITY_MGMT_HEADER_POS = (1336, 0)
ROYAL_CITY_MGMT_HEADER_SIZE = (1163, 112)
MANAGE_BUTTON_SEARCH_REGION = (1750, 650, 750, 600)  # Keep X stable, tolerate vertical shift
MANAGE_BUTTON_THRESHOLD = 0.06  # Slightly relaxed for recent UI antialiasing variance

KINGDOM_TITLE_HEADER_POS = (1332, 0)
KINGDOM_TITLE_HEADER_SIZE = (1167, 110)

TITLE_DETAIL_POS = (1378, 200)
TITLE_DETAIL_SIZE = (1079, 113)

APPLY_BUTTON_POS = (1789, 1792)
APPLY_BUTTON_SIZE = (250, 104)

HOLDING_TITLE_POS = (1550, 1795)
HOLDING_TITLE_SIZE = (750, 60)

SERVING_AS_POS = (1550, 1773)
SERVING_AS_SIZE = (730, 42)

TIME_IN_OFFICE_POS = (1716, 671)
TIME_IN_OFFICE_SIZE = (407, 41)

TITLE_DURATION_SECONDS = 300  # 5 minutes

THRESHOLD = 0.05
from utils.timings import POLL_INTERVAL, POLL_TIMEOUT_MEDIUM as POLL_TIMEOUT
STAR_ICON_THRESHOLD = 0.06
STAR_SINGLE_THRESHOLD = 0.10


def _poll_for_template(
    win: WindowsScreenshotHelper,
    template_path: str | Path,
    pos: tuple[int, int],
    size: tuple[int, int],
    timeout: float = POLL_TIMEOUT,
    debug: bool = False
) -> tuple[bool, npt.NDArray[Any] | None]:
    """Poll until template matches or timeout."""
    # Extract template name from path
    template_name = Path(template_path).name
    # Combine pos (x, y) and size (w, h) into search_region
    search_region = (*pos, *size)

    start = time.time()
    last_score = 1.0
    while time.time() - start < timeout:
        frame = win.get_screenshot_cv2()
        matched, score, _ = match_template(frame, template_name, search_region=search_region, threshold=THRESHOLD)
        last_score = score
        if matched:
            if debug:
                print(f"    Template matched: {score:.4f}")
            return True, frame
        time.sleep(POLL_INTERVAL)
    if debug:
        print(f"    Poll timeout. Last score: {last_score:.4f}")
    return False, None


def check_holding_status(
    frame: npt.NDArray[Any],
    debug: bool = False
) -> tuple[str, int | None, int | None]:
    """
    Check title holding status. Three possible states:
    1. CAN_APPLY - Apply button visible, can apply for this title
    2. HOLDING_THIS - "You're currently holding this title" - already have this title
    3. HOLDING_OTHER - "You're currently serving as" - have a different title

    Returns:
        (status: str, time_in_office_secs: int or None, remaining_secs: int or None)
        status is one of: "CAN_APPLY", "HOLDING_THIS", "HOLDING_OTHER"
    """
    import re
    from utils.ocr_client import OCRClient

    # Check for "You're currently holding this title" text
    holding_this_matched, holding_this_score, _ = match_template(
        frame, "mark_currently_holding_title_4k.png",
        search_region=(*HOLDING_TITLE_POS, *HOLDING_TITLE_SIZE), threshold=THRESHOLD
    )

    # Check for "You're currently serving as" text (holding different title)
    serving_as_matched, serving_as_score, _ = match_template(
        frame, "mark_currently_serving_as_4k.png",
        search_region=(*SERVING_AS_POS, *SERVING_AS_SIZE), threshold=THRESHOLD
    )

    # Check if Apply button is visible
    apply_matched, apply_score, _ = match_template(
        frame, "mark_apply_button_4k.png",
        search_region=(*APPLY_BUTTON_POS, *APPLY_BUTTON_SIZE), threshold=THRESHOLD
    )

    if debug:
        print(f"    Holding THIS title: {holding_this_matched} (score: {holding_this_score:.4f})")
        print(f"    Serving as OTHER: {serving_as_matched} (score: {serving_as_score:.4f})")
        print(f"    Apply button: {apply_matched} (score: {apply_score:.4f})")

    # Determine status
    if holding_this_matched:
        status = "HOLDING_THIS"
    elif serving_as_matched:
        status = "HOLDING_OTHER"
    elif apply_matched:
        status = "CAN_APPLY"
    else:
        status = "UNKNOWN"

    if debug:
        print(f"    Status: {status}")

    # OCR time in office if holding this title
    if status == "HOLDING_THIS":
        try:
            time_roi = frame[TIME_IN_OFFICE_POS[1]:TIME_IN_OFFICE_POS[1]+TIME_IN_OFFICE_SIZE[1],
                            TIME_IN_OFFICE_POS[0]:TIME_IN_OFFICE_POS[0]+TIME_IN_OFFICE_SIZE[0]]

            ocr = OCRClient()
            time_text = ocr.extract_text(time_roi, prompt='Extract only the time in HH:MM:SS format')

            if time_text:
                match = re.search(r'(\d+):(\d+):(\d+)', time_text)
                if match:
                    hours, mins, secs = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    total_secs = hours * 3600 + mins * 60 + secs
                    remaining = TITLE_DURATION_SECONDS - total_secs

                    if debug:
                        print(f"    Time in office: {hours:02d}:{mins:02d}:{secs:02d} ({total_secs}s)")
                        if remaining > 0:
                            print(f"    Remaining: {remaining}s ({remaining//60}m {remaining%60}s)")
                        else:
                            print(f"    Title expired {abs(remaining)}s ago")

                    return status, total_secs, remaining
        except Exception as e:
            if debug:
                print(f"    OCR error: {e}")

    return status, None, None


def title_management_flow(
    adb: ADBHelper,
    title_name: str,
    screenshot_helper: WindowsScreenshotHelper | None = None,
    debug: bool = False,
    return_to_base: bool = True
) -> bool:
    """
    Apply a kingdom title at marked Royal City.

    Args:
        adb: ADBHelper instance
        title_name: One of the title keys from kingdom_titles.json
        screenshot_helper: WindowsScreenshotHelper instance
        debug: Enable debug logging
        return_to_base: If True, return to base view after applying

    Returns:
        True if successful, False otherwise
    """
    win = screenshot_helper or WindowsScreenshotHelper()

    # Must be in WORLD view and at Royal City to apply titles
    from scripts.flows.go_to_mark_flow import go_to_mark_flow
    nav_ok = False
    for nav_try in range(3):
        if go_to_mark_flow(adb, win, debug=debug):
            nav_ok = True
            break
        if debug:
            print(f"  Initial go_to_mark failed (attempt {nav_try + 1}/3), retrying...")
        time.sleep(0.8)
    if not nav_ok:
        print("  ERROR: Failed to navigate to marked Royal City")
        return False
    time.sleep(0.5)

    # Validate title name
    titles = TITLE_DATA.get("titles", {})
    if title_name not in titles:
        print(f"  ERROR: Unknown title: {title_name}")
        print(f"  Available titles: {list(titles.keys())}")
        return False

    title_info = titles[title_name]
    title_click = tuple(title_info["click_position"])
    title_template = title_info.get("template")

    if debug:
        print(f"  Applying title: {title_info['display_name']}")
        print(f"  Buffs: {[b['name'] + ' ' + b['value'] for b in title_info['buffs']]}")

    try:
        # Step 1: Find and click star icon (with re-navigation retry)
        if debug:
            print("  Step 1: Searching for star icon...")

        panel_ready = False
        ready_source = ""
        last_header_score = 1.0
        last_manage_score = 1.0

        for nav_attempt in range(2):
            if nav_attempt > 0:
                if debug:
                    print("    Panel not detected; re-running go_to_mark and retrying...")
                re_nav_ok = False
                for re_nav_try in range(2):
                    if go_to_mark_flow(adb, win, debug=debug):
                        re_nav_ok = True
                        break
                    if debug:
                        print(
                            f"    Re-navigation attempt {re_nav_try + 1}/2 failed; "
                            "retrying..."
                        )
                    time.sleep(0.6)
                if not re_nav_ok:
                    continue
                time.sleep(0.5)

            frame = win.get_screenshot_cv2()
            found, score, detected_pos = match_template(
                frame, "mark_star_icon_4k.png",
                search_region=STAR_SEARCH_REGION,
                threshold=STAR_ICON_THRESHOLD  # Keep strict to avoid false positives in center region
            )
            found_single, score_single, detected_pos_single = match_template(
                frame, "star_single_4k.png",
                search_region=STAR_SEARCH_REGION,
                threshold=STAR_SINGLE_THRESHOLD
            )

            if found_single and (not found or score_single < score):
                found = True
                score = score_single
                detected_pos = detected_pos_single

            if found and detected_pos is not None:
                if debug:
                    print(f"    Star icon found at {detected_pos} (score={score:.4f})")
                star_clicks = [("detected", detected_pos), ("fixed", STAR_ICON_CLICK), ("city_center", ROYAL_CITY_CENTER_CLICK)]
            else:
                if debug:
                    print(
                        "    Star icon not found, trying fallback taps "
                        f"(mark_star_score={score:.4f}, star_single_score={score_single:.4f})"
                    )
                star_clicks = [("fixed", STAR_ICON_CLICK), ("city_center", ROYAL_CITY_CENTER_CLICK)]

            for tap_label, tap_pos in star_clicks:
                if debug:
                    print(f"    Clicking {tap_label} target at {tap_pos}")
                    print(
                        "    Polling for Royal City panel (header or Manage button) "
                        f"header_pos={ROYAL_CITY_HEADER_SEARCH_POS}, header_size={ROYAL_CITY_HEADER_SEARCH_SIZE}, "
                        f"manage_region={MANAGE_BUTTON_SEARCH_REGION}..."
                    )

                adb.tap(*tap_pos, source=f"flow:title_management:click_star_{tap_label}")

                start = time.time()
                while time.time() - start < POLL_TIMEOUT:
                    frame = win.get_screenshot_cv2()
                    header_found, header_score, _ = match_template(
                        frame,
                        "mark_royal_city_header_4k.png",
                        search_region=(*ROYAL_CITY_HEADER_SEARCH_POS, *ROYAL_CITY_HEADER_SEARCH_SIZE),
                        threshold=THRESHOLD,
                    )
                    manage_found, manage_score, _ = match_template(
                        frame,
                        "mark_manage_button_4k.png",
                        search_region=MANAGE_BUTTON_SEARCH_REGION,
                        threshold=MANAGE_BUTTON_THRESHOLD,
                    )
                    last_header_score = header_score
                    last_manage_score = manage_score

                    if header_found:
                        panel_ready = True
                        ready_source = f"header (score={header_score:.4f})"
                        break

                    if manage_found:
                        panel_ready = True
                        ready_source = f"manage button (score={manage_score:.4f})"
                        break

                    time.sleep(POLL_INTERVAL)

                if panel_ready:
                    break

                if debug:
                    print(
                        f"    {tap_label} tap did not open panel "
                        f"(header_score={last_header_score:.4f}, manage_score={last_manage_score:.4f})"
                    )

            if panel_ready:
                break

        if not panel_ready:
            print(
                "  ERROR: Royal City panel not detected "
                f"(header_score={last_header_score:.4f}, manage_score={last_manage_score:.4f})"
            )
            return False
        if debug:
            print(f"    Royal City panel ready via {ready_source}")

        # Step 2: Click Manage button (template-first, then fixed fallback).
        matched = False
        frame = win.get_screenshot_cv2()
        manage_found, manage_score, manage_pos = match_template(
            frame,
            "mark_manage_button_4k.png",
            search_region=MANAGE_BUTTON_SEARCH_REGION,
            threshold=MANAGE_BUTTON_THRESHOLD,
        )
        if manage_found and manage_pos is not None:
            if debug:
                print(
                    f"  Step 2: Clicking Manage (template) at {manage_pos} "
                    f"(score={manage_score:.4f})"
                )
            adb.tap(*manage_pos, source="flow:title_management:manage_button")
            if debug:
                print("    Polling for Royal City Management header...")
            matched, _ = _poll_for_template(
                win, TEMPLATE_DIR / "mark_royal_city_mgmt_header_4k.png",
                ROYAL_CITY_MGMT_HEADER_POS, ROYAL_CITY_MGMT_HEADER_SIZE, debug=debug
            )
        else:
            if debug:
                print(
                    f"  Step 2: Manage template not found in {MANAGE_BUTTON_SEARCH_REGION} "
                    f"(score={manage_score:.4f}); trying fixed positions"
                )

        if not matched:
            manage_positions = [MANAGE_BUTTON_CLICK_OWN, MANAGE_BUTTON_CLICK]  # Own city first, then other
            for i, manage_pos in enumerate(manage_positions):
                if debug:
                    pos_name = "OWN city" if i == 0 else "OTHER city"
                    print(f"  Step 2: Clicking Manage at {manage_pos} ({pos_name})")
                adb.tap(*manage_pos, source="flow:title_management:manage_button")

                # Poll for Royal City Management header
                if debug:
                    print("    Polling for Royal City Management header...")
                matched, _ = _poll_for_template(
                    win, TEMPLATE_DIR / "mark_royal_city_mgmt_header_4k.png",
                    ROYAL_CITY_MGMT_HEADER_POS, ROYAL_CITY_MGMT_HEADER_SIZE, debug=debug
                )
                if matched:
                    break
                if debug and i < len(manage_positions) - 1:
                    print("    Not found, trying alternate position...")

        if not matched:
            print("  ERROR: Royal City Management header not found")
            return False

        # Step 3: Click Title Assignment
        if debug:
            print(f"  Step 3: Clicking Title Assignment at {TITLE_ASSIGNMENT_CLICK}")
        adb.tap(*TITLE_ASSIGNMENT_CLICK, source="flow:title_management:title_assignment")

        # Poll for Kingdom Title header (LIST view)
        if debug:
            print("    Polling for Kingdom Title header...")
        matched, _ = _poll_for_template(
            win, TEMPLATE_DIR / "mark_kingdom_title_header_4k.png",
            KINGDOM_TITLE_HEADER_POS, KINGDOM_TITLE_HEADER_SIZE, debug=debug
        )
        if not matched:
            print("  ERROR: Kingdom Title header not found")
            return False

        # Step 4: Find and click desired title using template matching with scrolling
        if debug:
            print(f"  Step 4: Searching for {title_name} using template...")

        title_template_name = title_info.get("template")
        detected_pos = None
        found = False

        # Search full title list area
        search_region = (1350, 500, 1100, 1400)

        # TIGHT threshold - must be very close match
        TIGHT_THRESHOLD = 0.015

        if title_template_name:
            # Try up to 4 scroll attempts to find the title
            for scroll_attempt in range(4):  # 0 = no scroll, 1-3 = scroll down
                frame = win.get_screenshot_cv2()
                found, score, detected_pos = match_template(
                    frame, title_template_name,
                    search_region=search_region,
                    threshold=TIGHT_THRESHOLD
                )

                if debug:
                    print(f"    Attempt {scroll_attempt}: score={score:.4f}, found={found}, pos={detected_pos}")

                if found and detected_pos:
                    if debug:
                        print(f"    Found {title_name} at {detected_pos}")
                    break

                if scroll_attempt < 3:
                    if debug:
                        print(f"    Not found, scrolling down...")
                    adb.swipe(1920, 1400, 1920, 800, 500)
                    time.sleep(0.8)

            if found and detected_pos:
                adb.tap(*detected_pos, source="flow:title_management:select_title")
            else:
                print(f"  ERROR: Could not find {title_name} template after scrolling")
                return False
        else:
            print(f"  ERROR: No template defined for {title_name}")
            return False

        # Wait for detail view to load
        # Note: title_template is now a LIST VIEW template, not suitable for detail view polling
        # The check_holding_status below will verify we're on the correct screen
        if debug:
            print("    Waiting for detail view to load...")
        time.sleep(1.0)

        # Check current holding status
        if debug:
            print("    Checking holding status...")
        frame = win.get_screenshot_cv2()
        status, time_in_office, remaining = check_holding_status(frame, debug=debug)

        if status == "HOLDING_THIS":
            if debug:
                print(f"  Already holding this title!")
                if time_in_office is not None:
                    print(f"  Time in office: {time_in_office}s")
                    if remaining is not None and remaining > 0:
                        print(f"  Remaining: {remaining}s ({remaining//60}m {remaining%60}s)")
            return True  # Already in office, success

        if status == "HOLDING_OTHER":
            print(f"  ERROR: Already holding a different title. Cannot apply.")
            return False

        if status == "CAN_APPLY":
            # Step 5: Click Apply
            if debug:
                print(f"  Step 5: Clicking Apply at {APPLY_BUTTON_CLICK}")
            adb.tap(*APPLY_BUTTON_CLICK, source="flow:title_management:apply_button")
            time.sleep(1.0)

            if debug:
                print("  Title application submitted!")
            return True

        # Unknown state
        print(f"  ERROR: Unknown status: {status}")
        return False

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        if return_to_base:
            if debug:
                print("  Returning to WORLD...")
            return_to_base_view(adb, win, debug=debug)
        else:
            if debug:
                print("  Staying on screen (--no-return)")


def list_titles() -> None:
    """Print available titles."""
    print("\nAvailable Kingdom Titles:")
    print("-" * 60)
    titles = TITLE_DATA.get("titles", {})
    for key, info in titles.items():
        buffs = ", ".join([f"{b['name']} {b['value']}" for b in info['buffs']])
        print(f"  {key}")
        print(f"    Display: {info['display_name']}")
        print(f"    Buffs: {buffs}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply kingdom title at Royal City")
    parser.add_argument("title", nargs="?", help="Title key (e.g., minister_of_science)")
    parser.add_argument("--list", "-l", action="store_true", help="List available titles")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug output")
    parser.add_argument("--no-return", action="store_true", help="Don't return to base view after applying")

    args = parser.parse_args()

    if args.list:
        list_titles()
        sys.exit(0)

    if not args.title:
        print("Usage: python title_management_flow.py <title_name>")
        print("       python title_management_flow.py --list")
        list_titles()
        sys.exit(1)

    print(f"=== Title Management Flow ===")
    print(f"Title: {args.title}")
    print()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    result = title_management_flow(
        adb, args.title, win,
        debug=args.debug,
        return_to_base=not args.no_return
    )

    print(f"\nResult: {'SUCCESS' if result else 'FAILED'}")
