"""
Unified template matching with automatic mask detection.

Uses COLOR matching by default (not grayscale).
Uses GPU (CUDA) for full-frame searches when available (20x faster).

Naming convention:
- Template: `<name>_4k.png`
- Mask: `<name>_mask_4k.png`

Uses TM_SQDIFF_NORMED for non-masked, TM_CCORR_NORMED for masked (converted to lower=better).
Score ~0.0 is always a perfect match.

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

# GPU template cache and matchers
_gpu_templates: dict[str, Any] = {}  # cv2.cuda_GpuMat
_gpu_matchers: dict[str, Any] = {}  # cv2.cuda.TemplateMatching

# Check CUDA availability and initialize device once at import
try:
    _CUDA_DEVICE_COUNT = cv2.cuda.getCudaEnabledDeviceCount()
    if _CUDA_DEVICE_COUNT > 0:
        cv2.cuda.setDevice(0)
except Exception:
    _CUDA_DEVICE_COUNT = 0


def _is_gpu_enabled() -> bool:
    """Check if GPU template matching is enabled and available."""
    if _CUDA_DEVICE_COUNT == 0:
        return False
    try:
        from config import GPU_TEMPLATE_MATCHING
        return GPU_TEMPLATE_MATCHING
    except ImportError:
        return True  # Default to GPU if config not available

# Default thresholds (all TM_SQDIFF_NORMED: lower=better)
DEFAULT_THRESHOLD = 0.1   # Max score for TM_SQDIFF_NORMED
DEFAULT_MASKED_THRESHOLD = 0.05   # Stricter threshold for masked matching


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


def _get_gpu_template(name: str, template: NDArray) -> Any:
    """Get GPU-uploaded template with caching."""
    if name not in _gpu_templates:
        gpu_template = cv2.cuda_GpuMat()
        gpu_template.upload(template)
        _gpu_templates[name] = gpu_template
    return _gpu_templates[name]


def _get_gpu_matcher(template_type: int, method: int) -> Any:
    """Get GPU template matcher with caching."""
    key = (template_type, method)
    if key not in _gpu_matchers:
        _gpu_matchers[key] = cv2.cuda.createTemplateMatching(template_type, method)
    return _gpu_matchers[key]


# Cache for masked matching data: (gpu_masked_template, gpu_mask_squared, template_energy)
_gpu_masked_data: dict[str, tuple[Any, Any, float]] = {}


def _match_template_gpu(
    frame: NDArray,
    template: NDArray,
    template_name: str,
    method: int = cv2.TM_SQDIFF_NORMED
) -> tuple[float, tuple[int, int]]:
    """
    GPU-accelerated template matching for full-frame searches.

    Returns (score, location) where score uses same convention as CPU (lower=better for SQDIFF).
    """
    # Upload frame to GPU (not cached - changes each call)
    gpu_frame = cv2.cuda_GpuMat()
    gpu_frame.upload(frame)

    # Get cached GPU template
    gpu_template = _get_gpu_template(template_name, template)

    # Get or create matcher
    template_type = cv2.CV_8UC3 if len(template.shape) == 3 else cv2.CV_8UC1
    matcher = _get_gpu_matcher(template_type, method)

    # Match
    gpu_result = matcher.match(gpu_frame, gpu_template)

    # Download result
    result = gpu_result.download()

    # Find best match
    th, tw = template.shape[:2]
    if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
        min_val, _, min_loc, _ = cv2.minMaxLoc(result)
        location = (min_loc[0] + tw // 2, min_loc[1] + th // 2)
        return min_val, location
    else:
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        location = (max_loc[0] + tw // 2, max_loc[1] + th // 2)
        # Convert to lower=better for consistent interface
        return 1.0 - max_val, location


def _get_gpu_masked_data(template_name: str, template: NDArray, mask: NDArray) -> tuple[Any, Any, float]:
    """
    Get cached GPU data for masked matching.

    Returns: (gpu_masked_template, gpu_mask_squared, template_energy)
    - gpu_masked_template: T * M uploaded to GPU
    - gpu_mask_squared: M^2 uploaded to GPU (for frame energy computation)
    - template_energy: sum((T * M)^2) precomputed
    """
    if template_name not in _gpu_masked_data:
        # Expand mask to 3 channels if needed
        if len(template.shape) == 3 and len(mask.shape) == 2:
            mask_3ch = np.stack([mask, mask, mask], axis=-1)
        else:
            mask_3ch = mask

        # Normalize mask to 0-1 range
        mask_norm = mask_3ch.astype(np.float32) / 255.0

        # Compute masked template: T * M
        masked_template = (template.astype(np.float32) * mask_norm).astype(np.uint8)

        # Compute template energy: sum((T * M)^2)
        template_energy = float(np.sum((template.astype(np.float64) * mask_norm) ** 2))

        # Compute mask squared for frame energy computation
        # For grayscale frame matching, we need single channel M^2
        mask_sq = (mask.astype(np.float32) / 255.0) ** 2
        mask_sq_uint8 = (mask_sq * 255).astype(np.uint8)

        # Upload to GPU
        gpu_masked_template = cv2.cuda_GpuMat()
        gpu_masked_template.upload(masked_template)

        gpu_mask_sq = cv2.cuda_GpuMat()
        gpu_mask_sq.upload(mask_sq_uint8)

        _gpu_masked_data[template_name] = (gpu_masked_template, gpu_mask_sq, template_energy)

    return _gpu_masked_data[template_name]


def _match_template_gpu_masked(
    frame: NDArray,
    template: NDArray,
    mask: NDArray,
    template_name: str
) -> tuple[float, tuple[int, int]]:
    """
    GPU-accelerated masked template matching with proper normalization.

    Identical math to CPU cv2.matchTemplate with mask:
    R(x,y) = sum(T*M*I) / sqrt(sum((T*M)^2) * sum((I*M)^2))

    Returns (score, location) where score is lower=better (0 = perfect match).
    """
    # Get cached masked data
    gpu_masked_template, gpu_mask_sq, template_energy = _get_gpu_masked_data(
        template_name, template, mask
    )

    # Upload frame to GPU
    gpu_frame = cv2.cuda_GpuMat()
    gpu_frame.upload(frame)

    # Step 1: Compute correlation sum(T*M*I) using TM_CCORR (non-normalized)
    template_type = cv2.CV_8UC3 if len(template.shape) == 3 else cv2.CV_8UC1
    matcher_ccorr = _get_gpu_matcher(template_type, cv2.TM_CCORR)
    gpu_corr_result = matcher_ccorr.match(gpu_frame, gpu_masked_template)
    corr_result = gpu_corr_result.download().astype(np.float64)

    # Step 2: Compute frame energy sum((I*M)^2) at each position
    # For color: sum((I_r*M)^2 + (I_g*M)^2 + (I_b*M)^2) = sum((I_r^2 + I_g^2 + I_b^2) * M^2)
    if len(frame.shape) == 3:
        # Sum of squares across color channels
        frame_sq_sum = np.sum(frame.astype(np.float32) ** 2, axis=2)
    else:
        frame_sq_sum = frame.astype(np.float32) ** 2

    # Normalize mask squared to float
    mask_sq_float = (mask.astype(np.float32) / 255.0) ** 2

    # Use CPU convolution for frame energy (more accurate with float)
    frame_energy = cv2.matchTemplate(
        frame_sq_sum.astype(np.float32),
        mask_sq_float,
        cv2.TM_CCORR
    )

    # Step 3: Normalize: corr / sqrt(template_energy * frame_energy)
    frame_energy = np.maximum(frame_energy, 1e-10)
    normalizer = np.sqrt(template_energy * frame_energy)
    normalized = corr_result / normalizer

    # Find best match (higher normalized correlation = better match)
    th, tw = template.shape[:2]
    _, max_val, _, max_loc = cv2.minMaxLoc(normalized)
    location = (max_loc[0] + tw // 2, max_loc[1] + th // 2)

    # Convert to lower=better for consistent interface (0 = perfect, 1 = worst)
    score = 1.0 - max_val
    return score, location


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
    it will be used automatically with TM_CCORR_NORMED matching (score converted to lower=better).

    Args:
        frame: BGR image
        template_name: Name of template file (e.g., "search_button_4k.png")
        search_region: Optional (x, y, w, h) to limit search area
        threshold: Override default threshold (max allowed score, lower=better)
        grayscale: Use grayscale matching instead of color (default False)

    Returns:
        (found: bool, score: float, location: tuple or None)
        - found: True if match meets threshold (score <= threshold)
        - score: Raw matching score (lower = better, ~0.0 is perfect)
        - location: Center point (x, y) in original frame coordinates, or None if template not found
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

    use_gpu = _is_gpu_enabled()

    if mask is not None:
        # Masked matching
        if use_gpu:
            # GPU masked matching with proper normalization
            score, rel_location = _match_template_gpu_masked(
                search_area, template, mask, template_name
            )
            location = (offset[0] + rel_location[0], offset[1] + rel_location[1])
        else:
            # CPU masked matching
            result = cv2.matchTemplate(search_area, template, cv2.TM_CCORR_NORMED, mask=mask)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            location = (offset[0] + max_loc[0] + tw // 2, offset[1] + max_loc[1] + th // 2)
            # Convert to SQDIFF-like score for consistent interface (lower = better)
            score = 1.0 - max_val

        thresh = threshold if threshold is not None else DEFAULT_MASKED_THRESHOLD
        found = score <= thresh
        return found, score, location
    else:
        # Use GPU whenever available (20x faster for large frames)
        if use_gpu:
            # GPU matching - TM_SQDIFF_NORMED
            # _match_template_gpu returns location with template center offset already applied
            score, rel_location = _match_template_gpu(
                search_area, template, template_name, cv2.TM_SQDIFF_NORMED
            )
            # Add search region offset to get location in original frame
            location = (offset[0] + rel_location[0], offset[1] + rel_location[1])
        else:
            # CPU fallback - TM_SQDIFF_NORMED (lower = better, ~0.0 is perfect)
            result = cv2.matchTemplate(search_area, template, cv2.TM_SQDIFF_NORMED)
            min_val, _, min_loc, _ = cv2.minMaxLoc(result)
            location = (offset[0] + min_loc[0] + tw // 2, offset[1] + min_loc[1] + th // 2)
            score = min_val

        thresh = threshold if threshold is not None else DEFAULT_THRESHOLD
        found = score <= thresh
        return found, score, location


def clear_cache() -> None:
    """Clear template and mask caches. Useful for testing or reloading."""
    _templates_color.clear()
    _templates_gray.clear()
    _masks.clear()
    _mask_exists.clear()
    _gpu_templates.clear()
    _gpu_matchers.clear()
    _gpu_masked_data.clear()
