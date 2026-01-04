"""
Safe Grass Matcher - Finds clickable grass tiles in WORLD view to dismiss popups.

When a floating panel (like Team Up panel) is open in WORLD view, there's no
back button to close it. Clicking on grass outside the panel dismisses it.

Usage:
    from utils.safe_grass_matcher import find_safe_grass

    pos = find_safe_grass(frame)
    if pos:
        adb.tap(*pos)  # Clicks on grass, dismissing floating panel
"""
from __future__ import annotations

import numpy as np
import numpy.typing as npt
from typing import Any

from utils.template_matcher import match_template

# Search regions - areas where panels never appear
# Panels are typically centered, so search in corners/edges
SEARCH_REGIONS = [
    (200, 300, 600, 500),    # Top-left area
    (3000, 300, 600, 500),   # Top-right area (avoid right sidebar)
    (200, 1400, 600, 500),   # Bottom-left area
]

# Match threshold (TM_SQDIFF_NORMED - lower is better)
MATCH_THRESHOLD = 0.02


class SafeGrassMatcher:
    """Finds safe grass tiles to click for dismissing floating panels in WORLD view."""

    TEMPLATE_NAME = "safe_grass_tile_4k.png"

    def __init__(self, threshold: float | None = None) -> None:
        self.threshold = threshold if threshold is not None else MATCH_THRESHOLD

    def find_grass(self, frame: npt.NDArray[Any], debug: bool = False) -> tuple[int, int] | None:
        """
        Find a safe grass tile in the frame.

        Args:
            frame: BGR numpy array screenshot
            debug: Print debug info

        Returns:
            (x, y) click position if found, None otherwise
        """
        if frame is None or frame.size == 0:
            return None

        best_score = float('inf')
        best_pos = None

        # Try each search region
        for rx, ry, rw, rh in SEARCH_REGIONS:
            # Bounds check
            if ry + rh > frame.shape[0] or rx + rw > frame.shape[1]:
                continue

            found, score, location = match_template(
                frame,
                self.TEMPLATE_NAME,
                search_region=(rx, ry, rw, rh),
                threshold=self.threshold
            )

            if debug:
                print(f"  SafeGrass: region ({rx},{ry}) score={score:.4f}")

            if found and score < best_score:
                best_score = score
                best_pos = location  # match_template returns center position

        if debug:
            print(f"  SafeGrass: best_score={best_score:.4f}, threshold={self.threshold}")

        if best_pos:
            if debug:
                print(f"  SafeGrass: Found at {best_pos}")
            return best_pos

        if debug:
            print(f"  SafeGrass: Not found (best_score {best_score:.4f} > threshold {self.threshold})")
        return None


# Singleton instance
_matcher = None


def get_matcher() -> SafeGrassMatcher:
    """Get singleton matcher instance."""
    global _matcher
    if _matcher is None:
        _matcher = SafeGrassMatcher()
    return _matcher


def find_safe_grass(frame: npt.NDArray[Any], debug: bool = False) -> tuple[int, int] | None:
    """
    Convenience function to find safe grass tile.

    Args:
        frame: BGR numpy array screenshot
        debug: Print debug info

    Returns:
        (x, y) click position if found, None otherwise
    """
    return get_matcher().find_grass(frame, debug=debug)
