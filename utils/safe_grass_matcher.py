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

from pathlib import Path
import cv2
import numpy as np

# Template path
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"
GRASS_TEMPLATE_PATH = TEMPLATE_DIR / "safe_grass_tile_4k.png"

# Search regions - areas where panels never appear
# Panels are typically centered, so search in corners/edges
# Top-left area (avoid UI bar at very top)
SEARCH_REGIONS = [
    (200, 300, 600, 500),    # Top-left area
    (3000, 300, 600, 500),   # Top-right area (avoid right sidebar)
    (200, 1400, 600, 500),   # Bottom-left area
]

# Match threshold (TM_SQDIFF_NORMED - lower is better)
MATCH_THRESHOLD = 0.02  # Tight threshold


class SafeGrassMatcher:
    """Finds safe grass tiles to click for dismissing floating panels in WORLD view."""

    def __init__(self):
        self.template = cv2.imread(str(GRASS_TEMPLATE_PATH))
        if self.template is None:
            print(f"Warning: Could not load {GRASS_TEMPLATE_PATH}")
        self.threshold = MATCH_THRESHOLD

    def find_grass(self, frame: np.ndarray, debug: bool = False) -> tuple[int, int] | None:
        """
        Find a safe grass tile in the frame.

        Args:
            frame: BGR numpy array screenshot
            debug: Print debug info

        Returns:
            (x, y) click position if found, None otherwise
        """
        if self.template is None:
            return None

        best_score = float('inf')
        best_pos = None

        # Try each search region
        for rx, ry, rw, rh in SEARCH_REGIONS:
            # Bounds check
            if ry + rh > frame.shape[0] or rx + rw > frame.shape[1]:
                continue

            roi = frame[ry:ry+rh, rx:rx+rw]

            # Skip if ROI is smaller than template
            if roi.shape[0] < self.template.shape[0] or roi.shape[1] < self.template.shape[1]:
                continue

            # Template match
            result = cv2.matchTemplate(roi, self.template, cv2.TM_SQDIFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if debug:
                print(f"  SafeGrass: region ({rx},{ry}) score={min_val:.4f}")

            if min_val < best_score:
                best_score = min_val
                roi_x, roi_y = min_loc
                best_pos = (
                    rx + roi_x + self.template.shape[1] // 2,
                    ry + roi_y + self.template.shape[0] // 2
                )

        if debug:
            print(f"  SafeGrass: best_score={best_score:.4f}, threshold={self.threshold}")

        if best_score <= self.threshold and best_pos:
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


def find_safe_grass(frame: np.ndarray, debug: bool = False) -> tuple[int, int] | None:
    """
    Convenience function to find safe grass tile.

    Args:
        frame: BGR numpy array screenshot
        debug: Print debug info

    Returns:
        (x, y) click position if found, None otherwise
    """
    return get_matcher().find_grass(frame, debug=debug)
