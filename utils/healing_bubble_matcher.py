"""
Healing Bubble Matcher - Detects the healing briefcase icon above the hospital.

Fixed position detection at (3302, 343) size 77x43.
Click position: (3340, 364)

Template: healing_bubble_4k.png
"""

from pathlib import Path
import cv2
import numpy as np

# Template path
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "ground_truth" / "healing_bubble_4k.png"

# Fixed position (4K resolution)
ICON_X = 3302
ICON_Y = 343
ICON_WIDTH = 77
ICON_HEIGHT = 43

# Click position (center of icon)
CLICK_X = 3340
CLICK_Y = 364

# Match threshold (TM_SQDIFF_NORMED - lower is better)
MATCH_THRESHOLD = 0.06


class HealingBubbleMatcher:
    """Detects the healing bubble icon at fixed position."""

    def __init__(self):
        self.template = cv2.imread(str(TEMPLATE_PATH))
        if self.template is None:
            raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")
        self.template_h, self.template_w = self.template.shape[:2]

    def is_present(self, frame: np.ndarray, debug: bool = False) -> tuple[bool, float]:
        """
        Check if healing bubble is present at fixed position.

        Args:
            frame: BGR numpy array screenshot (4K resolution)
            debug: Enable debug output

        Returns:
            tuple: (is_present: bool, score: float)
        """
        # Extract ROI at fixed position
        roi = frame[ICON_Y:ICON_Y + self.template_h, ICON_X:ICON_X + self.template_w]

        # Template match
        result = cv2.matchTemplate(roi, self.template, cv2.TM_SQDIFF_NORMED)
        score = result[0, 0]

        is_present = score < MATCH_THRESHOLD

        if debug:
            print(f"  Healing bubble: score={score:.6f}, threshold={MATCH_THRESHOLD}, present={is_present}")

        return is_present, score

    def get_click_position(self) -> tuple[int, int]:
        """Return the click position for the healing bubble."""
        return (CLICK_X, CLICK_Y)


# Singleton instance
_matcher = None


def get_matcher() -> HealingBubbleMatcher:
    """Get singleton matcher instance."""
    global _matcher
    if _matcher is None:
        _matcher = HealingBubbleMatcher()
    return _matcher


def is_healing_present(frame: np.ndarray, debug: bool = False) -> tuple[bool, float]:
    """Convenience function to check if healing bubble is present."""
    return get_matcher().is_present(frame, debug=debug)


def get_healing_click() -> tuple[int, int]:
    """Convenience function to get click position."""
    return get_matcher().get_click_position()
