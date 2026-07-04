"""
Community Daily Sign-in flow -- v2 (post mid-2026 community rework).

The game reworked the Community hub: it now opens a webview with a left nav
(Home / News / Circle / Me). Daily check-in is no longer a top-right "Daily Sig"
icon -- it lives behind the hamburger menu on the Home page.

Navigation (v2):
1. Click the Community icon (masked template) -- opens the community webview.
2. Reach the Home feed: poll for the hamburger menu (nudge the Home left-nav
   tab if a splash / another tab is showing).
3. Click the hamburger -> side drawer; click "Daily Sign-In".
4. Wait for the sign-in panel (polar-bear header), scroll down to the button.
5. Click blue "Check in" (or note grey "Checked in" if already done).
6. Dismiss the "Check-in Success" popup, then close the webview.

Resilience:
- REVERT FALLBACK: if the old top-right "Daily Sig" icon is present (the game
  rolled the UI back), delegate to the v1 flow (community_click_flow).
- HEALTH SIGNAL: if neither the new anchors nor the old icon can be found, the
  layout changed again -- record a health failure (utils.current_state) so the
  dashboard shows a top-of-page warning instead of failing silently.

The panel-handling templates are shared with v1 and matched here unchanged:
- daily_signin_loading_bear_4k.png / daily_signin_checkin_button_4k.png /
  daily_signin_checked_button_4k.png
New v2 templates:
- community_hamburger_4k.png / community_daily_signin_row_4k.png /
  daily_signin_success_close_4k.png
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.template_matcher import match_template
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.view_state_detector import go_to_town, detect_view, ViewState

# Reuse v1's shared logic and constants so behavior stays in one place.
from scripts.flows.community_click_flow import (
    logger,
    _save_debug,
    _is_already_checked_in_today,
    _save_checkin_state,
    community_click_flow as community_click_flow_v1,
    COMMUNITY_ICON_TEMPLATES,
    DAILY_SIG_TEMPLATE,
    DAILY_SIG_SEARCH_REGION,
    DAILY_SIG_THRESHOLD,
    LOADING_BEAR_TEMPLATE,
    LOADING_BEAR_SEARCH_REGION,
    CHECKIN_BUTTON_TEMPLATE,
    CHECKED_BUTTON_TEMPLATE,
    BUTTON_SEARCH_REGION,
    SQDIFF_THRESHOLD,
    MASKED_THRESHOLD,
    _get_threshold,
)
from utils.timings import POLL_INTERVAL_SLOW as POLL_INTERVAL, POLL_TIMEOUT_LONG as POLL_TIMEOUT

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

# --- v2 navigation templates / regions ---
HAMBURGER_TEMPLATE = "community_hamburger_4k.png"
HAMBURGER_SEARCH_REGION = (300, 0, 900, 260)  # top-left, next to the X-Clash logo
DAILY_SIGNIN_ROW_TEMPLATE = "community_daily_signin_row_4k.png"
DAILY_SIGNIN_ROW_SEARCH_REGION = (0, 850, 1000, 300)  # drawer row under FEATURES & BENEFITS
SUCCESS_CLOSE_TEMPLATE = "daily_signin_success_close_4k.png"
SUCCESS_CLOSE_SEARCH_REGION = (2100, 500, 700, 400)  # red X on the Check-in Success popup
NAV_THRESHOLD = 0.05

# Fixed chrome coords (webview layout is stable at 4K)
LEFT_NAV_HOME_CLICK = (224, 470)       # Home tab in the community left nav (safe; never exits)
COMMUNITY_OUTER_X_CLICK = (3755, 96)   # top-right X that closes the whole webview
WEBVIEW_LOAD_TIMEOUT = 25              # community webview + splashes can be slow to settle
PANEL_SCROLL_MAX = 6                   # swipe-ups while hunting for the Check in button


def _signal_health(ok: bool, reason: str | None = None) -> None:
    """Record check-in navigation health so the dashboard can warn on breakage."""
    try:
        from utils.current_state import update_community_checkin_health
        update_community_checkin_health(ok, reason)
    except Exception as e:
        logger.error(f"[COMMUNITY2] Failed to record health ({ok}, {reason}): {e}")


def _exit_community(adb: ADBHelper, win: WindowsScreenshotHelper, debug: bool = False) -> bool:
    """Close the community webview and confirm we're back on TOWN/WORLD.

    The webview's own top-right X exits to the game; tap it a few times (the
    webview is laggy) until the view detector reports a base view.
    """
    for _ in range(6):
        frame = win.get_screenshot_cv2()
        state, _ = detect_view(frame)
        if state in (ViewState.TOWN, ViewState.WORLD):
            return True
        adb.tap(*COMMUNITY_OUTER_X_CLICK, source="flow:community2:exit")
        time.sleep(2.5)
    try:
        from utils.return_to_base_view import return_to_base_view
        return return_to_base_view(adb, win, debug=debug)
    except Exception:
        return False


def _open_community(adb: ADBHelper, win: WindowsScreenshotHelper, debug: bool) -> bool:
    """Ensure TOWN view and click the Community icon. Returns True if clicked."""
    go_to_town(adb)
    time.sleep(0.5)
    frame = win.get_screenshot_cv2()
    _save_debug(frame, "v2_01_before_community_icon")
    for template_name in COMMUNITY_ICON_TEMPLATES:
        found, score, pos = match_template(frame, template_name, threshold=_get_threshold(template_name))
        if debug:
            print(f"[COMMUNITY2] {template_name}: found={found} score={score:.4f} pos={pos}")
        if found and pos is not None:
            adb.tap(pos[0], pos[1], source="flow:community2:icon_click")
            return True
    _save_debug(frame, "v2_01_community_icon_NOT_FOUND")
    return False


def _reach_home_and_open_drawer(
    adb: ADBHelper, win: WindowsScreenshotHelper, debug: bool
) -> tuple[str, tuple[int, int] | None]:
    """Get from a freshly-opened community webview to the Daily Sign-In drawer row.

    Returns (status, signin_pos):
      - ("ok", pos)         -> found the Daily Sign-In row, click pos returned
      - ("reverted", None)  -> old top-right Daily Sig icon present; caller uses v1
      - ("no_home", None)   -> never reached the Home feed (hamburger not found)
      - ("no_signin", None) -> reached Home but drawer had no Daily Sign-In row
    """
    # Poll for the Home-feed hamburger. Meanwhile watch for the OLD Daily Sig
    # icon (revert case). Halfway through, nudge the Home left-nav tab once in
    # case a splash or another tab is showing (safe -- never exits community).
    start = time.time()
    nudged_home = False
    hamburger_pos = None
    while time.time() - start < WEBVIEW_LOAD_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        frame = win.get_screenshot_cv2()

        # Revert detection: old flow's Daily Sig icon at top-right.
        found_old, _, _ = match_template(
            frame, DAILY_SIG_TEMPLATE,
            search_region=DAILY_SIG_SEARCH_REGION, threshold=DAILY_SIG_THRESHOLD,
        )
        if found_old:
            _save_debug(frame, "v2_02_old_daily_sig_present_revert")
            return "reverted", None

        found, score, pos = match_template(
            frame, HAMBURGER_TEMPLATE,
            search_region=HAMBURGER_SEARCH_REGION, threshold=NAV_THRESHOLD,
        )
        if debug:
            print(f"[COMMUNITY2] hamburger poll: found={found} score={score:.4f}")
        if found and pos is not None:
            hamburger_pos = pos
            _save_debug(frame, "v2_02_home_hamburger_found")
            break

        if not nudged_home and (time.time() - start) > WEBVIEW_LOAD_TIMEOUT / 2:
            adb.tap(*LEFT_NAV_HOME_CLICK, source="flow:community2:nav_home")
            nudged_home = True

    if hamburger_pos is None:
        _save_debug(win.get_screenshot_cv2(), "v2_02_home_NOT_reached")
        return "no_home", None

    # Open the drawer and find the Daily Sign-In row.
    adb.tap(*hamburger_pos, source="flow:community2:hamburger")
    time.sleep(1.5)

    start = time.time()
    while time.time() - start < POLL_TIMEOUT:
        frame = win.get_screenshot_cv2()
        found, score, pos = match_template(
            frame, DAILY_SIGNIN_ROW_TEMPLATE,
            search_region=DAILY_SIGNIN_ROW_SEARCH_REGION, threshold=NAV_THRESHOLD,
        )
        if debug:
            print(f"[COMMUNITY2] daily-signin row: found={found} score={score:.4f}")
        if found and pos is not None:
            _save_debug(frame, "v2_03_daily_signin_row_found")
            return "ok", pos
        time.sleep(POLL_INTERVAL)

    _save_debug(win.get_screenshot_cv2(), "v2_03_daily_signin_row_NOT_FOUND")
    return "no_signin", None


def _operate_signin_panel(
    adb: ADBHelper, win: WindowsScreenshotHelper, result: dict, debug: bool
) -> bool:
    """From an opened Daily Sign-In panel: wait for load, scroll to the button,
    click Check in (or note already-done), dismiss the success popup.

    Returns True if a button (blue or grey) was found and handled.
    """
    # Wait for the polar-bear header (panel loaded).
    start = time.time()
    panel_loaded = False
    while time.time() - start < POLL_TIMEOUT:
        frame = win.get_screenshot_cv2()
        found_bear, score_bear, _ = match_template(
            frame, LOADING_BEAR_TEMPLATE,
            search_region=LOADING_BEAR_SEARCH_REGION, threshold=SQDIFF_THRESHOLD,
        )
        if debug:
            print(f"[COMMUNITY2] bear header: found={found_bear} score={score_bear:.4f}")
        if found_bear:
            panel_loaded = True
            _save_debug(frame, "v2_04_panel_loaded")
            break
        time.sleep(POLL_INTERVAL)

    if not panel_loaded:
        _save_debug(win.get_screenshot_cv2(), "v2_04_panel_NOT_loaded")
        return False

    def _check_buttons() -> tuple[bool, str, tuple[int, int] | None]:
        frame = win.get_screenshot_cv2()
        f_blue, s_blue, p_blue = match_template(
            frame, CHECKIN_BUTTON_TEMPLATE, search_region=BUTTON_SEARCH_REGION, threshold=SQDIFF_THRESHOLD,
        )
        if f_blue and p_blue is not None:
            _save_debug(frame, f"v2_05_blue_{s_blue:.4f}")
            return True, "blue", p_blue
        f_grey, s_grey, p_grey = match_template(
            frame, CHECKED_BUTTON_TEMPLATE, search_region=BUTTON_SEARCH_REGION, threshold=SQDIFF_THRESHOLD,
        )
        if f_grey and p_grey is not None:
            _save_debug(frame, f"v2_05_grey_{s_grey:.4f}")
            return True, "grey", p_grey
        return False, "", None

    # The button sits below the reward tiers -- scroll down (swipe up) to find it.
    found, btn_type, btn_pos = _check_buttons()
    for attempt in range(PANEL_SCROLL_MAX):
        if found:
            break
        if debug:
            print(f"[COMMUNITY2] scroll {attempt + 1}/{PANEL_SCROLL_MAX} to find button")
        adb.swipe(1920, 1600, 1920, 600, duration=600)
        time.sleep(1.5)
        found, btn_type, btn_pos = _check_buttons()

    if not (found and btn_pos is not None):
        _save_debug(win.get_screenshot_cv2(), "v2_05_button_NOT_FOUND")
        return False

    if btn_type == "blue":
        adb.tap(btn_pos[0], btn_pos[1], source="flow:community2:checkin_click")
        result["checked_in"] = True
        time.sleep(1.5)
        # Dismiss the "Check-in Success" popup (red X) if it appeared.
        frame = win.get_screenshot_cv2()
        f_sx, _, p_sx = match_template(
            frame, SUCCESS_CLOSE_TEMPLATE, search_region=SUCCESS_CLOSE_SEARCH_REGION, threshold=NAV_THRESHOLD,
        )
        if f_sx and p_sx is not None:
            adb.tap(p_sx[0], p_sx[1], source="flow:community2:success_close")
            time.sleep(1.0)
        _save_debug(win.get_screenshot_cv2(), "v2_06_after_checkin")
    else:
        result["already_done"] = True
        _save_debug(win.get_screenshot_cv2(), "v2_06_already_done")
    return True


def community_click_flow2(
    adb: ADBHelper,
    win: WindowsScreenshotHelper | None = None,
    debug: bool = False,
    force: bool = False,
) -> dict:
    """Daily check-in via the reworked community hub, with v1 fallback + health signal.

    Returns dict: {success, checked_in, already_done, skipped, reverted}.
    """
    result = {"success": False, "checked_in": False, "already_done": False,
              "skipped": False, "reverted": False}

    if win is None:
        win = WindowsScreenshotHelper()

    if not force and _is_already_checked_in_today():
        logger.info("[COMMUNITY2] Already checked in today, returning success (full cooldown)")
        result["already_done"] = True
        result["success"] = True
        return result

    if debug:
        print("[COMMUNITY2] Starting community check-in flow v2")

    if not _open_community(adb, win, debug):
        logger.warning("[COMMUNITY2] Community icon not found")
        # Icon missing is a game-state issue, not a layout change; don't flip health.
        return result

    status, signin_pos = _reach_home_and_open_drawer(adb, win, debug)

    if status == "reverted":
        logger.info("[COMMUNITY2] Old Daily Sig icon detected -> delegating to v1 flow")
        result["reverted"] = True
        # v1 expects a fresh start; it re-navigates from town itself.
        _exit_community(adb, win, debug)
        v1 = community_click_flow_v1(adb, win, debug=debug, force=force)
        v1["reverted"] = True
        if v1.get("success"):
            _signal_health(True)  # v1 path worked -> not broken, just reverted
        else:
            _signal_health(False, "revert_v1_failed")
        return v1

    if status != "ok" or signin_pos is None:
        # Layout changed and no known path worked -> warn on the dashboard.
        logger.error(f"[COMMUNITY2] Navigation failed at '{status}' -- community layout changed")
        _signal_health(False, status)
        _exit_community(adb, win, debug)
        return result

    adb.tap(signin_pos[0], signin_pos[1], source="flow:community2:daily_signin")

    handled = _operate_signin_panel(adb, win, result, debug)
    if not handled:
        logger.error("[COMMUNITY2] Sign-in panel opened but button not operable -- layout changed")
        _signal_health(False, "signin_panel")
        _exit_community(adb, win, debug)
        return result

    # Success: persist check-in state and clear any prior health warning.
    if result["checked_in"] or result["already_done"]:
        _save_checkin_state(datetime.now(timezone.utc).isoformat())
    _signal_health(True)
    result["success"] = True

    _exit_community(adb, win, debug)
    if debug:
        print(f"[COMMUNITY2] Flow complete: {result}")
    return result


if __name__ == "__main__":
    from utils.adb_helper import ADBHelper

    adb = ADBHelper()
    win = WindowsScreenshotHelper()
    res = community_click_flow2(adb, win, debug=True, force=True)
    print(f"\nResult: {res}")
