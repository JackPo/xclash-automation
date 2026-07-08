#!/usr/bin/env python3
"""
Sandstorm / Union Rally Point rally flow.

On the WORLD map a "Union Rally Point" appears as a swirling brown sandstorm
vortex with a glowing red eye, ringed by a thin yellow-green circle (level badge
above it). Tapping it opens a rally screen; the user wants to start a rally from it.

STATUS: CAPTURE MODE. We have not yet seen the screen that opens after tapping the
vortex, so this flow currently only TAPS the vortex and BACKS OUT (it does NOT
commit a rally). The tap goes through ADBHelper, so the action-capture system
records the before-shot + an after-burst of the next screen. Once that next screen
is known, fill in the rally sequence (rally-flag / deploy) below where marked.

Template: sandstorm_rally_4k.png (the ringed red-eye vortex; number badge excluded).
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
from utils.return_to_base_view import return_to_base_view
from utils.view_state_detector import detect_view, ViewState

logger = logging.getLogger("sandstorm_rally_flow")

SANDSTORM_TEMPLATE = "sandstorm_rally_4k.png"
SANDSTORM_THRESHOLD = 0.10   # animated vortex; empty map scored ~0.21, so 0.10 is safe-ish
# The sandstorm/Union Rally Point is an EVENT ICON in the left toolbar row (same
# fixed-Y row as the cobra icon); its X shifts as icons come/go, so search only
# that horizontal strip - not the whole screen (avoids false matches on the map).
SANDSTORM_SEARCH_REGION = (30, 1428, 520, 104)


def sandstorm_rally_flow(adb: Any, win: WindowsScreenshotHelper | None = None) -> dict[str, Any]:
    """Tap the Union Rally Point vortex to capture the next screen, then back out.

    Returns {"tapped": bool, "success": bool, "stop_reason": str, "center": tuple|None}.
    """
    win = win or WindowsScreenshotHelper()
    result: dict[str, Any] = {"tapped": False, "success": True, "stop_reason": "", "center": None}

    frame = win.get_screenshot_cv2()
    state, _ = detect_view(frame)
    if state != ViewState.WORLD:
        logger.info(f"[SANDSTORM] not in WORLD ({state}) - navigating there")
        return_to_base_view(adb, win, target=ViewState.WORLD)
        time.sleep(1.0)
        frame = win.get_screenshot_cv2()

    found, score, center = match_template(frame, SANDSTORM_TEMPLATE,
                                          search_region=SANDSTORM_SEARCH_REGION,
                                          threshold=SANDSTORM_THRESHOLD)
    logger.info(f"[SANDSTORM] scan: found={found} score={score:.4f} center={center}")
    if not found or center is None:
        result["stop_reason"] = "not_found"
        return result

    # Tap the vortex. This tap is recorded by action-capture (before-shot +
    # after-burst), which gives us the "next screen" we need to build the rally.
    logger.info(f"[SANDSTORM] tapping Union Rally Point at {center} (score={score:.4f}) - CAPTURE MODE")
    adb.tap(*center, source="flow:sandstorm:tap_rally_point")
    result["tapped"] = True
    result["center"] = center

    # Let the next screen render (and the after-burst finish capturing it).
    time.sleep(2.5)

    # === TODO (once the next screen is known): start the rally here instead of
    # backing out - e.g. poll for the rally-flag / deploy button and click it. ===

    # For now, back out WITHOUT committing a rally.
    return_to_base_view(adb, win, target=ViewState.WORLD)
    result["stop_reason"] = "captured_backed_out"
    logger.info(f"[SANDSTORM] done (capture mode): {result}")
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from utils.adb_helper import ADBHelper
    print(sandstorm_rally_flow(ADBHelper(), WindowsScreenshotHelper()))
