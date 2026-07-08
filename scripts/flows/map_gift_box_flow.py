#!/usr/bin/env python3
"""
Map Gift Box flow.

On the WORLD map, alliance members share treasure "gift boxes" (a red present with
a gold bow on an orange pin, with an "N/5" counter). Tapping one opens a
"Congratulations, you've got ..." reward popup; tapping that closes it and claims
the reward. This flow finds each gift box, taps it, claims the reward popup, and
repeats until none remain.

Detection is number/pin/overlap tolerant: map_gift_box_4k.png +
map_gift_box_mask_4k.png (an elliptical mask over the present core), so it matches
regardless of the counter, the pin, or partial overlap with neighbors.

Templates (templates/ground_truth/):
- map_gift_box_4k.png + map_gift_box_mask_4k.png  (the present, masked to its core)
- gift_claim_header_4k.png                         ("Congratulations, you've got" popup)
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.template_matcher import match_template
from utils.windows_screenshot_helper import WindowsScreenshotHelper

logger = logging.getLogger("map_gift_box_flow")

GIFT_BOX_TEMPLATE = "map_gift_box_4k.png"       # mask auto-detected (map_gift_box_mask_4k.png)
CLAIM_HEADER_TEMPLATE = "gift_claim_header_4k.png"
GIFT_BOX_THRESHOLD = 0.07   # loose: borderline/occluded boxes score ~0.05; a false hit self-corrects (no reward popup -> dismiss)
CLAIM_THRESHOLD = 0.06

# Tapping anywhere on the "Congratulations" popup claims + closes it. The
# "Tap to Close" strip sits below the reward icons.
CLAIM_CLOSE_TAP = (1920, 1290)

MAX_CLAIMS = 8            # safety cap per run
CLAIM_POLL_TIMEOUT = 3.0  # wait for the reward popup after tapping a gift box
POLL_INTERVAL = 0.5


def _claim_popup_present(win: WindowsScreenshotHelper, frame: Any = None) -> bool:
    frame = frame if frame is not None else win.get_screenshot_cv2()
    found, _s, _c = match_template(frame, CLAIM_HEADER_TEMPLATE, threshold=CLAIM_THRESHOLD)
    return found


def map_gift_box_flow(adb: Any, win: WindowsScreenshotHelper | None = None,
                      max_claims: int = MAX_CLAIMS) -> dict[str, Any]:
    """Tap and claim every shared gift box visible on the WORLD map.

    Returns {"claimed": int, "success": bool, "stop_reason": str}.
    Assumes the caller has already confirmed WORLD view + a gift box present.
    """
    win = win or WindowsScreenshotHelper()
    result: dict[str, Any] = {"claimed": 0, "success": True, "stop_reason": ""}

    for i in range(max_claims):
        frame = win.get_screenshot_cv2()

        # If a reward popup is already open (leftover), claim/close it first.
        if _claim_popup_present(win, frame):
            adb.tap(*CLAIM_CLOSE_TAP, source="flow:map_gift:claim_close")
            time.sleep(0.8)
            result["claimed"] += 1
            continue

        # Find a gift box (masked match - number/pin/overlap tolerant).
        found, score, center = match_template(frame, GIFT_BOX_TEMPLATE, threshold=GIFT_BOX_THRESHOLD)
        logger.info(f"[GIFT] scan {i+1}: found={found} score={score:.4f} center={center}")
        if not found or center is None:
            result["stop_reason"] = "no_more_gift_boxes"
            break

        # Tap the gift box.
        adb.tap(*center, source="flow:map_gift:open")

        # Poll for the "Congratulations" reward popup.
        deadline = time.time() + CLAIM_POLL_TIMEOUT
        got_popup = False
        while time.time() < deadline:
            time.sleep(POLL_INTERVAL)
            if _claim_popup_present(win):
                got_popup = True
                break

        if got_popup:
            adb.tap(*CLAIM_CLOSE_TAP, source="flow:map_gift:claim_close")
            time.sleep(0.8)
            result["claimed"] += 1
            logger.info(f"[GIFT] claimed #{result['claimed']}")
        else:
            # Tap didn't open a reward popup (mis-hit / not a gift box). Dismiss by
            # tapping open terrain above the target and stop to avoid a bad loop.
            logger.info("[GIFT] no reward popup after tap - dismissing, stopping")
            adb.tap(center[0], max(150, center[1] - 350), source="flow:map_gift:dismiss")
            time.sleep(0.6)
            result["stop_reason"] = "no_popup"
            break
    else:
        result["stop_reason"] = "hit_max_claims"

    logger.info(f"[GIFT] done: {result}")
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from utils.adb_helper import ADBHelper
    print(map_gift_box_flow(ADBHelper(), WindowsScreenshotHelper()))
