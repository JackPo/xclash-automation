"""
Soldier Tile Matcher - Detects soldier level tiles in the barracks training panel.

Searches horizontally (X-axis) within a fixed Y region (Y=810-967) to find
which soldier levels are visible in the panel.

Templates: soldier_lv3_4k.png through soldier_lv8_4k.png (148x157 pixels)
"""

from pathlib import Path
import cv2
import numpy as np

# Template paths
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"

# Fixed Y-axis region for soldier tiles (same for all levels)
SOLDIER_Y_START = 810
SOLDIER_Y_END = 967
SOLDIER_HEIGHT = 157
SOLDIER_WIDTH = 148

# Match threshold (TM_SQDIFF_NORMED - lower is better)
# 0.01 is very strict - only exact matches
# 0.03 allows some variation
MATCH_THRESHOLD = 0.015


class SoldierTileMatcher:
    """Detects soldier level tiles in the barracks training panel."""

    def __init__(self):
        # Load all soldier templates (Lv3-8)
        self.templates = {}
        for level in range(3, 9):
            path = TEMPLATE_DIR / f"soldier_lv{level}_4k.png"
            template = cv2.imread(str(path))
            if template is not None:
                self.templates[level] = template
            else:
                print(f"Warning: Could not load {path}")

    def find_visible_soldiers(self, frame):
        """
        Find all visible soldier tiles in the barracks panel.

        Args:
            frame: BGR numpy array screenshot

        Returns:
            dict: {level: {'x': x_position, 'score': match_score, 'center': (cx, cy)}}
        """
        results = {}

        for level, template in self.templates.items():
            # Use TM_SQDIFF_NORMED for matching
            result = cv2.matchTemplate(frame, template, cv2.TM_SQDIFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            x, y = min_loc

            # Only count as found if score is below threshold and Y is in expected range
            if min_val < MATCH_THRESHOLD and SOLDIER_Y_START - 10 <= y <= SOLDIER_Y_START + 10:
                center_x = x + SOLDIER_WIDTH // 2
                center_y = y + SOLDIER_HEIGHT // 2
                results[level] = {
                    'x': x,
                    'y': y,
                    'score': min_val,
                    'center': (center_x, center_y)
                }

        return results

    def find_soldier_level(self, frame, target_level):
        """
        Find a specific soldier level in the panel.

        Args:
            frame: BGR numpy array screenshot
            target_level: int (3-8) - the soldier level to find

        Returns:
            dict or None: {'x': x, 'y': y, 'score': score, 'center': (cx, cy)} if found
        """
        if target_level not in self.templates:
            return None

        template = self.templates[target_level]
        result = cv2.matchTemplate(frame, template, cv2.TM_SQDIFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        x, y = min_loc

        # Check if found at expected Y position
        if min_val < MATCH_THRESHOLD and SOLDIER_Y_START - 10 <= y <= SOLDIER_Y_START + 10:
            center_x = x + SOLDIER_WIDTH // 2
            center_y = y + SOLDIER_HEIGHT // 2
            return {
                'x': x,
                'y': y,
                'score': min_val,
                'center': (center_x, center_y)
            }

        return None

    def get_leftmost_visible(self, frame):
        """
        Find the leftmost visible soldier tile.

        Args:
            frame: BGR numpy array screenshot

        Returns:
            tuple or None: (level, info_dict) of leftmost tile, or None if none found
        """
        visible = self.find_visible_soldiers(frame)

        if not visible:
            return None

        # Find leftmost by x position
        leftmost_level = min(visible.keys(), key=lambda lvl: visible[lvl]['x'])
        return leftmost_level, visible[leftmost_level]

    def get_rightmost_visible(self, frame):
        """
        Find the rightmost visible soldier tile.

        Args:
            frame: BGR numpy array screenshot

        Returns:
            tuple or None: (level, info_dict) of rightmost tile, or None if none found
        """
        visible = self.find_visible_soldiers(frame)

        if not visible:
            return None

        # Find rightmost by x position
        rightmost_level = max(visible.keys(), key=lambda lvl: visible[lvl]['x'])
        return rightmost_level, visible[rightmost_level]


# Singleton instance
_matcher = None

def get_matcher():
    global _matcher
    if _matcher is None:
        _matcher = SoldierTileMatcher()
    return _matcher


def find_visible_soldiers(frame):
    """Convenience function to find all visible soldier tiles."""
    return get_matcher().find_visible_soldiers(frame)


def find_soldier_level(frame, target_level):
    """Convenience function to find a specific soldier level."""
    return get_matcher().find_soldier_level(frame, target_level)


def get_leftmost_visible(frame):
    """Convenience function to get leftmost visible soldier tile."""
    return get_matcher().get_leftmost_visible(frame)


def get_rightmost_visible(frame):
    """Convenience function to get rightmost visible soldier tile."""
    return get_matcher().get_rightmost_visible(frame)
