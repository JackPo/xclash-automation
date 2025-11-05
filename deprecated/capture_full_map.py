"""
⚠️ DEPRECATED - DO NOT USE ⚠️
Deprecated as of 2025-11-05

This approach has been abandoned due to:
- Tile stitching complexity and unreliable results
- Inconsistent overlap detection between tiles
- Better alternatives needed for map analysis

See .claude/claude.MD for details.

---

Capture full map tiles for Clash of Clans world map
Grid: 33 columns x 39 rows = 1287 screenshots
Pattern: Snake (zigzag) - alternating left-to-right and right-to-left
Over-captures by 5 tiles in each direction to ensure complete coverage
"""
import subprocess
import time
import os
from datetime import datetime

# Configuration
GRID_COLS = 33
GRID_ROWS = 39
DELAY_AFTER_MOVE = 0.5  # seconds to wait for view to settle
OUTPUT_DIR = "map_tiles"

# Paths
ADB_PATH = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
DEVICE = "emulator-5554"
PYTHON_PATH = r"C:\Users\mail\AppData\Local\Programs\Python\Python312\python.exe"
ARROW_SCRIPT = "send_arrow_proper.py"

def take_screenshot(row, col):
    """Take screenshot and save to map_tiles directory"""
    filename = os.path.join(OUTPUT_DIR, f"tile_{row:02d}_{col:02d}.png")
    cmd = [ADB_PATH, "-s", DEVICE, "exec-out", "screencap", "-p"]

    try:
        with open(filename, 'wb') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, check=True)
        return True
    except Exception as e:
        print(f"Error capturing tile {row},{col}: {e}")
        return False

def send_arrow(direction):
    """Send arrow key using send_arrow_proper.py"""
    cmd = [PYTHON_PATH, ARROW_SCRIPT, direction]
    try:
        # Run arrow script (it handles window focusing)
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except Exception as e:
        print(f"Error sending {direction} arrow: {e}")
        return False

def main():
    print("="*60)
    print("Clash of Clans World Map Capture")
    print("="*60)
    print(f"Grid size: {GRID_COLS} columns x {GRID_ROWS} rows")
    print(f"Total tiles: {GRID_COLS * GRID_ROWS}")
    print(f"Delay per tile: {DELAY_AFTER_MOVE}s")
    print(f"Pattern: Snake (zigzag)")
    print(f"Output directory: {OUTPUT_DIR}")
    print("="*60)

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("\nStarting capture in 3 seconds...")
    time.sleep(3)

    start_time = datetime.now()
    total_tiles = GRID_COLS * GRID_ROWS
    tiles_captured = 0

    # Traverse in snake pattern
    for row in range(GRID_ROWS):
        # Determine direction for this row
        if row % 2 == 0:
            # Even rows: left to right (0 -> GRID_COLS-1)
            cols = range(GRID_COLS)
            move_direction = "right"
        else:
            # Odd rows: right to left (GRID_COLS-1 -> 0)
            cols = range(GRID_COLS - 1, -1, -1)
            move_direction = "left"

        print(f"\n--- Row {row}/{GRID_ROWS-1} ({'LEFT->RIGHT' if row % 2 == 0 else 'RIGHT->LEFT'}) ---")

        for i, col in enumerate(cols):
            # Wait for view to settle before screenshot
            time.sleep(DELAY_AFTER_MOVE)

            # Take screenshot
            success = take_screenshot(row, col)
            if success:
                tiles_captured += 1

                # Progress update every 10 tiles
                if tiles_captured % 10 == 0:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    avg_per_tile = elapsed / tiles_captured
                    remaining = (total_tiles - tiles_captured) * avg_per_tile
                    print(f"  [{tiles_captured}/{total_tiles}] tiles captured | "
                          f"Avg: {avg_per_tile:.2f}s/tile | "
                          f"ETA: {remaining/60:.1f} min")
                else:
                    print(f"  Captured tile_{row:02d}_{col:02d}.png [{tiles_captured}/{total_tiles}]")

            # Move to next column (except last column in row)
            if i < len(cols) - 1:
                send_arrow(move_direction)

        # Move down to next row (except last row)
        if row < GRID_ROWS - 1:
            print(f"  Moving DOWN to row {row+1}...")
            send_arrow("down")

    # Final summary
    end_time = datetime.now()
    total_time = (end_time - start_time).total_seconds()

    print("\n" + "="*60)
    print("CAPTURE COMPLETE!")
    print("="*60)
    print(f"Total tiles captured: {tiles_captured}/{total_tiles}")
    print(f"Total time: {total_time/60:.2f} minutes ({total_time:.1f} seconds)")
    print(f"Average per tile: {total_time/tiles_captured:.2f} seconds")
    print(f"Output directory: {OUTPUT_DIR}/")
    print("="*60)

if __name__ == "__main__":
    main()
