"""
Scale-Invariant Zoom Level Detector

Uses two-template approach to determine zoom level:
1. Complex castle template (detailed architecture) - indicates TOO ZOOMED IN
2. Simple castle template (icon-like, minimal detail) - indicates CORRECT ZONE

For each screenshot, matches both templates at multiple scales and compares scores.
"""
from pathlib import Path
from typing import Tuple, Optional
from dataclasses import dataclass
import cv2
import numpy as np


@dataclass
class ZoomDetectionResult:
    """Result from zoom level detection."""
    complex_score: float
    simple_score: float
    best_scale: float
    recommendation: str  # "ZOOM_OUT", "ZOOM_IN", "PERFECT"
    detail: str  # "COMPLEX", "SIMPLE", "UNKNOWN"


class ZoomLevelDetector:
    """
    Detects current zoom level using scale-invariant template matching.

    Strategy:
    1. Match complex template at multiple scales → get best score
    2. Match simple template at multiple scales → get best score
    3. Compare scores to determine if too zoomed in (complex wins)
    4. Use winning template's scale to determine zoom adjustment needed
    """

    def __init__(
        self,
        complex_template_path: Optional[Path] = None,
        simple_template_dir: Optional[Path] = None,
        scale_range: Tuple[float, float] = (0.5, 2.0),
        scale_step: float = 0.1,
        target_scale: float = 1.0,
        scale_tolerance: float = 0.1
    ):
        """
        Initialize zoom level detector.

        Args:
            complex_template_path: Path to complex castle template
            simple_template_dir: Directory with simple castle templates
            scale_range: (min, max) scale factors to test
            scale_step: Step size for scale testing
            target_scale: Target scale for perfect zoom (default 1.0)
            scale_tolerance: Acceptable deviation from target (default 0.1)
        """
        base_dir = Path(__file__).parent

        # Load complex template
        if complex_template_path is None:
            complex_template_path = base_dir / "templates" / "complex_castle_template.png"

        self.complex_template = cv2.imread(str(complex_template_path), cv2.IMREAD_GRAYSCALE)
        if self.complex_template is None:
            raise FileNotFoundError(f"Complex template not found: {complex_template_path}")

        # Load simple templates
        if simple_template_dir is None:
            simple_template_dir = base_dir / "castle_cutouts"

        self.simple_templates = self._load_simple_templates(simple_template_dir)
        if not self.simple_templates:
            raise FileNotFoundError(f"No simple templates found in: {simple_template_dir}")

        self.scale_range = scale_range
        self.scale_step = scale_step
        self.target_scale = target_scale
        self.scale_tolerance = scale_tolerance

    def _load_simple_templates(self, template_dir: Path, max_templates: int = 5) -> list:
        """Load simple castle templates."""
        templates = []
        all_paths = sorted(template_dir.glob("castle_*.png"))

        if len(all_paths) > max_templates:
            # Sample evenly
            step = len(all_paths) // max_templates
            paths = [all_paths[i * step] for i in range(max_templates)]
        else:
            paths = all_paths

        for path in paths:
            img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                templates.append(img)

        return templates

    def _match_template_multiscale(
        self,
        frame: np.ndarray,
        template: np.ndarray
    ) -> Tuple[float, float]:
        """
        Match template at multiple scales and return best score and scale.

        Returns:
            (best_score, best_scale)
        """
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame

        best_score = 0.0
        best_scale = 1.0

        scales = np.arange(self.scale_range[0], self.scale_range[1] + self.scale_step, self.scale_step)

        for scale in scales:
            # Resize template
            scaled_template = cv2.resize(
                template,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_CUBIC if scale > 1.0 else cv2.INTER_AREA
            )

            # Skip if template is too large for frame
            if scaled_template.shape[0] >= frame_gray.shape[0] or \
               scaled_template.shape[1] >= frame_gray.shape[1]:
                continue

            # Match
            result = cv2.matchTemplate(frame_gray, scaled_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)

            if max_val > best_score:
                best_score = max_val
                best_scale = scale

        return best_score, best_scale

    def detect(self, frame: np.ndarray) -> ZoomDetectionResult:
        """
        Detect zoom level from frame.

        Args:
            frame: BGR image frame

        Returns:
            ZoomDetectionResult with scores and recommendation
        """
        # Match complex template at multiple scales
        complex_score, complex_scale = self._match_template_multiscale(frame, self.complex_template)

        # Match simple templates at multiple scales (use best of all templates)
        simple_score = 0.0
        simple_scale = 1.0

        for template in self.simple_templates:
            score, scale = self._match_template_multiscale(frame, template)
            if score > simple_score:
                simple_score = score
                simple_scale = scale

        # Determine detail level
        if complex_score > simple_score:
            detail = "COMPLEX"
            best_scale = complex_scale
        elif simple_score > complex_score:
            detail = "SIMPLE"
            best_scale = simple_scale
        else:
            detail = "UNKNOWN"
            best_scale = 1.0

        # Determine recommendation
        if detail == "COMPLEX":
            # Too zoomed in - complex castles visible
            recommendation = "ZOOM_OUT"
        elif detail == "SIMPLE":
            # In correct zone - check scale
            if best_scale < self.target_scale - self.scale_tolerance:
                recommendation = "ZOOM_IN"
            elif best_scale > self.target_scale + self.scale_tolerance:
                recommendation = "ZOOM_OUT"
            else:
                recommendation = "PERFECT"
        else:
            recommendation = "UNKNOWN"

        return ZoomDetectionResult(
            complex_score=complex_score,
            simple_score=simple_score,
            best_scale=best_scale,
            recommendation=recommendation,
            detail=detail
        )

    def detect_from_file(self, image_path: Path) -> ZoomDetectionResult:
        """Detect zoom level from image file."""
        frame = cv2.imread(str(image_path))
        if frame is None:
            raise FileNotFoundError(f"Could not load image: {image_path}")
        return self.detect(frame)


if __name__ == "__main__":
    # Test on existing screenshots
    detector = ZoomLevelDetector()

    test_images = [
        "zoom_adjusted.png",
        "proper_calibration_test.png",
        "zoom_12_test.png",
    ]

    print("=" * 60)
    print("ZOOM LEVEL DETECTION TEST")
    print("=" * 60)

    for img_path in test_images:
        path = Path(img_path)
        if not path.exists():
            print(f"\n{img_path}: NOT FOUND")
            continue

        result = detector.detect_from_file(path)

        print(f"\n{img_path}:")
        print(f"  Complex Score: {result.complex_score:.3f}")
        print(f"  Simple Score: {result.simple_score:.3f}")
        print(f"  Detail Level: {result.detail}")
        print(f"  Best Scale: {result.best_scale:.2f}")
        print(f"  Recommendation: {result.recommendation}")
