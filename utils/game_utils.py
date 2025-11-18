#!/usr/bin/env python3
"""
Game utility functions for XClash automation.
Handles view detection, zoom control, and UI interactions.
"""

import time
from pathlib import Path
from PIL import Image
import pytesseract


class GameHelper:
    """Helper functions for game state management."""

    def __init__(self, adb_controller, config):
        self.adb = adb_controller
        self.config = config

        # UI element positions (approximate - may need tuning)
        # Lower right corner: World/Town toggle button
        self.world_toggle_x = 2350  # Right side
        self.world_toggle_y = 1350  # Bottom

        # Zoom buttons (need to find these)
        self.zoom_in_x = 2400
        self.zoom_in_y = 700
        self.zoom_out_x = 2400
        self.zoom_out_y = 800

    def take_screenshot_pil(self):
        """Take screenshot and return as PIL Image."""
        temp_path = Path("temp_check.png")
        self.adb.screenshot(temp_path)
        img = Image.open(temp_path)
        temp_path.unlink()
        return img

    def check_world_view(self):
        """
        Check if we're in World view by OCRing lower right corner.
        Returns: (is_world_view, detected_text)
        """
        # Take screenshot
        img = self.take_screenshot_pil()

        # Crop lower right corner (where World/Town button is)
        # Approximate area: last 300x200 pixels
        width, height = img.size
        crop_box = (width - 300, height - 200, width, height)
        corner_img = img.crop(crop_box)

        # Save for debugging
        corner_img.save("corner_check.png")

        # OCR the corner
        pytesseract.pytesseract.tesseract_cmd = self.config.TESSERACT_CMD
        text = pytesseract.image_to_string(corner_img)

        # Check for "WORLD" or "TOWN"
        text_upper = text.upper()
        is_world = "WORLD" in text_upper
        is_town = "TOWN" in text_upper

        return (is_world or is_town, text)

    def switch_to_world_view(self):
        """
        Switch to World view if not already there.
        Returns: True if successful, False otherwise
        """
        print("🌍 Checking current view...")

        # Check current state
        is_detected, text = self.check_world_view()

        if is_detected:
            if "WORLD" in text.upper():
                print("✅ Already in World view")
                return True
            elif "TOWN" in text.upper():
                print("📍 Currently in Town view, need to switch...")
        else:
            print(f"⚠️  Could not detect view from OCR: '{text}'")
            print("   Attempting to click World toggle anyway...")

        # Click the toggle button
        print(f"   Clicking World/Town toggle at ({self.world_toggle_x}, {self.world_toggle_y})...")
        self.adb.tap(self.world_toggle_x, self.world_toggle_y)
        time.sleep(1.5)  # Wait for view change

        # Verify
        is_detected, text = self.check_world_view()
        if is_detected and "WORLD" in text.upper():
            print("✅ Successfully switched to World view")
            return True
        else:
            print(f"⚠️  View switch unclear. OCR result: '{text}'")
            print("   Please manually verify you're in World view")
            return False

    def adjust_zoom(self, zoom_level="out"):
        """
        Adjust zoom level.
        zoom_level: "in" or "out"
        """
        if zoom_level == "out":
            print("🔍 Zooming out...")
            for i in range(3):
                self.adb.tap(self.zoom_out_x, self.zoom_out_y)
                time.sleep(0.5)
        elif zoom_level == "in":
            print("🔍 Zooming in...")
            for i in range(3):
                self.adb.tap(self.zoom_in_x, self.zoom_in_y)
                time.sleep(0.5)

    def get_screen_info(self):
        """Get current screen OCR info for debugging."""
        img = self.take_screenshot_pil()

        pytesseract.pytesseract.tesseract_cmd = self.config.TESSERACT_CMD
        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

        # Extract text with positions
        results = []
        n_boxes = len(ocr_data['text'])
        for i in range(n_boxes):
            text = ocr_data['text'][i].strip()
            conf = int(ocr_data['conf'][i])
            if text and conf > 30:
                x = ocr_data['left'][i]
                y = ocr_data['top'][i]
                results.append({
                    'text': text,
                    'confidence': conf,
                    'x': x,
                    'y': y
                })

        return results


def test_world_detection():
    """Test function to verify World view detection."""
    from find_player import ADBController, Config

    print("Testing World view detection...")
    config = Config()
    adb = ADBController(config)
    helper = GameHelper(adb, config)

    # Check current view
    is_detected, text = helper.check_world_view()
    print(f"\nDetected: {is_detected}")
    print(f"OCR Text: '{text}'")
    print(f"\nCorner screenshot saved to: corner_check.png")

    # Get all screen text for finding UI elements
    print("\nGetting full screen OCR...")
    screen_info = helper.get_screen_info()

    print(f"\nFound {len(screen_info)} text elements:")
    for item in sorted(screen_info, key=lambda x: x['confidence'], reverse=True)[:20]:
        print(f"  [{item['confidence']:3d}%] at ({item['x']:4d}, {item['y']:4d}): '{item['text']}'")


if __name__ == "__main__":
    test_world_detection()
