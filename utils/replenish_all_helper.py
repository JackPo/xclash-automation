"""
Replenish All Resources Helper

Detects and clicks "Replenish all" button when resources are insufficient.
Used across multiple flows: soldier training, upgrades, barracks building, etc.
"""

import cv2
import numpy as np
import time
import logging
from pathlib import Path


class ReplenishAllHelper:
    """Helper for detecting and clicking Replenish all button"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Replenish all button template (372x131)
        replenish_path = Path(__file__).parent.parent / "templates" / "ground_truth" / "replenish_all_button_4k.png"
        self.replenish_template = cv2.imread(str(replenish_path), cv2.IMREAD_GRAYSCALE)
        if self.replenish_template is None:
            raise FileNotFoundError(f"Template not found: {replenish_path}")

        # Use Items header template (983x113)
        header_path = Path(__file__).parent.parent / "templates" / "ground_truth" / "use_items_header_4k.png"
        self.header_template = cv2.imread(str(header_path), cv2.IMREAD_GRAYSCALE)
        if self.header_template is None:
            raise FileNotFoundError(f"Template not found: {header_path}")

        # Replenish all button - fixed coordinates from Gemini detection
        self.REPLENISH_BUTTON_X = 1728  # Top-left X
        self.REPLENISH_BUTTON_Y = 1838  # Top-left Y
        self.REPLENISH_BUTTON_W = 372   # Width
        self.REPLENISH_BUTTON_H = 131   # Height
        self.REPLENISH_BUTTON_CENTER = (1914, 1903)  # Click center

        # Use Items header - fixed coordinates from Gemini detection
        self.USE_ITEMS_HEADER_X = 1424  # Top-left X
        self.USE_ITEMS_HEADER_Y = 537   # Top-left Y
        self.USE_ITEMS_HEADER_W = 983   # Width
        self.USE_ITEMS_HEADER_H = 113   # Height

        # Confirm button click position
        self.CONFIRM_BUTTON_POS = (2150, 1429)  # From Gemini detection

        # Detection threshold
        self.threshold = 0.1  # TM_SQDIFF_NORMED

    def find_replenish_button(self, frame) -> bool:
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

    def find_use_items_header(self, frame) -> bool:
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

    def handle_replenish_flow(self, adb, win, debug: bool = False) -> bool:
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

        if not self.find_replenish_button(frame):
            if debug:
                self.logger.info("No replenish button found - skipping")
            return False

        self.logger.info("REPLENISH FLOW: Starting")

        # Step 1: Click "Replenish all" button
        self.logger.info(f"Clicking Replenish all button at {self.REPLENISH_BUTTON_CENTER}")
        adb.tap(*self.REPLENISH_BUTTON_CENTER)
        time.sleep(0.5)

        # Step 2: Check for "Use Items" dialog
        frame = win.get_screenshot_cv2()
        if self.find_use_items_header(frame):
            # Step 3: Click Confirm button
            self.logger.info(f"Clicking Confirm button at {self.CONFIRM_BUTTON_POS}")
            adb.tap(*self.CONFIRM_BUTTON_POS)
            time.sleep(0.5)
        else:
            self.logger.warning("Use Items dialog not found after clicking Replenish all")

        self.logger.info("REPLENISH FLOW: Complete")
        return True
