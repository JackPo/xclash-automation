#!/usr/bin/env python3
"""
Desert Python rally flow.

On the WORLD map a Desert Python monster sits at a FIXED screen position (the map
recenters on our own castle, so trapped monsters land in the same spot). It shows
as a golden scorpion/cobra with blue crystal spikes and a level badge. This flow:

  1. Detects the python at its fixed position (number-badge excluded from the
     template, so the level doesn't matter).
  2. Taps the python -> its info panel opens.
  3. Clicks the red flag "Rally" button (rally_button_4k.png) -> the rally/troop
     deployment screen opens.
  4. Clicks the launch button on the deploy screen (Deploy / March) -> the rally
     kicks off with our troops.

Runs only as an opted-in mode (python_rally_mode) and only after a SHORT idle
(~20s), so it fires when the user pauses but never fights active clicking.

A step screenshot is saved at EVERY stage to screenshots/debug/desert_python_rally/
(that tree is in the daemon's 3-day auto-clean list, so it self-erases).

NOTE (calibration): the tap offset and rally-flag region were derived from a
single screenshot; the deploy-screen LAUNCH button was calibrated BLIND (we hadn't
seen that screen when this was written). On the first live run, check the step
screenshots and tune LAUNCH_TEMPLATES / regions if needed.
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import cv2

from utils.template_matcher import match_template
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.return_to_base_view import return_to_base_view
from utils.view_state_detector import detect_view, ViewState

logger = logging.getLogger("desert_python_rally_flow")

# --- Detection: the cobra EVENT ICON in the left toolbar row -----------------
# The cobra icon (orange dragon head, next to the healing 6% bag) sits in the
# left toolbar at a FIXED Y (~1478); its X can shift as other event icons come
# and go, so search a horizontal strip along that row only.
PYTHON_TEMPLATE = "cobra_icon_4k.png"
PYTHON_SEARCH_REGION = (30, 1428, 520, 104)    # x, y, w, h - the fixed-Y toolbar row
PYTHON_THRESHOLD = 0.08
PYTHON_TAP_OFFSET = (0, 0)                      # click the icon center

# --- The red flag "Rally" button on the python info panel --------------------
RALLY_FLAG_TEMPLATE = "rally_button_4k.png"    # mask auto-detected (rally_button_mask_4k.png)
RALLY_FLAG_REGION = (1600, 1500, 750, 450)     # x, y, w, h (bottom-center of the panel)
RALLY_FLAG_THRESHOLD = 0.06

# --- The launch button on the rally/deploy screen (calibrated blind) ---------
# Try each in order; click the first that appears. Whichever is right for this
# game's monster-rally deploy screen will match; the others just miss.
LAUNCH_TEMPLATES = [
    ("deploy_button_4k.png", 0.06),
    ("rally_march_button_4k.png", 0.08),
    ("march_button_4k.png", 0.06),
]
LAUNCH_REGION = (1400, 1400, 1200, 600)        # broad lower-center

POLL_INTERVAL = 0.5
RALLY_FLAG_TIMEOUT = 5.0        # wait for the panel's rally flag after tapping the python
LAUNCH_TIMEOUT = 6.0           # wait for the deploy-screen launch button after clicking rally

# After a successful launch, don't re-rally the same python for this long (a rally
# runs several minutes; the monster stays on the map until it lands).
POST_LAUNCH_COOLDOWN_MIN = 15

DEBUG_DIR = Path(__file__).parent.parent.parent / "screenshots" / "debug" / "desert_python_rally"


def _save(frame: Any, tag: str) -> None:
    """Save a step screenshot to the self-erasing debug folder."""
    try:
        from config import DEBUG_SCREENSHOTS_ENABLED
        if not DEBUG_SCREENSHOTS_ENABLED:  # action-capture is the sole screenshot system now
            return
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%H%M%S_%f")[:-3]
        cv2.imwrite(str(DEBUG_DIR / f"{ts}_{tag}.png"), frame)
    except Exception as e:  # never let debug I/O break the flow
        logger.debug(f"[PYTHON] debug save failed: {e}")


def _poll_for_template(
    win: WindowsScreenshotHelper,
    template: str,
    threshold: float,
    timeout: float,
    search_region: tuple[int, int, int, int] | None = None,
    interval: float = POLL_INTERVAL,
) -> tuple[bool, float, tuple[int, int] | None, Any]:
    """Poll every `interval`s until `template` appears or `timeout`.

    Returns (found, best_score, center, last_frame).
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


def _poll_for_launch_button(
    win: WindowsScreenshotHelper, timeout: float
) -> tuple[str | None, tuple[int, int] | None, Any]:
    """Poll for any of the LAUNCH_TEMPLATES on the deploy screen.

    Returns (template_name, center, last_frame) -- template_name is None if none
    appeared before the timeout.
    """
    deadline = time.time() + timeout
    frame = win.get_screenshot_cv2()
    while True:
        frame = win.get_screenshot_cv2()
        for tpl, thr in LAUNCH_TEMPLATES:
            found, score, center = match_template(
                frame, tpl, search_region=LAUNCH_REGION, threshold=thr,
            )
            if found and center is not None:
                logger.info(f"[PYTHON] launch button '{tpl}' found (score={score:.4f}) at {center}")
                return tpl, center, frame
        if time.time() >= deadline:
            return None, None, frame
        time.sleep(POLL_INTERVAL)


def desert_python_rally_flow(
    adb: Any,
    win: WindowsScreenshotHelper | None = None,
) -> dict[str, Any]:
    """Rally the Desert Python at its fixed WORLD-map position.

    Returns {"launched": bool, "success": bool, "stop_reason": str}.
    """
    win = win or WindowsScreenshotHelper()
    result: dict[str, Any] = {"launched": False, "success": False, "stop_reason": ""}

    # Must be on the WORLD map to see / click the monster.
    frame = win.get_screenshot_cv2()
    state, _ = detect_view(frame)
    if state != ViewState.WORLD:
        logger.info(f"[PYTHON] Not in WORLD ({state}) - navigating there")
        return_to_base_view(adb, win, target=ViewState.WORLD)
        time.sleep(1.0)
        frame = win.get_screenshot_cv2()

    # Step 1: detect the python at its fixed position.
    found, score, center = match_template(
        frame, PYTHON_TEMPLATE, search_region=PYTHON_SEARCH_REGION, threshold=PYTHON_THRESHOLD,
    )
    logger.info(f"[PYTHON] scan: found={found} score={score:.4f} center={center}")
    _save(frame, f"01_scan_found{found}_score{score:.3f}")
    if not found or center is None:
        result["stop_reason"] = "no_python"
        result["success"] = True
        return result

    # Step 2: tap the python body -> info panel.
    tx = center[0] + PYTHON_TAP_OFFSET[0]
    ty = center[1] + PYTHON_TAP_OFFSET[1]
    logger.info(f"[PYTHON] tapping python at ({tx}, {ty})")
    adb.tap(tx, ty, source="flow:python_rally:open_panel")

    # Step 3: wait for the red flag Rally button on the panel.
    rf, rsc, rc, frame = _poll_for_template(
        win, RALLY_FLAG_TEMPLATE, RALLY_FLAG_THRESHOLD,
        timeout=RALLY_FLAG_TIMEOUT, search_region=RALLY_FLAG_REGION,
    )
    _save(frame, f"02_panel_rallyflag{rf}_score{rsc:.3f}")
    if not (rf and rc is not None):
        # Panel didn't open, or the python is already being rallied (no clickable
        # flag). Close it by tapping open terrain above the monster (NOT Android
        # back -- that tries to exit the game), then bail.
        logger.warning(f"[PYTHON] rally flag not found (best={rsc:.4f}) - closing, skip")
        adb.tap(center[0], max(150, center[1] - 350), source="flow:python_rally:close_panel")
        time.sleep(0.8)
        return_to_base_view(adb, win, target=ViewState.WORLD)
        result["stop_reason"] = "no_rally_flag"
        result["success"] = True
        return result

    # Step 4: click the rally flag -> deploy/troop screen.
    logger.info(f"[PYTHON] clicking rally flag at {rc} (score={rsc:.4f})")
    adb.tap(*rc, source="flow:python_rally:click_rally_flag")

    # Step 5: wait for the deploy-screen launch button and click it.
    tpl, lc, frame = _poll_for_launch_button(win, timeout=LAUNCH_TIMEOUT)
    _save(frame, f"03_deploy_launch{'None' if tpl is None else tpl.split('_')[0]}")
    if tpl is None or lc is None:
        # Reached the deploy screen but couldn't find a launch button (blind
        # calibration miss, or a hero-select step in the way). Back out WITHOUT
        # committing troops so nothing half-fires; the step screenshots let us fix it.
        logger.warning("[PYTHON] launch button not found on deploy screen - backing out (no rally sent)")
        return_to_base_view(adb, win, target=ViewState.WORLD)
        result["stop_reason"] = "no_launch_button"
        result["success"] = True   # not an error; just needs calibration
        return result

    logger.info(f"[PYTHON] clicking launch button '{tpl}' at {lc}")
    adb.tap(*lc, source="flow:python_rally:launch")
    time.sleep(1.2)
    frame = win.get_screenshot_cv2()
    _save(frame, "04_after_launch")

    # Success: don't re-rally this python for a while (it stays on the map until
    # the rally lands).
    try:
        from utils.scheduler import get_scheduler
        reset = datetime.now() + timedelta(minutes=POST_LAUNCH_COOLDOWN_MIN)
        get_scheduler().mark_exhausted("desert_python_rally", reset)
        logger.info(f"[PYTHON] rally launched; suppressed until {reset:%H:%M}")
    except Exception as e:
        logger.debug(f"[PYTHON] mark_exhausted failed: {e}")

    return_to_base_view(adb, win, target=ViewState.WORLD)
    result["launched"] = True
    result["success"] = True
    result["stop_reason"] = "launched"
    logger.info(f"[PYTHON] done: {result}")
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from utils.adb_helper import ADBHelper
    adb = ADBHelper()
    win = WindowsScreenshotHelper()
    print(desert_python_rally_flow(adb, win))
