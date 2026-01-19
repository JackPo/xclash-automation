"""
Tavern Quest Counter Reader - OCR for Assist Allies and Plunder Others counters.

Reads the "X/5" format counters from the tavern quest screen.

Usage:
    from utils.tavern_counter_reader import read_tavern_counters, read_assist_counter

    counters = read_tavern_counters(frame)
    print(f"Assist: {counters['assist_allies']}")  # (2, 5)
    print(f"Plunder: {counters['plunder_others']}")  # (0, 5)
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy.typing as npt

# OCR regions for counters (4K resolution)
# Format: (x, y, width, height)
ASSIST_ALLIES_REGION = (1700, 545, 120, 65)
PLUNDER_OTHERS_REGION = (1700, 608, 120, 65)


def _parse_counter(text: str) -> tuple[int, int] | None:
    """
    Parse "X/Y" format text into (current, max) tuple.

    Args:
        text: OCR text like "2/5" or "0/5"

    Returns:
        Tuple of (current, max) or None if parse failed
    """
    if not text:
        return None

    # Match patterns like "2/5", "0/5", etc.
    match = re.search(r'(\d+)\s*/\s*(\d+)', text)
    if match:
        current = int(match.group(1))
        maximum = int(match.group(2))
        return (current, maximum)

    return None


def read_assist_counter(frame: npt.NDArray[Any]) -> tuple[int, int] | None:
    """
    Read the Assist Allies counter from tavern quest screen.

    Args:
        frame: BGR image from WindowsScreenshotHelper

    Returns:
        Tuple of (current, max) like (2, 5) or None if failed
    """
    from utils.ocr_client import OCRClient

    ocr = OCRClient()
    text = ocr.extract_text(
        frame,
        region=ASSIST_ALLIES_REGION,
        prompt="Extract only the counter number in X/Y format like '2/5'"
    )

    return _parse_counter(text)


def read_plunder_counter(frame: npt.NDArray[Any]) -> tuple[int, int] | None:
    """
    Read the Plunder Others counter from tavern quest screen.

    Args:
        frame: BGR image from WindowsScreenshotHelper

    Returns:
        Tuple of (current, max) like (0, 5) or None if failed
    """
    from utils.ocr_client import OCRClient

    ocr = OCRClient()
    text = ocr.extract_text(
        frame,
        region=PLUNDER_OTHERS_REGION,
        prompt="Extract only the counter number in X/Y format like '2/5'"
    )

    return _parse_counter(text)


def read_tavern_counters(frame: npt.NDArray[Any]) -> dict[str, tuple[int, int] | None]:
    """
    Read both Assist Allies and Plunder Others counters.

    Args:
        frame: BGR image from WindowsScreenshotHelper

    Returns:
        Dict with keys 'assist_allies' and 'plunder_others',
        values are (current, max) tuples or None if failed
    """
    return {
        "assist_allies": read_assist_counter(frame),
        "plunder_others": read_plunder_counter(frame),
    }


if __name__ == "__main__":
    import cv2
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    print("Reading tavern counters from current screen...")

    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()

    counters = read_tavern_counters(frame)

    print(f"\nResults:")
    print(f"  Assist Allies: {counters['assist_allies']}")
    print(f"  Plunder Others: {counters['plunder_others']}")

    # Also save the ROI images for debugging
    x, y, w, h = ASSIST_ALLIES_REGION
    assist_roi = frame[y:y+h, x:x+w]
    cv2.imwrite("screenshots/debug/assist_counter_roi.png", assist_roi)

    x, y, w, h = PLUNDER_OTHERS_REGION
    plunder_roi = frame[y:y+h, x:x+w]
    cv2.imwrite("screenshots/debug/plunder_counter_roi.png", plunder_roi)

    print("\nDebug ROIs saved to screenshots/debug/")
