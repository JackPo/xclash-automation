"""
Upgrade Button Matcher - Detects available/unavailable upgrade buttons in hero detail view.

Uses template_matcher for search-based detection.
Compares two templates to distinguish between green (available) and grayed (unavailable) upgrade buttons.
"""
from __future__ import annotations

import re
from typing import Any

import numpy as np
import numpy.typing as npt

from utils.template_matcher import match_template

# Fixed search region for upgrade button (4K resolution)
UPGRADE_BUTTON_REGION = (1700, 1750, 450, 160)  # x, y, w, h

# Click position (center of button)
UPGRADE_BUTTON_CLICK = (1919, 1829)

# Resource cost line ("OWNED / REQUIRED", e.g. "6479M/7680K") sits just
# above the Upgrade button. Used to decide whether we have enough to
# afford the upgrade before clicking.
UPGRADE_RESOURCE_REGION = (1500, 1700, 900, 80)  # x, y, w, h

# Matching threshold
THRESHOLD = 0.1  # TM_SQDIFF_NORMED - lower is better

_SUFFIX_MULTIPLIERS = {
    "": 1,
    "K": 1_000,
    "M": 1_000_000,
    "B": 1_000_000_000,
    "T": 1_000_000_000_000,
}


def parse_resource_amount(s: str) -> int | None:
    """Parse a single amount like '6479M', '7.68B', '12345', or '6,479M'.

    Returns the value in absolute units (e.g. '7.68B' -> 7_680_000_000), or
    None if the string can't be parsed.
    """
    if not s:
        return None
    s = s.strip().replace(",", "").upper()
    m = re.fullmatch(r"([\d.]+)\s*([KMBT]?)", s)
    if not m:
        return None
    try:
        value = float(m.group(1))
    except ValueError:
        return None
    suffix = m.group(2)
    mult = _SUFFIX_MULTIPLIERS.get(suffix)
    if mult is None:
        return None
    return int(value * mult)


def parse_resource_line(text: str) -> tuple[int | None, int | None]:
    """Parse 'OWNED / REQUIRED' text. Tolerant of OCR whitespace quirks.

    Returns (owned, required). Either or both may be None if unparseable.
    """
    if not text:
        return None, None
    # Strip non-resource chrome that OCR sometimes prepends.
    cleaned = text.strip()
    if "/" not in cleaned:
        return None, None
    left, _, right = cleaned.partition("/")
    return parse_resource_amount(left), parse_resource_amount(right)


class UpgradeButtonMatcher:
    """Detects upgrade button state using two-template comparison."""

    AVAILABLE_TEMPLATE = "upgrade_button_available_4k.png"
    UNAVAILABLE_TEMPLATE = "upgrade_button_unavailable_4k.png"

    def __init__(self, threshold: float | None = None):
        self.threshold = threshold if threshold is not None else THRESHOLD

    def check_upgrade_available(self, frame: npt.NDArray[Any], debug: bool = False) -> tuple[bool, float, float]:
        """
        Check if upgrade button is available (green) or unavailable (grayed).

        Args:
            frame: Full screenshot (BGR numpy array)
            debug: If True, print debug info

        Returns:
            (is_available, available_score, unavailable_score)
            is_available is True if green upgrade button detected
        """
        if frame is None or frame.size == 0:
            return False, 1.0, 1.0

        # Match both templates in the search region
        _, available_score, _ = match_template(
            frame,
            self.AVAILABLE_TEMPLATE,
            search_region=UPGRADE_BUTTON_REGION,
            threshold=self.threshold
        )

        _, unavailable_score, _ = match_template(
            frame,
            self.UNAVAILABLE_TEMPLATE,
            search_region=UPGRADE_BUTTON_REGION,
            threshold=self.threshold
        )

        if debug:
            print(f"  Upgrade button - available: {available_score:.4f}, unavailable: {unavailable_score:.4f}")

        # Return True if available matches better than unavailable
        # Both must be under threshold to be considered a valid button
        if available_score < self.threshold and available_score < unavailable_score:
            return True, available_score, unavailable_score
        elif unavailable_score < self.threshold:
            return False, available_score, unavailable_score
        else:
            # Neither matches well - button not visible
            return False, available_score, unavailable_score

    def get_click_position(self) -> tuple[int, int]:
        """Get the click position for the upgrade button."""
        return UPGRADE_BUTTON_CLICK

    def read_resource_cost(
        self,
        frame: npt.NDArray[Any],
        ocr_client: Any = None,
        debug: bool = False,
    ) -> tuple[int | None, int | None, str]:
        """OCR the 'OWNED / REQUIRED' line above the Upgrade button.

        Returns (owned, required, raw_text). Owned and required are absolute
        integer counts; None if unreadable.
        """
        if frame is None or frame.size == 0:
            return None, None, ""
        x, y, w, h = UPGRADE_RESOURCE_REGION
        crop = frame[y:y+h, x:x+w]
        if ocr_client is None:
            from utils.ocr_client import ocr_extract_text
            text = ocr_extract_text(crop, prompt="Read the text. Return exactly what you see.")
        else:
            text = ocr_client.extract_text(crop, prompt="Read the text. Return exactly what you see.")
        owned, required = parse_resource_line(text)
        if debug:
            print(f"  Resource line raw={text!r} -> owned={owned} required={required}")
        return owned, required, text or ""


if __name__ == '__main__':
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    print("Taking screenshot...")
    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()

    matcher = UpgradeButtonMatcher()
    is_available, avail_score, unavail_score = matcher.check_upgrade_available(frame, debug=True)

    print(f"\nUpgrade button available: {is_available}")
    print(f"  Available score: {avail_score:.4f}")
    print(f"  Unavailable score: {unavail_score:.4f}")
