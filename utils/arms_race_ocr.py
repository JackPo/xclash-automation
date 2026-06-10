"""
Arms Race OCR helper for extracting scores and detecting events.

Provides fixed-position OCR extraction for the Arms Race panel:
- Current points (player's score)
- Chest thresholds (chest1, chest2, chest3)
- Event title detection

All coordinates are for 4K resolution (3840x2160).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

logger = logging.getLogger(__name__)

# Arms Race blocks last 4 hours; a stored score older than this is from a
# previous block and must not be used as a monotonic floor.
SAME_BLOCK_MAX_AGE_SECONDS = 4 * 3600

# OCR region coordinates (4K resolution)
# Format: (x, y, width, height)
TITLE_REGION = (1405, 116, 791, 74)
CURRENT_POINTS_REGION = (1350, 693, 265, 50)  # Wide enough for 8+ digits, coin icon OK
CHEST1_REGION = (1363, 1054, 349, 92)
CHEST2_REGION = (1743, 1054, 353, 92)
CHEST3_REGION = (2119, 1054, 346, 92)

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"


def extract_region(frame: npt.NDArray[Any], region: tuple[int, int, int, int]) -> npt.NDArray[Any]:
    """Extract a region from the frame."""
    x, y, w, h = region
    return frame[y:y+h, x:x+w]


def ocr_number_from_region(frame: npt.NDArray[Any], region: tuple[int, int, int, int]) -> int | None:
    """Extract a number from a specific region using OCR."""
    from utils.ocr_client import OCRClient

    roi = extract_region(frame, region)
    if roi.size == 0:
        return None

    ocr = OCRClient()
    return ocr.extract_number(roi)


def get_current_points(frame: npt.NDArray[Any]) -> int | None:
    """Get the player's current points from the Arms Race panel (single frame)."""
    return ocr_number_from_region(frame, CURRENT_POINTS_REGION)


def get_last_confirmed_points(
    event: str | None,
    block_start: datetime | None = None,
) -> int | None:
    """
    Last confirmed Arms Race score usable as a monotonic floor.

    Returns the score stored in current_state only if it is for the same
    event AND from the current block (timestamp >= block_start when given,
    otherwise younger than one block length). Scores from a previous block
    must not constrain the new block, which starts back at 0.
    """
    from utils.current_state import get_arms_race_score

    last = get_arms_race_score()
    points = last.get("current_points")
    if points is None:
        return None

    if event and last.get("event") and last["event"] != event:
        return None

    ts_raw = last.get("timestamp")
    if not ts_raw:
        return None
    try:
        ts = datetime.fromisoformat(ts_raw)
    except (ValueError, TypeError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    if block_start is not None:
        try:
            if ts < block_start:
                return None
        except TypeError:
            return None  # naive/aware mismatch - can't trust the comparison
    elif (datetime.now(timezone.utc) - ts).total_seconds() > SAME_BLOCK_MAX_AGE_SECONDS:
        return None

    return int(points)


def get_current_points_verified(
    win: WindowsScreenshotHelper,
    retries: int = 3,
    last_known: int | None = None,
) -> int | None:
    """
    Get the player's current points with consensus + plausibility verification.

    Takes multiple screenshots and performs OCR on each. A value needs at
    least 2 matching readings. When last_known (same event, same block) is
    provided, one extra rule applies, because scores within a block only go up:

    - A consensus value BELOW last_known is rejected unless every reading
      unanimously agrees (unanimity means our stored state was stale, not OCR
      noise - accept with a warning).

    Upward jumps of any size are accepted - scores legitimately leap when
    rallies complete while the panel is closed.

    Args:
        win: WindowsScreenshotHelper instance
        retries: Number of screenshot/OCR attempts (default 3)
        last_known: Last confirmed score for this event in this block, if any

    Returns:
        Points if consistent and plausible, None otherwise
    """
    import time
    from collections import Counter

    results = []
    for i in range(retries):
        frame = win.get_screenshot_cv2()
        val = ocr_number_from_region(frame, CURRENT_POINTS_REGION)
        if val is not None:
            results.append(val)
        if i < retries - 1:
            time.sleep(0.1)  # Small delay between screenshots

    if not results:
        return None

    counter = Counter(results)
    most_common, count = counter.most_common(1)[0]

    if count < 2:
        logger.warning(f"ARMS RACE OCR: no consensus across {retries} reads: {results}")
        return None

    if last_known is not None and most_common < last_known:
        if count == retries:
            logger.warning(
                f"ARMS RACE OCR: unanimous reading {most_common} below last known "
                f"{last_known} - accepting, stored state was presumably stale"
            )
            return most_common
        logger.warning(
            f"ARMS RACE OCR: reading {most_common} below last known {last_known} "
            f"without unanimity ({count}/{retries}, all reads: {results}) - rejecting"
        )
        return None

    return most_common


def get_chest_thresholds(frame: npt.NDArray[Any]) -> dict[str, int | None]:
    """Get all three chest thresholds from the Arms Race panel."""
    return {
        "chest1": ocr_number_from_region(frame, CHEST1_REGION),
        "chest2": ocr_number_from_region(frame, CHEST2_REGION),
        "chest3": ocr_number_from_region(frame, CHEST3_REGION),
    }


def get_all_scores(frame: npt.NDArray[Any]) -> dict[str, int | None]:
    """Get current points and all chest thresholds."""
    thresholds = get_chest_thresholds(frame)
    return {
        "current_points": get_current_points(frame),
        **thresholds,
    }


def detect_active_event(frame: npt.NDArray[Any]) -> tuple[str | None, float]:
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
        if not isinstance(metadata, dict):
            continue
        template_name = metadata.get("header_template")
        if not template_name or not isinstance(template_name, str):
            continue

        template_path = TEMPLATE_DIR / template_name
        if not template_path.exists():
            continue

        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            continue  # type: ignore[unreachable]

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


def is_arms_race_panel_open(frame: npt.NDArray[Any], threshold: float = 0.1) -> bool:
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
        return False  # type: ignore[unreachable]

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
