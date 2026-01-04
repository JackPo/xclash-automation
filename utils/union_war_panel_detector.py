"""
Union War Panel Detector - Validates Union War panel state.

Uses template_matcher for fixed-position detection.

Checks for:
1. Union War heading at top of screen
2. Team Intelligence tab being selected (vs Solo Intelligence)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from utils.template_matcher import match_template

if TYPE_CHECKING:
    import numpy.typing as npt


class UnionWarPanelDetector:
    """Detects Union War panel state using template matching."""

    # Union War heading coordinates (from docs/joining_rallies.md)
    HEADING_X = 1754
    HEADING_Y = 30
    HEADING_WIDTH = 315
    HEADING_HEIGHT = 58
    HEADING_THRESHOLD = 0.05

    # Team Intelligence tab coordinates
    TAB_X = 1336
    TAB_Y = 125
    TAB_WIDTH = 587
    TAB_HEIGHT = 116
    TAB_THRESHOLD = 0.05

    HEADING_TEMPLATE = "union_war_heading_4k.png"
    TAB_TEMPLATE = "team_intelligence_tab_4k.png"

    def __init__(self) -> None:
        """Initialize detector."""
        pass  # Templates loaded by template_matcher

    def is_union_war_panel(self, frame: npt.NDArray[Any]) -> tuple[bool, float]:
        """
        Check if Union War heading is present at top of screen.

        Returns:
            (present, score) - True if heading detected
        """
        found, score, _ = match_template(frame, self.HEADING_TEMPLATE, search_region=(self.HEADING_X, self.HEADING_Y, self.HEADING_WIDTH, self.HEADING_HEIGHT),
            threshold=self.HEADING_THRESHOLD
        )

        return found, score

    def is_team_intelligence_tab(self, frame: npt.NDArray[Any]) -> tuple[bool, float]:
        """
        Check if Team Intelligence tab is selected (highlighted).

        Returns:
            (selected, score) - True if tab is selected
        """
        found, score, _ = match_template(frame, self.TAB_TEMPLATE, search_region=(self.TAB_X, self.TAB_Y, self.TAB_WIDTH, self.TAB_HEIGHT),
            threshold=self.TAB_THRESHOLD
        )

        return found, score

    def validate_panel_state(self, frame: npt.NDArray[Any]) -> tuple[bool, str, dict[str, Any]]:
        """
        Validate complete panel state (heading + tab).

        Returns:
            (valid, message, details) - True if panel is ready for rally joining
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
