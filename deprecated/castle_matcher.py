"""
Template-based castle matcher used to estimate zoom scale.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

import cv2
import numpy as np


@dataclass
class CastleScaleResult:
    """Represents an estimated castle scale for the current frame."""

    scale: float
    avg_score: float
    best_candidate: float
    metrics: List[tuple]


class CastleMatcher:
    """
    Estimate castle size/scale using template matching across multiple scales.

    The matcher loads castle cutouts from castle_cutouts/ and evaluates them
    across a range of scale factors. The scale corresponding to the highest
    aggregate match score approximates the current zoom level relative to the
    templates' baseline size (scale=1.0).
    """

    def __init__(
        self,
        template_dir: Optional[Path] = None,
        scale_range: Sequence[float] | None = None,
        scale_step: float = 0.03,
        max_templates: int = 6,
        min_template_pixels: int = 1500,
        min_detection_score: float = 0.6,
        frame_downscale: float = 0.5,
        roi_margin: int = 120,
    ) -> None:
        base_dir = Path(__file__).resolve().parent
        self.template_dir = template_dir or (base_dir / "castle_cutouts")
        self.scale_min, self.scale_max = scale_range or (0.7, 1.2)
        self.scale_step = scale_step
        self.max_templates = max_templates
        self.min_template_pixels = min_template_pixels
        self.min_detection_score = min_detection_score
        self.frame_downscale = frame_downscale
        self.roi_margin = roi_margin
        self.target_scale = 1.0

        self.templates = self._load_templates()
        if not self.templates:
            raise FileNotFoundError(
                f"No castle templates found in {self.template_dir}. "
                "Expected PNG files with castle cutouts."
            )

        heights = [tpl.shape[0] for tpl in self.templates]
        widths = [tpl.shape[1] for tpl in self.templates]
        self.reference_height = float(np.mean(heights))
        self.reference_width = float(np.mean(widths))
        self.templates_downscaled = [
            cv2.resize(
                tpl,
                dsize=None,
                fx=self.frame_downscale,
                fy=self.frame_downscale,
                interpolation=cv2.INTER_AREA,
            )
            for tpl in self.templates
        ]

    def _load_templates(self) -> List[np.ndarray]:
        templates: List[np.ndarray] = []
        all_paths = sorted(self.template_dir.glob("*.png"))
        if not all_paths:
            return templates

        if len(all_paths) <= self.max_templates:
            candidate_paths = all_paths
        else:
            step = max(1, len(all_paths) // self.max_templates)
            candidate_paths = [p for idx, p in enumerate(all_paths) if idx % step == 0]
            candidate_paths = candidate_paths[: self.max_templates]

        for path in candidate_paths:
            image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if image is None:
                continue
            if image.shape[0] * image.shape[1] < self.min_template_pixels:
                continue
            templates.append(image)
        return templates

    def estimate_scale(self, frame: np.ndarray) -> Optional[CastleScaleResult]:
        """Estimate the current castle scale in a frame."""
        if frame is None or frame.size == 0:
            return None

        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_gray = cv2.GaussianBlur(frame_gray, (3, 3), 0)

        if self.frame_downscale != 1.0:
            frame_gray = cv2.resize(
                frame_gray,
                dsize=None,
                fx=self.frame_downscale,
                fy=self.frame_downscale,
                interpolation=cv2.INTER_AREA,
            )

        frame_h, frame_w = frame_gray.shape[:2]
        if self.roi_margin > 0:
            margin = max(10, int(self.roi_margin * self.frame_downscale))
            if frame_h > 2 * margin and frame_w > 2 * margin:
                frame_gray = frame_gray[margin : frame_h - margin, margin : frame_w - margin]
                frame_h, frame_w = frame_gray.shape[:2]

        scales = np.arange(self.scale_min, self.scale_max + self.scale_step, self.scale_step)

        best_scale = None
        best_score = -np.inf
        best_candidate = 0.0
        metrics: List[tuple] = []

        for scale in scales:
            total_score = 0.0
            detection_scores: List[float] = []

            for template in self.templates_downscaled:
                resized = cv2.resize(
                    template,
                    dsize=None,
                    fx=scale,
                    fy=scale,
                    interpolation=cv2.INTER_CUBIC if scale > 1.0 else cv2.INTER_AREA,
                )
                th, tw = resized.shape[:2]

                if th >= frame_h or tw >= frame_w or th < 20 or tw < 20:
                    continue

                result = cv2.matchTemplate(frame_gray, resized, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                total_score += max_val
                detection_scores.append(max_val)

            if not detection_scores:
                continue

            avg_score = total_score / len(detection_scores)
            peak_score = max(detection_scores)
            metrics.append((scale, avg_score, peak_score))

            if avg_score > best_score:
                best_score = avg_score
                best_scale = scale
                best_candidate = peak_score

        if best_scale is None:
            return None

        return CastleScaleResult(
            scale=float(best_scale),
            avg_score=float(best_score),
            best_candidate=float(best_candidate),
            metrics=metrics,
        )

    def approximate_castle_dimensions(self, scale: float) -> tuple[float, float]:
        """Return approximate castle width/height at the supplied scale."""
        return self.reference_width * scale, self.reference_height * scale
