#!/usr/bin/env python3
"""
Tavern Steal Sniper Flow.

Watches the open world view for a floating Steal button (hexagon with running
thief). When found, OCRs the countdown timer floating above it and "locks on".
At STEAL_SPAM_LEAD seconds before the timer hits zero it spam-clicks the Steal
button until STEAL_SPAM_TAIL seconds after zero, sniping the chest right as it
unlocks.

Runs as an exclusive daemon mode (like reinforce mode): the daemon calls
sniper_tick() every iteration while sniper mode is active. Status is published
via get_sniper_status() for the dashboard.

The user is expected to leave the game parked on a view where the Steal button
and its timer are visible. Do not pan/zoom while the mode is armed.
"""
import logging
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import (
    STEAL_BUTTON_TEMPLATE,
    STEAL_BUTTON_THRESHOLD,
    STEAL_FINAL_APPROACH_SECONDS,
    STEAL_REFINE_AT_SECONDS,
    STEAL_SPAM_LEAD,
    STEAL_SPAM_TAIL,
    STEAL_SPAM_TAP_DELAY,
    STEAL_TIMER_REGION_OFFSET,
)
from utils.adb_helper import ADBHelper
from utils.template_matcher import match_template
from utils.windows_screenshot_helper import WindowsScreenshotHelper

logger = logging.getLogger(__name__)

# Module-level status, read by daemon_server for the dashboard.
_status_lock = threading.Lock()
_status: dict[str, Any] = {
    "state": "idle",  # idle | searching | locked | sniping
    "seconds_left": None,
    "deadline_epoch": None,  # unix time when the steal timer hits 0
    "button_pos": None,
    "last_result": None,
    "snipes_attempted": 0,
    "taps_last_snipe": 0,
    "updated_at": None,
}

_ocr_client = None


def _get_ocr():
    global _ocr_client
    if _ocr_client is None:
        from utils.ocr_client import OCRClient
        _ocr_client = OCRClient()
    return _ocr_client


def _set_status(**kwargs: Any) -> None:
    with _status_lock:
        _status.update(kwargs)
        _status["updated_at"] = time.time()


def get_sniper_status() -> dict[str, Any]:
    """Snapshot of sniper state for the dashboard. Thread-safe."""
    with _status_lock:
        snap = dict(_status)
    # Recompute live countdown from the deadline
    if snap.get("deadline_epoch"):
        snap["seconds_left"] = round(snap["deadline_epoch"] - time.time(), 1)
    return snap


def reset_sniper_status() -> None:
    """Reset to idle (called when the mode is stopped)."""
    _set_status(state="idle", seconds_left=None, deadline_epoch=None, button_pos=None)


def parse_timer_text(text: str) -> int | None:
    """Parse 'HH:MM:SS' or 'MM:SS' into total seconds."""
    match = re.search(r"(\d{1,2}):(\d{2}):(\d{2})", text)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return h * 3600 + m * 60 + s
    match = re.search(r"(\d{1,2}):(\d{2})", text)
    if match:
        m, s = int(match.group(1)), int(match.group(2))
        return m * 60 + s
    return None


def _ocr_steal_timer(frame: Any, button_center: tuple[int, int]) -> int | None:
    """OCR the countdown floating above the Steal button. Returns seconds or None."""
    dx, dy, w, h = STEAL_TIMER_REGION_OFFSET
    cx, cy = button_center
    x = max(0, cx + dx)
    y = max(0, cy + dy)
    try:
        text = _get_ocr().extract_text(
            frame,
            region=(x, y, w, h),
            prompt="Read the countdown timer in this image. Return ONLY the time (e.g. 00:02:04), nothing else.",
        )
    except Exception as e:
        logger.warning(f"Steal timer OCR failed: {e}")
        return None
    secs = parse_timer_text(text)
    if secs is not None and not (0 <= secs <= 86400):
        logger.warning(f"Steal timer OCR out of bounds: {text!r} -> {secs}s")
        return None
    logger.debug(f"Steal timer OCR: {text!r} -> {secs}")
    return secs


def _find_steal_button(frame: Any) -> tuple[bool, float, tuple[int, int]]:
    return match_template(frame, STEAL_BUTTON_TEMPLATE, threshold=STEAL_BUTTON_THRESHOLD)


def sniper_tick(
    adb: ADBHelper,
    win: WindowsScreenshotHelper | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    """
    One sniper iteration. Called repeatedly by the daemon while sniper mode is on.

    Fast path: scan for the Steal button; if found, OCR the timer and lock on.
    When the deadline is within STEAL_FINAL_APPROACH_SECONDS this call BLOCKS
    through the snipe (sleep to T-lead, spam-click to T+tail) and returns the
    outcome.

    Returns dict with at least {"state": ...}; "newly_locked": True on the tick
    that acquires a lock (daemon logs SNIPE ACTIVATED).
    """
    win = win or WindowsScreenshotHelper()

    frame = win.get_screenshot_cv2()
    t_frame = time.monotonic()
    found, score, center = _find_steal_button(frame)

    if not found:
        was_locked = _status["state"] in ("locked", "sniping")
        if was_locked:
            logger.info(f"STEAL SNIPER: lost lock (best score {score:.4f})")
        _set_status(state="searching", seconds_left=None, deadline_epoch=None, button_pos=None)
        return {"state": "searching", "score": score}

    secs = _ocr_steal_timer(frame, center)
    if secs is None:
        # Button visible but timer unreadable - hold position, retry next tick
        _set_status(state="locked", button_pos=list(center))
        return {"state": "locked", "seconds_left": None, "score": score}

    deadline_mono = t_frame + secs
    deadline_epoch = time.time() - (time.monotonic() - deadline_mono)
    newly_locked = _status["state"] != "locked"
    _set_status(
        state="locked",
        seconds_left=secs,
        deadline_epoch=deadline_epoch,
        button_pos=list(center),
    )
    if newly_locked:
        logger.info(
            f"STEAL SNIPER: SNIPE ACTIVATED - steal button at {center}, "
            f"timer {secs}s (score {score:.4f})"
        )

    if secs > STEAL_FINAL_APPROACH_SECONDS:
        return {"state": "locked", "seconds_left": secs, "newly_locked": newly_locked}

    return _execute_snipe(adb, win, center, deadline_mono, newly_locked)


def _execute_snipe(
    adb: ADBHelper,
    win: WindowsScreenshotHelper,
    button_center: tuple[int, int],
    deadline_mono: float,
    newly_locked: bool,
) -> dict[str, Any]:
    """Final approach: refine deadline once, sleep to T-lead, spam to T+tail."""
    # One refinement pass to correct OCR/latency drift, if there's time for it
    remaining = deadline_mono - time.monotonic()
    if remaining > STEAL_REFINE_AT_SECONDS + 1:
        time.sleep(remaining - STEAL_REFINE_AT_SECONDS)
        frame = win.get_screenshot_cv2()
        t_frame = time.monotonic()
        found, score, center = _find_steal_button(frame)
        if not found:
            logger.info(f"STEAL SNIPER: button vanished during final approach (score {score:.4f})")
            _set_status(state="searching", seconds_left=None, deadline_epoch=None,
                        button_pos=None, last_result="lost_lock_in_approach")
            return {"state": "searching", "last_result": "lost_lock_in_approach"}
        button_center = center
        secs = _ocr_steal_timer(frame, center)
        if secs is not None:
            deadline_mono = t_frame + secs
            _set_status(deadline_epoch=time.time() + (deadline_mono - time.monotonic()),
                        button_pos=list(center))
            logger.info(f"STEAL SNIPER: refined deadline, {secs}s to steal")

    # Sleep until spam window opens (T - lead)
    wait = deadline_mono - STEAL_SPAM_LEAD - time.monotonic()
    if wait > 0:
        time.sleep(wait)

    # SPAM until T + tail
    spam_end = deadline_mono + STEAL_SPAM_TAIL
    x, y = button_center
    taps = 0
    logger.info(f"STEAL SNIPER: FIRING - spamming steal at ({x}, {y})")
    _set_status(state="sniping")
    while time.monotonic() < spam_end:
        try:
            adb.tap(x, y, source="flow:steal_sniper:spam")
        except Exception as e:
            logger.warning(f"STEAL SNIPER: tap failed mid-spam: {e}")
        taps += 1
        if STEAL_SPAM_TAP_DELAY > 0:
            time.sleep(STEAL_SPAM_TAP_DELAY)

    # Verify outcome: is the button gone?
    time.sleep(1.0)
    frame = win.get_screenshot_cv2()
    found, score, _ = _find_steal_button(frame)
    result = "button_still_present" if found else "button_gone"
    logger.info(f"STEAL SNIPER: snipe done - {taps} taps, result: {result} (score {score:.4f})")
    _set_status(
        state="searching",
        seconds_left=None,
        deadline_epoch=None,
        button_pos=None,
        last_result=result,
        snipes_attempted=_status["snipes_attempted"] + 1,
        taps_last_snipe=taps,
    )
    return {"state": "searching", "last_result": result, "taps": taps,
            "newly_locked": newly_locked}


if __name__ == "__main__":
    # Standalone test: run the sniper loop directly (no daemon)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    adb = ADBHelper()
    win = WindowsScreenshotHelper()
    print("Steal sniper standalone - Ctrl+C to stop")
    while True:
        result = sniper_tick(adb, win, debug=True)
        status = get_sniper_status()
        print(f"  {result.get('state')} | seconds_left={status.get('seconds_left')} | {result}")
        time.sleep(2.0)
