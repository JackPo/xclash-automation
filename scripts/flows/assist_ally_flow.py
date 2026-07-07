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

# The helmet floats up-and-right of the castle body. Castle center is offset
# from the helmet center by roughly this (4K px). Castle hitbox is large (~200px)
# so this tolerates some error. CALIBRATE on first live run.
CASTLE_CLICK_OFFSET = (-142, 174)

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

    # Must be on the WORLD map to see the markers.
    frame = win.get_screenshot_cv2()
    state, _ = detect_view(frame)
    if state != ViewState.WORLD:
        logger.info(f"[ASSIST] Not in WORLD ({state}) - navigating there")
        return_to_base_view(adb, win, target=ViewState.WORLD, debug=debug)
        time.sleep(1.0)

    failed_centers: list[tuple[int, int]] = []  # helmets that opened a castle with no Assist
    for i in range(max_assists):
        frame = win.get_screenshot_cv2()
        found, score, center = match_template(frame, HELMET_TEMPLATE, threshold=HELMET_THRESHOLD)
        logger.info(f"[ASSIST] scan {i+1}: helmet found={found} score={score:.4f} center={center}")
        if not found or center is None:
            result["stop_reason"] = "no_more_helmets"
            break
        # If the only helmet we can find is one we already failed to assist (e.g.
        # already-assisted castle whose marker lingers), stop -- don't keep
        # re-opening it (which was what kept popping the trade/other menu).
        if any(abs(center[0] - fx) < 70 and abs(center[1] - fy) < 70 for fx, fy in failed_centers):
            logger.info("[ASSIST] only non-assistable helmet(s) remain - stopping")
            result["stop_reason"] = "only_non_assistable"
            break
        if debug:
            _save(frame, f"{i:02d}_helmet_score{score:.3f}")

        # Click the castle under the helmet.
        cx = center[0] + CASTLE_CLICK_OFFSET[0]
        cy = center[1] + CASTLE_CLICK_OFFSET[1]
        logger.info(f"[ASSIST] clicking castle at ({cx}, {cy}) under helmet {center}")
        adb.tap(cx, cy, source="flow:assist:open_castle")

        # Poll every 0.5s for the Assist button to appear (popup render time varies).
        af, asc, ac, frame = _poll_for_template(
            win, ASSIST_BUTTON_TEMPLATE, ASSIST_BUTTON_THRESHOLD,
            timeout=ASSIST_POPUP_TIMEOUT, search_region=ASSIST_SEARCH_REGION,
        )
        if debug:
            _save(frame, f"{i:02d}_popup")
        if not (af and ac is not None):
            # No Assist here (wrong castle / already assisted / not an ally).
            # Close the popup with the Android BACK key -- NEVER tap a screen spot
            # to "dismiss" (that hit a left-side UI button and opened Trade).
            logger.warning(f"[ASSIST] Assist button not found (score={asc:.4f}) - back out, skip this helmet")
            if debug:
                _save(frame, f"{i:02d}_no_assist_button")
            adb.key_event(4)  # KEYCODE_BACK
            time.sleep(1.0)
            failed_centers.append(center)
            continue

        logger.info(f"[ASSIST] clicking Assist button at {ac} (score={asc:.4f})")
        adb.tap(*ac, source="flow:assist:click_assist")

        # Post-Assist: some assists open a reinforcement march screen. Poll every
        # 0.5s for a March button; if it never appears, the assist auto-sent.
        mf, ms, ml, frame = _poll_for_template(
            win, MARCH_TEMPLATE, MARCH_THRESHOLD,
            timeout=MARCH_SCREEN_TIMEOUT, search_region=MARCH_SEARCH_REGION,
        )
        if debug:
            _save(frame, f"{i:02d}_after_assist")
        if mf and ml is not None:
            logger.info(f"[ASSIST] reinforcement march screen - clicking March at {ml}")
            adb.tap(*ml, source="flow:assist:march")
            time.sleep(1.2)

        result["assisted"] += 1
        logger.info(f"[ASSIST] assisted #{result['assisted']}")

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
