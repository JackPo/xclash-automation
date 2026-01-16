"""
Community Daily Sign-in flow.

1. Clicks the Community icon in the upper right corner (masked template)
2. Polls for Daily Sig icon to appear
3. Clicks Daily Sig to open sign-in panel
4. Scrolls up to find Check-in button
5. Clicks blue "Check in" if available, or notes grey "Checked in" if already done
6. Closes panel with X button

Templates:
- community_icon_4k.png + community_icon_mask_4k.png (masked)
- daily_sig_icon_4k.png (fixed background, no mask)
- daily_signin_checkin_button_4k.png (blue Check in)
- daily_signin_checked_button_4k.png (grey Checked in)
- daily_signin_close_x_4k.png (X close button)
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import win32gui
import win32con
import win32api

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.template_matcher import match_template, has_mask
from utils.windows_screenshot_helper import WindowsScreenshotHelper

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper


def _find_bluestacks_window() -> int | None:
    """Find BlueStacks window handle."""
    windows: list[tuple[int, str]] = []

    def callback(hwnd: int, windows: list[tuple[int, str]]) -> None:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "BlueStacks" in title:
                windows.append((hwnd, title))

    win32gui.EnumWindows(callback, windows)
    return windows[0][0] if windows else None


def _send_arrow_key(direction: str) -> None:
    """Send arrow key to BlueStacks via Win32.

    Args:
        direction: 'up' or 'down'
    """
    hwnd = _find_bluestacks_window()
    if not hwnd:
        return

    try:
        win32gui.SetForegroundWindow(hwnd)
    except:
        pass
    time.sleep(0.05)

    vk = win32con.VK_DOWN if direction == "down" else win32con.VK_UP
    win32api.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)


# Templates
COMMUNITY_ICON_TEMPLATE = "community_icon_4k.png"
DAILY_SIG_TEMPLATE = "daily_sig_icon_4k.png"
LOADING_BEAR_TEMPLATE = "daily_signin_loading_bear_4k.png"
CHECKIN_BUTTON_TEMPLATE = "daily_signin_checkin_button_4k.png"
CHECKED_BUTTON_TEMPLATE = "daily_signin_checked_button_4k.png"
CLOSE_X_TEMPLATE = "daily_signin_close_x_4k.png"

# Thresholds
MASKED_THRESHOLD = 0.05
SQDIFF_THRESHOLD = 0.01  # Tight threshold for button matching

# Polling
POLL_TIMEOUT = 10.0
POLL_INTERVAL = 0.5

# Search region for Daily Sig (fixed position in Community panel)
# Detected at center (3008, 172), template 219x155
DAILY_SIG_SEARCH_REGION = (2850, 50, 300, 250)  # x, y, w, h

# Search region for loading bear (panel header while loading)
# Detected at (844, 373), size 261x264, center (974, 505)
LOADING_BEAR_SEARCH_REGION = (750, 300, 450, 400)  # x, y, w, h

# Search region for buttons (full width, variable Y)
# Template is 2289 wide, so need enough room
BUTTON_SEARCH_REGION = (700, 400, 2400, 1400)  # x, y, w, h

# State file
STATE_FILE = Path(__file__).parent.parent.parent / "data" / "daemon_current_state.json"


def _get_threshold(template_name: str) -> float:
    """Get appropriate threshold based on whether template has a mask."""
    return MASKED_THRESHOLD if has_mask(template_name) else SQDIFF_THRESHOLD


def _load_state() -> dict:
    """Load daemon state from JSON file."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def _save_checkin_state(timestamp: str) -> None:
    """Save daily check-in timestamp to state file."""
    state = _load_state()
    state["daily_checkin"] = {
        "timestamp": timestamp,
        "checked_in": True,
    }
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _is_already_checked_in_today() -> bool:
    """Check if already checked in since last server reset (02:00 UTC)."""
    state = _load_state()
    checkin = state.get("daily_checkin", {})
    last_timestamp = checkin.get("timestamp")

    if not last_timestamp:
        return False

    try:
        last_checkin = datetime.fromisoformat(last_timestamp)
        now = datetime.now(timezone.utc)

        # Server resets at 02:00 UTC
        today_reset = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if now.hour < 2:
            # Before today's reset, use yesterday's reset
            today_reset = today_reset.replace(day=today_reset.day - 1)

        return last_checkin > today_reset
    except (ValueError, TypeError):
        return False


def community_click_flow(
    adb: ADBHelper,
    win: WindowsScreenshotHelper | None = None,
    debug: bool = False,
    force: bool = False,
) -> dict:
    """
    Complete daily check-in flow.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (created if None)
        debug: Enable debug logging
        force: Run even if already checked in today

    Returns:
        dict with keys:
        - success: True if flow completed
        - checked_in: True if clicked blue button
        - already_done: True if grey button was found
        - skipped: True if skipped due to already checked in today
    """
    result = {"success": False, "checked_in": False, "already_done": False, "skipped": False}

    if win is None:
        win = WindowsScreenshotHelper()

    # Check if already done today
    if not force and _is_already_checked_in_today():
        if debug:
            print("[COMMUNITY] Already checked in today, skipping")
        result["skipped"] = True
        result["success"] = True
        return result

    if debug:
        print("[COMMUNITY] Starting community click flow")

    # Step 1: Find and click Community icon
    frame = win.get_screenshot_cv2()
    threshold = _get_threshold(COMMUNITY_ICON_TEMPLATE)
    found, score, pos = match_template(
        frame,
        COMMUNITY_ICON_TEMPLATE,
        threshold=threshold,
    )

    if debug:
        print(f"[COMMUNITY] Community icon: found={found}, score={score:.4f}, pos={pos}")

    if not found or pos is None:
        if debug:
            print("[COMMUNITY] Community icon not found")
        return result

    adb.tap(pos[0], pos[1], source="flow:community:icon_click")
    if debug:
        print(f"[COMMUNITY] Clicked Community at {pos}")

    # Step 2: Poll for Daily Sig icon
    if debug:
        print("[COMMUNITY] Waiting for Daily Sig icon...")

    start_time = time.time()
    daily_sig_pos = None

    while time.time() - start_time < POLL_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        frame = win.get_screenshot_cv2()

        found, score, pos = match_template(
            frame,
            DAILY_SIG_TEMPLATE,
            search_region=DAILY_SIG_SEARCH_REGION,
            threshold=SQDIFF_THRESHOLD,
        )

        if debug:
            print(f"[COMMUNITY] Daily Sig poll: found={found}, score={score:.4f}")

        if found and pos is not None:
            daily_sig_pos = pos
            break

    if daily_sig_pos is None:
        if debug:
            print("[COMMUNITY] Daily Sig icon not found (timeout)")
        return result

    # Step 3: Click Daily Sig
    adb.tap(daily_sig_pos[0], daily_sig_pos[1], source="flow:community:daily_sig_click")
    if debug:
        print(f"[COMMUNITY] Clicked Daily Sig at {daily_sig_pos}")

    # Step 3b: Wait for panel to fully load (poll until bear header appears)
    if debug:
        print("[COMMUNITY] Waiting for panel to load (polling for bear header)...")

    time.sleep(1.0)  # Initial wait for panel to start opening
    start_time = time.time()
    panel_loaded = False

    while time.time() - start_time < POLL_TIMEOUT:
        frame = win.get_screenshot_cv2()
        found_bear, score_bear, _ = match_template(
            frame,
            LOADING_BEAR_TEMPLATE,
            search_region=LOADING_BEAR_SEARCH_REGION,
            threshold=SQDIFF_THRESHOLD,
        )

        if debug:
            print(f"[COMMUNITY] Bear header poll: found={found_bear}, score={score_bear:.4f}")

        if found_bear:
            # Bear found = panel loaded and ready
            panel_loaded = True
            if debug:
                print("[COMMUNITY] Panel loaded (bear header visible)")
            break

        time.sleep(POLL_INTERVAL)

    if not panel_loaded:
        if debug:
            print("[COMMUNITY] Panel load timeout (bear header not found)")
        return result

    # Step 4: Search for button, scroll DOWN one at a time if not found
    button_found = False

    def _check_buttons() -> tuple[bool, str, tuple[int, int] | None]:
        """Check for check-in buttons. Returns (found, type, position)."""
        frame = win.get_screenshot_cv2()

        # Check blue "Check in" button
        found_blue, score_blue, pos_blue = match_template(
            frame,
            CHECKIN_BUTTON_TEMPLATE,
            search_region=BUTTON_SEARCH_REGION,
            threshold=SQDIFF_THRESHOLD,
        )
        if debug:
            print(f"[COMMUNITY] Blue button: found={found_blue}, score={score_blue:.4f}")
        if found_blue and pos_blue is not None:
            return True, "blue", pos_blue

        # Check grey "Checked in" button
        found_grey, score_grey, pos_grey = match_template(
            frame,
            CHECKED_BUTTON_TEMPLATE,
            search_region=BUTTON_SEARCH_REGION,
            threshold=SQDIFF_THRESHOLD,
        )
        if debug:
            print(f"[COMMUNITY] Grey button: found={found_grey}, score={score_grey:.4f}")
        if found_grey and pos_grey is not None:
            return True, "grey", pos_grey

        return False, "", None

    # Initial check after 4 DOWNs
    found, btn_type, btn_pos = _check_buttons()

    if not found:
        # Keep scrolling DOWN and checking, up to 10 more times
        for attempt in range(10):
            if debug:
                print(f"[COMMUNITY] Attempt {attempt + 1}: scroll DOWN and check...")
            _send_arrow_key("down")
            time.sleep(0.3)

            found, btn_type, btn_pos = _check_buttons()
            if found:
                break

    if found and btn_pos is not None:
        if btn_type == "blue":
            if debug:
                print(f"[COMMUNITY] Clicking Check in at {btn_pos}")
            adb.tap(btn_pos[0], btn_pos[1], source="flow:community:checkin_click")
            time.sleep(1.0)
            result["checked_in"] = True
            button_found = True
        else:  # grey
            if debug:
                print("[COMMUNITY] Already checked in (grey button found)")
            result["already_done"] = True
            button_found = True

    if not button_found:
        if debug:
            print("[COMMUNITY] Could not find check-in button after 10 scroll attempts")

    # Step 6: Close panel with X button
    frame = win.get_screenshot_cv2()
    found_x, score_x, pos_x = match_template(
        frame,
        CLOSE_X_TEMPLATE,
        threshold=SQDIFF_THRESHOLD,
    )

    if debug:
        print(f"[COMMUNITY] Close X: found={found_x}, score={score_x:.4f}")

    if found_x and pos_x is not None:
        adb.tap(pos_x[0], pos_x[1], source="flow:community:close_x")
        if debug:
            print(f"[COMMUNITY] Clicked X to close at {pos_x}")
        time.sleep(0.5)

    # Save state if we checked in or found already done
    if result["checked_in"] or result["already_done"]:
        timestamp = datetime.now(timezone.utc).isoformat()
        _save_checkin_state(timestamp)
        if debug:
            print(f"[COMMUNITY] Saved check-in state: {timestamp}")

    result["success"] = button_found

    if debug:
        print(f"[COMMUNITY] Flow complete: {result}")

    return result


if __name__ == "__main__":
    from utils.adb_helper import ADBHelper

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    result = community_click_flow(adb, win, debug=True, force=True)
    print(f"\nResult: {result}")
