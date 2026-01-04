"""
Barracks Training Flow - Train soldiers at a specific level for a target time.

Called when training panel is ALREADY OPEN (icon_daemon clicked the bubble).

Args:
    soldier_level: int (3-8) - which soldier level to train (default 4)
    target_hours: float - target training time in hours (default 4.0)
    pack_resources: bool - whether to pack resources after (default True, NOT YET IMPLEMENTED)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING, Any

import numpy.typing as npt

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.ocr_client import OCRClient
from utils.soldier_training_header_matcher import is_panel_open
from utils.debug_screenshot import save_debug_screenshot
from scripts.flows.soldier_training_flow import find_and_click_soldier_level
from utils.soldier_panel_slider import (
    find_plus_button, drag_slider_to_max,
    MINUS_BUTTON, calculate_slider_position
)

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

# Train button time OCR
TRAIN_BUTTON_POS = (1969, 1399)
TRAIN_TIME_REGION = (50, 80, 280, 45)
TRAIN_BUTTON_CENTER = (2155, 1464)

# Timeout protection
MAX_FLOW_TIME = 60  # 60 seconds max for entire flow

# Panel dismiss position (dark area outside panel)
DISMISS_TAP = (500, 500)


def _log(msg: str, debug: bool = True) -> None:
    """Print timestamped log message."""
    if debug:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] [BARRACKS] {msg}", flush=True)


def ocr_time(
    frame: npt.NDArray[Any], ocr: OCRClient
) -> tuple[int | None, str]:
    """OCR training time, return seconds and string."""
    x = TRAIN_BUTTON_POS[0] + TRAIN_TIME_REGION[0]
    y = TRAIN_BUTTON_POS[1] + TRAIN_TIME_REGION[1]
    w, h = TRAIN_TIME_REGION[2], TRAIN_TIME_REGION[3]

    crop = frame[y:y+h, x:x+w].copy()
    time_str = ocr.extract_text(crop).strip()

    try:
        parts = time_str.split(':')
        if len(parts) == 3:
            hr, mn, sc = int(parts[0]), int(parts[1]), int(parts[2])
            return hr * 3600 + mn * 60 + sc, time_str
    except Exception:
        pass
    return None, time_str


def barracks_training_flow(
    adb: ADBHelper,
    soldier_level: int = 4,
    target_hours: float = 4.0,
    pack_resources: bool = True,
    debug: bool = False,
) -> bool:
    """
    Train soldiers at the barracks with configurable level and time.

    ASSUMES: Training panel is already open (called from icon_daemon after bubble click).

    Args:
        adb: ADBHelper instance
        soldier_level: int (3-8) - which soldier level to train
        target_hours: float - target training time in hours
        pack_resources: bool - pack resources after (NOT YET IMPLEMENTED)
        debug: bool - enable debug logging

    Returns:
        bool: True if training started successfully
    """
    # Import here to avoid circular import at module level
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    flow_start = time.time()

    def check_timeout() -> bool:
        elapsed = time.time() - flow_start
        if elapsed > MAX_FLOW_TIME:
            _log(f"TIMEOUT: Flow exceeded {MAX_FLOW_TIME}s (elapsed={elapsed:.1f}s)", debug)
            return True
        return False

    win = WindowsScreenshotHelper()
    success = False

    _log(f"=== STARTING FLOW: Lv{soldier_level}, target={target_hours:.2f}h ===", debug)

    target_seconds = int(target_hours * 3600)
    _log(f"Target time: {target_seconds}s ({target_hours}h)", debug)

    try:
        # Step 0: Verify panel is open
        _log("Step 0: Verifying soldier training panel is open...", debug)

        if check_timeout():
            return False

        frame = win.get_screenshot_cv2()
        panel_open, score = is_panel_open(frame, debug=debug)

        if not panel_open:
            _log(f"Step 0 FAILED: Soldier training panel not detected (score={score:.6f})", debug)
            save_debug_screenshot(frame, "barracks", "FAIL_step0_panel_not_open")
            return False

        _log(f"Step 0 SUCCESS: Panel is open (score={score:.6f})", debug)

        # Wait for tiles to fully render
        time.sleep(0.5)

        # Step 1: Find and click soldier level using existing function
        _log(f"Step 1: Finding and clicking Lv{soldier_level} tile...", debug)

        if check_timeout():
            return False

        if not find_and_click_soldier_level(adb, win, soldier_level, debug=debug):
            _log(f"Step 1 FAILED: Could not find Lv{soldier_level} tile", debug)
            frame = win.get_screenshot_cv2()
            save_debug_screenshot(frame, "barracks", f"FAIL_step1_no_lv{soldier_level}")
            return False

        _log(f"Step 1 SUCCESS: Clicked Lv{soldier_level} tile", debug)
        time.sleep(0.8)

        # Validation: Check plus button is visible (indicates slider panel is showing)
        _log("VALIDATION: Checking slider visibility after clicking tile...", debug)

        frame = win.get_screenshot_cv2()
        plus_x, plus_y, score = find_plus_button(frame)
        if plus_x is None or plus_y is None:
            _log(f"VALIDATION FAILED: Slider not visible after clicking Lv{soldier_level} (score={score:.4f})", debug)
            save_debug_screenshot(frame, "barracks", "FAIL_validation_no_slider")
            return False
        _log(f"VALIDATION OK: Slider visible, plus button at ({plus_x}, {plus_y}) (score={score:.4f})", debug)

        ocr = OCRClient()

        # Step 2: Push slider to MAX to read full time
        _log("Step 2: Push slider to MAX to read full time...", debug)

        if check_timeout():
            return False

        # Click on track right edge to set to max (uses detected plus button Y)
        drag_slider_to_max(adb, frame, debug=debug)
        time.sleep(0.5)

        frame = win.get_screenshot_cv2()
        max_secs, max_str = ocr_time(frame, ocr)

        _log(f"  MAX time OCR: {max_str!r} -> {max_secs}s", debug)

        if max_secs is None or max_secs == 0:
            _log("Step 2 FAILED: Could not read max time from OCR", debug)
            save_debug_screenshot(frame, "barracks", "FAIL_step2_no_max_time")
            return False

        _log(f"Step 2 SUCCESS: MAX time = {max_str} ({max_secs}s)", debug)

        # Check if target exceeds max
        if target_seconds >= max_secs:
            _log(f"Target ({target_hours}h = {target_seconds}s) >= max ({max_secs}s), using max", debug)
            _log("Step 3-4 SKIPPED: Already at max, clicking Train directly", debug)
            _log(f"Step 5: Clicking Train button at ({TRAIN_BUTTON_CENTER[0]}, {TRAIN_BUTTON_CENTER[1]})...", debug)
            adb.tap(TRAIN_BUTTON_CENTER[0], TRAIN_BUTTON_CENTER[1])
            time.sleep(0.5)
            _log("Step 5 SUCCESS: Train button clicked", debug)
            success = True
            return True

        # Step 3: Calculate target X and drag slider
        ratio = target_seconds / max_secs
        target_x = calculate_slider_position(ratio)
        _log(f"Step 3: Drag slider to target X={target_x} (ratio={ratio:.2%})", debug)

        if check_timeout():
            return False

        # Click directly on target position (slider will move there)
        _log(f"  Clicking at target X={target_x} on track (Y={plus_y})", debug)
        adb.tap(target_x, plus_y)
        time.sleep(0.5)

        # Check current time
        frame = win.get_screenshot_cv2()
        current_secs, current_str = ocr_time(frame, ocr)
        if current_secs:
            diff = current_secs - target_seconds
            _log(f"  After click: time={current_str} ({current_secs}s), diff={diff}s ({diff/60:.1f}min)", debug)

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

            # Over target - click minus (use detected plus_y for correct Y position)
            if i % 5 == 0:
                _log(f"  [{i+1}] {current_str} ({current_secs}s) - over by {diff}s, clicking minus at ({MINUS_BUTTON[0]}, {plus_y})", debug)
            adb.tap(MINUS_BUTTON[0], plus_y)
            time.sleep(0.25)

        if fine_tune_success:
            _log("Step 4 SUCCESS: Fine-tuning complete", debug)
        else:
            _log("Step 4 WARNING: Fine-tuning loop exhausted (50 iterations)", debug)
            frame = win.get_screenshot_cv2()
            save_debug_screenshot(frame, "barracks", "WARN_step4_fine_tune_exhausted")

        # Step 5: Click Train button
        _log(f"Step 5: Clicking Train button at ({TRAIN_BUTTON_CENTER[0]}, {TRAIN_BUTTON_CENTER[1]})...", debug)

        if check_timeout():
            return False

        adb.tap(TRAIN_BUTTON_CENTER[0], TRAIN_BUTTON_CENTER[1])
        time.sleep(0.5)

        # Validation: Take screenshot after clicking Train to verify
        frame = win.get_screenshot_cv2()
        save_debug_screenshot(frame, "barracks", "after_train_click")
        _log("Step 5 SUCCESS: Train button clicked", debug)

        # TODO: pack_resources implementation
        if pack_resources:
            _log("(pack_resources not yet implemented)", debug)

        success = True
        return True

    except Exception as e:
        _log(f"EXCEPTION: {type(e).__name__}: {e}", True)
        try:
            frame = win.get_screenshot_cv2()
            save_debug_screenshot(frame, "barracks", f"EXCEPTION_{type(e).__name__}")
        except Exception:
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
    from utils.adb_helper import ADBHelper

    adb = ADBHelper()
    success = barracks_training_flow(adb, soldier_level=4, target_hours=4.0, debug=True)
    print(f"\nResult: {'SUCCESS' if success else 'FAILED'}")
