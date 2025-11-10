#!/usr/bin/env python3
"""
XClash Player Finder - Grid Map Scanner with OCR
Automatically navigates the world map and uses Tesseract OCR to find a specific player.

Usage:
    python find_player.py "PlayerName"
    python find_player.py "PlayerName" --debug  (saves all screenshots)
"""

import sys
import os
import subprocess
import time
import argparse
from pathlib import Path
from PIL import Image
import pytesseract

# Configuration
class Config:
    # ADB settings
    ADB_PATH = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
    DEVICE = "127.0.0.1:5556"  # Actual device (port changes on restart, use 127.0.0.1:5556 or emulator-5554)
    PACKAGE = "com.xman.na.gp"

    # Tesseract path (adjust if needed)
    TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    # Screen dimensions (BlueStacks default)
    SCREEN_WIDTH = 2560
    SCREEN_HEIGHT = 1440

    # Actual render resolution (BlueStacks native 4K)
    RENDER_WIDTH = 3840  # Native 4K resolution
    RENDER_HEIGHT = 2160

    # Auto-crop screenshots to SCREEN_WIDTH x SCREEN_HEIGHT
    AUTO_CROP = True  # Crop center region to match templates/coordinates

    # Map navigation settings
    # These are initial estimates - may need tuning
    SCROLL_DURATION = 300  # milliseconds for swipe
    HORIZONTAL_SCROLL_DISTANCE = 1500  # pixels to scroll right/left
    VERTICAL_SCROLL_DISTANCE = 800     # pixels to scroll down

    # Map boundaries (safe area to avoid UI elements)
    MAP_LEFT = 400
    MAP_RIGHT = 2160
    MAP_TOP = 200
    MAP_BOTTOM = 1240

    # Navigation to top-left corner
    INITIAL_LEFT_SWIPES = 15   # How many times to swipe left
    INITIAL_UP_SWIPES = 15     # How many times to swipe up

    # Grid scanning
    HORIZONTAL_STEPS = 10  # Number of views across
    VERTICAL_STEPS = 8     # Number of rows down

    # Delays (in seconds)
    DELAY_AFTER_SWIPE = 0.8   # Wait for map to settle
    DELAY_AFTER_SCREENSHOT = 0.3
    DELAY_BETWEEN_SCANS = 0.2

    # OCR settings
    OCR_CONFIDENCE_THRESHOLD = 30  # Minimum confidence for OCR results


class ADBController:
    """Handles all ADB interactions with BlueStacks."""

    def __init__(self, config):
        self.config = config
        self.adb = config.ADB_PATH
        self.device = config.DEVICE

        # Check if ADB exists
        if not os.path.exists(self.adb):
            raise FileNotFoundError(f"ADB not found at {self.adb}")

        # Connect to device
        self._execute(["connect", self.device])

    def _execute(self, args, capture_output=True):
        """Execute ADB command."""
        cmd = [self.adb, "-s", self.device] + args
        try:
            if capture_output:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                return result.stdout.strip()
            else:
                subprocess.run(cmd, check=True)
                return None
        except subprocess.CalledProcessError as e:
            print(f"ADB command failed: {' '.join(cmd)}")
            print(f"Error: {e.stderr if hasattr(e, 'stderr') else str(e)}")
            raise

    def swipe(self, x1, y1, x2, y2, duration):
        """Perform a swipe gesture."""
        self._execute(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)])

    def tap(self, x, y):
        """Tap at coordinates."""
        self._execute(["shell", "input", "tap", str(x), str(y)])

    def screenshot(self, local_path):
        """Capture screenshot and save locally."""
        import cv2
        import numpy as np

        # Capture to device
        remote_path = "/sdcard/screenshot.png"
        self._execute(["shell", "screencap", "-p", remote_path])

        # Pull to local
        self._execute(["pull", remote_path, str(local_path)])

        # Auto-crop if enabled and resolution doesn't match
        if self.config.AUTO_CROP:
            img = cv2.imread(str(local_path))
            if img is not None and img.shape[1] != self.config.SCREEN_WIDTH:
                # Crop center to match expected resolution
                h, w = img.shape[:2]
                target_w = self.config.SCREEN_WIDTH
                target_h = self.config.SCREEN_HEIGHT

                # Calculate crop region (center)
                x_offset = (w - target_w) // 2
                y_offset = (h - target_h) // 2

                cropped = img[y_offset:y_offset+target_h, x_offset:x_offset+target_w]
                cv2.imwrite(str(local_path), cropped)

        return local_path


class MapNavigator:
    """Handles map navigation and positioning."""

    def __init__(self, adb_controller, config):
        self.adb = adb_controller
        self.config = config
        self.current_row = 0
        self.current_col = 0

    def go_to_top_left(self):
        """Navigate to the top-left corner of the map."""
        print("📍 Navigating to top-left corner...")

        # Calculate center of safe map area for swiping
        center_x = (self.config.MAP_LEFT + self.config.MAP_RIGHT) // 2
        center_y = (self.config.MAP_TOP + self.config.MAP_BOTTOM) // 2

        # Swipe left multiple times
        print(f"   Swiping left {self.config.INITIAL_LEFT_SWIPES} times...")
        for i in range(self.config.INITIAL_LEFT_SWIPES):
            # Swipe from center-right to left
            self.adb.swipe(
                center_x + self.config.HORIZONTAL_SCROLL_DISTANCE // 2,
                center_y,
                center_x - self.config.HORIZONTAL_SCROLL_DISTANCE // 2,
                center_y,
                self.config.SCROLL_DURATION
            )
            time.sleep(self.config.DELAY_AFTER_SWIPE)

        # Swipe up multiple times
        print(f"   Swiping up {self.config.INITIAL_UP_SWIPES} times...")
        for i in range(self.config.INITIAL_UP_SWIPES):
            # Swipe from center-bottom to top
            self.adb.swipe(
                center_x,
                center_y + self.config.VERTICAL_SCROLL_DISTANCE // 2,
                center_x,
                center_y - self.config.VERTICAL_SCROLL_DISTANCE // 2,
                self.config.SCROLL_DURATION
            )
            time.sleep(self.config.DELAY_AFTER_SWIPE)

        print("✅ Reached top-left corner")
        self.current_row = 0
        self.current_col = 0

    def scroll_right(self):
        """Scroll one step to the right."""
        center_x = (self.config.MAP_LEFT + self.config.MAP_RIGHT) // 2
        center_y = (self.config.MAP_TOP + self.config.MAP_BOTTOM) // 2

        # Swipe from right to left (scrolls map right)
        self.adb.swipe(
            center_x - self.config.HORIZONTAL_SCROLL_DISTANCE // 2,
            center_y,
            center_x + self.config.HORIZONTAL_SCROLL_DISTANCE // 2,
            center_y,
            self.config.SCROLL_DURATION
        )
        time.sleep(self.config.DELAY_AFTER_SWIPE)
        self.current_col += 1

    def scroll_left(self):
        """Scroll one step to the left."""
        center_x = (self.config.MAP_LEFT + self.config.MAP_RIGHT) // 2
        center_y = (self.config.MAP_TOP + self.config.MAP_BOTTOM) // 2

        # Swipe from left to right (scrolls map left)
        self.adb.swipe(
            center_x + self.config.HORIZONTAL_SCROLL_DISTANCE // 2,
            center_y,
            center_x - self.config.HORIZONTAL_SCROLL_DISTANCE // 2,
            center_y,
            self.config.SCROLL_DURATION
        )
        time.sleep(self.config.DELAY_AFTER_SWIPE)
        self.current_col -= 1

    def scroll_down(self):
        """Scroll one step down."""
        center_x = (self.config.MAP_LEFT + self.config.MAP_RIGHT) // 2
        center_y = (self.config.MAP_TOP + self.config.MAP_BOTTOM) // 2

        # Swipe from bottom to top (scrolls map down)
        self.adb.swipe(
            center_x,
            center_y - self.config.VERTICAL_SCROLL_DISTANCE // 2,
            center_x,
            center_y + self.config.VERTICAL_SCROLL_DISTANCE // 2,
            self.config.SCROLL_DURATION
        )
        time.sleep(self.config.DELAY_AFTER_SWIPE)
        self.current_row += 1

    def get_position(self):
        """Return current grid position."""
        return (self.current_row, self.current_col)


class OCRProcessor:
    """Handles screenshot OCR processing."""

    def __init__(self, config, debug=False):
        self.config = config
        self.debug = debug

        # Configure Tesseract path
        pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

        # Create debug directory if needed
        if debug:
            self.debug_dir = Path("ocr_debug")
            self.debug_dir.mkdir(exist_ok=True)

    def process_screenshot(self, screenshot_path):
        """
        Process screenshot with OCR and return all detected text.
        Returns: List of (text, confidence) tuples
        """
        try:
            # Open image
            img = Image.open(screenshot_path)

            # Run OCR with detailed data
            ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

            # Extract text with confidence
            results = []
            n_boxes = len(ocr_data['text'])
            for i in range(n_boxes):
                text = ocr_data['text'][i].strip()
                conf = int(ocr_data['conf'][i])

                if text and conf > self.config.OCR_CONFIDENCE_THRESHOLD:
                    results.append((text, conf))

            return results

        except Exception as e:
            print(f"⚠️  OCR processing failed: {e}")
            return []

    def search_for_player(self, ocr_results, player_name):
        """
        Search for player name in OCR results (case-insensitive).
        Returns: (found, confidence, matched_text) tuple
        """
        player_lower = player_name.lower()

        for text, conf in ocr_results:
            if player_lower in text.lower():
                return (True, conf, text)

        return (False, 0, None)


class GridScanner:
    """Orchestrates the complete grid scanning process."""

    def __init__(self, config, debug=False):
        self.config = config
        self.debug = debug

        print("🔧 Initializing components...")
        self.adb = ADBController(config)
        self.navigator = MapNavigator(self.adb, config)
        self.ocr = OCRProcessor(config, debug)

        # Stats
        self.total_scans = 0
        self.screenshots_dir = Path("screenshots")
        if debug:
            self.screenshots_dir.mkdir(exist_ok=True)

    def scan_current_view(self, save_as=None):
        """Scan current map view with OCR."""
        # Generate filename
        if save_as is None:
            row, col = self.navigator.get_position()
            save_as = f"scan_r{row}_c{col}.png"

        screenshot_path = self.screenshots_dir / save_as if self.debug else Path("temp_screenshot.png")

        # Capture screenshot
        self.adb.screenshot(screenshot_path)
        time.sleep(self.config.DELAY_AFTER_SCREENSHOT)

        # Process with OCR
        ocr_results = self.ocr.process_screenshot(screenshot_path)

        # Clean up temp file if not debugging
        if not self.debug and screenshot_path.exists():
            screenshot_path.unlink()

        self.total_scans += 1
        return ocr_results

    def find_player(self, player_name):
        """
        Main scanning loop - grid pattern search for player.
        Returns: (found, row, col) tuple
        """
        print(f"\n🔍 Starting grid scan for player: '{player_name}'")
        print(f"📊 Scan grid: {self.config.HORIZONTAL_STEPS} columns × {self.config.VERTICAL_STEPS} rows")
        print("=" * 60)

        # Navigate to starting position
        self.navigator.go_to_top_left()
        time.sleep(1)

        # Grid scan pattern
        for row in range(self.config.VERTICAL_STEPS):
            # Determine scan direction for this row
            if row % 2 == 0:
                # Even rows: scan left to right
                cols = range(self.config.HORIZONTAL_STEPS)
                direction = "→"
            else:
                # Odd rows: scan right to left
                cols = range(self.config.HORIZONTAL_STEPS - 1, -1, -1)
                direction = "←"

            for col in cols:
                # Scan current position
                print(f"[Row {row+1}/{self.config.VERTICAL_STEPS}, Col {col+1}/{self.config.HORIZONTAL_STEPS}] {direction} Scanning...", end=" ")

                ocr_results = self.scan_current_view()
                found, confidence, matched_text = self.ocr.search_for_player(ocr_results, player_name)

                if found:
                    print(f"✅ FOUND!")
                    print("\n" + "=" * 60)
                    print(f"🎯 PLAYER FOUND: '{matched_text}' (confidence: {confidence}%)")
                    print(f"📍 Position: Row {row+1}, Column {col+1}")
                    print(f"📊 Total scans: {self.total_scans}")
                    print("=" * 60)
                    return (True, row, col)
                else:
                    print(f"❌ Not found ({len(ocr_results)} text items detected)")

                # Move to next column (except at row end)
                if row % 2 == 0:  # Left to right
                    if col < self.config.HORIZONTAL_STEPS - 1:
                        self.navigator.scroll_right()
                else:  # Right to left
                    if col > 0:
                        self.navigator.scroll_left()

                time.sleep(self.config.DELAY_BETWEEN_SCANS)

            # Move to next row (except at last row)
            if row < self.config.VERTICAL_STEPS - 1:
                print(f"   ⬇️  Moving to row {row+2}...")
                self.navigator.scroll_down()
                time.sleep(self.config.DELAY_AFTER_SWIPE)

        # Not found
        print("\n" + "=" * 60)
        print(f"❌ Player '{player_name}' not found in {self.total_scans} scans")
        print("=" * 60)
        return (False, -1, -1)


def main():
    parser = argparse.ArgumentParser(description="XClash Player Finder - Grid Map Scanner")
    parser.add_argument("player_name", help="Name of player to find")
    parser.add_argument("--debug", action="store_true", help="Save all screenshots for debugging")
    parser.add_argument("--test-ocr", action="store_true", help="Test OCR on current screen only (no navigation)")

    args = parser.parse_args()

    try:
        config = Config()
        scanner = GridScanner(config, debug=args.debug)

        if args.test_ocr:
            # Test mode: just OCR current screen
            print("🧪 Test mode: OCR current screen only")
            results = scanner.scan_current_view(save_as="test_ocr.png")
            print(f"\n✅ Detected {len(results)} text items:")
            for text, conf in sorted(results, key=lambda x: x[1], reverse=True):
                print(f"  [{conf}%] {text}")
        else:
            # Full scan
            found, row, col = scanner.find_player(args.player_name)

            if found:
                sys.exit(0)  # Success
            else:
                sys.exit(1)  # Not found

    except KeyboardInterrupt:
        print("\n\n⚠️  Scan interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
