"""
Soldier Tile Matcher - Detects soldier level tiles in the barracks training panel.

Searches horizontally (X-axis) within a fixed Y region to find
which soldier levels are visible in the panel.

Uses template_matcher for search-based detection.

Templates: half_soldier_lv3_4k.png through half_soldier_lv8_4k.png (78x148 pixels)
Uses HALF templates (top half only) to avoid overlapping detections.
"""

import numpy as np
from typing import Optional, Dict, Tuple

from utils.template_matcher import match_template

# Fixed Y-axis region for soldier tiles (same for all levels)
SOLDIER_Y_START = 890  # Bottom half starts at Y=890
SOLDIER_Y_END = 969   # 890 + 79
SOLDIER_HEIGHT = 79   # Bottom half of original 157
SOLDIER_WIDTH = 148

# ROI for template matching (reduces computation by ~95%)
ROI_X_START = 1300
ROI_X_END = 2600
ROI_Y_START = 870  # SOLDIER_Y_START - 20 margin
ROI_Y_END = 990    # SOLDIER_Y_END + 20 margin

# Match threshold (TM_SQDIFF_NORMED - lower is better)
MATCH_THRESHOLD = 0.02


class SoldierTileMatcher:
    """Detects soldier level tiles in the barracks training panel."""

    def __init__(self):
        # Template names for levels 3-8
        self.template_names = {
            level: f"half_soldier_lv{level}_4k.png"
            for level in range(3, 9)
        }

    def find_visible_soldiers(self, frame: np.ndarray, debug_timing: bool = False) -> Dict[int, Dict]:
        """
        Find all visible soldier tiles in the barracks panel.

        Args:
            frame: BGR numpy array screenshot
            debug_timing: If True, print timing info

        Returns:
            dict: {level: {'x': x_position, 'score': match_score, 'center': (cx, cy)}}
        """
        import time as _time
        results = {}

        if debug_timing:
            total_start = _time.time()
            print(f"    ROI size: {ROI_X_END - ROI_X_START}x{ROI_Y_END - ROI_Y_START}")

        search_region = (ROI_X_START, ROI_Y_START, ROI_X_END - ROI_X_START, ROI_Y_END - ROI_Y_START)

        for level, template_name in self.template_names.items():
            if debug_timing:
                match_start = _time.time()

            found, score, location = match_template(
                frame,
                template_name,
                search_region=search_region,
                threshold=MATCH_THRESHOLD
            )

            if debug_timing:
                match_time = (_time.time() - match_start) * 1000
                print(f"    Lv{level} template match: {match_time:.1f}ms")

            if found and location:
                x, y = location[0] - SOLDIER_WIDTH // 2, location[1] - SOLDIER_HEIGHT // 2
                # Verify Y is in expected range
                if SOLDIER_Y_START - 10 <= y <= SOLDIER_Y_START + 10:
                    results[level] = {
                        'x': x,
                        'y': y,
                        'score': score,
                        'center': location
                    }

        if debug_timing:
            total_time = (_time.time() - total_start) * 1000
            print(f"    Total find_visible_soldiers: {total_time:.1f}ms")

        return results

    def find_soldier_level(self, frame: np.ndarray, target_level: int) -> Optional[Dict]:
        """
        Find a specific soldier level in the panel.

        Args:
            frame: BGR numpy array screenshot
            target_level: int (3-8) - the soldier level to find

        Returns:
            dict or None: {'x': x, 'y': y, 'score': score, 'center': (cx, cy)} if found
        """
        if target_level not in self.template_names:
            return None

        search_region = (ROI_X_START, ROI_Y_START, ROI_X_END - ROI_X_START, ROI_Y_END - ROI_Y_START)

        found, score, location = match_template(
            frame,
            self.template_names[target_level],
            search_region=search_region,
            threshold=MATCH_THRESHOLD
        )

        if found and location:
            x, y = location[0] - SOLDIER_WIDTH // 2, location[1] - SOLDIER_HEIGHT // 2
            if SOLDIER_Y_START - 10 <= y <= SOLDIER_Y_START + 10:
                return {
                    'x': x,
                    'y': y,
                    'score': score,
                    'center': location
                }

        return None

    def get_leftmost_visible(self, frame: np.ndarray) -> Optional[Tuple[int, Dict]]:
        """
        Find the leftmost visible soldier tile.

        Returns:
            tuple or None: (level, info_dict) of leftmost tile
        """
        visible = self.find_visible_soldiers(frame)

        if not visible:
            return None

        leftmost_level = min(visible.keys(), key=lambda lvl: visible[lvl]['x'])
        return leftmost_level, visible[leftmost_level]

    def get_rightmost_visible(self, frame: np.ndarray) -> Optional[Tuple[int, Dict]]:
        """
        Find the rightmost visible soldier tile.

        Returns:
            tuple or None: (level, info_dict) of rightmost tile
        """
        visible = self.find_visible_soldiers(frame)

        if not visible:
            return None

        rightmost_level = max(visible.keys(), key=lambda lvl: visible[lvl]['x'])
        return rightmost_level, visible[rightmost_level]


# Singleton instance
_matcher = None


def get_matcher() -> SoldierTileMatcher:
    global _matcher
    if _matcher is None:
        _matcher = SoldierTileMatcher()
    return _matcher


def find_visible_soldiers(frame: np.ndarray, debug_timing: bool = False) -> Dict[int, Dict]:
    """Convenience function to find all visible soldier tiles."""
    return get_matcher().find_visible_soldiers(frame, debug_timing=debug_timing)


def find_soldier_level(frame: np.ndarray, target_level: int) -> Optional[Dict]:
    """Convenience function to find a specific soldier level."""
    return get_matcher().find_soldier_level(frame, target_level)


def get_leftmost_visible(frame: np.ndarray) -> Optional[Tuple[int, Dict]]:
    """Convenience function to get leftmost visible soldier tile."""
    return get_matcher().get_leftmost_visible(frame)


def get_rightmost_visible(frame: np.ndarray) -> Optional[Tuple[int, Dict]]:
    """Convenience function to get rightmost visible soldier tile."""
    return get_matcher().get_rightmost_visible(frame)
