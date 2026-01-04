"""
Replenish All Resources Helper

Detects and clicks "Replenish all" button when resources are insufficient.
Used across multiple flows: soldier training, upgrades, barracks building, etc.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy.typing as npt

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

# Debug screenshot directory
DEBUG_DIR = Path(__file__).parent.parent / "screenshots" / "debug" / "replenish"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)


def _save_debug_screenshot(frame: npt.NDArray[Any], step: str, extra: str = "") -> None:
    """Save screenshot with step text annotated on image."""
    annotated = frame.copy()
    text = f"REPLENISH: {step}"
    if extra:
        text += f" | {extra}"
    # Draw black background for text
    cv2.rectangle(annotated, (10, 10), (1400, 80), (0, 0, 0), -1)
    # Draw white text
    cv2.putText(annotated, text, (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)

    timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]
    filename = DEBUG_DIR / f"{timestamp}_{step.replace(' ', '_').lower()}.png"
    cv2.imwrite(str(filename), annotated)
    logging.getLogger(__name__).info(f"DEBUG screenshot: {filename}")


class ReplenishAllHelper:
    """Helper for detecting and clicking Replenish all button"""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

        # Replenish all button template (372x125)
        replenish_path = Path(__file__).parent.parent / "templates" / "ground_truth" / "replenish_all_button_4k.png"
        replenish_img = cv2.imread(str(replenish_path), cv2.IMREAD_GRAYSCALE)
        if replenish_img is None:
            raise FileNotFoundError(f"Template not found: {replenish_path}")
        self.replenish_template: npt.NDArray[Any] = replenish_img

        # Use Items header template (983x113)
        header_path = Path(__file__).parent.parent / "templates" / "ground_truth" / "use_items_header_4k.png"
        header_img = cv2.imread(str(header_path), cv2.IMREAD_GRAYSCALE)
        if header_img is None:
            raise FileNotFoundError(f"Template not found: {header_path}")
        self.header_template: npt.NDArray[Any] = header_img

        # Insufficient Resources tab template (1163x126)
        tab_path = Path(__file__).parent.parent / "templates" / "ground_truth" / "insufficient_resources_tab_4k.png"
        tab_img: npt.NDArray[Any] | None = cv2.imread(str(tab_path), cv2.IMREAD_GRAYSCALE)
        self.insufficient_tab_template: npt.NDArray[Any] | None = tab_img
        # Tab template is optional - don't fail if not found
        if self.insufficient_tab_template is None:
            self.logger.warning(f"Optional template not found: {tab_path}")

        # Replenish all button - fixed coordinates from Gemini detection (2026-01-03)
        self.REPLENISH_BUTTON_X = 1728  # Top-left X
        self.REPLENISH_BUTTON_Y = 1842  # Top-left Y (updated)
        self.REPLENISH_BUTTON_W = 372   # Width
        self.REPLENISH_BUTTON_H = 125   # Height (updated)
        self.REPLENISH_BUTTON_CENTER = (1914, 1904)  # Click center

        # Insufficient Resources tab - fixed coordinates at top of screen
        self.INSUFFICIENT_TAB_X = 1336  # Top-left X
        self.INSUFFICIENT_TAB_Y = 144   # Top-left Y
        self.INSUFFICIENT_TAB_W = 1163  # Width
        self.INSUFFICIENT_TAB_H = 126   # Height

        # Use Items header - fixed coordinates from Gemini detection
        self.USE_ITEMS_HEADER_X = 1424  # Top-left X
        self.USE_ITEMS_HEADER_Y = 537   # Top-left Y
        self.USE_ITEMS_HEADER_W = 983   # Width
        self.USE_ITEMS_HEADER_H = 113   # Height

        # Confirm button click position
        self.CONFIRM_BUTTON_POS = (2141, 1426)  # From template matching

        # Detection threshold
        self.threshold = 0.1  # TM_SQDIFF_NORMED

    def find_replenish_button(self, frame: npt.NDArray[Any]) -> bool:
        """
        Check if Replenish all button is present at fixed coordinates.

        Args:
            frame: BGR image from WindowsScreenshotHelper

        Returns:
            True if button found, False otherwise
        """
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Extract ROI at fixed coordinates
        roi = frame_gray[
            self.REPLENISH_BUTTON_Y : self.REPLENISH_BUTTON_Y + self.REPLENISH_BUTTON_H,
            self.REPLENISH_BUTTON_X : self.REPLENISH_BUTTON_X + self.REPLENISH_BUTTON_W
        ]

        # Template matching on ROI
        result = cv2.matchTemplate(roi, self.replenish_template, cv2.TM_SQDIFF_NORMED)
        min_val, _, _, _ = cv2.minMaxLoc(result)

        if min_val <= self.threshold:
            self.logger.info(f"Replenish all button detected at fixed position with score {min_val:.4f}")
            return True

        self.logger.debug(f"Replenish all button NOT detected (score: {min_val:.4f})")
        return False

    def find_use_items_header(self, frame: npt.NDArray[Any]) -> bool:
        """
        Check if Use Items dialog header is present at fixed coordinates.

        Args:
            frame: BGR image from WindowsScreenshotHelper

        Returns:
            True if header found, False otherwise
        """
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Extract ROI at fixed coordinates
        roi = frame_gray[
            self.USE_ITEMS_HEADER_Y : self.USE_ITEMS_HEADER_Y + self.USE_ITEMS_HEADER_H,
            self.USE_ITEMS_HEADER_X : self.USE_ITEMS_HEADER_X + self.USE_ITEMS_HEADER_W
        ]

        # Template matching on ROI
        result = cv2.matchTemplate(roi, self.header_template, cv2.TM_SQDIFF_NORMED)
        min_val, _, _, _ = cv2.minMaxLoc(result)

        if min_val <= self.threshold:
            self.logger.info(f"Use Items header detected at fixed position with score {min_val:.4f}")
            return True

        self.logger.debug(f"Use Items header NOT detected (score: {min_val:.4f})")
        return False

    def find_insufficient_resources_tab(self, frame: npt.NDArray[Any]) -> bool:
        """
        Check if Insufficient Resources tab is visible at top of screen.

        Args:
            frame: BGR image from WindowsScreenshotHelper

        Returns:
            True if tab found, False otherwise
        """
        if self.insufficient_tab_template is None:
            return False

        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Extract ROI at fixed coordinates (top of screen)
        roi = frame_gray[
            self.INSUFFICIENT_TAB_Y : self.INSUFFICIENT_TAB_Y + self.INSUFFICIENT_TAB_H,
            self.INSUFFICIENT_TAB_X : self.INSUFFICIENT_TAB_X + self.INSUFFICIENT_TAB_W
        ]

        # Template matching on ROI
        result = cv2.matchTemplate(roi, self.insufficient_tab_template, cv2.TM_SQDIFF_NORMED)
        min_val, _, _, _ = cv2.minMaxLoc(result)

        if min_val <= self.threshold:
            self.logger.info(f"Insufficient Resources tab detected at top with score {min_val:.4f}")
            return True

        self.logger.debug(f"Insufficient Resources tab NOT detected (score: {min_val:.4f})")
        return False

    def handle_replenish_flow(self, adb: ADBHelper, win: WindowsScreenshotHelper, debug: bool = False) -> bool:
        """
        Check for and handle replenish all flow.

        Flow:
        1. Check if "Replenish all" button is present
        2. If not found: return False (no action needed)
        3. If found:
           - Click "Replenish all" button
           - Check for "Use Items" dialog header
           - If header found: click "Confirm" button
           - Return True

        Args:
            adb: ADBHelper instance
            win: WindowsScreenshotHelper instance
            debug: Enable debug logging

        Returns:
            True if replenish flow was triggered, False if button not found
        """
        # Take screenshot and check for Replenish all button
        frame = win.get_screenshot_cv2()
        _save_debug_screenshot(frame, "STEP1 Check replenish btn")

        if not self.find_replenish_button(frame):
            if debug:
                self.logger.info("No replenish button found - skipping")
            _save_debug_screenshot(frame, "STEP1 NO replenish btn found")
            return False

        self.logger.info("REPLENISH FLOW: Starting")
        _save_debug_screenshot(frame, "STEP1 FOUND replenish btn")

        # Step 2: Click "Replenish all" button
        self.logger.info(f"Clicking Replenish all button at {self.REPLENISH_BUTTON_CENTER}")
        adb.tap(*self.REPLENISH_BUTTON_CENTER)
        time.sleep(0.3)

        frame = win.get_screenshot_cv2()
        _save_debug_screenshot(frame, "STEP2 AFTER click replenish")

        # Step 3: Poll for EITHER "Use Items" dialog OR dimmed "Soldier Training" tab (result screen)
        # Sometimes clicking Replenish All goes directly to results without confirmation
        # The dimmed tab appears at top when congrats screen shows - click it to dismiss
        DIMMED_TAB_CLICK = (1913, 347)  # Center of dimmed Soldier Training tab

        found_use_items = False
        found_result_screen = False
        for attempt in range(8):  # 8 attempts * 0.25s = 2 seconds
            frame = win.get_screenshot_cv2()

            # Check for Use Items dialog (needs confirmation)
            if self.find_use_items_header(frame):
                self.logger.info(f"Use Items dialog found after {attempt + 1} attempts")
                _save_debug_screenshot(frame, f"STEP3 FOUND UseItems dialog", f"attempt={attempt+1}")
                found_use_items = True
                break

            # Check for dimmed Soldier Training tab (result screen - already done)
            from utils.template_matcher import match_template
            found_dimmed, score, _ = match_template(frame, "soldier_training_dimmed_tab_4k.png", threshold=0.1)
            if found_dimmed:
                self.logger.info(f"Result screen found (dimmed tab) after {attempt + 1} attempts - replenish succeeded!")
                _save_debug_screenshot(frame, f"STEP3 FOUND result screen", f"attempt={attempt+1}")
                found_result_screen = True
                break

            time.sleep(0.25)

        if found_use_items:
            # Need to click Confirm button
            from utils.template_matcher import match_template
            found_confirm, score, confirm_loc = match_template(frame, "confirm_button_4k.png", threshold=0.1)

            if found_confirm and confirm_loc:
                self.logger.info(f"Confirm button found at {confirm_loc} (score={score:.4f}), clicking...")
                _save_debug_screenshot(frame, "STEP4 CLICKING Confirm", f"pos={confirm_loc}")
                adb.tap(*confirm_loc)
            else:
                self.logger.warning(f"Confirm button not found (score={score:.4f}), using fallback position")
                _save_debug_screenshot(frame, "STEP4 Confirm NOT found using fallback", f"score={score:.4f}")
                adb.tap(*self.CONFIRM_BUTTON_POS)
            time.sleep(0.5)

            frame = win.get_screenshot_cv2()
            _save_debug_screenshot(frame, "STEP5 AFTER click Confirm")

            # After confirm, tap to close result screen
            self.logger.info("Tapping to close resources result screen")
            adb.tap(1920, 1080)
            time.sleep(0.3)

        elif found_result_screen:
            # Result screen showing - click dimmed tab to dismiss
            _save_debug_screenshot(frame, "STEP4 Clicking dimmed tab to dismiss", f"pos={DIMMED_TAB_CLICK}")
            self.logger.info(f"Clicking dimmed Soldier Training tab at {DIMMED_TAB_CLICK} to dismiss")
            adb.tap(*DIMMED_TAB_CLICK)
            time.sleep(0.3)

        else:
            # Neither found - one more check
            _save_debug_screenshot(frame, "STEP3 checking final state")
            from utils.template_matcher import match_template
            found_dimmed, score, _ = match_template(frame, "soldier_training_dimmed_tab_4k.png", threshold=0.1)
            if not found_dimmed:
                _save_debug_screenshot(frame, "STEP3 FAIL no expected screen")
                self.logger.warning("Neither Use Items dialog nor result screen found")
                self.logger.info("REPLENISH FLOW: Failed (no expected screen found)")
                return False
            # Found on final check - click to dismiss
            self.logger.info("Result screen found on final check - clicking to dismiss")
            adb.tap(*DIMMED_TAB_CLICK)
            time.sleep(0.3)

        frame = win.get_screenshot_cv2()
        _save_debug_screenshot(frame, "STEP6 AFTER dismiss")

        self.logger.info("REPLENISH FLOW: Complete")
        return True

    def poll_and_handle_replenish(self, adb: ADBHelper, win: WindowsScreenshotHelper, debug: bool = False) -> bool:
        """
        Poll for Insufficient Resources tab after clicking Train/Promote.
        If found, handle replenish flow.

        This is the UNIFIED method to be used by both training and upgrade flows.

        Args:
            adb: ADBHelper instance
            win: WindowsScreenshotHelper instance
            debug: Enable debug logging

        Returns:
            True if replenish was needed and handled, False otherwise
        """
        _save_debug_screenshot(win.get_screenshot_cv2(), "POLL START checking insufficient tab")

        for attempt in range(8):  # 8 attempts * 0.25s = 2 seconds
            time.sleep(0.25)
            frame = win.get_screenshot_cv2()
            if self.find_insufficient_resources_tab(frame):
                if debug:
                    print(f"  Insufficient Resources tab detected (attempt {attempt + 1})")
                _save_debug_screenshot(frame, f"POLL FOUND insufficient tab", f"attempt={attempt+1}")
                self.handle_replenish_flow(adb, win, debug=debug)
                return True

        _save_debug_screenshot(frame, "POLL END no insufficient tab")
        if debug:
            print("  No Insufficient Resources tab found - action succeeded")
        return False
