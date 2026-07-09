"""
Quick Production flow - use the Quick Production class skill.

This flow:
1. Apply Minister of Domestic Affairs title (+100% resource output)
2. Navigates to WORLD view (from TOWN)
3. Clicks on own castle to open the castle popup
4. Clicks the "Class Skill" button
5. Waits for Class Skill panel to open
6. Clicks the "Quick Production" Use button
7. VERIFIES reward popup appeared (proof skill was used)
8. Returns to base view

Quick Production grants 24 hours of wheat, iron, and gold production instantly.
With Minister of Domestic Affairs title, output is doubled.
Cooldown: ~23.5 hours between uses.

Templates:
- class_skill_header_4k.png (690x92) - panel header verification
- class_skill_button_4k.png (200x160) - button in castle popup
- quick_production_reward_4k.png - reward popup verification
"""
from __future__ import annotations

import cv2
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from config import (
    QUICK_PROD_CASTLE_CLICK,
    QUICK_PROD_CLASS_SKILL_CLICK,
    QUICK_PROD_CLASS_SKILL_REGION,
    QUICK_PROD_HEADER_REGION,
)
from utils.template_matcher import match_template
from utils.view_state_detector import detect_view, ViewState, go_to_town, go_to_world
from utils.return_to_base_view import return_to_base_view
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.current_state import update_quick_production
from scripts.flows.title_management_flow import title_management_flow

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

# Template matching thresholds
CLASS_SKILL_BUTTON_THRESHOLD = 0.05
CLASS_SKILL_HEADER_THRESHOLD = 0.05

# Debug screenshot directory
DEBUG_DIR = Path(__file__).parent.parent.parent / "screenshots" / "debug" / "quick_prod"


def _save_debug_screenshot(win: WindowsScreenshotHelper, step: str) -> None:
    """Save a debug screenshot with timestamp."""
    from config import DEBUG_SCREENSHOTS_ENABLED
    if not DEBUG_SCREENSHOTS_ENABLED:  # action-capture is the sole screenshot system now
        return
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    frame = win.get_screenshot_cv2()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = DEBUG_DIR / f"{ts}_{step}.png"
    cv2.imwrite(str(path), frame)
    print(f"    [QUICK-PROD] Screenshot: {path.name}")


def quick_production_flow(
    adb: ADBHelper,
    win: WindowsScreenshotHelper | None = None,
    debug: bool = False
) -> bool | dict:
    """
    Use the Quick Production class skill.

    Flow: TOWN -> WORLD (centers on castle) -> click center -> Class Skill -> Quick Production Use

    IMPORTANT: Must go TOWN -> WORLD to center the map on own castle.
    After centering, castle is at screen center (1920, 1080).

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (optional)
        debug: Enable debug output (default False)

    Returns:
        bool: True if Quick Production was successfully used AND verified
    """
    if win is None:
        win = WindowsScreenshotHelper()

    print("    [QUICK-PROD] Starting Quick Production flow...")

    # Always save screenshots for this important daily flow
    _save_debug_screenshot(win, "00_initial")

    try:
        # PRE-CHECK cooldown BEFORE touching the user's title. Quick Production
        # applies the Minister of Domestic Affairs title (+100% output) to double
        # the reward - but that title swap must only happen when QP is actually
        # going to fire. Otherwise every cooldown-skip run would hijack the user's
        # title for nothing. This read-only check does NOT apply any title.
        print("    [QUICK-PROD] Pre-check: reading Quick Production cooldown (no title change)...")
        precheck = verify_quick_production_cooldown_flow(adb, win, debug=debug)
        remaining = precheck.get("remaining_seconds")
        if not precheck.get("ok"):
            print(f"    [QUICK-PROD] Availability unknown ({precheck.get('reason')}) - NOT applying title, retry later")
            return {"success": False, "skipped": True, "reason": precheck.get("reason"),
                    "cooldown_seconds": 1800}
        if remaining and remaining > 0:
            hrs, mins = remaining // 3600, (remaining % 3600) // 60
            print(f"    [QUICK-PROD] On cooldown ~{hrs}h{mins}m - skipping, title left untouched")
            return {"success": False, "skipped": True, "on_cooldown": True,
                    "cooldown_seconds": remaining + 300, "raw_text": precheck.get("raw_text")}
        print("    [QUICK-PROD] Available -> proceeding (title swap is now warranted)")

        # Step 0: Apply Minister of Domestic Affairs title for +100% resource output
        # Note: return_to_base=False because go_to_town() below is more reliable
        # (return_to_base_view can exit early if user activity is detected)
        print("    [QUICK-PROD] Step 0: Applying Minister of Domestic Affairs title...")
        title_result = title_management_flow(
            adb, "minister_of_domestic_affairs", win,
            debug=debug, return_to_base=False
        )
        if title_result:
            print("    [QUICK-PROD] Title applied successfully!")
        else:
            print("    [QUICK-PROD] WARNING: Could not apply title, proceeding anyway...")
        time.sleep(0.5)
        _save_debug_screenshot(win, "01_after_title")

        # Steps 1-4: TOWN -> WORLD -> castle click -> verify popup
        # This sequence is wrapped in a retry loop because clicking (1920, 1080)
        # can sometimes hit rally markers or other world elements instead of castle
        MAX_CASTLE_CLICK_RETRIES = 3
        button_found = False
        center = None

        for castle_retry in range(MAX_CASTLE_CLICK_RETRIES):
            if castle_retry > 0:
                print(f"    [QUICK-PROD] Retry {castle_retry}/{MAX_CASTLE_CLICK_RETRIES-1}: Wrong popup detected, retrying TOWN->WORLD->castle sequence...")
                _save_debug_screenshot(win, f"retry{castle_retry}_before_town")

            # Step 1: Go to TOWN first (required for centering)
            print("    [QUICK-PROD] Step 1: Going to TOWN...")
            go_to_town(adb, debug=False)
            time.sleep(1.0)
            _save_debug_screenshot(win, f"02_town" if castle_retry == 0 else f"retry{castle_retry}_town")

            # Step 2: Go to WORLD - this centers the map on own castle
            print("    [QUICK-PROD] Step 2: Going to WORLD (centers on castle)...")
            go_to_world(adb, debug=False)
            time.sleep(1.0)
            _save_debug_screenshot(win, f"03_world" if castle_retry == 0 else f"retry{castle_retry}_world")

            # Step 3: Click on own castle to open castle popup
            # After TOWN->WORLD, castle is centered - use config position
            print(f"    [QUICK-PROD] Step 3: Clicking castle at {QUICK_PROD_CASTLE_CLICK}...")
            adb.tap(*QUICK_PROD_CASTLE_CLICK, source="flow:quick_prod:castle")
            time.sleep(1.5)  # Give popup time to appear
            _save_debug_screenshot(win, f"04_castle_popup" if castle_retry == 0 else f"retry{castle_retry}_popup")

            # Step 4: Find and click Class Skill button (poll up to 3 seconds)
            print("    [QUICK-PROD] Step 4: Looking for Class Skill button...")
            score = 1.0
            for attempt in range(6):
                frame = win.get_screenshot_cv2()
                found, score, center = match_template(
                    frame, "class_skill_button_4k.png",
                    threshold=CLASS_SKILL_BUTTON_THRESHOLD
                )
                if found:
                    button_found = True
                    print(f"    [QUICK-PROD] Class Skill button found at {center} (score={score:.4f}, attempt {attempt+1})")
                    break
                time.sleep(0.5)

            if button_found:
                break  # Success! Exit retry loop

            # Class Skill button not found - we likely clicked something wrong
            print(f"    [QUICK-PROD] Class Skill button not found (score={score:.4f}) - wrong popup?")
            _save_debug_screenshot(win, f"retry{castle_retry}_wrong_popup")

            # Dismiss whatever popup appeared by returning to base view
            print("    [QUICK-PROD] Dismissing wrong popup...")
            return_to_base_view(adb, win, debug=False)
            time.sleep(0.5)

        if not button_found:
            print(f"    [QUICK-PROD] FAILED: Class Skill button not found after {MAX_CASTLE_CLICK_RETRIES} attempts")
            _save_debug_screenshot(win, "FAIL_no_class_skill_button")
            return_to_base_view(adb, win, debug=False)
            return False

        adb.tap(*center, source="flow:quick_prod:class_skill")
        time.sleep(1.0)

        # Step 5: Wait for Class Skill panel to open (poll up to 3 seconds)
        print("    [QUICK-PROD] Step 5: Waiting for Class Skill panel...")
        panel_found = False
        frame = None
        for attempt in range(6):
            time.sleep(0.5)
            frame = win.get_screenshot_cv2()
            found, score, _ = match_template(
                frame, "class_skill_header_4k.png",
                threshold=CLASS_SKILL_HEADER_THRESHOLD
            )
            if found:
                panel_found = True
                print(f"    [QUICK-PROD] Class Skill panel open (score={score:.4f}, attempt {attempt+1})")
                break

        if not panel_found:
            print(f"    [QUICK-PROD] FAILED: Class Skill panel not found after 3s (score={score:.4f})")
            _save_debug_screenshot(win, "FAIL_no_class_skill_panel")
            return_to_base_view(adb, win, debug=False)
            return False

        _save_debug_screenshot(win, "05_class_skill_panel")

        # Step 6: Find Quick Production icon to get its row position
        print("    [QUICK-PROD] Step 6: Looking for Quick Production icon...")

        qp_found, qp_score, qp_center = match_template(
            frame, "quick_production_icon_4k.png",
            threshold=0.15
        )

        if not qp_found:
            print(f"    [QUICK-PROD] FAILED: Quick Production icon not found (score={qp_score:.4f})")
            _save_debug_screenshot(win, "FAIL_no_qp_icon")
            return_to_base_view(adb, win, debug=False)
            return False

        qp_y = qp_center[1]
        print(f"    [QUICK-PROD] Quick Production icon at {qp_center} (score={qp_score:.4f})")

        # Step 7: Availability check via OCR. When on cooldown the row shows a
        # COUNTDOWN TIMER, not a Use button. Blindly clicking (the old behavior)
        # just taps the timer -> nothing happens -> the flow "fails" and the daemon
        # retries every 15 min forever (this ran 40+ times in one day). So OCR the
        # row first: a readable countdown = on cooldown -> skip until it expires.
        # Only click Use when there is genuinely no timer.
        print("    [QUICK-PROD] Step 7: Checking availability (OCR cooldown)...")
        use_search_region = (1920, qp_y - 60, 800, 120)  # x, y, w, h

        from utils.ocr_client import ocr_extract_text
        cooldown_text = ocr_extract_text(
            frame, region=use_search_region,
            prompt=("Read the cooldown timer if one is shown. Examples: '23h 12m', "
                    "'1d 4h', '05:14:32'. If there is no timer (e.g. a 'Use' button "
                    "is shown instead), return 'none'. Return only the time string or 'none'."),
        )
        remaining = _parse_cooldown_text(cooldown_text)
        print(f"    [QUICK-PROD] OCR row text={cooldown_text!r} -> remaining={remaining}")

        if remaining and remaining > 0:
            # Genuinely on cooldown. Record the REAL wait so the daemon doesn't
            # re-run until it's actually ready (re-check 5 min after expiry).
            hrs, mins = remaining // 3600, (remaining % 3600) // 60
            print(f"    [QUICK-PROD] On cooldown ~{hrs}h{mins}m - skipping until ready (no click)")
            _save_debug_screenshot(win, "07_on_cooldown")
            return_to_base_view(adb, win, debug=False)
            return {"success": False, "skipped": True, "on_cooldown": True,
                    "cooldown_seconds": remaining + 300, "raw_text": cooldown_text}

        # Not on cooldown per OCR -> find and click the Use button.
        use_found, use_score, use_center = match_template(
            frame, "class_skill_use_button_4k.png",
            search_region=use_search_region,
            threshold=0.10  # tighter than before (0.15 let a timer false-match as a button)
        )

        if not use_found:
            # No timer read AND no Use button - ambiguous. Skip 30 min rather than
            # hammer a 15-min fail loop.
            print(f"    [QUICK-PROD] No Use button (score={use_score:.4f}) and no readable cooldown - skipping 30 min")
            _save_debug_screenshot(win, "FAIL_no_use_no_cooldown")
            return_to_base_view(adb, win, debug=False)
            return {"success": False, "skipped": True, "reason": "no_use_no_cooldown",
                    "cooldown_seconds": 1800}

        print(f"    [QUICK-PROD] Use button found at {use_center} (score={use_score:.4f}), clicking...")
        adb.tap(*use_center, source="flow:quick_prod:use")
        time.sleep(1.5)

        # Step 8: VERIFY reward popup appeared - THIS IS CRITICAL
        print("    [QUICK-PROD] Step 8: Verifying reward popup...")
        frame = win.get_screenshot_cv2()
        _save_debug_screenshot(win, "06_after_use_click")

        # Check for "Congratulations" text or reward popup
        # The reward popup shows Gold/Wheat/Iron icons with amounts
        # Look for the "Tap to Close" text or congratulations header
        reward_verified = False

        # Try matching congratulations popup (we need to create this template if it doesn't exist)
        # For now, check if the Class Skill panel is GONE (popup replaced it)
        panel_gone, panel_score, _ = match_template(
            frame, "class_skill_header_4k.png",
            threshold=CLASS_SKILL_HEADER_THRESHOLD
        )

        if not panel_gone:
            # Panel is gone, something else is on screen - likely reward popup
            reward_verified = True
            print(f"    [QUICK-PROD] Reward popup detected (panel gone, score={panel_score:.4f})")
        else:
            # Panel still visible - click might not have worked
            print(f"    [QUICK-PROD] WARNING: Class Skill panel still visible (score={panel_score:.4f})")
            # Try clicking Use again
            print("    [QUICK-PROD] Retrying Use button click...")
            adb.tap(*use_center, source="flow:quick_prod:use_retry")
            time.sleep(1.5)
            frame = win.get_screenshot_cv2()
            _save_debug_screenshot(win, "07_after_retry")

            panel_gone2, panel_score2, _ = match_template(
                frame, "class_skill_header_4k.png",
                threshold=CLASS_SKILL_HEADER_THRESHOLD
            )
            if not panel_gone2:
                reward_verified = True
                print(f"    [QUICK-PROD] Reward popup detected on retry (score={panel_score2:.4f})")

        if not reward_verified:
            print("    [QUICK-PROD] FAILED: Could not verify reward popup - skill may not have been used!")
            _save_debug_screenshot(win, "FAIL_no_reward_popup")
            return_to_base_view(adb, win, debug=False)
            return False

        # Step 9: Tap to close reward popup
        print("    [QUICK-PROD] Step 9: Closing reward popup...")
        adb.tap(1920, 1500, source="flow:quick_prod:close")
        time.sleep(0.5)
        _save_debug_screenshot(win, "08_after_close")

        # Step 10: Return to base view
        print("    [QUICK-PROD] Step 10: Returning to base view...")
        return_to_base_view(adb, win, debug=False)
        _save_debug_screenshot(win, "09_final")

        # Update state with next available time (24 hours from now)
        update_quick_production(success=True)

        print("    [QUICK-PROD] SUCCESS - Quick Production used and verified!")
        return True

    except Exception as e:
        print(f"    [QUICK-PROD] ERROR: {e}")
        _save_debug_screenshot(win, f"ERROR_{type(e).__name__}")
        try:
            return_to_base_view(adb, win, debug=False)
        except Exception as nav_err:
            print(f"    [QUICK-PROD] return_to_base_view failed during cleanup: {nav_err}")
        return False


# ============================================================================
# Cooldown verification (no-side-effect flow)
# ============================================================================

import re
from typing import Optional


def _parse_cooldown_text(text: str) -> int | None:
    """
    Parse cooldown text like "23h 12m", "23:45:12", "1d 2h", "Available" etc.
    Returns seconds remaining, or None if the text indicates "available now"
    or can't be parsed.
    """
    t = text.strip().lower()
    if not t:
        return None
    if any(word in t for word in ("available", "use", "ready", "now")):
        return 0
    # 23:45:12 or 23:45
    m = re.search(r"(\d+):(\d{1,2})(?::(\d{1,2}))?", t)
    if m:
        h = int(m.group(1)); mn = int(m.group(2)); s = int(m.group(3) or 0)
        return h * 3600 + mn * 60 + s
    # "1d 2h 3m" - allow any subset
    total = 0
    found_any = False
    for amt, unit in re.findall(r"(\d+)\s*([dhms])", t):
        found_any = True
        amt_i = int(amt)
        if unit == "d": total += amt_i * 86400
        elif unit == "h": total += amt_i * 3600
        elif unit == "m": total += amt_i * 60
        elif unit == "s": total += amt_i
    return total if found_any else None


# Class Skill panel layout (4K): three skill rows evenly spaced, Quick Production
# is row 3. Anchor off the QP icon and step up by the pitch for rows 2 and 1.
CLASS_SKILL_ROW_PITCH = 348
CLASS_SKILL_QP_ROW_FALLBACK_CY = 1411


def _open_class_skill_panel(adb: ADBHelper, win: WindowsScreenshotHelper, tag: str = "cskills"):
    """Navigate TOWN->WORLD->castle->Class Skill button and wait for the panel.

    Returns (ok, frame, reason). Leaves the panel OPEN on success (caller must
    return_to_base_view afterwards).
    """
    go_to_town(adb, debug=False)
    time.sleep(1.0)
    go_to_world(adb, debug=False)
    time.sleep(1.0)

    center = None
    for retry in range(3):
        if retry > 0:
            go_to_town(adb, debug=False); time.sleep(1.0)
            go_to_world(adb, debug=False); time.sleep(1.0)
        adb.tap(*QUICK_PROD_CASTLE_CLICK, source=f"flow:{tag}:castle")
        time.sleep(1.5)
        frame = win.get_screenshot_cv2()
        found, _score, center = match_template(
            frame, "class_skill_button_4k.png", threshold=CLASS_SKILL_BUTTON_THRESHOLD,
        )
        if found:
            break
        return_to_base_view(adb, win, debug=False)
        time.sleep(0.5)
    else:
        return False, None, "castle popup did not open (protection mode? wrong centering?)"

    adb.tap(*center, source=f"flow:{tag}:class_skill")
    time.sleep(1.0)

    panel_score = 1.0
    for _attempt in range(6):
        time.sleep(0.5)
        frame = win.get_screenshot_cv2()
        panel_found, panel_score, _ = match_template(
            frame, "class_skill_header_4k.png", threshold=CLASS_SKILL_HEADER_THRESHOLD,
        )
        if panel_found:
            return True, frame, None
    return False, None, f"Class Skill panel did not open (score={panel_score:.4f})"


def _parse_skill_block(block_text: str):
    """Split a class-skill OCR block into (name, effect, cooldown_spec)."""
    lines = [l.strip() for l in (block_text or "").split("\n") if l.strip()]
    name = lines[0] if lines else ""
    effect = next((l for l in lines if l.lower().startswith("upon use")), "")
    cooldown = next((l for l in lines if "cooldown" in l.lower()), "")
    return name, effect, cooldown


def read_class_skills(adb: ADBHelper, win: WindowsScreenshotHelper | None = None,
                      debug: bool = False) -> dict:
    """Open the Class Skill panel and OCR ALL skills: effect (description) + the
    current cooldown status (Ready or countdown). Records the readout to state
    (utils.current_state.update_class_skills) for the dashboard portal.

    Returns {"ok": bool, "skills": [{name, effect, cooldown, status,
    remaining_seconds, ready}, ...], "reason": str|None}.
    """
    if win is None:
        win = WindowsScreenshotHelper()
    from utils.ocr_client import ocr_extract_text
    from utils.current_state import update_class_skills

    try:
        ok, frame, reason = _open_class_skill_panel(adb, win, tag="cskills")
        if not ok:
            return_to_base_view(adb, win, debug=False)
            return {"ok": False, "skills": [], "reason": reason}

        # Anchor row 3 (Quick Production) via its icon; step up by pitch for 2 & 1.
        qp_found, _qs, qp_center = match_template(
            frame, "quick_production_icon_4k.png", threshold=0.15,
        )
        qp_cy = qp_center[1] if qp_found else CLASS_SKILL_QP_ROW_FALLBACK_CY
        rows_cy = [qp_cy - 2 * CLASS_SKILL_ROW_PITCH, qp_cy - CLASS_SKILL_ROW_PITCH, qp_cy]

        skills = []
        for cy in rows_cy:
            block = ocr_extract_text(
                frame, region=(1590, cy - 135, 660, 260),
                prompt=("Read all text in this class skill entry verbatim: the skill "
                        "name, its description, and the Cooldown line. Return the text."),
            )
            status = ocr_extract_text(
                frame, region=(1590, cy + 38, 440, 82),
                prompt=("Read the status: either the word 'Ready' or a countdown like "
                        "'05:14:32' or '23h 12m'. Return only that."),
            )
            name, effect, cooldown = _parse_skill_block(block)
            remaining = _parse_cooldown_text(status)
            # Persist the ABSOLUTE expected-completion timestamp, not just a
            # duration snapshot - so the portal computes ready/countdown LIVE
            # (a skill read 7h ago with a 3h cooldown then correctly shows READY),
            # instead of freezing a stale value + stale ready flag.
            from datetime import datetime, timezone, timedelta
            if remaining is None:
                completion_time = None            # OCR couldn't read it -> unknown
                ready_now = False
            elif remaining <= 0:
                completion_time = datetime.now(timezone.utc).isoformat()
                ready_now = True
            else:
                completion_time = (datetime.now(timezone.utc) + timedelta(seconds=remaining)).isoformat()
                ready_now = False
            skills.append({
                "name": name, "effect": effect, "cooldown": cooldown,
                "status": (status or "").strip(),
                "remaining_seconds": remaining,
                "completion_time": completion_time,  # absolute ISO; portal computes live
                "ready": ready_now,                  # read-time value; portal recomputes vs now
            })
            print(f"    [CSKILLS] {name!r} status={status!r} remaining={remaining} completion={completion_time}")

        update_class_skills(skills)
        return_to_base_view(adb, win, debug=False)
        return {"ok": True, "skills": skills, "reason": None}

    except Exception as e:
        print(f"    [CSKILLS] ERROR: {e}")
        try:
            return_to_base_view(adb, win, debug=False)
        except Exception as nav_err:
            print(f"    [CSKILLS] return_to_base_view failed during cleanup: {nav_err}")
        return {"ok": False, "skills": [], "reason": f"exception: {e}"}


def verify_quick_production_cooldown_flow(
    adb: ADBHelper,
    win: WindowsScreenshotHelper | None = None,
    debug: bool = False,
) -> dict:
    """Read-only Quick Production cooldown check. Now reads the WHOLE Class Skill
    panel (all skills + effects + timers, recorded to state for the dashboard) via
    read_class_skills, and returns the Quick Production entry in the original
    format for backward compatibility (dashboard "Mark Done", the QP pre-check).

    Returns {"ok", "remaining_seconds", "raw_text", "reason"}.
    """
    result = read_class_skills(adb, win, debug=debug)
    if not result.get("ok"):
        return {"ok": False, "remaining_seconds": None, "raw_text": None,
                "reason": result.get("reason")}
    qp = next((s for s in result["skills"] if "quick production" in s["name"].lower()), None)
    if qp is None:
        return {"ok": False, "remaining_seconds": None, "raw_text": None,
                "reason": "Quick Production row not found in panel readout"}
    return {"ok": True, "remaining_seconds": qp["remaining_seconds"],
            "raw_text": qp["status"], "reason": None}
