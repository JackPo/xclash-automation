"""
Go to Marked Location Flow - Navigate to first marked Special location.

Pre-condition: Search panel is open (magnifying glass clicked)

Flow:
1. Click Mark tab
2. Click Special tab
3. Search for Go button
4. Click Go button

Templates:
- search_mark_tab_active_4k.png - (2204, 1047) 265x99, click (2336, 1096)
- search_special_tab_active_4k.png - (1347, 1216) 196x196, click (1445, 1314)
- go_button_4k.png - search in entry area, click at center of found
"""

import time
from pathlib import Path

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.return_to_base_view import return_to_base_view
from utils.template_matcher import match_template

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "ground_truth"

# Tab positions (4K)
MARK_TAB_CLICK = (2336, 1096)
SPECIAL_TAB_CLICK = (1445, 1314)

# Go button search region (right side of entries)
GO_BUTTON_SEARCH_X_START = 2200
GO_BUTTON_SEARCH_X_END = 2500
GO_BUTTON_SEARCH_Y_START = 1200
GO_BUTTON_SEARCH_Y_END = 1800

THRESHOLD = 0.05

# Search region for Go button
GO_BUTTON_SEARCH_REGION = (
    GO_BUTTON_SEARCH_X_START,
    GO_BUTTON_SEARCH_Y_START,
    GO_BUTTON_SEARCH_X_END - GO_BUTTON_SEARCH_X_START,
    GO_BUTTON_SEARCH_Y_END - GO_BUTTON_SEARCH_Y_START
)


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
        # Step 1: Click Mark tab
        if debug:
            print(f"  Step 1: Clicking Mark tab at {MARK_TAB_CLICK}")
        adb.tap(*MARK_TAB_CLICK)
        time.sleep(0.5)

        # Step 2: Click Special tab
        if debug:
            print(f"  Step 2: Clicking Special tab at {SPECIAL_TAB_CLICK}")
        adb.tap(*SPECIAL_TAB_CLICK)
        time.sleep(0.5)

        # Step 3: Search for Go button
        if debug:
            print("  Step 3: Searching for Go button...")
        frame = win.get_screenshot_cv2()

        found, score, click_pos = match_template(
            frame, "go_button_4k.png",
            search_region=GO_BUTTON_SEARCH_REGION,
            threshold=THRESHOLD
        )
        if debug:
            print(f"    Go button: found={found}, score={score:.4f}, pos={click_pos}")

        if not found:
            print("  ERROR: Go button not found")
            return False

        # Step 4: Click Go button
        if debug:
            print(f"  Step 4: Clicking Go at {click_pos}")
        adb.tap(*click_pos)
        time.sleep(1.0)

        if debug:
            print("  Go to mark complete!")
        return True

    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    finally:
        return_to_base_view(adb, win, debug=debug)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from utils.adb_helper import ADBHelper

    print("=== Go to Mark Flow Test ===")
    print("Pre-condition: Search panel must be open!")
    print()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    result = go_to_mark_flow(adb, win, debug=True)
    print(f"\nResult: {'SUCCESS' if result else 'FAILED'}")
