#!/usr/bin/env python3
"""
XClash Level 20 Castle Finder (Phase 1)
Scans the map at zoomed-out level to find all castle level 20s.
Saves screenshots and coordinates for later investigation.

Usage:
    python find_level20.py --run-id scan001
    python find_level20.py --run-id scan001 --debug
"""

import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from PIL import Image
import pytesseract
from find_player import ADBController, Config, OCRProcessor


class MapConfig:
    """Loads and manages map calibration config."""

    def __init__(self, config_file="map_config.json"):
        self.config_file = Path(config_file)

        if not self.config_file.exists():
            raise FileNotFoundError(
                f"Map config not found: {config_file}\n"
                f"Please run calibrate_map.py first to generate configuration."
            )

        with open(self.config_file, 'r') as f:
            self.data = json.load(f)

        # Extract key values
        self.swipes_to_left = self.data["navigation"]["swipes_to_left_edge"]
        self.swipes_to_top = self.data["navigation"]["swipes_to_top_edge"]
        self.horizontal_steps = self.data["map_size"]["horizontal_steps"]
        self.vertical_steps = self.data["map_size"]["vertical_steps"]
        self.h_scroll_dist = self.data["scroll_distances"]["horizontal_scroll_distance"]
        self.v_scroll_dist = self.data["scroll_distances"]["vertical_scroll_distance"]

    def __str__(self):
        return (f"MapConfig(grid={self.horizontal_steps}×{self.vertical_steps}, "
                f"to_corner=left:{self.swipes_to_left},up:{self.swipes_to_top})")


class CoordinateTracker:
    """Tracks and converts between grid positions and screen coordinates."""

    def __init__(self, map_config, screen_config):
        self.map_config = map_config
        self.screen_config = screen_config

        # Calculate center of map viewing area
        self.center_x = (screen_config.MAP_LEFT + screen_config.MAP_RIGHT) // 2
        self.center_y = (screen_config.MAP_TOP + screen_config.MAP_BOTTOM) // 2

        # Current position
        self.current_row = 0
        self.current_col = 0

    def get_current_position(self):
        """Get current grid position."""
        return (self.current_row, self.current_col)

    def get_screen_center(self):
        """Get screen center coordinates for current position."""
        return (self.center_x, self.center_y)

    def move_to(self, row, col):
        """Update current position."""
        self.current_row = row
        self.current_col = col

    def get_position_info(self):
        """Get detailed position info for saving."""
        return {
            "grid_row": self.current_row,
            "grid_col": self.current_col,
            "screen_center_x": self.center_x,
            "screen_center_y": self.center_y,
            "description": f"Row {self.current_row}, Column {self.current_col}"
        }


class Level20Navigator:
    """Handles navigation for Level 20 scanning."""

    def __init__(self, adb, map_config, coord_tracker, screen_config):
        self.adb = adb
        self.map_config = map_config
        self.coords = coord_tracker
        self.config = screen_config

    def go_to_top_left(self):
        """Navigate to top-left corner using calibrated values."""
        print("📍 Navigating to top-left corner...")

        center_x = self.coords.center_x
        center_y = self.coords.center_y

        # Swipe left
        print(f"   Swiping left {self.map_config.swipes_to_left} times...")
        for i in range(self.map_config.swipes_to_left):
            self.adb.swipe(
                center_x + self.map_config.h_scroll_dist // 2,
                center_y,
                center_x - self.map_config.h_scroll_dist // 2,
                center_y,
                self.config.SCROLL_DURATION
            )
            time.sleep(self.config.DELAY_AFTER_SWIPE)

        # Swipe up
        print(f"   Swiping up {self.map_config.swipes_to_top} times...")
        for i in range(self.map_config.swipes_to_top):
            self.adb.swipe(
                center_x,
                center_y + self.map_config.v_scroll_dist // 2,
                center_x,
                center_y - self.map_config.v_scroll_dist // 2,
                self.config.SCROLL_DURATION
            )
            time.sleep(self.config.DELAY_AFTER_SWIPE)

        print("✅ Reached top-left corner")
        self.coords.move_to(0, 0)

    def scroll_right(self):
        """Scroll one step to the right."""
        self.adb.swipe(
            self.coords.center_x - self.map_config.h_scroll_dist // 2,
            self.coords.center_y,
            self.coords.center_x + self.map_config.h_scroll_dist // 2,
            self.coords.center_y,
            self.config.SCROLL_DURATION
        )
        time.sleep(self.config.DELAY_AFTER_SWIPE)
        self.coords.move_to(self.coords.current_row, self.coords.current_col + 1)

    def scroll_left(self):
        """Scroll one step to the left."""
        self.adb.swipe(
            self.coords.center_x + self.map_config.h_scroll_dist // 2,
            self.coords.center_y,
            self.coords.center_x - self.map_config.h_scroll_dist // 2,
            self.coords.center_y,
            self.config.SCROLL_DURATION
        )
        time.sleep(self.config.DELAY_AFTER_SWIPE)
        self.coords.move_to(self.coords.current_row, self.coords.current_col - 1)

    def scroll_down(self):
        """Scroll one step down."""
        self.adb.swipe(
            self.coords.center_x,
            self.coords.center_y - self.map_config.v_scroll_dist // 2,
            self.coords.center_x,
            self.coords.center_y + self.map_config.v_scroll_dist // 2,
            self.config.SCROLL_DURATION
        )
        time.sleep(self.config.DELAY_AFTER_SWIPE)
        self.coords.move_to(self.coords.current_row + 1, self.coords.current_col)


class Level20Scanner:
    """Main scanner for finding Level 20 castles."""

    def __init__(self, run_id, debug=False):
        self.run_id = run_id
        self.debug = debug

        # Load configs
        self.screen_config = Config()
        self.map_config = MapConfig()

        print(f"📋 Map configuration: {self.map_config}")

        # Initialize components
        self.adb = ADBController(self.screen_config)
        self.coords = CoordinateTracker(self.map_config, self.screen_config)
        self.navigator = Level20Navigator(self.adb, self.map_config, self.coords, self.screen_config)
        self.ocr = OCRProcessor(self.screen_config, debug=False)

        # Setup output directories
        self.output_dir = Path(f"{run_id}_level20")
        self.output_dir.mkdir(exist_ok=True)
        print(f"📁 Output directory: {self.output_dir}")

        # Results tracking
        self.results = {
            "run_id": run_id,
            "started_at": datetime.now().isoformat(),
            "map_config": str(self.map_config),
            "castles": []
        }

        self.total_scans = 0
        self.level20_count = 0

    def scan_current_view(self):
        """Scan current view for level 20 castles."""
        row, col = self.coords.get_current_position()
        screenshot_file = f"r{row}_c{col}.png"
        screenshot_path = self.output_dir / screenshot_file

        # Capture screenshot
        self.adb.screenshot(screenshot_path)
        time.sleep(self.screen_config.DELAY_AFTER_SCREENSHOT)

        # OCR
        ocr_results = self.ocr.process_screenshot(screenshot_path)

        # Look for "20" in results
        found_20 = False
        for text, conf in ocr_results:
            # Look for exactly "20" or "Lv20" or "Level 20"
            if "20" in text:
                found_20 = True
                break

        self.total_scans += 1

        if found_20:
            self.level20_count += 1

            # Save result
            castle_info = {
                "id": self.level20_count,
                "position": self.coords.get_position_info(),
                "screenshot": screenshot_file,
                "ocr_text": [text for text, conf in ocr_results if "20" in text],
                "all_text": [text for text, conf in ocr_results[:10]]  # Top 10 for debugging
            }
            self.results["castles"].append(castle_info)

            return (True, ocr_results)
        else:
            # Delete screenshot if no level 20 found (save disk space)
            if not self.debug:
                screenshot_path.unlink()
            return (False, ocr_results)

    def scan_grid(self):
        """Scan entire map in grid pattern."""
        print(f"\n🔍 Starting Level 20 castle scan")
        print(f"📊 Scan grid: {self.map_config.horizontal_steps} × {self.map_config.vertical_steps}")
        print("="*60)

        # Navigate to starting position
        self.navigator.go_to_top_left()
        time.sleep(1)

        # Grid scan
        for row in range(self.map_config.vertical_steps):
            # Determine direction for this row (zigzag)
            if row % 2 == 0:
                cols = range(self.map_config.horizontal_steps)
                direction = "→"
            else:
                cols = range(self.map_config.horizontal_steps - 1, -1, -1)
                direction = "←"

            for col in cols:
                # Scan
                print(f"[{row+1:2d}/{self.map_config.vertical_steps}, "
                      f"{col+1:2d}/{self.map_config.horizontal_steps}] {direction} ", end="")

                found, ocr_results = self.scan_current_view()

                if found:
                    print(f"🏰 LEVEL 20 FOUND! (Total: {self.level20_count})")
                else:
                    print(f"❌ ({len(ocr_results)} items)")

                # Move to next column (except at row end)
                if row % 2 == 0:  # Left to right
                    if col < self.map_config.horizontal_steps - 1:
                        self.navigator.scroll_right()
                else:  # Right to left
                    if col > 0:
                        self.navigator.scroll_left()

                time.sleep(self.screen_config.DELAY_BETWEEN_SCANS)

            # Move to next row
            if row < self.map_config.vertical_steps - 1:
                print(f"   ⬇️  Moving to row {row+2}...")
                self.navigator.scroll_down()

        # Finalize results
        self.results["completed_at"] = datetime.now().isoformat()
        self.results["total_scans"] = self.total_scans
        self.results["level20_found"] = self.level20_count

    def save_results(self):
        """Save results to JSON file."""
        results_file = Path(f"{self.run_id}_level20_results.json")

        with open(results_file, 'w') as f:
            json.dump(self.results, indent=2, fp=f)

        print("\n" + "="*60)
        print(f"📊 SCAN COMPLETE")
        print("="*60)
        print(f"Total scans: {self.total_scans}")
        print(f"Level 20 castles found: {self.level20_count}")
        print(f"Screenshots saved to: {self.output_dir}/")
        print(f"Results saved to: {results_file}")
        print("="*60)

        if self.level20_count > 0:
            print("\n🏰 Level 20 Castles:")
            for castle in self.results["castles"]:
                pos = castle["position"]
                print(f"  #{castle['id']}: {pos['description']} -> {castle['screenshot']}")


def main():
    parser = argparse.ArgumentParser(description="XClash Level 20 Castle Finder (Phase 1)")
    parser.add_argument("--run-id", required=True, help="Run ID for organizing results (e.g., scan001)")
    parser.add_argument("--debug", action="store_true", help="Save all screenshots (even without level 20)")

    args = parser.parse_args()

    try:
        scanner = Level20Scanner(args.run_id, debug=args.debug)
        scanner.scan_grid()
        scanner.save_results()

        sys.exit(0)

    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Scan interrupted by user")
        # Try to save partial results
        try:
            scanner.save_results()
        except:
            pass
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
