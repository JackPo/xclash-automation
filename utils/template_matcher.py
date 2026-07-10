"""
Unified template matching with automatic mask detection.

Uses COLOR matching by default (not grayscale).
Uses GPU (CUDA) for full-frame searches when available (20x faster).

Naming convention:
- Template: `<name>_4k.png`
- Mask: `<name>_mask_4k.png`

Uses TM_SQDIFF_NORMED for non-masked.
For masked templates, uses explicit normalized correlation:
R(x,y) = sum(T*M*I) / sqrt(sum((T*M)^2) * sum((I*M)^2))
with energy gating for flat/dark regions (invalid denominator -> worst score).
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
import threading

TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"

# Type alias for numpy arrays (using Any for cv2 compatibility)
from typing import Any
NDArray = npt.NDArray[Any]

# Caches for loaded templates and masks (COLOR by default)
_templates_color: dict[str, NDArray | None] = {}
_templates_gray: dict[str, NDArray | None] = {}
_masks: dict[str, NDArray | None] = {}
_mask_exists: dict[str, bool] = {}  # Cache for mask existence checks

# GPU template cache
_gpu_templates: dict[str, Any] = {}  # cv2.cuda_GpuMat

# Cache for masked matching data: (gpu_masked_template, gpu_mask_squared, template_energy)
# Note: This is also defined later but we need cleanup access here
_gpu_masked_data: dict[str, tuple[Any, Any, float]] = {}

# OpenCV CUDA objects are not safe to mutate/release concurrently across threads.
# Serialize all GPU cache and matching operations through a single lock.
_gpu_lock = threading.RLock()

# Template/mask disk-cache loads are dict get-or-load; without a lock, two
# threads (main loop / flow thread / detector thread) can race the mutation.
_cache_lock = threading.RLock()


def clear_gpu_cache() -> int:
    """
    Release all cached GPU memory (templates and masked data).

    Call this periodically to prevent GPU memory leaks.
    Returns the number of GPU objects released.
    """
    global _gpu_templates, _gpu_masked_data
    released = 0

    with _gpu_lock:
        # Release cached GPU templates
        for name, gpu_mat in list(_gpu_templates.items()):
            try:
                gpu_mat.release()
                released += 1
            except Exception:
                pass
        _gpu_templates.clear()

        # Release cached masked GPU data
        for name, (gpu_masked_template, gpu_mask_sq, _) in list(_gpu_masked_data.items()):
            try:
                gpu_masked_template.release()
                released += 1
            except Exception:
                pass
            try:
                gpu_mask_sq.release()
                released += 1
            except Exception:
                pass
        _gpu_masked_data.clear()

    return released


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
_MASKED_ENERGY_EPS = 1e-6


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
    """Load template with caching. COLOR by default. Thread-safe."""
    cache = _templates_gray if grayscale else _templates_color
    with _cache_lock:
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
    with _gpu_lock:
        if name not in _gpu_templates:
            gpu_template = cv2.cuda_GpuMat()
            gpu_template.upload(template)
            _gpu_templates[name] = gpu_template
        return _gpu_templates[name]


def _get_gpu_matcher(template_type: int, method: int) -> Any:
    """Create GPU template matcher (no caching - causes CUDA state issues)."""
    return cv2.cuda.createTemplateMatching(template_type, method)


def _prepare_masked_template_data(
    template: NDArray,
    mask: NDArray,
) -> tuple[NDArray, NDArray, float] | None:
    """
    Prepare masked template artifacts used by CPU and GPU masked matching.

    Returns:
        (masked_template_f32, mask_sq_f32, template_energy)
    """
    if mask.shape[:2] != template.shape[:2]:
        return None

    mask_norm = mask.astype(np.float32) / 255.0

    if len(template.shape) == 3:
        mask_for_template = mask_norm[:, :, None]
    else:
        mask_for_template = mask_norm

    template_f32 = template.astype(np.float32)
    masked_template = template_f32 * mask_for_template
    template_energy = float(np.sum(masked_template.astype(np.float64) ** 2))
    mask_sq = (mask_norm * mask_norm).astype(np.float32)
    return masked_template.astype(np.float32), mask_sq, template_energy


def _normalize_masked_correlation(
    corr_result: NDArray,
    frame_energy: NDArray,
    template_energy: float,
    eps: float = _MASKED_ENERGY_EPS,
) -> NDArray:
    """
    Normalize masked correlation with energy gating to avoid inf/nan blowups.
    """
    normalized = np.zeros_like(corr_result, dtype=np.float32)
    if template_energy <= eps:
        return normalized

    denominator = np.sqrt(np.maximum(template_energy * frame_energy, 0.0))
    valid = denominator > eps
    if np.any(valid):
        normalized[valid] = corr_result[valid] / denominator[valid]

    np.clip(normalized, 0.0, 1.0, out=normalized)
    return normalized


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
    with _gpu_lock:
        gpu_frame = None
        gpu_result = None
        matcher = None
        try:
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
                # Guard against inf/-inf from invalid template matching
                if not np.isfinite(min_val):
                    return 1.0, (0, 0)  # Return "not found" score
                location = (min_loc[0] + tw // 2, min_loc[1] + th // 2)
                return min_val, location
            else:
                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                # Guard against inf/-inf from invalid template matching
                if not np.isfinite(max_val):
                    return 1.0, (0, 0)  # Return "not found" score
                location = (max_loc[0] + tw // 2, max_loc[1] + th // 2)
                # Convert to lower=better for consistent interface
                return 1.0 - max_val, location
        finally:
            # Explicitly clear matcher state to avoid CUDA-side accumulation
            if matcher is not None:
                try:
                    matcher.clear()
                except Exception:
                    pass
            # Explicitly release GPU memory to prevent leaks
            if gpu_result is not None:
                gpu_result.release()
            if gpu_frame is not None:
                gpu_frame.release()


def _get_gpu_masked_data(template_name: str, template: NDArray, mask: NDArray) -> tuple[Any, Any, float]:
    """
    Get cached GPU data for masked matching.

    Returns: (gpu_masked_template, gpu_mask_squared, template_energy)
    - gpu_masked_template: T * M uploaded to GPU
    - gpu_mask_squared: M^2 uploaded to GPU (for frame energy computation)
    - template_energy: sum((T * M)^2) precomputed
    """
    with _gpu_lock:
        if template_name not in _gpu_masked_data:
            prepared = _prepare_masked_template_data(template, mask)
            if prepared is None:
                raise ValueError("Masked template shape mismatch")
            masked_template, mask_sq, template_energy = prepared

            # Upload to GPU
            gpu_masked_template = cv2.cuda_GpuMat()
            gpu_masked_template.upload(masked_template)

            gpu_mask_sq = cv2.cuda_GpuMat()
            gpu_mask_sq.upload(mask_sq)

            _gpu_masked_data[template_name] = (gpu_masked_template, gpu_mask_sq, template_energy)

        return _gpu_masked_data[template_name]


def _match_template_gpu_masked(
    frame: NDArray,
    template: NDArray,
    mask: NDArray,
    template_name: str
) -> tuple[float, tuple[int, int]]:
    """
    GPU-accelerated masked template matching with robust normalization.

    Identical math to CPU cv2.matchTemplate with mask:
    R(x,y) = sum(T*M*I) / sqrt(sum((T*M)^2) * sum((I*M)^2))

    Returns (score, location) where score is lower=better (0 = perfect match).
    """
    with _gpu_lock:
        # Track all GPU objects for cleanup
        gpu_objects: list[Any] = []
        matcher_objects: list[Any] = []

        try:
            # Get cached masked data
            gpu_masked_template, gpu_mask_sq, template_energy = _get_gpu_masked_data(
                template_name, template, mask
            )

            if template_energy <= _MASKED_ENERGY_EPS:
                return 1.0, (0, 0)

            # Upload frame as float32 to match masked template type
            gpu_frame_f = cv2.cuda_GpuMat()
            gpu_frame_f.upload(frame.astype(np.float32))
            gpu_objects.append(gpu_frame_f)

            # Step 1: Compute correlation sum(T*M*I) using TM_CCORR (non-normalized)
            template_type = cv2.CV_32FC3 if len(template.shape) == 3 else cv2.CV_32FC1
            matcher_ccorr = _get_gpu_matcher(template_type, cv2.TM_CCORR)
            matcher_objects.append(matcher_ccorr)
            gpu_corr_result = matcher_ccorr.match(gpu_frame_f, gpu_masked_template)
            gpu_objects.append(gpu_corr_result)
            corr_result = gpu_corr_result.download().astype(np.float64)

            # Step 2: Compute frame energy sum((I*M)^2) at each position using GPU
            # For color: sum((I_r^2 + I_g^2 + I_b^2) * M^2) = TM_CCORR(I_sq_gray, M^2)
            # Use GPU for squaring and channel sum
            gpu_sq = cv2.cuda.sqr(gpu_frame_f)
            gpu_objects.append(gpu_sq)

            if len(frame.shape) == 3:
                # Sum channels: download and sum (GPU channel sum not directly available)
                frame_sq = gpu_sq.download()
                frame_sq_sum = np.sum(frame_sq, axis=2).astype(np.float32)
            else:
                frame_sq_sum = gpu_sq.download()

            # Upload frame_sq and do GPU convolution for frame energy
            gpu_frame_sq = cv2.cuda_GpuMat()
            gpu_frame_sq.upload(frame_sq_sum)
            gpu_objects.append(gpu_frame_sq)

            matcher_energy = cv2.cuda.createTemplateMatching(cv2.CV_32FC1, cv2.TM_CCORR)
            matcher_objects.append(matcher_energy)
            gpu_energy_result = matcher_energy.match(gpu_frame_sq, gpu_mask_sq)
            gpu_objects.append(gpu_energy_result)
            frame_energy = gpu_energy_result.download().astype(np.float64)

            # Step 3: Robust normalization with energy gating
            normalized = _normalize_masked_correlation(corr_result, frame_energy, template_energy)

            # Find best match (higher normalized correlation = better match)
            th, tw = template.shape[:2]
            _, max_val, _, max_loc = cv2.minMaxLoc(normalized)
            # Guard against inf/-inf from invalid template matching
            if not np.isfinite(max_val):
                return 1.0, (0, 0)  # Return "not found" score
            location = (max_loc[0] + tw // 2, max_loc[1] + th // 2)

            # Convert to lower=better for consistent interface (0 = perfect, 1 = worst)
            score = 1.0 - max_val
            return score, location
        finally:
            for matcher in matcher_objects:
                try:
                    matcher.clear()
                except Exception:
                    pass
            # Explicitly release ALL GPU memory to prevent leaks
            for gpu_obj in gpu_objects:
                try:
                    gpu_obj.release()
                except Exception:
                    pass


def _match_template_cpu_masked(
    frame: NDArray,
    template: NDArray,
    mask: NDArray,
) -> tuple[float, tuple[int, int]]:
    """
    CPU masked matching with robust normalization and flat-region gating.
    """
    prepared = _prepare_masked_template_data(template, mask)
    if prepared is None:
        return 1.0, (0, 0)

    masked_template, mask_sq, template_energy = prepared
    if template_energy <= _MASKED_ENERGY_EPS:
        return 1.0, (0, 0)

    frame_f = frame.astype(np.float32)
    corr_result = cv2.matchTemplate(frame_f, masked_template, cv2.TM_CCORR).astype(np.float64)

    frame_sq = frame_f * frame_f
    if len(frame_sq.shape) == 3:
        frame_sq = np.sum(frame_sq, axis=2).astype(np.float32)
    frame_energy = cv2.matchTemplate(frame_sq, mask_sq, cv2.TM_CCORR).astype(np.float64)

    normalized = _normalize_masked_correlation(corr_result, frame_energy, template_energy)
    th, tw = template.shape[:2]
    _, max_val, _, max_loc = cv2.minMaxLoc(normalized)
    if not np.isfinite(max_val):
        return 1.0, (0, 0)
    location = (max_loc[0] + tw // 2, max_loc[1] + th // 2)
    score = 1.0 - float(max_val)
    return score, location


def _load_mask(template_name: str) -> NDArray | None:
    """Load mask for template if it exists, with caching. Thread-safe."""
    with _cache_lock:
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
    it will be used automatically with robust masked normalization (score converted to lower=better).

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
    if mask is not None and mask.shape[:2] != (th, tw):
        # Defensive fallback: malformed mask dimensions should not crash matching.
        mask = None

    # Check if search area is large enough
    if search_area.shape[0] < th or search_area.shape[1] < tw:
        return False, 1.0, None

    use_gpu = _is_gpu_enabled()

    if mask is not None:
        # Masked matching - use GPU only for small regions (large frames cause GPU contention)
        # Threshold: search area < 500x500 pixels
        use_gpu_masked = use_gpu and search_area.shape[0] < 500 and search_area.shape[1] < 500

        if use_gpu_masked:
            # GPU masked matching with proper normalization
            score, rel_location = _match_template_gpu_masked(
                search_area, template, mask, template_name
            )
            location = (offset[0] + rel_location[0], offset[1] + rel_location[1])
        else:
            # CPU masked matching with robust energy-gated normalization
            score, rel_location = _match_template_cpu_masked(search_area, template, mask)
            location = (offset[0] + rel_location[0], offset[1] + rel_location[1])

        thresh = threshold if threshold is not None else DEFAULT_MASKED_THRESHOLD
        found = score <= thresh
        return found, score, location
    else:
        # Non-masked matching - use GPU only for small regions (GPU contention with BlueStacks)
        use_gpu_here = use_gpu and search_area.shape[0] < 500 and search_area.shape[1] < 500

        if use_gpu_here:
            # GPU matching - TM_SQDIFF_NORMED
            score, rel_location = _match_template_gpu(
                search_area, template, template_name, cv2.TM_SQDIFF_NORMED
            )
            location = (offset[0] + rel_location[0], offset[1] + rel_location[1])
        else:
            # CPU matching (more predictable for large frames)
            result = cv2.matchTemplate(search_area, template, cv2.TM_SQDIFF_NORMED)
            min_val, _, min_loc, _ = cv2.minMaxLoc(result)
            # Guard against inf/-inf from invalid template matching
            if not np.isfinite(min_val):
                return False, 1.0, None  # Return "not found"
            location = (offset[0] + min_loc[0] + tw // 2, offset[1] + min_loc[1] + th // 2)
            score = min_val

        thresh = threshold if threshold is not None else DEFAULT_THRESHOLD
        # Extra guard for GPU path inf values
        if not np.isfinite(score):
            return False, 1.0, None
        found = score <= thresh
        return found, score, location


def clear_cache() -> None:
    """Clear template and mask caches. Useful for testing or reloading."""
    _templates_color.clear()
    _templates_gray.clear()
    _masks.clear()
    _mask_exists.clear()
    clear_gpu_cache()
