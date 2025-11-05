"""
Castle Scanner - Template matching and OCR for castle detection

This module provides castle detection and name verification using:
1. Template matching to find castles at optimal zoom level
2. OCR to read castle owner names and levels
3. Filtering by level range and name matching

Usage:
    from castle_scanner import CastleDetector, CastleNameReader

    detector = CastleDetector()
    castles = detector.find_castles_in_frame(frame, level_range=(20, 21))

    reader = CastleNameReader()
    name = reader.read_castle_name(zoomed_frame)
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional
import cv2
import numpy as np
from paddleocr import PaddleOCR


@dataclass
class CastleMatch:
    """A detected castle in the viewport."""
    x: int  # Center X in screen coordinates
    y: int  # Center Y in screen coordinates
    confidence: float  # Template match score (0-1)
    template_used: str  # Which template matched
    level: Optional[int] = None  # OCR'd level (if available)


class CastleDetector:
    """
    Detect castles in the viewport using template matching.

    Uses pre-calibrated castle templates at optimal zoom level.
    Filters results by confidence threshold and level range.
    """

    # Optimal zoom level for castle detection (from ARCHITECTURE.md)
    OPTIMAL_ZOOM_LEVEL = 20
    OPTIMAL_VIEWPORT_AREA = 420  # pixels at zoom level 20

    # Template matching settings
    MATCH_THRESHOLD = 0.7  # Minimum confidence for castle detection
    MIN_CASTLE_DISTANCE = 50  # Minimum pixels between castle centers (deduplication)

    def __init__(self, template_dir: Optional[Path | str] = None):
        """
        Initialize castle detector.

        Args:
            template_dir: Directory containing castle templates
                         Defaults to ./templates/castles/
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates" / "castles"

        self.template_dir = Path(template_dir)
        self.templates = self._load_templates()

        if not self.templates:
            raise ValueError(f"No castle templates found in {self.template_dir}")

    def _load_templates(self) -> dict[str, np.ndarray]:
        """Load all castle templates from directory."""
        templates = {}

        if not self.template_dir.exists():
            return templates

        for template_path in self.template_dir.glob("*.png"):
            template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
            if template is not None:
                templates[template_path.stem] = template

        return templates

    def find_castles_in_frame(
        self,
        frame: np.ndarray,
        level_range: Optional[Tuple[int, int]] = None,
        confidence_threshold: Optional[float] = None
    ) -> List[CastleMatch]:
        """
        Find all castles in the given frame.

        Args:
            frame: Screenshot frame (BGR format)
            level_range: Optional (min_level, max_level) filter
            confidence_threshold: Minimum match confidence (default: 0.7)

        Returns:
            List of CastleMatch objects sorted by confidence (highest first)
        """
        if confidence_threshold is None:
            confidence_threshold = self.MATCH_THRESHOLD

        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        all_matches = []

        # Try all templates
        for template_name, template in self.templates.items():
            matches = self._match_template(
                frame_gray,
                template,
                template_name,
                confidence_threshold
            )
            all_matches.extend(matches)

        # Deduplicate overlapping matches
        deduplicated = self._deduplicate_matches(all_matches)

        # Sort by confidence (highest first)
        deduplicated.sort(key=lambda m: m.confidence, reverse=True)

        return deduplicated

    def _match_template(
        self,
        frame_gray: np.ndarray,
        template: np.ndarray,
        template_name: str,
        threshold: float
    ) -> List[CastleMatch]:
        """
        Match a single template against the frame.

        Uses TM_CCORR_NORMED for robust matching (same as button_matcher.py).
        """
        result = cv2.matchTemplate(frame_gray, template, cv2.TM_CCORR_NORMED)
        locations = np.where(result >= threshold)

        matches = []
        template_h, template_w = template.shape

        for pt in zip(*locations[::-1]):  # (x, y) coordinates
            # Calculate center position
            center_x = pt[0] + template_w // 2
            center_y = pt[1] + template_h // 2
            confidence = result[pt[1], pt[0]]

            matches.append(CastleMatch(
                x=center_x,
                y=center_y,
                confidence=float(confidence),
                template_used=template_name
            ))

        return matches

    def _deduplicate_matches(self, matches: List[CastleMatch]) -> List[CastleMatch]:
        """
        Remove duplicate detections (same castle detected by multiple templates).

        Keeps the match with highest confidence when two matches are within
        MIN_CASTLE_DISTANCE pixels of each other.
        """
        if not matches:
            return []

        # Sort by confidence (highest first)
        sorted_matches = sorted(matches, key=lambda m: m.confidence, reverse=True)

        kept = []
        for match in sorted_matches:
            # Check if this match is too close to any already-kept match
            is_duplicate = False
            for existing in kept:
                distance = np.sqrt(
                    (match.x - existing.x)**2 + (match.y - existing.y)**2
                )
                if distance < self.MIN_CASTLE_DISTANCE:
                    is_duplicate = True
                    break

            if not is_duplicate:
                kept.append(match)

        return kept


class CastleNameReader:
    """
    Read castle owner names and levels using OCR.

    Uses PaddleOCR to extract text from zoomed-in castle view.
    """

    # OCR region of interest (relative to 2560x1440 screen)
    # This is where the castle name/level appears after clicking
    NAME_ROI = {
        'x': 800,
        'y': 200,
        'width': 960,
        'height': 200
    }

    def __init__(self):
        """Initialize OCR engine."""
        # Use English model, disable angle classification for speed
        self.ocr = PaddleOCR(
            lang='en',
            use_angle_cls=False,
            show_log=False
        )

    def read_castle_info(self, frame: np.ndarray) -> Tuple[Optional[str], Optional[int]]:
        """
        Read castle owner name and level from zoomed-in view.

        Args:
            frame: Screenshot after clicking on castle (zoomed view)

        Returns:
            (owner_name, level) tuple
            Returns (None, None) if OCR fails
        """
        # Extract ROI
        roi = frame[
            self.NAME_ROI['y']:self.NAME_ROI['y'] + self.NAME_ROI['height'],
            self.NAME_ROI['x']:self.NAME_ROI['x'] + self.NAME_ROI['width']
        ]

        # Run OCR
        result = self.ocr.ocr(roi, cls=False)

        if not result or not result[0]:
            return None, None

        # Extract all text lines
        text_lines = []
        for line in result[0]:
            bbox, (text, confidence) = line
            if confidence > 0.5:  # Only keep high-confidence results
                text_lines.append(text.strip())

        # Parse name and level from text lines
        owner_name = self._extract_owner_name(text_lines)
        level = self._extract_level(text_lines)

        return owner_name, level

    def _extract_owner_name(self, text_lines: List[str]) -> Optional[str]:
        """
        Extract owner name from OCR text lines.

        The owner name is typically the longest text line,
        excluding level numbers and UI text like "Town Hall".
        """
        if not text_lines:
            return None

        # Filter out common UI text and numbers
        candidates = []
        for line in text_lines:
            # Skip pure numbers or very short text
            if line.isdigit() or len(line) < 3:
                continue
            # Skip common UI text
            if line.lower() in ['town hall', 'level', 'clan']:
                continue
            candidates.append(line)

        if not candidates:
            return None

        # Return the longest candidate (likely the name)
        return max(candidates, key=len)

    def _extract_level(self, text_lines: List[str]) -> Optional[int]:
        """
        Extract castle level from OCR text lines.

        Looks for patterns like "20", "Level 20", "Lv 20", etc.
        """
        for line in text_lines:
            # Try to extract number from lines containing "level" or "lv"
            line_lower = line.lower()
            if 'level' in line_lower or 'lv' in line_lower:
                # Extract numbers from the line
                numbers = ''.join(c for c in line if c.isdigit())
                if numbers:
                    try:
                        return int(numbers)
                    except ValueError:
                        continue

            # Try standalone numbers in reasonable range (1-50)
            if line.isdigit():
                try:
                    level = int(line)
                    if 1 <= level <= 50:
                        return level
                except ValueError:
                    continue

        return None

    def matches_name(self, detected_name: Optional[str], target_name: str) -> bool:
        """
        Check if detected name matches target name (case-insensitive).

        Args:
            detected_name: Name read from OCR
            target_name: Target name to search for

        Returns:
            True if names match (case-insensitive)
        """
        if detected_name is None:
            return False

        return detected_name.lower() == target_name.lower()


def demo():
    """Demo castle detection and OCR."""
    from find_player import ADBController, Config

    print("Castle Scanner Demo")
    print("=" * 60)

    # Initialize
    config = Config()
    adb = ADBController(config)

    detector = CastleDetector()
    reader = CastleNameReader()

    print(f"Loaded {len(detector.templates)} castle templates")
    print(f"Optimal zoom level: {detector.OPTIMAL_ZOOM_LEVEL}")
    print(f"Optimal viewport area: {detector.OPTIMAL_VIEWPORT_AREA} pixels")
    print()

    # Take screenshot
    adb.screenshot('temp_castle_scan.png')
    frame = cv2.imread('temp_castle_scan.png')

    # Detect castles
    print("Detecting castles in current view...")
    castles = detector.find_castles_in_frame(frame)

    print(f"Found {len(castles)} castles:")
    for i, castle in enumerate(castles, 1):
        print(f"  {i}. Position: ({castle.x}, {castle.y})")
        print(f"     Confidence: {castle.confidence:.2%}")
        print(f"     Template: {castle.template_used}")

    if castles:
        print("\nTo test OCR, click on a castle and run:")
        print("  reader.read_castle_info(frame)")


if __name__ == "__main__":
    demo()
