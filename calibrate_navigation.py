"""
Comprehensive Zoom Calibration Matrix

Builds a complete calibration table mapping ALL zoom levels from when minimap
first appears. Records viewport area and arrow deltas at each zoom level.

IMPORTANT: Before running:
1. Be in WORLD view
2. BlueStacks window must be VISIBLE (script will bring to foreground)
3. Can be at any zoom level (script will zoom out to find minimap)

Usage:
    python calibrate_navigation.py

Output:
    - zoom_calibration_matrix.json: Complete calibration data
    - calibration_log.txt: Detailed execution log
"""

import json
import time
from pathlib import Path
from datetime import datetime
from find_player import ADBController, Config
from view_detection import ViewDetector
from send_arrow_proper import send_arrow
from send_zoom import send_zoom
import win32gui
import win32con
import cv2

# Output files
CALIBRATION_FILE = Path(__file__).parent / "zoom_calibration_matrix.json"
LOG_FILE = Path(__file__).parent / "calibration_log.txt"

# Calibration parameters
MAX_ZOOM_LEVELS = 40
WAIT_AFTER_ACTION = 1.5  # seconds - increased to ensure zoom registers
POSITION_TOLERANCE = 3  # pixels


class CalibrationLogger:
    """Logger for calibration process."""

    def __init__(self, log_file):
        self.log_file = log_file
        self.log_file.write_text("")  # Clear file

    def log(self, message):
        """Log message to both console and file."""
        print(message)
        with open(self.log_file, 'a') as f:
            timestamp = datetime.now().strftime("%H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")


def find_bluestacks_window():
    """Find BlueStacks window handle."""
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "BlueStacks" in title:
                windows.append((hwnd, title))

    windows = []
    win32gui.EnumWindows(callback, windows)

    if windows:
        return windows[0][0]
    return None


def ensure_foreground(logger):
    """Bring BlueStacks to foreground."""
    hwnd = find_bluestacks_window()
    if not hwnd:
        logger.log("ERROR: BlueStacks window not found!")
        return False

    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.1)
        # Try to bring to foreground - may fail if Windows blocks it, but that's OK
        try:
            win32gui.SetForegroundWindow(hwnd)
        except:
            # Windows blocked foreground switch - not critical, continue anyway
            pass
        time.sleep(0.2)
        return True
    except Exception as e:
        logger.log(f"WARNING: Could not ensure foreground: {e}")
        return False


def get_viewport_info(adb, detector, temp_file="temp_calibration.png"):
    """Capture viewport information from current screen."""
    adb.screenshot(temp_file)
    frame = cv2.imread(temp_file)
    result = detector.detect_from_frame(frame)

    if not result.minimap_viewport:
        return None

    vp = result.minimap_viewport
    minimap_total = 226 * 226
    area_pct = (vp.area / minimap_total) * 100

    return {
        "x": vp.x,
        "y": vp.y,
        "width": vp.width,
        "height": vp.height,
        "area": vp.area,
        "area_pct": area_pct,
        "center_x": vp.center_x,
        "center_y": vp.center_y,
        "corners": {
            "top_left": list(vp.top_left),
            "top_right": list(vp.top_right),
            "bottom_left": list(vp.bottom_left),
            "bottom_right": list(vp.bottom_right)
        }
    }


def find_minimap_threshold(adb, detector, logger):
    """Zoom out until minimap appears. Returns number of zoom-outs performed."""
    logger.log("\n" + "="*60)
    logger.log("FINDING MINIMAP THRESHOLD")
    logger.log("="*60)

    zoom_count = 0
    max_attempts = 20

    for i in range(max_attempts):
        adb.screenshot("temp_calibration.png")
        frame = cv2.imread("temp_calibration.png")
        result = detector.detect_from_frame(frame)

        if result.minimap_present:
            logger.log(f"[OK] Minimap appeared after {zoom_count} zoom-out steps")
            return zoom_count

        logger.log(f"  Zoom-out #{zoom_count + 1}: No minimap yet...")
        ensure_foreground(logger)
        send_zoom('out')
        time.sleep(WAIT_AFTER_ACTION)
        zoom_count += 1

    logger.log(f"WARNING: Minimap did not appear after {max_attempts} zoom-outs")
    return zoom_count


def test_arrow_direction(adb, detector, logger, direction, initial_vp):
    """
    Test one arrow direction and measure viewport delta.

    Returns: {dx, dy} or None if failed
    """
    logger.log(f"    Testing {direction.upper()} arrow...")

    # Press arrow
    send_arrow(direction)
    time.sleep(WAIT_AFTER_ACTION)

    # Get new viewport
    new_vp = get_viewport_info(adb, detector)
    if not new_vp:
        logger.log(f"      ERROR: Viewport not detected after {direction}")
        return None

    # Calculate deltas
    dx = new_vp['center_x'] - initial_vp['center_x']
    dy = new_vp['center_y'] - initial_vp['center_y']

    logger.log(f"      Delta: dx={dx}, dy={dy}")

    return {"dx": dx, "dy": dy}


def calibrate_zoom_level(adb, detector, logger, level):
    """
    Calibrate one zoom level: record viewport and test all 4 arrows.

    Returns: dict with viewport and arrow_deltas, or None if failed
    """
    logger.log(f"\n  --- Zoom Level {level} ---")

    # Ensure foreground before testing
    ensure_foreground(logger)

    # Get initial viewport state
    initial_vp = get_viewport_info(adb, detector)
    if not initial_vp:
        logger.log(f"    ERROR: No viewport detected at level {level}")
        return None

    logger.log(f"    Viewport: {initial_vp['width']}x{initial_vp['height']}, " +
               f"area={initial_vp['area_pct']:.2f}%")

    # Test all 4 arrow directions
    arrow_deltas = {}

    # RIGHT
    right_delta = test_arrow_direction(adb, detector, logger, 'right', initial_vp)
    if right_delta:
        arrow_deltas['right'] = right_delta
        # Move back LEFT
        send_arrow('left')
        time.sleep(WAIT_AFTER_ACTION)

    # Verify position restored
    current_vp = get_viewport_info(adb, detector)
    if current_vp:
        pos_diff = abs(current_vp['center_x'] - initial_vp['center_x'])
        if pos_diff > POSITION_TOLERANCE:
            logger.log(f"      WARNING: Position not restored (diff={pos_diff}px)")

    # LEFT (from initial)
    left_delta = test_arrow_direction(adb, detector, logger, 'left', initial_vp)
    if left_delta:
        arrow_deltas['left'] = left_delta
        # Move back RIGHT
        send_arrow('right')
        time.sleep(WAIT_AFTER_ACTION)

    # DOWN
    down_delta = test_arrow_direction(adb, detector, logger, 'down', initial_vp)
    if down_delta:
        arrow_deltas['down'] = down_delta
        # Move back UP
        send_arrow('up')
        time.sleep(WAIT_AFTER_ACTION)

    # UP (from initial)
    up_delta = test_arrow_direction(adb, detector, logger, 'up', initial_vp)
    if up_delta:
        arrow_deltas['up'] = up_delta
        # Move back DOWN
        send_arrow('down')
        time.sleep(WAIT_AFTER_ACTION)

    return {
        "level": level,
        "viewport": initial_vp,
        "arrow_deltas": arrow_deltas
    }


def build_complete_matrix(adb, detector, logger, max_levels=MAX_ZOOM_LEVELS):
    """
    Build complete calibration matrix for all zoom levels.

    Returns: list of calibration data for each zoom level
    """
    logger.log("\n" + "="*60)
    logger.log("BUILDING COMPLETE CALIBRATION MATRIX")
    logger.log(f"Target: {max_levels} zoom levels")
    logger.log("="*60)

    calibration_data = []
    previous_area = None
    unchanged_count = 0

    for level in range(max_levels):
        level_data = calibrate_zoom_level(adb, detector, logger, level)

        if level_data:
            calibration_data.append(level_data)

            # Check if viewport stopped changing (max zoom reached)
            # Require 3 consecutive unchanged areas to confirm max zoom
            current_area = level_data['viewport']['area']
            if previous_area and current_area == previous_area:
                unchanged_count += 1
                logger.log(f"  Area unchanged ({unchanged_count}/3)")
                if unchanged_count >= 3:
                    logger.log(f"\n  Max zoom reached at level {level} (area unchanged 3 times)")
                    break
            else:
                unchanged_count = 0
            previous_area = current_area
        else:
            logger.log(f"  Skipping level {level} (viewport not detected)")
            unchanged_count = 0

        # Zoom out for next level
        if level < max_levels - 1:
            logger.log(f"  Zooming out to level {level + 1}...")
            ensure_foreground(logger)
            send_zoom('out')
            time.sleep(WAIT_AFTER_ACTION)

    logger.log(f"\n[OK] Calibrated {len(calibration_data)} zoom levels")
    return calibration_data


def save_calibration_matrix(matrix_data, minimap_threshold, logger):
    """Save complete calibration matrix to JSON file."""
    logger.log("\n" + "="*60)
    logger.log("SAVING CALIBRATION MATRIX")
    logger.log("="*60)

    output = {
        "calibration_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "calibration_method": "comprehensive_zoom_matrix",
        "minimap_first_appears_at_level": minimap_threshold,
        "total_zoom_levels": len(matrix_data),
        "zoom_levels": matrix_data
    }

    with open(CALIBRATION_FILE, 'w') as f:
        json.dump(output, f, indent=2)

    logger.log(f"[OK] Saved to: {CALIBRATION_FILE}")
    logger.log(f"  Total levels: {len(matrix_data)}")
    logger.log(f"  Minimap threshold: {minimap_threshold} zoom-outs from start")

    return output


def main():
    print("="*60)
    print("COMPREHENSIVE ZOOM CALIBRATION MATRIX")
    print("="*60)
    print("\nCalibrating all zoom levels...")
    print("This will take ~10-15 minutes.")
    print("="*60)

    # Initialize
    logger = CalibrationLogger(LOG_FILE)
    config = Config()
    adb = ADBController(config)
    detector = ViewDetector()

    logger.log("\n" + "="*60)
    logger.log("CALIBRATION START")
    logger.log("="*60)
    start_time = time.time()

    try:
        # Bring BlueStacks to foreground
        logger.log("\nBringing BlueStacks to foreground...")
        if not ensure_foreground(logger):
            logger.log("ERROR: Could not bring BlueStacks to foreground")
            return

        logger.log("[OK] BlueStacks is in foreground")

        # Step 0: Ensure we're in WORLD view (minimap only appears in world view)
        logger.log("\nChecking current view...")
        adb.screenshot("temp_calibration.png")
        frame = cv2.imread("temp_calibration.png")
        result = detector.detect_from_frame(frame)

        if result.state.value == "TOWN":
            logger.log("  Currently in TOWN view, switching to WORLD...")
            # Click the button to switch to WORLD
            if result.match:
                adb.tap(result.match.center[0], result.match.center[1])
                time.sleep(1.5)
                logger.log("[OK] Switched to WORLD view")
        elif result.state.value == "WORLD":
            logger.log("[OK] Already in WORLD view")
        else:
            logger.log("  WARNING: View state unknown, assuming WORLD view")

        # Step 1: Find minimap threshold
        minimap_threshold = find_minimap_threshold(adb, detector, logger)

        # Step 2: Build complete matrix
        matrix_data = build_complete_matrix(adb, detector, logger, MAX_ZOOM_LEVELS)

        # Step 3: Save to JSON
        result = save_calibration_matrix(matrix_data, minimap_threshold, logger)

        # Summary
        elapsed = time.time() - start_time
        logger.log("\n" + "="*60)
        logger.log("CALIBRATION COMPLETE!")
        logger.log("="*60)
        logger.log(f"Time elapsed: {elapsed/60:.1f} minutes")
        logger.log(f"Calibration file: {CALIBRATION_FILE}")
        logger.log(f"Log file: {LOG_FILE}")
        logger.log("\nYou can now use this calibration matrix with minimap_navigator.py")
        logger.log("="*60)

    except KeyboardInterrupt:
        logger.log("\n\nCalibration interrupted by user")
    except Exception as e:
        logger.log(f"\n\nERROR: {str(e)}")
        raise


if __name__ == "__main__":
    main()
