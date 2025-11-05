"""
Utilities for detecting the World/Town toggle button via template matching.

CRITICAL: Uses cv2.TM_CCORR_NORMED matching algorithm.
- TM_CCORR_NORMED: Cross-correlation method, achieves 98%+ match scores
- DO NOT use TM_CCOEFF_NORMED: Coefficient method, only gets 70% scores due to
  compression artifacts and brightness sensitivity

The CCORR algorithm is required for reliable button detection across different
capture sessions with PNG compression artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np


@dataclass
class TemplateMatch:
    """Represents a single template match result."""

    label: str
    score: float
    center: Tuple[int, int]
    top_left: Tuple[int, int]
    bottom_right: Tuple[int, int]
    template_key: str = ""  # Original template key before inversion (e.g., "TOWN_ZOOMED")


class ButtonMatcher:
    """
    Template matcher for the bottom-right World/Town toggle button.

    IMPORTANT: The button shows the DESTINATION, not the current state.
    - Button shows "WORLD" → Currently in TOWN (can switch to World)
    - Button shows "TOWN" → Currently in WORLD (can switch to Town)

    This matcher inverts the labels so the returned state represents the
    CURRENT view, not the button label.

    The matcher loads templates from templates/buttons/ and can optionally
    write debug crops for inspection in templates/debug/.
    """

    def __init__(
        self,
        template_dir: Optional[Path] = None,
        debug_dir: Optional[Path] = None,
        threshold: float = 0.85,
        roi_margin: Tuple[int, int] = (80, 80),
    ) -> None:
        base_dir = Path(__file__).resolve().parent
        self.template_dir = template_dir or (base_dir / "templates" / "ground_truth")
        self.debug_dir = debug_dir or (base_dir / "templates" / "debug")
        self.threshold = threshold
        self.roi_margin = roi_margin

        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.templates: Dict[str, np.ndarray] = self._load_templates()
        if not self.templates:
            raise FileNotFoundError(
                f"No button templates found in {self.template_dir}. "
                "Expected world_button.png and town_button.png"
            )

        shapes = {img.shape for img in self.templates.values()}
        if len(shapes) != 1:
            raise ValueError(
                "Button templates must have identical dimensions for safe comparison."
            )
        self.template_shape = next(iter(shapes))

    def _load_templates(self) -> Dict[str, np.ndarray]:
        templates: Dict[str, np.ndarray] = {}
        for label in ("world", "town"):
            path = self.template_dir / f"{label}_button.png"
            image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if image is None:
                continue
            templates[label.upper()] = image

        # Load zoomed-out town button variant (appears when minimap is visible)
        town_zoomed_path = self.template_dir / "town_button_zoomed_out.png"
        town_zoomed = cv2.imread(str(town_zoomed_path), cv2.IMREAD_GRAYSCALE)
        if town_zoomed is not None:
            templates["TOWN_ZOOMED"] = town_zoomed

        return templates

    @staticmethod
    def _invert_label(button_label: str) -> str:
        """
        Invert button label to get current state.

        The button shows WHERE YOU CAN GO, not where you are:
        - Button shows "WORLD" (destination) → Currently in TOWN
        - Button shows "TOWN" (destination) → Currently in WORLD

        Our templates match the button image:
        - world_button_template matches button showing "WORLD" → return TOWN (current)
        - town_button_template matches button showing "TOWN" → return WORLD (current)
        - town_button_zoomed_out matches button showing "TOWN" (when minimap visible) → return WORLD (current)
        """
        if button_label == "WORLD":
            return "TOWN"  # Matched WORLD button → currently in TOWN
        elif button_label == "TOWN" or button_label == "TOWN_ZOOMED":
            return "WORLD"  # Matched TOWN button (any variant) → currently in WORLD
        return button_label

    def match(
        self,
        frame: np.ndarray,
        save_debug: bool = True,
        fallback_fullframe: bool = True,
    ) -> Optional[TemplateMatch]:
        """Match templates against a frame and return the best hit."""
        if frame is None or frame.size == 0:
            return None

        frame_height, frame_width = frame.shape[:2]
        template_height, template_width = self.template_shape[:2]

        # Static bottom-right region assumptions (BlueStacks 2560x1440)
        static_width = template_width
        static_height = template_height
        x1 = frame_width - static_width
        y1 = frame_height - static_height

        candidates: Dict[str, TemplateMatch] = {}

        def evaluate_region(x1: int, y1: int, region: np.ndarray, tag: str) -> Optional[TemplateMatch]:
            if region.size == 0 or region.shape[0] < template_height or region.shape[1] < template_width:
                return None
            region_gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            best: Optional[TemplateMatch] = None

            for label, template in self.templates.items():
                result = cv2.matchTemplate(region_gray, template, cv2.TM_CCORR_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)

                top_left = (max_loc[0] + x1, max_loc[1] + y1)
                bottom_right = (
                    top_left[0] + template_width,
                    top_left[1] + template_height,
                )
                center = (
                    int((top_left[0] + bottom_right[0]) / 2),
                    int((top_left[1] + bottom_right[1]) / 2),
                )
                # Invert label: button shows destination (where you can go), we want current state
                # If button shows TOWN → currently in WORLD (can switch TO town)
                # If button shows WORLD → currently in TOWN (can switch TO world)
                current_state = self._invert_label(label)
                candidate = TemplateMatch(
                    label=current_state,
                    score=float(max_val),
                    center=center,
                    top_left=top_left,
                    bottom_right=bottom_right,
                    template_key=label  # Store original template key (e.g., "TOWN_ZOOMED")
                )
                if best is None or candidate.score > best.score:
                    best = candidate

            if best:
                candidates[tag] = best
            return best

        roi = frame[y1:, x1:]
        primary_match = evaluate_region(x1, y1, roi, "static")

        if fallback_fullframe and (primary_match is None or primary_match.score < self.threshold):
            evaluate_region(0, 0, frame, "full")

        # Select the highest-scoring match
        best_match = None
        for match in candidates.values():
            if best_match is None or match.score > best_match.score:
                best_match = match

        if best_match and save_debug:
            self._write_debug_crop(frame, best_match)

        return best_match

    def match_from_adb(
        self,
        adb_controller,
        temp_path: Path | str = "temp_button_match.png",
        fallback_fullframe: bool = False,
    ) -> Optional[TemplateMatch]:
        """Capture a screenshot via ADB and run template matching."""
        temp_path_obj = Path(temp_path)
        adb_controller.screenshot(temp_path_obj)
        frame = cv2.imread(str(temp_path_obj))
        try:
            temp_path_obj.unlink()
        except FileNotFoundError:
            pass
        return self.match(frame, fallback_fullframe=fallback_fullframe)

    def _write_debug_crop(self, frame: np.ndarray, match: TemplateMatch) -> None:
        try:
            crop = frame[
                match.top_left[1] : match.bottom_right[1],
                match.top_left[0] : match.bottom_right[0],
            ]
            if crop.size == 0:
                return
            debug_path = self.debug_dir / f"button_match_{match.label.lower()}.png"
            cv2.imwrite(str(debug_path), crop)
        except Exception:
            pass
