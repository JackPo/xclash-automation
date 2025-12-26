"""
Arms Race OCR helper for extracting scores and detecting events.

Provides fixed-position OCR extraction for the Arms Race panel:
- Current points (player's score)
- Chest thresholds (chest1, chest2, chest3)
- Event title detection

All coordinates are for 4K resolution (3840x2160).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# OCR region coordinates (4K resolution)
# Format: (x, y, width, height)
TITLE_REGION = (1405, 116, 791, 74)
CURRENT_POINTS_REGION = (1466, 693, 135, 50)
CHEST1_REGION = (1363, 1054, 349, 92)
CHEST2_REGION = (1743, 1054, 353, 92)
CHEST3_REGION = (2119, 1054, 346, 92)

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"


def extract_region(frame: np.ndarray, region: tuple[int, int, int, int]) -> np.ndarray:
    """Extract a region from the frame."""
    x, y, w, h = region
    return frame[y:y+h, x:x+w]


def ocr_number_from_region(frame: np.ndarray, region: tuple[int, int, int, int]) -> int | None:
    """Extract a number from a specific region using OCR."""
    from utils.ocr_client import OCRClient

    roi = extract_region(frame, region)
    if roi.size == 0:
        return None

    ocr = OCRClient()
    return ocr.extract_number(roi)


def get_current_points(frame: np.ndarray) -> int | None:
    """Get the player's current points from the Arms Race panel."""
    return ocr_number_from_region(frame, CURRENT_POINTS_REGION)


def get_chest_thresholds(frame: np.ndarray) -> dict[str, int | None]:
    """Get all three chest thresholds from the Arms Race panel."""
    return {
        "chest1": ocr_number_from_region(frame, CHEST1_REGION),
        "chest2": ocr_number_from_region(frame, CHEST2_REGION),
        "chest3": ocr_number_from_region(frame, CHEST3_REGION),
    }


def get_all_scores(frame: np.ndarray) -> dict[str, int | None]:
    """Get current points and all chest thresholds."""
    thresholds = get_chest_thresholds(frame)
    return {
        "current_points": get_current_points(frame),
        **thresholds,
    }


def detect_active_event(frame: np.ndarray) -> tuple[str | None, float]:
    """
    Detect which Arms Race event is active by matching title templates.

    Returns:
        Tuple of (event_name, best_score) or (None, 1.0) if no match
    """
    from utils.arms_race import ARMS_RACE_EVENTS

    # Extract title region
    title_roi = extract_region(frame, TITLE_REGION)
    if title_roi.size == 0:
        return None, 1.0

    # Convert to grayscale
    if len(title_roi.shape) == 3:
        title_gray = cv2.cvtColor(title_roi, cv2.COLOR_BGR2GRAY)
    else:
        title_gray = title_roi

    best_event = None
    best_score = 1.0

    for event_name, metadata in ARMS_RACE_EVENTS.items():
        template_name = metadata.get("header_template")
        if not template_name:
            continue

        template_path = TEMPLATE_DIR / template_name
        if not template_path.exists():
            continue

        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            continue

        # Resize template if needed (should be same size ideally)
        if template.shape != title_gray.shape:
            # Try matching anyway - matchTemplate handles size differences
            pass

        try:
            result = cv2.matchTemplate(title_gray, template, cv2.TM_SQDIFF_NORMED)
            min_val, _, _, _ = cv2.minMaxLoc(result)

            if min_val < best_score:
                best_score = min_val
                best_event = event_name
        except cv2.error:
            continue

    return best_event, best_score


def is_arms_race_panel_open(frame: np.ndarray, threshold: float = 0.1) -> bool:
    """
    Check if the Arms Race panel is currently open.

    Uses template matching on the active Arms Race icon button.
    """
    # Check for active Arms Race icon
    active_template_path = TEMPLATE_DIR / "arms_race_icon_active_4k.png"
    if not active_template_path.exists():
        return False

    template = cv2.imread(str(active_template_path))
    if template is None:
        return False

    # Arms Race icon position
    ICON_X, ICON_Y = 1512, 1935
    ICON_W, ICON_H = 227, 219

    roi = frame[ICON_Y:ICON_Y+ICON_H, ICON_X:ICON_X+ICON_W]
    if roi.size == 0:
        return False

    # Convert to grayscale
    if len(roi.shape) == 3:
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    else:
        roi_gray = roi

    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

    result = cv2.matchTemplate(roi_gray, template_gray, cv2.TM_SQDIFF_NORMED)
    min_val, _, _, _ = cv2.minMaxLoc(result)

    return min_val <= threshold


if __name__ == "__main__":
    # Test the OCR functions
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    print("Testing Arms Race OCR...")

    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()

    # Check if panel is open
    panel_open = is_arms_race_panel_open(frame)
    print(f"\nArms Race panel open: {panel_open}")

    if panel_open:
        # Detect active event
        event, score = detect_active_event(frame)
        print(f"Active event: {event} (score={score:.4f})")

        # Get scores
        scores = get_all_scores(frame)
        print(f"\nScores:")
        for key, value in scores.items():
            print(f"  {key}: {value}")
    else:
        print("Arms Race panel is not open - cannot extract scores")
