"""
Unified template matching with automatic mask detection.

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

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional

TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"

# Caches for loaded templates and masks
_templates = {}
_masks = {}
_mask_exists = {}  # Cache for mask existence checks

# Default thresholds
DEFAULT_SQDIFF_THRESHOLD = 0.1   # Max score for TM_SQDIFF_NORMED (lower=better)
DEFAULT_CCORR_THRESHOLD = 0.95   # Min score for TM_CCORR_NORMED with mask (higher=better)


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


def _load_template(name: str) -> Optional[np.ndarray]:
    """Load template (grayscale) with caching."""
    if name not in _templates:
        path = TEMPLATE_DIR / name
        if path.exists():
            _templates[name] = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        else:
            _templates[name] = None
    return _templates[name]


def _load_mask(template_name: str) -> Optional[np.ndarray]:
    """Load mask for template if it exists, with caching."""
    if template_name not in _masks:
        mask_name = _get_mask_name(template_name)
        path = TEMPLATE_DIR / mask_name
        if path.exists():
            _masks[template_name] = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
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


def get_mask_path(template_name: str) -> Optional[Path]:
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
    frame: np.ndarray,
    template_name: str,
    search_region: Optional[Tuple[int, int, int, int]] = None,
    threshold: Optional[float] = None
) -> Tuple[bool, float, Optional[Tuple[int, int]]]:
    """
    Match template in frame with automatic mask detection.

    If a mask file exists (e.g., search_button_mask_4k.png for search_button_4k.png),
    it will be used automatically with TM_CCORR_NORMED matching.
    Otherwise, standard TM_SQDIFF_NORMED matching is used.

    Args:
        frame: BGR or grayscale image
        template_name: Name of template file (e.g., "search_button_4k.png")
        search_region: Optional (x, y, w, h) to limit search area
        threshold: Override default threshold.
                   - For masked (TM_CCORR_NORMED): min required score (default 0.95)
                   - For non-masked (TM_SQDIFF_NORMED): max allowed score (default 0.1)

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
    template = _load_template(template_name)
    if template is None:
        return False, 1.0, None

    mask = _load_mask(template_name)

    # Convert to grayscale if needed
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame

    # Extract search region
    if search_region:
        x, y, w, h = search_region
        search_area = gray[y:y+h, x:x+w]
        offset = (x, y)
    else:
        search_area = gray
        offset = (0, 0)

    th, tw = template.shape

    # Check if search area is large enough
    if search_area.shape[0] < th or search_area.shape[1] < tw:
        return False, 1.0, None

    if mask is not None:
        # Masked matching - TM_CCORR_NORMED (higher = better, ~1.0 is perfect)
        result = cv2.matchTemplate(search_area, template, cv2.TM_CCORR_NORMED, mask=mask)
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


def match_template_fixed(
    frame: np.ndarray,
    template_name: str,
    position: Tuple[int, int],
    size: Tuple[int, int],
    threshold: Optional[float] = None
) -> Tuple[bool, float, Tuple[int, int]]:
    """
    Match template at a fixed position (no searching).

    Useful for validating UI elements at known locations.

    Args:
        frame: BGR or grayscale image
        template_name: Name of template file
        position: (x, y) top-left corner of ROI
        size: (width, height) of ROI
        threshold: Override default threshold

    Returns:
        (found: bool, score: float, center: tuple)
        - center is (x + w//2, y + h//2) - the click position
    """
    template = _load_template(template_name)
    if template is None:
        return False, 1.0, (0, 0)

    mask = _load_mask(template_name)

    # Convert to grayscale if needed
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame

    # Extract ROI
    x, y = position
    w, h = size
    roi = gray[y:y+h, x:x+w]

    # Calculate center (click position)
    center = (x + w // 2, y + h // 2)

    # Check size compatibility
    th, tw = template.shape
    if roi.shape[0] < th or roi.shape[1] < tw:
        return False, 1.0, center

    if mask is not None:
        # Masked matching
        result = cv2.matchTemplate(roi, template, cv2.TM_CCORR_NORMED, mask=mask)
        score = cv2.minMaxLoc(result)[1]  # max_val
        thresh = threshold if threshold is not None else DEFAULT_CCORR_THRESHOLD
        return score >= thresh, score, center
    else:
        # Standard matching
        result = cv2.matchTemplate(roi, template, cv2.TM_SQDIFF_NORMED)
        score = cv2.minMaxLoc(result)[0]  # min_val
        thresh = threshold if threshold is not None else DEFAULT_SQDIFF_THRESHOLD
        return score <= thresh, score, center


def clear_cache():
    """Clear template and mask caches. Useful for testing or reloading."""
    _templates.clear()
    _masks.clear()
    _mask_exists.clear()
