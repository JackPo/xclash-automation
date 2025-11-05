"""
Find Castle by Level and Name - Main search orchestration

Searches the entire map for castles matching a specific level range and owner name.
Uses minimap navigation, castle detection, and OCR verification.

Usage:
    python find_castle_by_level.py --level-min 20 --level-max 21 --name yagamilight

    Or programmatically:
    from find_castle_by_level import find_castle

    result = find_castle(
        level_range=(20, 21),
        target_name="yagamilight"
    )
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Optional
import cv2
import time
import argparse

from find_player import ADBController, Config
from view_detection import ViewDetector, ViewState, switch_to_view
from minimap_navigator import MinimapNavigator
from castle_scanner import CastleDetector, CastleNameReader, CastleMatch
from send_zoom import send_zoom
from send_arrow_proper import send_arrow


@dataclass
class SearchResult:
    """Result of castle search."""
    found: bool
    castle_name: Optional[str] = None
    castle_level: Optional[int] = None
    screen_position: Optional[Tuple[int, int]] = None  # (x, y) where castle was found
    minimap_position: Optional[Tuple[int, int]] = None  # Viewport center when found
    search_time_seconds: Optional[float] = None
    screens_searched: int = 0


class CastleSearcher:
    """
    Orchestrate map-wide castle search.

    Search pattern:
    1. Switch to WORLD view
    2. Zoom to optimal level
    3. Navigate to top-left corner
    4. Scan current viewport for castles
    5. Click each matching castle, verify name with OCR
    6. Move in zigzag pattern to cover entire map
    """

    # Search pattern settings
    ARROWS_PER_STEP = 5  # Move 5 arrows horizontally/vertically per step
    WAIT_AFTER_ZOOM = 1.5  # Seconds to wait after zoom command
    WAIT_AFTER_ARROW = 1.0  # Seconds to wait after arrow command
    WAIT_AFTER_CLICK = 2.0  # Seconds to wait after clicking castle (for zoom animation)
    WAIT_FOR_OCR = 1.0  # Extra seconds to ensure text is visible

    # Map boundaries (approximate - will adjust based on minimap)
    MAP_TOP_LEFT = (20, 20)  # Conservative start position
    MAP_BOTTOM_RIGHT = (206, 206)  # Conservative end position

    def __init__(self):
        """Initialize search system."""
        self.config = Config()
        self.adb = ADBController(self.config)
        self.view_detector = ViewDetector()
        self.navigator = MinimapNavigator()
        self.castle_detector = CastleDetector()
        self.name_reader = CastleNameReader()

    def find_castle(
        self,
        level_range: Tuple[int, int],
        target_name: str,
        start_position: Optional[Tuple[int, int]] = None
    ) -> SearchResult:
        """
        Search for castle matching level range and owner name.

        Args:
            level_range: (min_level, max_level) inclusive
            target_name: Castle owner name (case-insensitive)
            start_position: Optional starting minimap position
                          Defaults to top-left corner

        Returns:
            SearchResult with found status and details
        """
        start_time = time.time()
        screens_searched = 0

        print(f"Searching for castle: Level {level_range[0]}-{level_range[1]}, Owner: {target_name}")
        print("=" * 60)

        # Step 1: Switch to WORLD view
        print("Step 1: Switching to WORLD view...")
        switch_to_view(self.adb, ViewState.WORLD)
        time.sleep(1.0)

        # Step 2: Zoom to optimal level
        print("Step 2: Zooming to optimal level...")
        optimal_zoom = self._zoom_to_optimal()
        print(f"  At zoom level {optimal_zoom}")

        # Step 3: Navigate to starting position
        if start_position is None:
            start_position = self.MAP_TOP_LEFT

        print(f"Step 3: Navigating to start position {start_position}...")
        self._navigate_to_position(optimal_zoom, start_position)

        # Step 4: Begin zigzag search
        print("Step 4: Beginning search...")
        print()

        current_pos = start_position
        direction = 1  # 1 = moving right, -1 = moving left

        while True:
            screens_searched += 1
            print(f"[Screen {screens_searched}] Searching at minimap position {current_pos}...")

            # Get current viewport
            self.adb.screenshot('temp_search.png')
            frame = cv2.imread('temp_search.png')

            # Detect current position from minimap
            result = self.view_detector.detect_from_frame(frame)
            if not result.minimap_present:
                print("  WARNING: Minimap not visible, skipping viewport update")
            else:
                current_pos = (result.minimap_viewport.center_x, result.minimap_viewport.center_y)
                print(f"  Current viewport center: {current_pos}")

            # Detect castles in current view
            castles = self.castle_detector.find_castles_in_frame(frame)
            print(f"  Found {len(castles)} castles in view")

            # Check each castle
            for i, castle in enumerate(castles, 1):
                print(f"    Castle {i}/{len(castles)}: ({castle.x}, {castle.y}) confidence={castle.confidence:.2%}")

                # Click castle to zoom in
                print(f"      Clicking castle...")
                self.adb.tap(castle.x, castle.y)
                time.sleep(self.WAIT_AFTER_CLICK)

                # Read name and level
                self.adb.screenshot('temp_zoomed.png')
                zoomed_frame = cv2.imread('temp_zoomed.png')
                time.sleep(self.WAIT_FOR_OCR)

                owner_name, owner_level = self.name_reader.read_castle_info(zoomed_frame)
                print(f"      OCR: Name='{owner_name}', Level={owner_level}")

                # Check if matches
                if owner_level is not None and level_range[0] <= owner_level <= level_range[1]:
                    if self.name_reader.matches_name(owner_name, target_name):
                        # FOUND IT!
                        elapsed = time.time() - start_time
                        print()
                        print("=" * 60)
                        print("CASTLE FOUND!")
                        print(f"  Name: {owner_name}")
                        print(f"  Level: {owner_level}")
                        print(f"  Position: ({castle.x}, {castle.y})")
                        print(f"  Minimap: {current_pos}")
                        print(f"  Searched {screens_searched} screens in {elapsed:.1f}s")
                        print("=" * 60)

                        return SearchResult(
                            found=True,
                            castle_name=owner_name,
                            castle_level=owner_level,
                            screen_position=(castle.x, castle.y),
                            minimap_position=current_pos,
                            search_time_seconds=elapsed,
                            screens_searched=screens_searched
                        )

                # Not a match, zoom back out
                print(f"      Not a match, zooming back out...")
                self._zoom_back_to_viewport(optimal_zoom, current_pos)

            # Move to next viewport
            next_pos = self._get_next_search_position(current_pos, direction)

            if next_pos is None:
                # Reached end of map
                elapsed = time.time() - start_time
                print()
                print("=" * 60)
                print("SEARCH COMPLETE - Castle not found")
                print(f"  Searched {screens_searched} screens in {elapsed:.1f}s")
                print("=" * 60)

                return SearchResult(
                    found=False,
                    search_time_seconds=elapsed,
                    screens_searched=screens_searched
                )

            # Check if we need to reverse direction (zigzag)
            if next_pos[0] != current_pos[0]:
                # Horizontal movement
                current_pos = next_pos
                self._move_horizontal(direction)
            else:
                # Vertical movement (end of row)
                direction *= -1  # Reverse direction
                current_pos = next_pos
                self._move_vertical()

    def _zoom_to_optimal(self) -> int:
        """
        Zoom to optimal castle detection level.

        Returns:
            Actual zoom level achieved
        """
        # Take screenshot to detect current zoom
        self.adb.screenshot('temp_zoom.png')
        frame = cv2.imread('temp_zoom.png')
        result = self.view_detector.detect_from_frame(frame)

        if not result.minimap_present:
            print("  WARNING: Minimap not visible, cannot detect zoom")
            print("  Assuming already at optimal zoom")
            return self.castle_detector.OPTIMAL_ZOOM_LEVEL

        current_area = result.minimap_viewport.area
        target_area = self.castle_detector.OPTIMAL_VIEWPORT_AREA

        # Calculate adjustment
        adjustment = self.navigator.calculate_zoom_adjustment(current_area, target_area)

        print(f"  Current: Level {adjustment['current_level']} ({current_area} pixels)")
        print(f"  Target: Level {adjustment['target_level']} ({target_area} pixels)")

        # Perform zoom
        for _ in range(adjustment['zoom_out']):
            send_zoom('out')
            time.sleep(self.WAIT_AFTER_ZOOM)

        for _ in range(adjustment['zoom_in']):
            send_zoom('in')
            time.sleep(self.WAIT_AFTER_ZOOM)

        return adjustment['target_level']

    def _navigate_to_position(self, zoom_level: int, target_pos: Tuple[int, int]):
        """Navigate to target minimap position."""
        # Get current position
        self.adb.screenshot('temp_nav.png')
        frame = cv2.imread('temp_nav.png')
        result = self.view_detector.detect_from_frame(frame)

        if not result.minimap_present:
            print("  WARNING: Cannot navigate - minimap not visible")
            return

        current_pos = (result.minimap_viewport.center_x, result.minimap_viewport.center_y)

        # Calculate movement
        movements = self.navigator.calculate_movement(zoom_level, current_pos, target_pos)

        print(f"  Moving from {current_pos} to {target_pos}")
        print(f"  Movements: {movements}")

        # Execute movements
        for _ in range(movements['right']):
            send_arrow('right')
            time.sleep(self.WAIT_AFTER_ARROW)

        for _ in range(movements['left']):
            send_arrow('left')
            time.sleep(self.WAIT_AFTER_ARROW)

        for _ in range(movements['down']):
            send_arrow('down')
            time.sleep(self.WAIT_AFTER_ARROW)

        for _ in range(movements['up']):
            send_arrow('up')
            time.sleep(self.WAIT_AFTER_ARROW)

    def _zoom_back_to_viewport(self, target_zoom: int, target_pos: Tuple[int, int]):
        """
        Zoom back out and restore viewport position after clicking castle.

        Args:
            target_zoom: Zoom level to return to
            target_pos: Minimap position to return to
        """
        # First, zoom back to target level
        # When clicking castle, game zooms IN, so we need to zoom OUT
        target_area = self.navigator.get_zoom_data(target_zoom).viewport_area

        # Zoom out until we're back at target level
        # Estimate: clicking castle typically zooms in ~10 levels
        estimated_zoom_out = 10

        for _ in range(estimated_zoom_out):
            send_zoom('out')
            time.sleep(self.WAIT_AFTER_ZOOM)

        # Verify and adjust
        self.adb.screenshot('temp_zoom_check.png')
        frame = cv2.imread('temp_zoom_check.png')
        result = self.view_detector.detect_from_frame(frame)

        if result.minimap_present:
            current_area = result.minimap_viewport.area
            adjustment = self.navigator.calculate_zoom_adjustment(current_area, target_area, tolerance=20)

            for _ in range(adjustment['zoom_out']):
                send_zoom('out')
                time.sleep(self.WAIT_AFTER_ZOOM)

            for _ in range(adjustment['zoom_in']):
                send_zoom('in')
                time.sleep(self.WAIT_AFTER_ZOOM)

        # Navigate back to target position
        self._navigate_to_position(target_zoom, target_pos)

    def _move_horizontal(self, direction: int):
        """Move horizontally by ARROWS_PER_STEP."""
        arrow = 'right' if direction > 0 else 'left'

        for _ in range(self.ARROWS_PER_STEP):
            send_arrow(arrow)
            time.sleep(self.WAIT_AFTER_ARROW)

    def _move_vertical(self):
        """Move down by ARROWS_PER_STEP."""
        for _ in range(self.ARROWS_PER_STEP):
            send_arrow('down')
            time.sleep(self.WAIT_AFTER_ARROW)

    def _get_next_search_position(
        self,
        current_pos: Tuple[int, int],
        direction: int
    ) -> Optional[Tuple[int, int]]:
        """
        Calculate next search position in zigzag pattern.

        Args:
            current_pos: Current minimap position (x, y)
            direction: 1 for moving right, -1 for moving left

        Returns:
            Next position (x, y) or None if search complete
        """
        x, y = current_pos

        # Calculate next horizontal position
        step_size = self.ARROWS_PER_STEP * 5  # Approximate pixels per step (varies by zoom)

        if direction > 0:
            # Moving right
            next_x = x + step_size
            if next_x > self.MAP_BOTTOM_RIGHT[0]:
                # Hit right edge, move down
                next_x = x
                next_y = y + step_size

                if next_y > self.MAP_BOTTOM_RIGHT[1]:
                    # Hit bottom edge, search complete
                    return None

                return (next_x, next_y)

            return (next_x, y)
        else:
            # Moving left
            next_x = x - step_size
            if next_x < self.MAP_TOP_LEFT[0]:
                # Hit left edge, move down
                next_x = x
                next_y = y + step_size

                if next_y > self.MAP_BOTTOM_RIGHT[1]:
                    # Hit bottom edge, search complete
                    return None

                return (next_x, next_y)

            return (next_x, y)


def main():
    """Command-line interface for castle search."""
    parser = argparse.ArgumentParser(
        description="Find castle by level range and owner name"
    )
    parser.add_argument(
        '--level-min',
        type=int,
        required=True,
        help='Minimum castle level (inclusive)'
    )
    parser.add_argument(
        '--level-max',
        type=int,
        required=True,
        help='Maximum castle level (inclusive)'
    )
    parser.add_argument(
        '--name',
        type=str,
        required=True,
        help='Castle owner name (case-insensitive)'
    )

    args = parser.parse_args()

    # Run search
    searcher = CastleSearcher()
    result = searcher.find_castle(
        level_range=(args.level_min, args.level_max),
        target_name=args.name
    )

    # Exit with status code
    exit(0 if result.found else 1)


if __name__ == "__main__":
    main()
