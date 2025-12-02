"""
Stamina Extractor - Extract stamina number from game UI using Tesseract OCR.

Fixed coordinates (4K resolution): (69, 203) size 96x60
Tesseract config: --psm 7 -c tessedit_char_whitelist=0123456789

Also detects red "+" boost button at (170, 218) to indicate stamina items available.
"""

import numpy as np
import pytesseract

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


class StaminaExtractor:
    """Extract stamina number and boost availability from screenshot."""

    # Fixed coordinates (4K resolution) for stamina number
    REGION_X = 69
    REGION_Y = 203
    REGION_WIDTH = 96
    REGION_HEIGHT = 60

    # Red boost button region (right of stamina number)
    BOOST_BUTTON_X = 170
    BOOST_BUTTON_Y = 218
    BOOST_BUTTON_WIDTH = 25
    BOOST_BUTTON_HEIGHT = 20

    def __init__(self):
        """Initialize the stamina extractor."""
        pass

    def extract_stamina(self, frame) -> int | None:
        """
        Extract stamina number from frame.

        Args:
            frame: BGR numpy array (4K resolution screenshot)

        Returns:
            int: Stamina value, or None if extraction failed
        """
        # Crop ROI at fixed coordinates
        roi = frame[self.REGION_Y:self.REGION_Y + self.REGION_HEIGHT,
                    self.REGION_X:self.REGION_X + self.REGION_WIDTH]

        # Tesseract with digit-only whitelist, single line mode
        config = '--psm 7 -c tessedit_char_whitelist=0123456789'
        text = pytesseract.image_to_string(roi, config=config).strip()

        try:
            return int(text)
        except ValueError:
            return None

    def has_boost_available(self, frame) -> bool:
        """
        Check if stamina boost items are available (red button visible).

        Args:
            frame: BGR numpy array (4K resolution screenshot)

        Returns:
            bool: True if red boost button is present
        """
        # Crop red button region
        roi = frame[self.BOOST_BUTTON_Y:self.BOOST_BUTTON_Y + self.BOOST_BUTTON_HEIGHT,
                    self.BOOST_BUTTON_X:self.BOOST_BUTTON_X + self.BOOST_BUTTON_WIDTH]

        # Check color channels (BGR format)
        b_mean = np.mean(roi[:, :, 0])
        g_mean = np.mean(roi[:, :, 1])
        r_mean = np.mean(roi[:, :, 2])

        # Red button: high red, low green/blue
        return r_mean > 200 and g_mean < 50 and b_mean < 50

    def extract_stamina_info(self, frame) -> tuple[int | None, bool]:
        """
        Extract stamina value and boost availability.

        Args:
            frame: BGR numpy array (4K resolution screenshot)

        Returns:
            tuple: (stamina_value, boost_available)
        """
        stamina = self.extract_stamina(frame)
        boost = self.has_boost_available(frame)
        return stamina, boost


if __name__ == "__main__":
    # Test the extractor
    import cv2
    from windows_screenshot_helper import WindowsScreenshotHelper

    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()

    extractor = StaminaExtractor()
    stamina, boost = extractor.extract_stamina_info(frame)

    print(f"Stamina: {stamina}")
    print(f"Boost available: {boost}")
