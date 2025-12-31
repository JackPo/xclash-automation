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

import argparse
import json
import time
import cv2
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.adb_helper import ADBHelper
from utils.return_to_base_view import return_to_base_view

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "ground_truth"
DATA_DIR = Path(__file__).parent.parent.parent / "data"

# Load title data
with open(DATA_DIR / "kingdom_titles.json") as f:
    TITLE_DATA = json.load(f)

# Fixed click positions (4K)
STAR_ICON_CLICK = (1919, 1285)
MANAGE_BUTTON_CLICK = (2230, 881)
TITLE_ASSIGNMENT_CLICK = (1650, 976)
APPLY_BUTTON_CLICK = (1914, 1844)

# Template positions for validation
ROYAL_CITY_HEADER_POS = (1463, 328)
ROYAL_CITY_HEADER_SIZE = (902, 93)

ROYAL_CITY_MGMT_HEADER_POS = (1336, 0)
ROYAL_CITY_MGMT_HEADER_SIZE = (1163, 112)

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
POLL_TIMEOUT = 5.0
POLL_INTERVAL = 0.3


def _match_template_fixed(frame, template_path, pos, size):
    """Match template at fixed position."""
    template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
    if template is None:
        print(f"    ERROR: Template not found: {template_path}")
        return False, 1.0

    x, y = pos
    w, h = size
    roi = frame[y:y+h, x:x+w]
    roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi

    # Handle size mismatch
    if roi_gray.shape[0] < template.shape[0] or roi_gray.shape[1] < template.shape[1]:
        return False, 1.0

    result = cv2.matchTemplate(roi_gray, template, cv2.TM_SQDIFF_NORMED)
    score = cv2.minMaxLoc(result)[0]
    return score <= THRESHOLD, score


def _poll_for_template(win, template_path, pos, size, timeout=POLL_TIMEOUT, debug=False):
    """Poll until template matches or timeout."""
    start = time.time()
    last_score = 1.0
    while time.time() - start < timeout:
        frame = win.get_screenshot_cv2()
        matched, score = _match_template_fixed(frame, template_path, pos, size)
        last_score = score
        if matched:
            if debug:
                print(f"    Template matched: {score:.4f}")
            return True, frame
        time.sleep(POLL_INTERVAL)
    if debug:
        print(f"    Poll timeout. Last score: {last_score:.4f}")
    return False, None


def check_holding_status(frame, debug=False):
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
    holding_this_matched, holding_this_score = _match_template_fixed(
        frame, TEMPLATE_DIR / "mark_currently_holding_title_4k.png",
        HOLDING_TITLE_POS, HOLDING_TITLE_SIZE
    )

    # Check for "You're currently serving as" text (holding different title)
    serving_as_matched, serving_as_score = _match_template_fixed(
        frame, TEMPLATE_DIR / "mark_currently_serving_as_4k.png",
        SERVING_AS_POS, SERVING_AS_SIZE
    )

    # Check if Apply button is visible
    apply_matched, apply_score = _match_template_fixed(
        frame, TEMPLATE_DIR / "mark_apply_button_4k.png",
        APPLY_BUTTON_POS, APPLY_BUTTON_SIZE
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


def title_management_flow(adb, title_name, screenshot_helper=None, debug=False, return_to_base=True):
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
        # Step 1: Click star icon
        if debug:
            print(f"  Step 1: Clicking star icon at {STAR_ICON_CLICK}")
        adb.tap(*STAR_ICON_CLICK)

        # Poll for Royal City header
        if debug:
            print("    Polling for Royal City header...")
        matched, _ = _poll_for_template(
            win, TEMPLATE_DIR / "mark_royal_city_header_4k.png",
            ROYAL_CITY_HEADER_POS, ROYAL_CITY_HEADER_SIZE, debug=debug
        )
        if not matched:
            print("  ERROR: Royal City header not found")
            return False

        # Step 2: Click Manage button
        if debug:
            print(f"  Step 2: Clicking Manage at {MANAGE_BUTTON_CLICK}")
        adb.tap(*MANAGE_BUTTON_CLICK)

        # Poll for Royal City Management header
        if debug:
            print("    Polling for Royal City Management header...")
        matched, _ = _poll_for_template(
            win, TEMPLATE_DIR / "mark_royal_city_mgmt_header_4k.png",
            ROYAL_CITY_MGMT_HEADER_POS, ROYAL_CITY_MGMT_HEADER_SIZE, debug=debug
        )
        if not matched:
            print("  ERROR: Royal City Management header not found")
            return False

        # Step 3: Click Title Assignment
        if debug:
            print(f"  Step 3: Clicking Title Assignment at {TITLE_ASSIGNMENT_CLICK}")
        adb.tap(*TITLE_ASSIGNMENT_CLICK)

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

        # Step 4: Click desired title row
        if debug:
            print(f"  Step 4: Clicking {title_name} at {title_click}")
        adb.tap(*title_click)

        # Poll for title detail view
        if title_template:
            if debug:
                print(f"    Polling for {title_template}...")
            matched, _ = _poll_for_template(
                win, TEMPLATE_DIR / title_template,
                TITLE_DETAIL_POS, TITLE_DETAIL_SIZE, debug=debug
            )
            if not matched:
                print(f"  ERROR: {title_name} detail view not found")
                return False

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
            adb.tap(*APPLY_BUTTON_CLICK)
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
                print("  Returning to base view...")
            return_to_base_view(adb, win, debug=debug)
        else:
            if debug:
                print("  Staying on screen (--no-return)")


def list_titles():
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
