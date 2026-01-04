"""
Unified template matching with automatic mask detection.

Uses COLOR matching by default (not grayscale).

Naming convention:
- Template: `<name>_4k.png`
- Mask: `<name>_mask_4k.png`

If mask exists, uses TM_CCORR_NORMED (higher=better, score ~1.0 is perfect).
If no mask, uses TM_SQDIFF_NORMED (lower=better, score ~0.0 is perfect).

Usage:
    from utils.template_matcher import match_template

    # Simple usage - auto-detects mask
    found, score, location = match_template(frame, "search_button_4k.png")

    # With search region
    found, score, location = match_template(
        frame, "search_button_4k.png",
        search_region=(1600, 1800, 700, 400),
        threshold=0.05
    )

    # Check if template has a mask
    if has_mask("search_button_4k.png"):
        print("Will use masked matching")
"""

from __future__ import annotations

import cv2
import numpy as np
import numpy.typing as npt
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"

# Type alias for numpy arrays (using Any for cv2 compatibility)
from typing import Any
NDArray = npt.NDArray[Any]

# Caches for loaded templates and masks (COLOR by default)
_templates_color: dict[str, NDArray | None] = {}
_templates_gray: dict[str, NDArray | None] = {}
_masks: dict[str, NDArray | None] = {}
_mask_exists: dict[str, bool] = {}  # Cache for mask existence checks

# Default thresholds
DEFAULT_SQDIFF_THRESHOLD = 0.1   # Max score for TM_SQDIFF_NORMED (lower=better)
DEFAULT_CCORR_THRESHOLD = 0.90   # Min score for TM_CCORR_NORMED with mask (higher=better)


def _get_mask_name(template_name: str) -> str:
    """
    Convert template name to mask name.

    Enforced naming convention:
        search_button_4k.png -> search_button_mask_4k.png
        icon_1080p.png -> icon_mask_1080p.png
        other.png -> other_mask.png
    """
    if "_4k.png" in template_name:
        return template_name.replace("_4k.png", "_mask_4k.png")
    elif "_1080p.png" in template_name:
        return template_name.replace("_1080p.png", "_mask_1080p.png")
    else:
        return template_name.replace(".png", "_mask.png")


def _load_template(name: str, grayscale: bool = False) -> NDArray | None:
    """Load template with caching. COLOR by default."""
    cache = _templates_gray if grayscale else _templates_color
    if name not in cache:
        path = TEMPLATE_DIR / name
        if path.exists():
            flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
            img = cv2.imread(str(path), flag)
            cache[name] = img if img is not None else None
        else:
            cache[name] = None
    return cache[name]


def _load_mask(template_name: str) -> NDArray | None:
    """Load mask for template if it exists, with caching."""
    if template_name not in _masks:
        mask_name = _get_mask_name(template_name)
        path = TEMPLATE_DIR / mask_name
        if path.exists():
            img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            _masks[template_name] = img if img is not None else None
            _mask_exists[template_name] = True
        else:
            _masks[template_name] = None
            _mask_exists[template_name] = False
    return _masks[template_name]


def has_mask(template_name: str) -> bool:
    """
    Check if a template has an associated mask file.

    Args:
        template_name: Name of template file (e.g., "search_button_4k.png")

    Returns:
        True if mask file exists, False otherwise
    """
    if template_name not in _mask_exists:
        _load_mask(template_name)  # This populates _mask_exists
    return _mask_exists.get(template_name, False)


def get_mask_path(template_name: str) -> Path:
    """
    Get the expected mask path for a template.

    Args:
        template_name: Name of template file

    Returns:
        Path to mask file (whether it exists or not)
    """
    mask_name = _get_mask_name(template_name)
    return TEMPLATE_DIR / mask_name


def match_template(
    frame: NDArray,
    template_name: str,
    search_region: tuple[int, int, int, int] | None = None,
    threshold: float | None = None,
    grayscale: bool = False
) -> tuple[bool, float, tuple[int, int] | None]:
    """
    Match template in frame with automatic mask detection.

    Uses COLOR matching by default. Set grayscale=True for grayscale matching.

    If a mask file exists (e.g., search_button_mask_4k.png for search_button_4k.png),
    it will be used automatically with TM_CCORR_NORMED matching.
    Otherwise, standard TM_SQDIFF_NORMED matching is used.

    Args:
        frame: BGR image
        template_name: Name of template file (e.g., "search_button_4k.png")
        search_region: Optional (x, y, w, h) to limit search area
        threshold: Override default threshold.
                   - For masked (TM_CCORR_NORMED): min required score (default 0.95)
                   - For non-masked (TM_SQDIFF_NORMED): max allowed score (default 0.1)
        grayscale: Use grayscale matching instead of color (default False)

    Returns:
        (found: bool, score: float, location: tuple or None)
        - found: True if match meets threshold
        - score: Raw matching score (interpretation depends on method)
        - location: Center point (x, y) in original frame coordinates, or None if template not found

    Note:
        Score semantics differ by method:
        - Masked (TM_CCORR_NORMED): higher = better, ~1.0 is perfect match
        - Non-masked (TM_SQDIFF_NORMED): lower = better, ~0.0 is perfect match
    """
    template = _load_template(template_name, grayscale=grayscale)
    if template is None:
        return False, 1.0, None

    mask = _load_mask(template_name)

    # Convert frame if needed
    if grayscale:
        if len(frame.shape) == 3:
            search_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            search_frame = frame
    else:
        search_frame = frame

    # Extract search region
    if search_region:
        x, y, w, h = search_region
        search_area = search_frame[y:y+h, x:x+w]
        offset = (x, y)
    else:
        search_area = search_frame
        offset = (0, 0)

    th, tw = template.shape[:2]

    # Check if search area is large enough
    if search_area.shape[0] < th or search_area.shape[1] < tw:
        return False, 1.0, None

    if mask is not None:
        # Masked matching requires grayscale
        if not grayscale:
            search_area_gray = cv2.cvtColor(search_area, cv2.COLOR_BGR2GRAY) if len(search_area.shape) == 3 else search_area
            template_gray = _load_template(template_name, grayscale=True)
        else:
            search_area_gray = search_area
            template_gray = template

        if template_gray is None:
            return False, 1.0, None

        # Masked matching - TM_CCORR_NORMED (higher = better, ~1.0 is perfect)
        result = cv2.matchTemplate(search_area_gray, template_gray, cv2.TM_CCORR_NORMED, mask=mask)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        location = (offset[0] + max_loc[0] + tw // 2, offset[1] + max_loc[1] + th // 2)

        thresh = threshold if threshold is not None else DEFAULT_CCORR_THRESHOLD
        found = max_val >= thresh
        return found, max_val, location
    else:
        # Standard matching - TM_SQDIFF_NORMED (lower = better, ~0.0 is perfect)
        result = cv2.matchTemplate(search_area, template, cv2.TM_SQDIFF_NORMED)
        min_val, _, min_loc, _ = cv2.minMaxLoc(result)
        location = (offset[0] + min_loc[0] + tw // 2, offset[1] + min_loc[1] + th // 2)

        thresh = threshold if threshold is not None else DEFAULT_SQDIFF_THRESHOLD
        found = min_val <= thresh
        return found, min_val, location


def clear_cache() -> None:
    """Clear template and mask caches. Useful for testing or reloading."""
    _templates_color.clear()
    _templates_gray.clear()
    _masks.clear()
    _mask_exists.clear()
