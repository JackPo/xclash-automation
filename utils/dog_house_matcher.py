"""
Dog House Matcher - Configurable town view anchor detection.

Used to verify the town view is in the correct position before harvesting resources.
Coordinates loaded from config - override in config_local.py for your town layout.
"""

import numpy as np

from config import DOG_HOUSE_POSITION, DOG_HOUSE_SIZE, THRESHOLDS
from utils.template_matcher import match_template


class DogHouseMatcher:
    """Detect dog house at configurable position to verify town view alignment."""

    # Load from config (can be overridden in config_local.py)
    POSITION = DOG_HOUSE_POSITION  # (x, y)
    SIZE = DOG_HOUSE_SIZE  # (width, height)

    TEMPLATE_NAME = "dog_house_4k.png"
    DEFAULT_THRESHOLD = THRESHOLDS.get('dog_house', 0.1)

    def __init__(self, threshold: float = None, debug_dir=None):
        """
        Initialize the dog house matcher.

        Args:
            threshold: Override default threshold
            debug_dir: Ignored (kept for backward compatibility)
        """
        self.threshold = threshold if threshold is not None else self.DEFAULT_THRESHOLD

    def is_aligned(self, frame: np.ndarray) -> tuple[bool, float]:
        """
        Check if the town view is properly aligned (dog house at expected position).

        Args:
            frame: BGR numpy array (4K screenshot)

        Returns:
            (is_aligned, score) - is_aligned=True if dog house is at expected position
        """
        is_aligned, score, _ = match_template(
            frame,
            self.TEMPLATE_NAME,
            position=self.POSITION,
            size=self.SIZE,
            threshold=self.threshold
        )

        return is_aligned, score


def is_town_aligned(frame: np.ndarray) -> bool:
    """
    Quick check if town view is properly aligned.

    Args:
        frame: BGR numpy array (4K screenshot)

    Returns:
        True if dog house is at expected position (town aligned)
    """
    matcher = DogHouseMatcher()
    is_aligned, _ = matcher.is_aligned(frame)
    return is_aligned


if __name__ == "__main__":
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()

    matcher = DogHouseMatcher()
    is_aligned, score = matcher.is_aligned(frame)

    print(f"Dog House Alignment Check")
    print(f"=" * 40)
    print(f"Position: {matcher.POSITION}")
    print(f"Size: {matcher.SIZE}")
    print(f"Threshold: {matcher.threshold}")
    print(f"Score: {score:.4f}")
    print(f"Aligned: {is_aligned}")
