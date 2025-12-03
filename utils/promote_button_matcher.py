"""
Promote Button Matcher - Detects "Promote" button in upgrade panel.

Uses fixed-location template matching on the "Promote" text.
Position: (2065, 1648), Size: 181x54
Click position: (2157, 1697) - center of full button
"""

import cv2
import numpy as np
from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "ground_truth" / "promote_text_4k.png"

# Fixed location for promote text
PROMOTE_REGION = (2065, 1648, 181, 54)  # x, y, width, height

# Click position (center of button, not text)
PROMOTE_CLICK = (2157, 1697)

# Match threshold (TM_SQDIFF_NORMED - lower is better)
THRESHOLD = 0.1


class PromoteButtonMatcher:
    """Detects Promote button using fixed-location template matching."""

    def __init__(self):
        self.template = cv2.imread(str(TEMPLATE_PATH))
        if self.template is None:
            raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")

    def is_present(self, frame, debug=False):
        """
        Check if Promote button is visible at fixed location.

        Args:
            frame: BGR numpy array (screenshot)
            debug: Save debug image if True

        Returns:
            tuple: (is_present: bool, score: float)
        """
        x, y, w, h = PROMOTE_REGION

        # Extract ROI at fixed location
        roi = frame[y:y+h, x:x+w]

        # Resize template to match ROI if needed
        template = self.template
        if roi.shape[:2] != template.shape[:2]:
            template = cv2.resize(template, (roi.shape[1], roi.shape[0]))

        # Template match
        result = cv2.matchTemplate(roi, template, cv2.TM_SQDIFF_NORMED)
        score = result[0, 0]

        is_match = score < THRESHOLD

        if debug:
            status = "present" if is_match else "absent"
            debug_path = Path(__file__).parent.parent / "templates" / "debug" / f"promote_{status}_{score:.3f}.png"
            cv2.imwrite(str(debug_path), roi)
            print(f"Promote button: {status} (score={score:.4f}, threshold={THRESHOLD})")

        return is_match, score

    def get_click_position(self):
        """Return the click position for the Promote button."""
        return PROMOTE_CLICK


# Module-level singleton
_matcher = None

def get_matcher():
    """Get or create singleton matcher instance."""
    global _matcher
    if _matcher is None:
        _matcher = PromoteButtonMatcher()
    return _matcher


def is_promote_visible(frame, debug=False):
    """Check if Promote button is visible."""
    return get_matcher().is_present(frame, debug=debug)


def get_promote_click():
    """Get click position for Promote button."""
    return get_matcher().get_click_position()


if __name__ == "__main__":
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()

    is_present, score = is_promote_visible(frame, debug=True)
    print(f"Promote button present: {is_present}, score: {score:.4f}")
    print(f"Click position: {get_promote_click()}")
