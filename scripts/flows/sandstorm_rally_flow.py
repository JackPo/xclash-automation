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

    # Tapping the icon re-centers the WORLD map on the Sandflow Mine vortex.
    # Tap the vortex (now at screen center) to open its rally / info panel.
    time.sleep(2.0)
    VORTEX_CENTER = (1912, 1010)
    logger.info(f"[SANDSTORM] tapping vortex at {VORTEX_CENTER} to open rally options")
    adb.tap(*VORTEX_CENTER, source="flow:sandstorm:tap_vortex")
    time.sleep(1.8)

    # The Sandflow Mine is ATTACKED (not rallied): its panel has an ATTACK button.
    # Threshold 0.03 (was 0.08): REAL attack buttons score 0.0014-0.0021; the
    # 0.069-0.076 "hits" were FALSE positives on an overlapping castle's UI
    # (Class Skill / shield / Appearance row) - clicking them attacked the
    # castle and march always failed (bimodal score data, 2026-07-12). 0.03
    # sits in the wide gap.
    def _find_attack(frm: Any) -> tuple[int, int] | None:
        for tpl, thr in [("royal_city_attack_button_4k.png", 0.03), ("attack_button_4k.png", 0.03)]:
            af, as_, ac = match_template(frm, tpl, search_region=(1500, 1450, 900, 550), threshold=thr)
            logger.info(f"[SANDSTORM] attack-button '{tpl}': found={af} score={as_:.4f} center={ac}")
            if af and ac is not None:
                return ac
        return None

    frame = win.get_screenshot_cv2()

    # CHOOSER FIRST (2026-07-12): tapping the vortex usually pops the "You want
    # to choose?" overlap menu listing the Phantom + an overlapping castle. We
    # MUST pick "Sandstorm Phantom" here first - otherwise the attack-button
    # matcher false-positives on the castle's UI (measured 0.068 on the chooser
    # frame), the flow attacks the CASTLE, and march fails. Phantom TEXT is
    # search-matched so it survives the level number changing width.
    pf, ps, pc = match_template(
        frame, "sandstorm_phantom_text_4k.png",
        search_region=(1450, 1080, 950, 260), threshold=0.06,
    )
    logger.info(f"[SANDSTORM] chooser Sandstorm-Phantom-text: found={pf} score={ps:.4f} center={pc}")
    if pf and pc is not None:
        logger.info(f"[SANDSTORM] chooser present - clicking Sandstorm Phantom at {pc}")
        adb.tap(*pc, source="flow:sandstorm:choose_phantom")
        time.sleep(1.8)
        frame = win.get_screenshot_cv2()

    attack_center = _find_attack(frame)

    if attack_center is None:
        logger.info("[SANDSTORM] no ATTACK button (and no chooser) - backing out (screen now captured)")
        return_to_base_view(adb, win, target=ViewState.WORLD)
        result["stop_reason"] = "captured_backed_out"
        return result

    logger.info(f"[SANDSTORM] clicking ATTACK at {attack_center}")
    adb.tap(*attack_center, source="flow:sandstorm:attack_button")
    time.sleep(1.8)

    # Deploy/March screen: click the March button to actually launch the attack
    # (the army is pre-configured on this screen). This is the step that was
    # missing - the flow used to just capture this screen and back out.
    frame = win.get_screenshot_cv2()
    mf, ms, mc = match_template(frame, "march_button_4k.png", search_region=(1500, 1550, 900, 350), threshold=0.10)
    logger.info(f"[SANDSTORM] march-button: found={mf} score={ms:.4f} center={mc}")
    if mf and mc is not None:
        logger.info(f"[SANDSTORM] clicking MARCH at {mc} - LAUNCHING attack")
        adb.tap(*mc, source="flow:sandstorm:march")
        time.sleep(1.5)
        # Don't re-attack the same phantom immediately (it goes on cooldown).
        try:
            from datetime import datetime, timedelta
            from utils.scheduler import get_scheduler
            get_scheduler().mark_exhausted("sandstorm_rally", datetime.now() + timedelta(minutes=20))
        except Exception as e:
            logger.debug(f"[SANDSTORM] mark_exhausted failed: {e}")
        return_to_base_view(adb, win, target=ViewState.WORLD)
        result["success"] = True
        result["stop_reason"] = "attack_launched"
        logger.info(f"[SANDSTORM] done (ATTACK LAUNCHED): {result}")
        return result

    logger.info("[SANDSTORM] March button not found on deploy screen - backing out (no launch)")
    return_to_base_view(adb, win, target=ViewState.WORLD)
    result["stop_reason"] = "deploy_no_march"
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from utils.adb_helper import ADBHelper
    print(sandstorm_rally_flow(ADBHelper(), WindowsScreenshotHelper()))
