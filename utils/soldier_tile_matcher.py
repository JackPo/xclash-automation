"""
Soldier Tile Matcher - Detects soldier level tiles in the barracks training panel.

Searches horizontally (X-axis) within a fixed Y region to find
which soldier levels are visible in the panel.

Templates: half_soldier_lv3_4k.png through half_soldier_lv8_4k.png (78x148 pixels)
Uses HALF templates (top half only) to avoid overlapping detections.
"""

from pathlib import Path
import cv2
import numpy as np

# Template paths
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"

# Fixed Y-axis region for soldier tiles (same for all levels)
# Using BOTTOM half templates now, so height is 79 instead of 157
SOLDIER_Y_START = 890  # Bottom half starts at Y=890
SOLDIER_Y_END = 969   # 890 + 79
SOLDIER_HEIGHT = 79   # Bottom half of original 157
SOLDIER_WIDTH = 148

# ROI for template matching (reduces computation by ~95%)
# Panel X range: ~1300 to ~2600 (soldier tiles appear here)
# Y range: 890 - 20 to 969 + 20 (soldier tiles with margin)
ROI_X_START = 1300
ROI_X_END = 2600
ROI_Y_START = 870  # SOLDIER_Y_START - 20 margin
ROI_Y_END = 990    # SOLDIER_Y_END + 20 margin

# Match threshold (TM_SQDIFF_NORMED - lower is better)
MATCH_THRESHOLD = 0.02


class SoldierTileMatcher:
    """Detects soldier level tiles in the barracks training panel."""

    def __init__(self):
        # Load all HALF soldier templates (Lv3-8)
        self.templates = {}
        for level in range(3, 9):
            path = TEMPLATE_DIR / f"half_soldier_lv{level}_4k.png"
            template = cv2.imread(str(path))
            if template is not None:
                self.templates[level] = template
            else:
                print(f"Warning: Could not load {path}")

    def find_visible_soldiers(self, frame, debug_timing=False):
        """
        Find all visible soldier tiles in the barracks panel.

        Uses ROI cropping to reduce template matching area by ~95%.

        Args:
            frame: BGR numpy array screenshot
            debug_timing: If True, print timing info for each template match

        Returns:
            dict: {level: {'x': x_position, 'score': match_score, 'center': (cx, cy)}}
                  Coordinates are in FULL FRAME space (not ROI space)
        """
        import time as _time
        results = {}

        if debug_timing:
            total_start = _time.time()

        # Crop to ROI for faster template matching
        roi = frame[ROI_Y_START:ROI_Y_END, ROI_X_START:ROI_X_END]

        if debug_timing:
            print(f"    ROI size: {roi.shape[1]}x{roi.shape[0]} (vs full frame {frame.shape[1]}x{frame.shape[0]})")

        for level, template in self.templates.items():
            if debug_timing:
                match_start = _time.time()

            # Use TM_SQDIFF_NORMED for matching on ROI
            result = cv2.matchTemplate(roi, template, cv2.TM_SQDIFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if debug_timing:
                match_time = (_time.time() - match_start) * 1000
                print(f"    Lv{level} template match: {match_time:.1f}ms")

            # Convert ROI coordinates back to full frame coordinates
            roi_x, roi_y = min_loc
            x = roi_x + ROI_X_START
            y = roi_y + ROI_Y_START

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

        if debug_timing:
            total_time = (_time.time() - total_start) * 1000
            print(f"    Total find_visible_soldiers: {total_time:.1f}ms")

        return results

    def find_soldier_level(self, frame, target_level):
        """
        Find a specific soldier level in the panel.

        Uses ROI cropping for faster matching.

        Args:
            frame: BGR numpy array screenshot
            target_level: int (3-8) - the soldier level to find

        Returns:
            dict or None: {'x': x, 'y': y, 'score': score, 'center': (cx, cy)} if found
                          Coordinates are in FULL FRAME space
        """
        if target_level not in self.templates:
            return None

        # Crop to ROI for faster template matching
        roi = frame[ROI_Y_START:ROI_Y_END, ROI_X_START:ROI_X_END]

        template = self.templates[target_level]
        result = cv2.matchTemplate(roi, template, cv2.TM_SQDIFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # Convert ROI coordinates back to full frame coordinates
        roi_x, roi_y = min_loc
        x = roi_x + ROI_X_START
        y = roi_y + ROI_Y_START

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


def find_visible_soldiers(frame, debug_timing=False):
    """Convenience function to find all visible soldier tiles."""
    return get_matcher().find_visible_soldiers(frame, debug_timing=debug_timing)


def find_soldier_level(frame, target_level):
    """Convenience function to find a specific soldier level."""
    return get_matcher().find_soldier_level(frame, target_level)


def get_leftmost_visible(frame):
    """Convenience function to get leftmost visible soldier tile."""
    return get_matcher().get_leftmost_visible(frame)


def get_rightmost_visible(frame):
    """Convenience function to get rightmost visible soldier tile."""
    return get_matcher().get_rightmost_visible(frame)
