"""
Stamina Extractor - Extract stamina number from game UI using Tesseract OCR.

Fixed coordinates (4K resolution): (69, 203) size 96x60
Tesseract config: --psm 7 -c tessedit_char_whitelist=0123456789
"""

import pytesseract

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


class StaminaExtractor:
    """Extract stamina number from screenshot at fixed coordinates."""

    # Fixed coordinates (4K resolution)
    REGION_X = 69
    REGION_Y = 203
    REGION_WIDTH = 96
    REGION_HEIGHT = 60

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


if __name__ == "__main__":
    # Test the extractor
    import cv2
    from windows_screenshot_helper import WindowsScreenshotHelper

    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()

    extractor = StaminaExtractor()
    stamina = extractor.extract_stamina(frame)

    print(f"Stamina: {stamina}")
