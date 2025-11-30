"""
Dog House Matcher - Fixed-location town view anchor detection.

Used to verify the town view is in the correct position before harvesting resources.
If the dog house is not at the expected location, the view may be panned and
clicking on resource bubbles would hit the wrong coordinates.

Fixed position (4K resolution):
- Position: (1605, 882)
- Size: 172x197
- Template: templates/ground_truth/dog_house_4k.png

Detection uses TM_SQDIFF_NORMED with threshold 0.1.
"""

import cv2
import numpy as np
from pathlib import Path


class DogHouseMatcher:
    """Detect dog house at fixed position to verify town view alignment."""

    # Template path
    TEMPLATE_PATH = Path('templates/ground_truth/dog_house_4k.png')

    # Fixed position (4K resolution)
    POSITION = (1605, 882)  # x, y
    SIZE = (172, 197)  # width, height

    # Detection threshold (TM_SQDIFF_NORMED - lower = better match)
    THRESHOLD = 0.1

    def __init__(self, threshold: float = None, debug_dir: Path = None):
        """
        Initialize the dog house matcher.

        Args:
            threshold: Override default threshold
            debug_dir: Directory to save debug images
        """
        self.template_path = self.TEMPLATE_PATH
        self.threshold = threshold if threshold is not None else self.THRESHOLD
        self.debug_dir = debug_dir

        # Load template
        self.template = cv2.imread(str(self.template_path), cv2.IMREAD_COLOR)
        if self.template is None:
            raise FileNotFoundError(f"Template not found: {self.template_path}")

    def is_aligned(self, frame: np.ndarray) -> tuple[bool, float]:
        """
        Check if the town view is properly aligned (dog house at expected position).

        Args:
            frame: BGR numpy array (4K screenshot)

        Returns:
            (is_aligned, score) - is_aligned=True if dog house is at expected position
        """
        x, y = self.POSITION
        w, h = self.SIZE

        # Extract ROI at fixed position
        roi = frame[y:y+h, x:x+w]

        # Template match
        result = cv2.matchTemplate(roi, self.template, cv2.TM_SQDIFF_NORMED)
        min_val, _, _, _ = cv2.minMaxLoc(result)
        score = float(min_val)

        is_aligned = score < self.threshold

        # Save debug image if enabled
        if self.debug_dir:
            status = "aligned" if is_aligned else "misaligned"
            debug_path = self.debug_dir / f"dog_house_{status}_{score:.3f}.png"
            cv2.imwrite(str(debug_path), roi)

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
    from windows_screenshot_helper import WindowsScreenshotHelper

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
