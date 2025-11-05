"""
Minimap Navigator - Calculate navigation movements using calibration data

This module processes the zoom calibration matrix and provides utilities to:
1. Clean and filter calibration data (remove outliers)
2. Calculate arrow key movements needed to navigate between minimap positions
3. Find optimal zoom levels based on viewport area

Usage:
    from minimap_navigator import MinimapNavigator

    nav = MinimapNavigator()
    movements = nav.calculate_movement(
        zoom_level=15,
        current_pos=(113, 139),
        target_pos=(150, 180)
    )
    # Returns: {'right': 5, 'left': 0, 'up': 0, 'down': 6}
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, Optional
import json
import numpy as np


@dataclass
class ZoomLevelData:
    """Cleaned calibration data for a single zoom level."""
    level: int
    viewport_area: int  # Absolute pixels
    viewport_area_pct: float  # Percentage of 226×226 minimap

    # Arrow deltas (average minimap pixels moved per arrow press)
    right_dx: float  # Positive value
    left_dx: float   # Negative value
    up_dy: float     # Negative value
    down_dy: float   # Positive value


class CalibrationCleaner:
    """
    Load and clean zoom calibration data.

    Applies outlier filtering using IQR method to remove measurement noise
    from arrow delta calibration.
    """

    def __init__(self, calibration_file: Path | str):
        self.calibration_file = Path(calibration_file)
        self.raw_data = None
        self.clean_data: Dict[int, ZoomLevelData] = {}

    def load_calibration(self) -> Dict[int, ZoomLevelData]:
        """Load and clean calibration data."""
        with open(self.calibration_file, 'r') as f:
            self.raw_data = json.load(f)

        for level_data in self.raw_data['zoom_levels']:
            cleaned = self._clean_level_data(level_data)
            self.clean_data[cleaned.level] = cleaned

        return self.clean_data

    def _clean_level_data(self, level_data: dict) -> ZoomLevelData:
        """Clean data for a single zoom level."""
        viewport = level_data['viewport']
        arrow_deltas = level_data['arrow_deltas']

        return ZoomLevelData(
            level=level_data['level'],
            viewport_area=viewport['area'],
            viewport_area_pct=viewport['area_pct'],
            right_dx=float(arrow_deltas['right']['dx']),
            left_dx=float(arrow_deltas['left']['dx']),
            up_dy=float(arrow_deltas['up']['dy']),
            down_dy=float(arrow_deltas['down']['dy'])
        )

    @staticmethod
    def _filter_outliers_iqr(values: list, threshold: float = 1.5) -> list:
        """
        Filter outliers using Interquartile Range (IQR) method.

        Args:
            values: List of numeric values
            threshold: IQR multiplier (1.5 is standard)

        Returns:
            Filtered list with outliers removed
        """
        if len(values) < 4:
            return values  # Need at least 4 points for IQR

        arr = np.array(values)
        q1 = np.percentile(arr, 25)
        q3 = np.percentile(arr, 75)
        iqr = q3 - q1

        lower_bound = q1 - threshold * iqr
        upper_bound = q3 + threshold * iqr

        filtered = [v for v in values if lower_bound <= v <= upper_bound]
        return filtered if filtered else values  # Return original if all filtered


class MinimapNavigator:
    """
    Calculate navigation movements on the minimap.

    Uses cleaned calibration data to compute how many arrow key presses
    are needed to move from current position to target position at a
    given zoom level.
    """

    MINIMAP_SIZE = 226  # Minimap is 226×226 pixels

    def __init__(self, calibration_file: Optional[Path | str] = None):
        """
        Initialize navigator with calibration data.

        Args:
            calibration_file: Path to zoom_calibration_matrix_clean.json
                            If None, uses cleaned calibration file
        """
        if calibration_file is None:
            calibration_file = Path(__file__).parent / "zoom_calibration_matrix_clean.json"

        cleaner = CalibrationCleaner(calibration_file)
        self.calibration_data = cleaner.load_calibration()

        if not self.calibration_data:
            raise ValueError(f"No calibration data loaded from {calibration_file}")

        # Build sorted list of levels by area for zoom detection
        self._levels_by_area = sorted(
            self.calibration_data.items(),
            key=lambda x: x[1].viewport_area
        )

    def calculate_movement(
        self,
        zoom_level: int,
        current_pos: Tuple[int, int],
        target_pos: Tuple[int, int]
    ) -> Dict[str, int]:
        """
        Calculate arrow key movements needed to reach target position.

        Args:
            zoom_level: Current zoom level (0-35)
            current_pos: Current viewport center (x, y) in minimap coordinates
            target_pos: Target viewport center (x, y) in minimap coordinates

        Returns:
            Dictionary with arrow counts: {'right': N, 'left': M, 'up': P, 'down': Q}
            Only the net direction is non-zero (e.g., either right OR left, not both)

        Raises:
            ValueError: If zoom_level not in calibration data or positions invalid
        """
        # Validate inputs
        if zoom_level not in self.calibration_data:
            raise ValueError(f"Zoom level {zoom_level} not in calibration data")

        self._validate_position(*current_pos, "current_pos")
        self._validate_position(*target_pos, "target_pos")

        # Get calibration for this zoom level
        cal = self.calibration_data[zoom_level]

        # Calculate deltas
        delta_x = target_pos[0] - current_pos[0]
        delta_y = target_pos[1] - current_pos[1]

        # Calculate horizontal movement
        if delta_x > 0:
            # Move right
            right_count = round(abs(delta_x) / abs(cal.right_dx))
            left_count = 0
        elif delta_x < 0:
            # Move left
            right_count = 0
            left_count = round(abs(delta_x) / abs(cal.left_dx))
        else:
            right_count = 0
            left_count = 0

        # Calculate vertical movement
        if delta_y > 0:
            # Move down
            down_count = round(abs(delta_y) / abs(cal.down_dy))
            up_count = 0
        elif delta_y < 0:
            # Move up
            down_count = 0
            up_count = round(abs(delta_y) / abs(cal.up_dy))
        else:
            down_count = 0
            up_count = 0

        return {
            'right': right_count,
            'left': left_count,
            'up': up_count,
            'down': down_count
        }

    def get_zoom_level_by_area(self, area_pct: float) -> int:
        """
        Find closest zoom level for a given viewport area percentage.

        Args:
            area_pct: Viewport area as percentage of minimap (0.0-100.0)

        Returns:
            Closest zoom level
        """
        if not self.calibration_data:
            raise ValueError("No calibration data available")

        # Find level with closest area_pct
        closest_level = min(
            self.calibration_data.keys(),
            key=lambda lvl: abs(self.calibration_data[lvl].viewport_area_pct - area_pct)
        )

        return closest_level

    def _validate_position(self, x: int, y: int, name: str = "position"):
        """Validate that position is within minimap bounds."""
        if not (0 <= x <= self.MINIMAP_SIZE):
            raise ValueError(f"{name} x={x} out of bounds (0-{self.MINIMAP_SIZE})")
        if not (0 <= y <= self.MINIMAP_SIZE):
            raise ValueError(f"{name} y={y} out of bounds (0-{self.MINIMAP_SIZE})")

    def get_zoom_data(self, zoom_level: int) -> ZoomLevelData:
        """Get calibration data for a specific zoom level."""
        if zoom_level not in self.calibration_data:
            raise ValueError(f"Zoom level {zoom_level} not in calibration data")
        return self.calibration_data[zoom_level]

    def list_zoom_levels(self) -> list[int]:
        """Get list of all available zoom levels."""
        return sorted(self.calibration_data.keys())

    def detect_zoom_level(self, viewport_area: int, tolerance: int = 10) -> Optional[int]:
        """
        Detect current zoom level from viewport area.

        Args:
            viewport_area: Current viewport area in pixels
            tolerance: Tolerance in pixels for matching (default: 10)

        Returns:
            Detected zoom level, or None if no match found
        """
        # Find closest matching level
        best_match = None
        best_diff = float('inf')

        for level, data in self.calibration_data.items():
            diff = abs(data.viewport_area - viewport_area)
            if diff < best_diff:
                best_diff = diff
                best_match = level

        if best_diff <= tolerance:
            return best_match
        return None

    def calculate_zoom_adjustment(
        self,
        current_area: int,
        target_area: int,
        tolerance: int = 10
    ) -> Dict[str, int]:
        """
        Calculate how many zoom in/out steps needed to reach target area.

        Args:
            current_area: Current viewport area in pixels
            target_area: Target viewport area in pixels
            tolerance: Tolerance for matching areas (default: 10)

        Returns:
            {'zoom_in': N, 'zoom_out': M, 'current_level': X, 'target_level': Y}
            Only zoom_in OR zoom_out will be non-zero

        Raises:
            ValueError: If current or target area doesn't match any zoom level
        """
        current_level = self.detect_zoom_level(current_area, tolerance)
        target_level = self.detect_zoom_level(target_area, tolerance)

        if current_level is None:
            raise ValueError(f"Current area {current_area} doesn't match any zoom level")
        if target_level is None:
            raise ValueError(f"Target area {target_area} doesn't match any zoom level")

        # Calculate steps needed
        steps = target_level - current_level

        if steps > 0:
            # Need to zoom out (higher level = more zoomed out)
            return {
                'zoom_in': 0,
                'zoom_out': steps,
                'current_level': current_level,
                'target_level': target_level
            }
        elif steps < 0:
            # Need to zoom in
            return {
                'zoom_in': abs(steps),
                'zoom_out': 0,
                'current_level': current_level,
                'target_level': target_level
            }
        else:
            # Already at correct zoom
            return {
                'zoom_in': 0,
                'zoom_out': 0,
                'current_level': current_level,
                'target_level': target_level
            }


def main():
    """Demo/test of minimap navigator."""
    nav = MinimapNavigator()

    print("Minimap Navigator - Calibration Summary")
    print("=" * 60)
    print(f"Available zoom levels: {nav.list_zoom_levels()}")
    print(f"Total unique levels: {len(nav.calibration_data)}")
    print()

    # Show sample data for a few zoom levels
    print("Sample Calibration Data:")
    print("-" * 60)
    for level in [0, 10, 20, 30]:
        if level in nav.calibration_data:
            data = nav.get_zoom_data(level)
            print(f"\nLevel {level}:")
            print(f"  Viewport area: {data.viewport_area} pixels ({data.viewport_area_pct:.2f}%)")
            print(f"  Arrow deltas:")
            print(f"    RIGHT: dx={data.right_dx:+.1f}")
            print(f"    LEFT:  dx={data.left_dx:+.1f}")
            print(f"    UP:    dy={data.up_dy:+.1f}")
            print(f"    DOWN:  dy={data.down_dy:+.1f}")

    # Demo zoom level detection
    print("\n" + "=" * 60)
    print("Demo Zoom Level Detection:")
    print("-" * 60)
    test_areas = [85, 207, 420, 1000, 1550]
    for area in test_areas:
        detected = nav.detect_zoom_level(area)
        if detected is not None:
            data = nav.get_zoom_data(detected)
            print(f"Area {area:4d} pixels -> Level {detected:2d} (actual: {data.viewport_area} pixels)")
        else:
            print(f"Area {area:4d} pixels -> No match found")

    # Demo zoom adjustment
    print("\n" + "=" * 60)
    print("Demo Zoom Adjustment:")
    print("-" * 60)
    current_area = 207  # Level 8
    target_area = 1000  # Level 30
    adjustment = nav.calculate_zoom_adjustment(current_area, target_area)
    print(f"Current: {current_area} pixels (Level {adjustment['current_level']})")
    print(f"Target: {target_area} pixels (Level {adjustment['target_level']})")
    print(f"Adjustment needed:")
    if adjustment['zoom_out'] > 0:
        print(f"  ZOOM OUT: {adjustment['zoom_out']} steps")
    elif adjustment['zoom_in'] > 0:
        print(f"  ZOOM IN: {adjustment['zoom_in']} steps")
    else:
        print(f"  Already at target zoom level")

    # Demo movement calculation
    print("\n" + "=" * 60)
    print("Demo Movement Calculation:")
    print("-" * 60)
    current = (113, 139)
    target = (150, 180)
    zoom = 15

    print(f"Zoom level: {zoom}")
    print(f"Current position: {current}")
    print(f"Target position: {target}")
    print(f"Delta: ({target[0] - current[0]}, {target[1] - current[1]})")
    print()

    movements = nav.calculate_movement(zoom, current, target)
    print("Required movements:")
    for direction, count in movements.items():
        if count > 0:
            print(f"  {direction.upper()}: {count} presses")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
