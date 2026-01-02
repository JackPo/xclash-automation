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

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional

TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"

# Caches for loaded templates and masks (COLOR by default)
_templates_color = {}
_templates_gray = {}
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


def _load_template(name: str, grayscale: bool = False) -> Optional[np.ndarray]:
    """Load template with caching. COLOR by default."""
    cache = _templates_gray if grayscale else _templates_color
    if name not in cache:
        path = TEMPLATE_DIR / name
        if path.exists():
            flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
            cache[name] = cv2.imread(str(path), flag)
        else:
            cache[name] = None
    return cache[name]


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
    threshold: Optional[float] = None,
    grayscale: bool = False
) -> Tuple[bool, float, Optional[Tuple[int, int]]]:
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


def match_template_fixed(
    frame: np.ndarray,
    template_name: str,
    position: Tuple[int, int],
    size: Tuple[int, int],
    threshold: Optional[float] = None,
    grayscale: bool = False
) -> Tuple[bool, float, Tuple[int, int]]:
    """
    Match template at a fixed position (no searching).

    Uses COLOR matching by default. Set grayscale=True for grayscale matching.

    Useful for validating UI elements at known locations.

    Args:
        frame: BGR image
        template_name: Name of template file
        position: (x, y) top-left corner of ROI
        size: (width, height) of ROI
        threshold: Override default threshold
        grayscale: Use grayscale matching instead of color (default False)

    Returns:
        (found: bool, score: float, center: tuple)
        - center is (x + w//2, y + h//2) - the click position
    """
    template = _load_template(template_name, grayscale=grayscale)
    if template is None:
        return False, 1.0, (0, 0)

    mask = _load_mask(template_name)

    # Convert frame if needed
    if grayscale:
        if len(frame.shape) == 3:
            match_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            match_frame = frame
    else:
        match_frame = frame

    # Extract ROI
    x, y = position
    w, h = size
    roi = match_frame[y:y+h, x:x+w]

    # Calculate center (click position)
    center = (x + w // 2, y + h // 2)

    # Check size compatibility
    th, tw = template.shape[:2]
    if roi.shape[0] < th or roi.shape[1] < tw:
        return False, 1.0, center

    if mask is not None:
        # Masked matching requires grayscale
        if not grayscale:
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
            template_gray = _load_template(template_name, grayscale=True)
        else:
            roi_gray = roi
            template_gray = template

        # Masked matching
        result = cv2.matchTemplate(roi_gray, template_gray, cv2.TM_CCORR_NORMED, mask=mask)
        score = cv2.minMaxLoc(result)[1]  # max_val
        thresh = threshold if threshold is not None else DEFAULT_CCORR_THRESHOLD
        return score >= thresh, score, center
    else:
        # Standard matching
        result = cv2.matchTemplate(roi, template, cv2.TM_SQDIFF_NORMED)
        score = cv2.minMaxLoc(result)[0]  # min_val
        thresh = threshold if threshold is not None else DEFAULT_SQDIFF_THRESHOLD
        return score <= thresh, score, center


def match_template_all(
    frame: np.ndarray,
    template_name: str,
    search_region: Optional[Tuple[int, int, int, int]] = None,
    threshold: Optional[float] = None,
    min_distance: int = 50,
    grayscale: bool = True
) -> list:
    """
    Find ALL matches of a template in frame (not just the best one).

    Useful for finding multiple instances like badge icons, plus buttons, etc.

    Args:
        frame: BGR image
        template_name: Name of template file
        search_region: Optional (x, y, w, h) to limit search area
        threshold: Max score for TM_SQDIFF_NORMED (default 0.1)
        min_distance: Minimum pixels between matches to avoid duplicates
        grayscale: Use grayscale matching (default True for multi-match)

    Returns:
        List of (center_x, center_y, score) tuples, sorted by Y then X.
        Returns empty list if no matches found.

    Note:
        Only supports TM_SQDIFF_NORMED (no masked matching for multi-match).
    """
    template = _load_template(template_name, grayscale=True)
    if template is None:
        return []

    # Convert frame to grayscale
    if len(frame.shape) == 3:
        search_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
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
        return []

    # Template match
    result = cv2.matchTemplate(search_area, template, cv2.TM_SQDIFF_NORMED)

    # Find all matches below threshold
    thresh = threshold if threshold is not None else DEFAULT_SQDIFF_THRESHOLD
    locations = np.where(result < thresh)

    matches = []
    for pt in zip(*locations[::-1]):  # x, y format
        score = float(result[pt[1], pt[0]])
        center_x = offset[0] + pt[0] + tw // 2
        center_y = offset[1] + pt[1] + th // 2
        matches.append((center_x, center_y, score))

    if not matches:
        return []

    # Remove duplicates (matches too close together)
    # Sort by score first, keep best matches when there are duplicates
    filtered = []
    for match in sorted(matches, key=lambda x: x[2]):
        x, y, score = match
        is_duplicate = False
        for fx, fy, _ in filtered:
            if abs(x - fx) < min_distance and abs(y - fy) < min_distance:
                is_duplicate = True
                break
        if not is_duplicate:
            filtered.append(match)

    # Sort by Y (top to bottom), then X (left to right)
    filtered.sort(key=lambda m: (m[1], m[0]))

    return filtered


def clear_cache():
    """Clear template and mask caches. Useful for testing or reloading."""
    _templates_color.clear()
    _templates_gray.clear()
    _masks.clear()
    _mask_exists.clear()
