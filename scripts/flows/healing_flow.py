"""
Healing Flow - Heal wounded soldiers at the hospital.

Called when healing panel is ALREADY OPEN (icon_daemon clicked the bubble).

Args:
    target_hours: float - target healing time in hours (default 4.0)
"""

import sys
import time
import cv2
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.adb_helper import ADBHelper
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.ocr_client import OCRClient
from utils.hospital_header_matcher import is_panel_open
from utils.debug_screenshot import save_debug_screenshot

# Slider parameters (from Gemini detection)
SLIDER_Y = 696  # Center Y of slider bar
SLIDER_MIN_X = 1697  # Left edge of slider
SLIDER_MAX_X = 2208  # Right edge of slider (1697 + 511)
SEARCH_Y_START = 650
SEARCH_Y_END = 750
SEARCH_X_START = 1600
SEARCH_X_END = 2300

# Healing button time OCR
HEAL_BUTTON_POS = (1966, 1406)  # Top-left of button
HEAL_TIME_REGION = (50, 80, 280, 45)  # Relative offset for time text
HEAL_BUTTON_CENTER = (2150, 1480)  # Click position

# Plus/Minus buttons (from Gemini detection)
PLUS_BUTTON = (2263, 703)  # Plus button center
MINUS_BUTTON = (1618, 701)  # Minus button center

# Template path for slider circle
TEMPLATE_PATH = Path(__file__).parent.parent.parent / "templates" / "ground_truth" / "slider_circle_4k.png"

# Timeout protection
MAX_FLOW_TIME = 60  # 60 seconds max for entire flow

# Panel dismiss position (dark area outside panel)
DISMISS_TAP = (500, 500)


def _log(msg, debug=True):
    """Print timestamped log message."""
    if debug:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] [HEALING] {msg}", flush=True)


def find_circle(frame, template):
    """Find slider circle, return X coord or None."""
    search_region = frame[SEARCH_Y_START:SEARCH_Y_END, SEARCH_X_START:SEARCH_X_END]
    result = cv2.matchTemplate(search_region, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)

    if min_val < 0.1:
        template_h, template_w = template.shape[:2]
        return SEARCH_X_START + min_loc[0] + template_w // 2, min_val
    return None, min_val


def ocr_time(frame, ocr):
    """OCR healing time, return seconds and string."""
    x = HEAL_BUTTON_POS[0] + HEAL_TIME_REGION[0]
    y = HEAL_BUTTON_POS[1] + HEAL_TIME_REGION[1]
    w, h = HEAL_TIME_REGION[2], HEAL_TIME_REGION[3]

    crop = frame[y:y+h, x:x+w].copy()
    time_str = ocr.extract_text(crop).strip()

    try:
        parts = time_str.split(':')
        if len(parts) == 3:
            hr, mn, sc = int(parts[0]), int(parts[1]), int(parts[2])
            return hr * 3600 + mn * 60 + sc, time_str
    except:
        pass
    return None, time_str


def calculate_target_x_proportional(target_seconds, max_seconds):
    """Calculate target X position proportionally based on actual max time.

    Args:
        target_seconds: Desired healing time in seconds
        max_seconds: Maximum healing time (slider at max) in seconds

    Returns:
        Target X coordinate for slider
    """
    if max_seconds <= 0:
        return SLIDER_MAX_X

    ratio = target_seconds / max_seconds
    ratio = max(0.0, min(1.0, ratio))  # Clamp to [0, 1]

    slider_width = SLIDER_MAX_X - SLIDER_MIN_X
    target_x = SLIDER_MIN_X + int(ratio * slider_width)

    return target_x


def healing_flow(adb, target_hours=4.0, debug=False):
    """
    Heal wounded soldiers at the hospital.

    ASSUMES: Healing panel is already open (called from icon_daemon after bubble click).

    Args:
        adb: ADBHelper instance
        target_hours: float - target healing time in hours
        debug: bool - enable debug logging

    Returns:
        bool: True if healing started successfully
    """
    flow_start = time.time()

    def check_timeout():
        elapsed = time.time() - flow_start
        if elapsed > MAX_FLOW_TIME:
            _log(f"TIMEOUT: Flow exceeded {MAX_FLOW_TIME}s (elapsed={elapsed:.1f}s)", debug)
            return True
        return False

    win = WindowsScreenshotHelper()
    success = False

    _log(f"=== STARTING HEALING FLOW: target={target_hours:.2f}h ===", debug)

    target_seconds = int(target_hours * 3600)
    _log(f"Target time: {target_seconds}s ({target_hours}h)", debug)

    try:
        # Step 0: Verify panel is open
        _log("Step 0: Verifying hospital panel is open...", debug)

        if check_timeout():
            return False

        frame = win.get_screenshot_cv2()
        panel_open, score = is_panel_open(frame, debug=debug)

        if not panel_open:
            _log(f"Step 0 FAILED: Hospital panel not detected (score={score:.6f})", debug)
            save_debug_screenshot(frame, "healing", "FAIL_step0_panel_not_open")
            return False

        _log(f"Step 0 SUCCESS: Panel is open (score={score:.6f})", debug)

        # Wait for UI to fully render
        time.sleep(0.5)

        # Step 1: Load template and verify slider is visible
        _log("Step 1: Checking slider visibility...", debug)

        if check_timeout():
            return False

        template = cv2.imread(str(TEMPLATE_PATH))
        if template is None:
            _log("Step 1 FAILED: Could not load slider template", debug)
            return False

        frame = win.get_screenshot_cv2()
        circle_x, score = find_circle(frame, template)
        if circle_x is None:
            _log(f"Step 1 FAILED: Slider not visible (score={score:.4f})", debug)
            save_debug_screenshot(frame, "healing", "FAIL_step1_no_slider")
            return False
        _log(f"Step 1 SUCCESS: Slider visible at X={circle_x} (score={score:.4f})", debug)

        ocr = OCRClient()

        # Step 2: Push slider to MAX to read full time
        _log("Step 2: Push slider to MAX to read full time...", debug)

        if check_timeout():
            return False

        _log(f"  Swiping from X={circle_x} to X=2200", debug)
        adb.swipe(circle_x, SLIDER_Y, 2200, SLIDER_Y, duration=500)
        time.sleep(0.5)

        frame = win.get_screenshot_cv2()
        max_x, max_score = find_circle(frame, template)
        max_secs, max_str = ocr_time(frame, ocr)

        _log(f"  MAX position: X={max_x} (score={max_score:.4f})", debug)
        _log(f"  MAX time OCR: {max_str!r} -> {max_secs}s", debug)

        if max_secs is None or max_secs == 0:
            _log("Step 2 FAILED: Could not read max time from OCR", debug)
            save_debug_screenshot(frame, "healing", "FAIL_step2_no_max_time")
            return False

        _log(f"Step 2 SUCCESS: MAX time = {max_str} ({max_secs}s)", debug)

        # Check if target exceeds max
        if target_seconds >= max_secs:
            _log(f"Target ({target_hours}h = {target_seconds}s) >= max ({max_secs}s), using max", debug)
            _log("Step 3-4 SKIPPED: Already at max, clicking Heal directly", debug)
            _log(f"Step 5: Clicking Heal button at ({HEAL_BUTTON_CENTER[0]}, {HEAL_BUTTON_CENTER[1]})...", debug)
            adb.tap(HEAL_BUTTON_CENTER[0], HEAL_BUTTON_CENTER[1])
            time.sleep(0.5)
            _log("Step 5 SUCCESS: Heal button clicked", debug)
            success = True
            return True

        # Step 3: Calculate target X and drag slider
        target_x = calculate_target_x_proportional(target_seconds, max_secs)
        ratio = target_seconds / max_secs
        _log(f"Step 3: Drag slider to target X={target_x} (ratio={ratio:.2%})", debug)

        if check_timeout():
            return False

        # Iterative drag (max 5 attempts)
        for drag_attempt in range(5):
            if check_timeout():
                return False

            frame = win.get_screenshot_cv2()
            circle_x, circle_score = find_circle(frame, template)

            if circle_x is None:
                _log(f"  [{drag_attempt+1}] WARNING: Circle not found (score={circle_score:.4f})", debug)
                time.sleep(0.3)
                continue

            current_secs, current_str = ocr_time(frame, ocr)
            if current_secs is None:
                _log(f"  [{drag_attempt+1}] WARNING: OCR failed, raw={current_str!r}", debug)
                time.sleep(0.3)
                continue

            diff = current_secs - target_seconds
            _log(f"  [{drag_attempt+1}] X={circle_x}, time={current_str} ({current_secs}s), diff={diff}s ({diff/60:.1f}min)", debug)

            # If under target, done with dragging
            if diff < 0:
                _log(f"  Under target by {-diff}s, moving to fine-tune", debug)
                break

            # If within 5 minutes, done with dragging
            if abs(diff) <= 300:
                _log(f"  Within 5min tolerance (diff={diff}s), moving to fine-tune", debug)
                break

            # Drag to target
            _log(f"  Swiping from X={circle_x} to X={target_x}", debug)
            adb.swipe(circle_x, SLIDER_Y, target_x, SLIDER_Y, duration=500)
            time.sleep(0.5)

        _log("Step 3 DONE: Coarse drag complete", debug)

        # Step 4: Fine-tune with minus button to get just UNDER target
        _log("Step 4: Fine-tune with minus button to get UNDER target...", debug)

        if check_timeout():
            return False

        fine_tune_success = False
        for i in range(50):
            if check_timeout():
                return False

            frame = win.get_screenshot_cv2()
            current_secs, current_str = ocr_time(frame, ocr)

            if current_secs is None:
                _log(f"  [{i+1}] WARNING: OCR failed, raw={current_str!r}", debug)
                time.sleep(0.3)
                continue

            diff = current_secs - target_seconds

            if current_secs < target_seconds:
                # Under target - done!
                _log(f"  [{i+1}] SUCCESS: {current_str} ({current_secs}s) - under target by {-diff}s", debug)
                fine_tune_success = True
                break

            # Over target - click minus
            if i % 5 == 0:
                _log(f"  [{i+1}] {current_str} ({current_secs}s) - over by {diff}s, clicking minus", debug)
            adb.tap(MINUS_BUTTON[0], MINUS_BUTTON[1])
            time.sleep(0.25)

        if fine_tune_success:
            _log("Step 4 SUCCESS: Fine-tuning complete", debug)
        else:
            _log("Step 4 WARNING: Fine-tuning loop exhausted (50 iterations)", debug)
            frame = win.get_screenshot_cv2()
            save_debug_screenshot(frame, "healing", "WARN_step4_fine_tune_exhausted")

        # Step 5: Click Heal button
        _log(f"Step 5: Clicking Heal button at ({HEAL_BUTTON_CENTER[0]}, {HEAL_BUTTON_CENTER[1]})...", debug)

        if check_timeout():
            return False

        adb.tap(HEAL_BUTTON_CENTER[0], HEAL_BUTTON_CENTER[1])
        time.sleep(0.5)

        # Validation: Take screenshot after clicking Heal to verify
        frame = win.get_screenshot_cv2()
        save_debug_screenshot(frame, "healing", "after_heal_click")
        _log("Step 5 SUCCESS: Heal button clicked", debug)

        success = True
        return True

    except Exception as e:
        _log(f"EXCEPTION: {type(e).__name__}: {e}", True)
        try:
            frame = win.get_screenshot_cv2()
            save_debug_screenshot(frame, "healing", f"EXCEPTION_{type(e).__name__}")
        except:
            pass
        return False

    finally:
        # ALWAYS close panel
        elapsed = time.time() - flow_start
        _log(f"Closing panel (elapsed={elapsed:.1f}s)...", debug)
        adb.tap(DISMISS_TAP[0], DISMISS_TAP[1])
        time.sleep(0.3)

        if success:
            _log(f"=== FLOW COMPLETE: SUCCESS (elapsed={elapsed:.1f}s) ===", debug)
        else:
            _log(f"=== FLOW COMPLETE: FAILED (elapsed={elapsed:.1f}s) ===", debug)


if __name__ == "__main__":
    adb = ADBHelper()
    success = healing_flow(adb, target_hours=4.0, debug=True)
    print(f"\nResult: {'SUCCESS' if success else 'FAILED'}")
