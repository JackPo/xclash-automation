#!/usr/bin/env python3
"""
Assist Ally flow.

On the WORLD map, alliance castles that need help show a distinctive green
knight-helmet marker (gold ring, flame crest) with a troop-count badge floating
above the castle. This flow finds each such helmet, clicks the castle beneath
it, clicks the green "Assist" (handshake) button in the castle popup, and repeats
until no helmet remains.

The helmet marker is detected number-agnostically: assist_helmet_mask_4k.png
masks out the count badge (generated from the diff of a "6" and a "12" helmet),
so it matches regardless of the number.

Templates (templates/ground_truth/):
- assist_helmet_4k.png + assist_helmet_mask_4k.png  (the helmet marker, number-masked)
- assist_button_4k.png                              (green handshake Assist button)

NOTE (calibration): CASTLE_CLICK_OFFSET and the post-Assist step were derived
from screenshots, not a live run. On the first real assist, check the debug
screenshots in screenshots/debug/assist_flow/ and tune the offset / post-Assist
handling if needed.
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import cv2

from utils.template_matcher import match_template
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.return_to_base_view import return_to_base_view
from utils.view_state_detector import detect_view, ViewState

logger = logging.getLogger("assist_ally_flow")

HELMET_TEMPLATE = "assist_helmet_4k.png"       # mask auto-detected (assist_helmet_mask_4k.png)
ASSIST_BUTTON_TEMPLATE = "assist_button_4k.png"
MARCH_TEMPLATE = "march_button_4k.png"

# Masked (TM_CCORR_NORMED-style via matcher): perfect ~0.0, our two real helmets
# scored 0.0 and 0.022; empty map best was ~0.07. 0.05 cleanly separates them.
HELMET_THRESHOLD = 0.05
ASSIST_BUTTON_THRESHOLD = 0.05
MARCH_THRESHOLD = 0.08

# The helmet floats directly above the castle body. Castle center = helmet
# center + this (4K px). Calibrated by marking it on a clean screenshot: the
# castle sits straight below the helmet, ~250px down (a hair right).
CASTLE_CLICK_OFFSET = (20, 250)

# Assist each castle this many times (castle->Assist combo repeated).
ASSIST_COMBO_COUNT = 3
# Fast timings so the 3 combos fire in quick succession (assist usually sends
# instantly - no need to wait seconds for a march screen that isn't coming).
ASSIST_COMBO_POLL_INTERVAL = 0.12   # re-check the popup/march this often
ASSIST_COMBO_POPUP_TIMEOUT = 2.5    # max wait for the Assist button per combo
ASSIST_COMBO_MARCH_TIMEOUT = 0.5    # brief check for a reinforcement march screen

# Where the popup / march screen live for detection. The castle popup appears
# near the clicked castle, so the Assist button can be anywhere in the central
# area depending on the castle's screen position -- search broadly (the green
# handshake icon is distinctive enough that a wide region is safe).
ASSIST_SEARCH_REGION = (400, 650, 3000, 1350)   # x, y, w, h
MARCH_SEARCH_REGION = (1400, 1400, 1000, 500)

MAX_ASSISTS = 25          # safety cap
POLL_INTERVAL = 0.5       # re-check every 0.5s while waiting for the popup/screen
ASSIST_POPUP_TIMEOUT = 5.0    # max wait for the Assist button after clicking the castle
MARCH_SCREEN_TIMEOUT = 3.0    # max wait for a reinforcement march screen after Assist

DEBUG_DIR = Path(__file__).parent.parent.parent / "screenshots" / "debug" / "assist_flow"


def _save(frame: Any, tag: str) -> None:
    from config import DEBUG_SCREENSHOTS_ENABLED
    if not DEBUG_SCREENSHOTS_ENABLED:  # action-capture is the sole screenshot system now
        return
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S_%f")[:-3]
    cv2.imwrite(str(DEBUG_DIR / f"{ts}_{tag}.png"), frame)


def _poll_for_template(
    win: WindowsScreenshotHelper,
    template: str,
    threshold: float,
    timeout: float,
    search_region: tuple[int, int, int, int] | None = None,
    interval: float = POLL_INTERVAL,
) -> tuple[bool, float, tuple[int, int] | None, Any]:
    """Poll every `interval`s (default 0.5s) until `template` appears or `timeout`.

    Returns (found, best_score, center, last_frame). More responsive and robust
    than a fixed sleep -- it returns as soon as the element renders and gives up
    cleanly if it never does.
    """
    deadline = time.time() + timeout
    best_score = 1.0
    frame = win.get_screenshot_cv2()
    while True:
        frame = win.get_screenshot_cv2()
        found, score, center = match_template(
            frame, template, search_region=search_region, threshold=threshold,
        )
        if score < best_score:
            best_score = score
        if found and center is not None:
            return True, score, center, frame
        if time.time() >= deadline:
            return False, best_score, None, frame
        time.sleep(interval)


# Persist non-assistable helmets ACROSS runs. A castle whose marker lingers but
# has no Assist button (already assisted / maxed / not an ally) was re-opened
# every single run because failed_centers reset each time - that's the "keeps
# clicking OptiMIZeD's castle" loop. Remember it for a cooldown and skip it.
# The map recenters on our base each run, so screen coords are stable enough.
_RECENT_FAILED_CENTERS: list[tuple[int, int, float]] = []  # (x, y, expiry_ts)
_FAILED_TTL_SEC = 900  # 15 min - don't re-open a non-assistable castle for this long


_HELMET_TMPL: Any = None
_HELMET_MASK: Any = None
# Pixel-by-pixel masked match threshold. The project's default masked matcher uses
# raw TM_CCORR (correlation) which scored a lookalike teal avatar the SAME as the
# real gold-ringed marker (~0.02). TM_SQDIFF_NORMED measures actual per-pixel
# differences: real marker ~0.0, avatar ~0.044. 0.03 cleanly separates them.
HELMET_SQDIFF_THRESHOLD = 0.03


def _find_helmet(frame: Any) -> tuple[bool, float, tuple[int, int] | None]:
    """Find the assist marker by PIXEL-BY-PIXEL masked matching (TM_SQDIFF_NORMED),
    not correlation. Returns (found, score, center)."""
    global _HELMET_TMPL, _HELMET_MASK
    import numpy as np
    from pathlib import Path
    if _HELMET_TMPL is None:
        base = Path(__file__).parent.parent.parent / "templates" / "ground_truth"
        _HELMET_TMPL = cv2.imread(str(base / HELMET_TEMPLATE))
        _HELMET_MASK = cv2.imread(str(base / "assist_helmet_mask_4k.png"))
    if _HELMET_TMPL is None or _HELMET_MASK is None:
        return False, 1.0, None
    th, tw = _HELMET_TMPL.shape[:2]
    res = cv2.matchTemplate(frame, _HELMET_TMPL, cv2.TM_SQDIFF_NORMED, mask=_HELMET_MASK)
    res[~np.isfinite(res)] = 1.0
    minv, _maxv, minloc, _maxloc = cv2.minMaxLoc(res)
    if minv <= HELMET_SQDIFF_THRESHOLD:
        return True, float(minv), (minloc[0] + tw // 2, minloc[1] + th // 2)
    return False, float(minv), None


def _prune_failed() -> None:
    now = time.time()
    _RECENT_FAILED_CENTERS[:] = [(x, y, exp) for (x, y, exp) in _RECENT_FAILED_CENTERS if exp > now]


def _is_recently_failed(center: tuple[int, int]) -> bool:
    return any(abs(center[0] - x) < 70 and abs(center[1] - y) < 70 for (x, y, _exp) in _RECENT_FAILED_CENTERS)


def assist_ally_flow(
    adb: Any,
    win: WindowsScreenshotHelper | None = None,
    debug: bool = False,
    max_assists: int = MAX_ASSISTS,
) -> dict[str, Any]:
    """Assist every ally castle showing the helmet marker, until none remain.

    Returns {"assisted": int, "success": bool, "stop_reason": str}.
    """
    win = win or WindowsScreenshotHelper()
    result: dict[str, Any] = {"assisted": 0, "success": False, "stop_reason": ""}

    # Must be on the WORLD map to see the markers. But navigating to the BASE
    # WORLD view recenters on our own castle and scrolls AWAY from a helmet the
    # screen is already showing (a nearby ally the user/daemon scrolled to) -
    # the flow would drive past the very marker it should assist. So if a
    # helmet is ALREADY on the current frame, assist it in place; only navigate
    # to base when nothing's visible here (2026-07-12: "not assisting big shady
    # on the screen" - it was on screen, the flow navigated off it).
    frame = win.get_screenshot_cv2()
    state, _ = detect_view(frame)
    here_found, _hs, _hc = _find_helmet(frame)
    if not here_found and state != ViewState.WORLD:
        logger.info(f"[ASSIST] no helmet on current frame and not WORLD ({state}) - navigating to base")
        return_to_base_view(adb, win, target=ViewState.WORLD, debug=debug)
        time.sleep(1.0)
    elif here_found:
        logger.info(f"[ASSIST] helmet already on screen (score={_hs:.4f}) - assisting in place, no navigation")

    _prune_failed()
    failed_centers: list[tuple[int, int]] = []  # helmets that opened a castle with no Assist
    for i in range(max_assists):
        frame = win.get_screenshot_cv2()
        found, score, center = _find_helmet(frame)  # pixel-by-pixel SQDIFF, not correlation
        logger.info(f"[ASSIST] scan {i+1}: helmet found={found} score={score:.4f} center={center}")
        if not found or center is None:
            result["stop_reason"] = "no_more_helmets"
            break
        # Skip a helmet we already failed to assist -- both this run AND recently
        # in a PRIOR run (persistent). A lingering marker on an already-assisted /
        # maxed castle (e.g. OptiMIZeD's) was otherwise re-opened every cycle.
        if _is_recently_failed(center) or any(abs(center[0] - fx) < 70 and abs(center[1] - fy) < 70 for fx, fy in failed_centers):
            logger.info(f"[ASSIST] helmet at {center} is a known non-assistable castle (recent) - stopping")
            result["stop_reason"] = "only_non_assistable"
            break
        if debug:
            _save(frame, f"{i:02d}_helmet_score{score:.3f}")

        # Assist this castle up to 3x. Each assist is a full COMBO: tap the castle
        # to open its popup, then tap the Assist button. After an assist the popup
        # closes, so we must RE-OPEN the castle for the next one -- tapping the
        # Assist spot 3x in a row just hits empty terrain.
        cx = center[0] + CASTLE_CLICK_OFFSET[0]
        cy = center[1] + CASTLE_CLICK_OFFSET[1]
        assists_here = 0
        for combo in range(ASSIST_COMBO_COUNT):
            logger.info(f"[ASSIST] combo {combo+1}/{ASSIST_COMBO_COUNT}: opening castle at ({cx}, {cy}) under helmet {center}")
            adb.tap(cx, cy, source="flow:assist:open_castle")

            # Poll fast for the Assist button - returns the instant it renders, so
            # the combos fire in quick succession (only slow if it never appears).
            af, asc, ac, frame = _poll_for_template(
                win, ASSIST_BUTTON_TEMPLATE, ASSIST_BUTTON_THRESHOLD,
                timeout=ASSIST_COMBO_POPUP_TIMEOUT, search_region=ASSIST_SEARCH_REGION,
                interval=ASSIST_COMBO_POLL_INTERVAL,
            )
            if not (af and ac is not None):
                if combo == 0:
                    # Not assistable (wrong castle / already assisted / not an ally).
                    # Close by tapping OPEN TERRAIN above the helmet (NOT Android back
                    # -> exits game; NOT a fixed spot -> hit Trade).
                    logger.warning(f"[ASSIST] Assist button not found (score={asc:.4f}) - closing popup, skip this helmet")
                    adb.tap(center[0], max(150, center[1] - 350), source="flow:assist:close_popup")
                    time.sleep(1.0)
                    failed_centers.append(center)
                    # Remember across runs so we stop re-opening this castle every cycle.
                    _RECENT_FAILED_CENTERS.append((center[0], center[1], time.time() + _FAILED_TTL_SEC))
                else:
                    logger.info(f"[ASSIST] no Assist button on combo {combo+1} - stopping (assisted {assists_here}x)")
                break

            logger.info(f"[ASSIST] combo {combo+1}/{ASSIST_COMBO_COUNT}: clicking Assist at {ac} (score={asc:.4f})")
            adb.tap(*ac, source="flow:assist:click_assist")
            assists_here += 1

            # Quick check for a reinforcement march screen (usually the assist just
            # sends instantly, so keep this short to stay in quick succession).
            mf, ms, ml, frame = _poll_for_template(
                win, MARCH_TEMPLATE, MARCH_THRESHOLD,
                timeout=ASSIST_COMBO_MARCH_TIMEOUT, search_region=MARCH_SEARCH_REGION,
                interval=ASSIST_COMBO_POLL_INTERVAL,
            )
            if mf and ml is not None:
                logger.info(f"[ASSIST] reinforcement march screen - clicking March at {ml}")
                adb.tap(*ml, source="flow:assist:march")
                time.sleep(0.8)
            time.sleep(0.1)

        if assists_here == 0:
            continue  # not assistable -> on to the next helmet

        result["assisted"] += 1
        logger.info(f"[ASSIST] assisted #{result['assisted']} ({assists_here}x)")

        # Back to WORLD to scan for the next helmet.
        return_to_base_view(adb, win, target=ViewState.WORLD, debug=False)
        time.sleep(0.6)
    else:
        result["stop_reason"] = "hit_max_assists"

    result["success"] = True
    logger.info(f"[ASSIST] done: {result}")
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from utils.adb_helper import ADBHelper
    adb = ADBHelper()
    win = WindowsScreenshotHelper()
    print(assist_ally_flow(adb, win, debug=True))
