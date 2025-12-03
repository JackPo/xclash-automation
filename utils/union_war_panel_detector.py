"""
Union War Panel Detector - Validates Union War panel state.

Checks for:
1. Union War heading at top of screen
2. Team Intelligence tab being selected (vs Solo Intelligence)
"""

from pathlib import Path
import cv2
import numpy as np


class UnionWarPanelDetector:
    """Detects Union War panel state using template matching."""

    # Union War heading coordinates (from docs/joining_rallies.md)
    HEADING_X = 1754
    HEADING_Y = 30
    HEADING_WIDTH = 315
    HEADING_HEIGHT = 58
    HEADING_THRESHOLD = 0.05  # TM_SQDIFF_NORMED

    # Team Intelligence tab coordinates
    TAB_X = 1336
    TAB_Y = 125
    TAB_WIDTH = 587
    TAB_HEIGHT = 116
    TAB_THRESHOLD = 0.05

    def __init__(self):
        """Initialize detector with templates."""
        template_dir = Path(__file__).parent.parent / "templates" / "ground_truth"

        # Load Union War heading template
        heading_path = template_dir / "union_war_heading_4k.png"
        if not heading_path.exists():
            raise FileNotFoundError(f"Union War heading template not found: {heading_path}")
        self.heading_template = cv2.imread(str(heading_path), cv2.IMREAD_GRAYSCALE)

        # Load Team Intelligence tab template
        tab_path = template_dir / "team_intelligence_tab_4k.png"
        if not tab_path.exists():
            raise FileNotFoundError(f"Team Intelligence tab template not found: {tab_path}")
        self.tab_template = cv2.imread(str(tab_path), cv2.IMREAD_GRAYSCALE)

    def is_union_war_panel(self, frame) -> tuple[bool, float]:
        """
        Check if Union War heading is present at top of screen.

        Args:
            frame: BGR screenshot from WindowsScreenshotHelper

        Returns:
            (present, score) - True if heading detected, score from template matching
        """
        # Extract ROI at fixed position
        roi = frame[
            self.HEADING_Y : self.HEADING_Y + self.HEADING_HEIGHT,
            self.HEADING_X : self.HEADING_X + self.HEADING_WIDTH
        ]

        # Convert to grayscale
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # Template matching
        result = cv2.matchTemplate(roi_gray, self.heading_template, cv2.TM_SQDIFF_NORMED)
        min_val = cv2.minMaxLoc(result)[0]
        score = float(min_val)

        is_present = score <= self.HEADING_THRESHOLD
        return is_present, score

    def is_team_intelligence_tab(self, frame) -> tuple[bool, float]:
        """
        Check if Team Intelligence tab is selected (highlighted).

        Args:
            frame: BGR screenshot from WindowsScreenshotHelper

        Returns:
            (selected, score) - True if tab is selected, score from template matching
        """
        # Extract ROI at fixed position
        roi = frame[
            self.TAB_Y : self.TAB_Y + self.TAB_HEIGHT,
            self.TAB_X : self.TAB_X + self.TAB_WIDTH
        ]

        # Convert to grayscale
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # Template matching
        result = cv2.matchTemplate(roi_gray, self.tab_template, cv2.TM_SQDIFF_NORMED)
        min_val = cv2.minMaxLoc(result)[0]
        score = float(min_val)

        is_selected = score <= self.TAB_THRESHOLD
        return is_selected, score

    def validate_panel_state(self, frame) -> tuple[bool, str, dict]:
        """
        Validate complete panel state (heading + tab).

        Args:
            frame: BGR screenshot from WindowsScreenshotHelper

        Returns:
            (valid, message, details) - True if panel is ready for rally joining,
                                       error message if not valid,
                                       dict with scores for debugging
        """
        heading_present, heading_score = self.is_union_war_panel(frame)
        tab_selected, tab_score = self.is_team_intelligence_tab(frame)

        details = {
            "heading_present": heading_present,
            "heading_score": heading_score,
            "tab_selected": tab_selected,
            "tab_score": tab_score
        }

        if not heading_present:
            return False, "Union War heading not found", details

        if not tab_selected:
            return False, "Team Intelligence tab not selected", details

        return True, "Panel valid", details
