"""
Upgrade Button Matcher - Detects available/unavailable upgrade buttons in hero detail view.

Uses template matching to distinguish between green (available) and grayed (unavailable) upgrade buttons.
"""

import cv2
import numpy as np
from pathlib import Path

# Template paths
TEMPLATES_DIR = Path(__file__).parent.parent / 'templates' / 'ground_truth'
AVAILABLE_TEMPLATE = TEMPLATES_DIR / 'upgrade_button_available_4k.png'
UNAVAILABLE_TEMPLATE = TEMPLATES_DIR / 'upgrade_button_unavailable_4k.png'

# Fixed search region for upgrade button (4K resolution)
# Both buttons appear at approximately same location
UPGRADE_BUTTON_REGION = (1700, 1750, 450, 160)  # x, y, w, h

# Click position (center of button)
UPGRADE_BUTTON_CLICK = (1919, 1829)

# Matching threshold
THRESHOLD = 0.1  # TM_SQDIFF_NORMED - lower is better


class UpgradeButtonMatcher:
    def __init__(self):
        self.available_template = cv2.imread(str(AVAILABLE_TEMPLATE))
        self.unavailable_template = cv2.imread(str(UNAVAILABLE_TEMPLATE))

        if self.available_template is None:
            raise FileNotFoundError(f"Template not found: {AVAILABLE_TEMPLATE}")
        if self.unavailable_template is None:
            raise FileNotFoundError(f"Template not found: {UNAVAILABLE_TEMPLATE}")

    def check_upgrade_available(self, frame: np.ndarray, debug: bool = False) -> tuple[bool, float, float]:
        """
        Check if upgrade button is available (green) or unavailable (grayed).

        Args:
            frame: Full screenshot (BGR numpy array)
            debug: If True, save debug image

        Returns:
            (is_available, available_score, unavailable_score)
            is_available is True if green upgrade button detected
        """
        # Extract search region
        x, y, w, h = UPGRADE_BUTTON_REGION
        roi = frame[y:y+h, x:x+w]

        # Match both templates
        available_result = cv2.matchTemplate(roi, self.available_template, cv2.TM_SQDIFF_NORMED)
        unavailable_result = cv2.matchTemplate(roi, self.unavailable_template, cv2.TM_SQDIFF_NORMED)

        available_score = float(available_result.min())
        unavailable_score = float(unavailable_result.min())

        if debug:
            print(f"  Upgrade button - available: {available_score:.4f}, unavailable: {unavailable_score:.4f}")
            # Save debug image
            debug_img = roi.copy()
            cv2.putText(debug_img, f"Avail: {available_score:.3f}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(debug_img, f"Unavail: {unavailable_score:.3f}", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            debug_path = TEMPLATES_DIR.parent / 'debug' / f'upgrade_button_check.png'
            cv2.imwrite(str(debug_path), debug_img)

        # Return True if available matches better than unavailable
        # Both must be under threshold to be considered a valid button
        if available_score < THRESHOLD and available_score < unavailable_score:
            return True, available_score, unavailable_score
        elif unavailable_score < THRESHOLD:
            return False, available_score, unavailable_score
        else:
            # Neither matches well - button not visible
            return False, available_score, unavailable_score

    def get_click_position(self) -> tuple[int, int]:
        """Get the click position for the upgrade button."""
        return UPGRADE_BUTTON_CLICK


if __name__ == '__main__':
    # Test with current screenshot
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    print("Taking screenshot...")
    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()

    matcher = UpgradeButtonMatcher()
    is_available, avail_score, unavail_score = matcher.check_upgrade_available(frame, debug=True)

    print(f"\nUpgrade button available: {is_available}")
    print(f"  Available score: {avail_score:.4f}")
    print(f"  Unavailable score: {unavail_score:.4f}")
