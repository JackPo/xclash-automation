"""
Training Slider Helper - Automates soldier training quantity selection.

Uses slider drag + OCR to set training time to a target duration.

Flow:
1. Read full training time from train button (slider at max)
2. Calculate target slider position based on ratio
3. Drag slider to calculated position
4. Validate with OCR and fine-tune with +/- buttons
"""

import time
import cv2
import numpy as np
from pathlib import Path

# Fixed UI coordinates (4K resolution, from Gemini detection)
# All coordinates are for the barracks training panel

# Train button - contains time text at bottom
TRAIN_BUTTON_POS = (1969, 1399)  # Top-left
TRAIN_BUTTON_SIZE = (373, 130)   # width, height
TRAIN_BUTTON_CENTER = (2155, 1464)

# Time region within train button (bottom portion shows "HH:MM:SS")
# Relative to train button top-left
TRAIN_TIME_REGION = (50, 80, 280, 45)  # x_offset, y_offset, width, height
# Absolute position: (2019, 1479) to (2299, 1524)

# Plus/Minus buttons for fine-tuning
PLUS_BUTTON_CENTER = (2207, 1179)
MINUS_BUTTON_CENTER = (1526, 1177)

# Slider bar parameters - VISUAL coordinates (from Windows screenshot)
# These are the circle center positions seen in screenshots
SLIDER_Y = 1170  # Y center of slider (circle center Y)
VISUAL_SLIDER_LEFT_X = 1600  # Circle center at MIN (leftmost) in screenshot
VISUAL_SLIDER_RIGHT_X = 2133  # Circle center at MAX (rightmost) in screenshot
VISUAL_SLIDER_WIDTH = VISUAL_SLIDER_RIGHT_X - VISUAL_SLIDER_LEFT_X  # 533 pixels

# ADB to Visual coordinate calibration
# IMPORTANT: Empirical testing (2024-12-02) shows ADB and Visual coords are 1:1
# for this slider. The previous calibration formula was WRONG.
# Using direct visual coordinates works perfectly.
ADB_SCALE = 1.0  # 1:1 mapping - visual coords = ADB coords
ADB_OFFSET = 0.0

# Slider endpoints - use VISUAL coords directly (they work as ADB coords too)
SLIDER_LEFT_X = VISUAL_SLIDER_LEFT_X   # 1600
SLIDER_RIGHT_X = VISUAL_SLIDER_RIGHT_X  # 2133
SLIDER_WIDTH = VISUAL_SLIDER_WIDTH      # 533 pixels

# Quantity number region (above train button)
QUANTITY_REGION = (2050, 1280, 200, 60)  # x, y, w, h


def visual_to_adb_x(visual_x: int) -> int:
    """Convert visual X coordinate (from screenshot) to ADB X coordinate.

    Args:
        visual_x: X coordinate from Windows screenshot

    Returns:
        Corresponding ADB X coordinate for swipe/tap operations
    """
    return int((visual_x - ADB_OFFSET) / ADB_SCALE)


def adb_to_visual_x(adb_x: int) -> int:
    """Convert ADB X coordinate to visual X coordinate.

    Args:
        adb_x: ADB X coordinate used in swipe/tap operations

    Returns:
        Expected visual X coordinate in screenshot
    """
    return int(ADB_SCALE * adb_x + ADB_OFFSET)


def parse_time_string(time_str: str) -> int:
    """Parse 'HH:MM:SS' or 'H:MM:SS' to seconds.

    Args:
        time_str: Time string like "17:44:23" or "4:30:00"

    Returns:
        Total seconds, or 0 if parsing fails
    """
    try:
        # Clean up the string
        time_str = time_str.strip()
        parts = time_str.split(':')

        if len(parts) == 3:
            h, m, s = map(int, parts)
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:
            m, s = map(int, parts)
            return m * 60 + s
    except (ValueError, AttributeError):
        pass

    return 0


def seconds_to_time_string(seconds: int) -> str:
    """Convert seconds to 'H:MM:SS' format.

    Args:
        seconds: Total seconds

    Returns:
        Formatted time string
    """
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}:{m:02d}:{s:02d}"


def get_training_time_region(frame):
    """Extract the time region from train button for OCR.

    Args:
        frame: BGR numpy array screenshot

    Returns:
        Cropped BGR image of time region
    """
    x = TRAIN_BUTTON_POS[0] + TRAIN_TIME_REGION[0]
    y = TRAIN_BUTTON_POS[1] + TRAIN_TIME_REGION[1]
    w = TRAIN_TIME_REGION[2]
    h = TRAIN_TIME_REGION[3]

    return frame[y:y+h, x:x+w].copy()


def get_training_time(frame, ocr, debug=False) -> int:
    """OCR the training time from the train button.

    Args:
        frame: BGR numpy array screenshot
        ocr: QwenOCR instance
        debug: Enable debug output

    Returns:
        Training time in seconds, or 0 if OCR fails
    """
    # Get time region
    time_crop = get_training_time_region(frame)

    if debug:
        cv2.imwrite('debug_train_time_crop.png', time_crop)

    # Use Qwen OCR to extract text
    # The time format is "HH:MM:SS" in white/yellow text
    try:
        # Extract as general text since it contains colons
        time_str = ocr.extract_text(time_crop)

        if debug:
            print(f"  OCR raw: '{time_str}'")

        # Parse the time
        seconds = parse_time_string(time_str)

        if debug:
            print(f"  Parsed: {seconds} seconds ({seconds_to_time_string(seconds)})")

        return seconds
    except Exception as e:
        if debug:
            print(f"  OCR error: {e}")
        return 0


def calculate_slider_position(target_seconds: int, full_seconds: int) -> int:
    """Calculate ADB X coordinate for target training time.

    Uses VISUAL coordinates for calculation (more intuitive), then converts
    to ADB coordinates for the actual swipe operation.

    Args:
        target_seconds: Desired training time in seconds
        full_seconds: Full training time (slider at max) in seconds

    Returns:
        ADB X coordinate to drag slider to
    """
    if full_seconds <= 0:
        return SLIDER_RIGHT_X  # Default to max if no data

    # Clamp ratio to [0, 1]
    ratio = min(1.0, max(0.0, target_seconds / full_seconds))

    # Calculate target VISUAL position (where we want the circle to appear)
    target_visual_x = VISUAL_SLIDER_LEFT_X + int(ratio * VISUAL_SLIDER_WIDTH)

    # Convert to ADB coordinate
    target_adb_x = visual_to_adb_x(target_visual_x)

    return target_adb_x


def find_slider_circle(frame, debug=False) -> int:
    """Find current slider handle position using template matching.

    The slider handle is a circular knob that can be anywhere
    between SLIDER_LEFT_X and SLIDER_RIGHT_X at SLIDER_Y.

    Args:
        frame: BGR numpy array screenshot
        debug: Enable debug output

    Returns:
        X coordinate of slider handle center, or -1 if not found
    """
    # Load slider circle template
    template_path = Path(__file__).parent.parent / "templates" / "ground_truth" / "slider_circle_4k.png"

    if not template_path.exists():
        if debug:
            print(f"  Slider template not found: {template_path}")
        # Fallback: assume slider is in the middle
        return (SLIDER_LEFT_X + SLIDER_RIGHT_X) // 2

    template = cv2.imread(str(template_path))
    if template is None:
        return (SLIDER_LEFT_X + SLIDER_RIGHT_X) // 2

    # Search in horizontal band around slider Y
    search_y_start = SLIDER_Y - 50
    search_y_end = SLIDER_Y + 50
    search_x_start = SLIDER_LEFT_X - 50
    search_x_end = SLIDER_RIGHT_X + 50

    # Crop search region
    search_region = frame[search_y_start:search_y_end, search_x_start:search_x_end]

    if debug:
        cv2.imwrite('debug_slider_search.png', search_region)

    # Template match
    result = cv2.matchTemplate(search_region, template, cv2.TM_SQDIFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if debug:
        print(f"  Slider match score: {min_val:.4f}")

    if min_val < 0.1:  # Good match
        # Convert to full image coordinates
        template_h, template_w = template.shape[:2]
        slider_x = search_x_start + min_loc[0] + template_w // 2
        return slider_x

    # Fallback
    return (SLIDER_LEFT_X + SLIDER_RIGHT_X) // 2


def drag_slider_to_position(adb, win, target_x: int, debug=False):
    """Drag slider from current position to target X.

    CRITICAL: Must find the circle first via template matching, then drag FROM
    the circle's actual position. Swiping from arbitrary positions does NOT work.

    Note: Visual coords and ADB coords are 1:1 for this slider (empirically verified).

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (needed to find circle)
        target_x: Target X coordinate (visual = ADB for this slider)
        debug: Enable debug output
    """
    # Take screenshot and find the circle's current position
    frame = win.get_screenshot_cv2()
    circle_x = find_slider_circle(frame, debug=debug)

    if circle_x < 0:
        if debug:
            print("  ERROR: Could not find slider circle")
        return

    if debug:
        print(f"  Circle found at X={circle_x}")
        print(f"  Dragging: ({circle_x}, {SLIDER_Y}) -> ({target_x}, {SLIDER_Y})")

    # Swipe FROM the circle's actual position TO the target
    # Visual coords work directly as ADB coords (1:1 mapping verified)
    adb.swipe(circle_x, SLIDER_Y, target_x, SLIDER_Y, duration=500)
    time.sleep(0.3)


def set_training_quantity(adb, win, target_hours: float, debug=False) -> bool:
    """Set soldier training quantity to achieve approximately target_hours of training.

    This function:
    1. Moves slider to max to read full training time
    2. Calculates proportional position for target time
    3. Drags slider to calculated position
    4. Validates with OCR and fine-tunes with +/- buttons

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        target_hours: Target training time in hours (e.g., 4.0)
        debug: Enable debug logging

    Returns:
        bool: True if successfully set to target (within tolerance)
    """
    from utils.ocr_client import OCRClient, ensure_ocr_server

    target_seconds = int(target_hours * 3600)
    tolerance_seconds = 300  # 5 minute tolerance

    if debug:
        print(f"Setting training quantity for {target_hours} hours ({seconds_to_time_string(target_seconds)})")

    # Ensure OCR server is running (auto-start if not)
    if not ensure_ocr_server(auto_start=True):
        if debug:
            print("  ERROR: OCR server not available")
        return False

    ocr = OCRClient()

    # Step 1: Move slider to max to read full training time
    if debug:
        print("Step 1: Reading full training time (slider at max)...")

    # First drag slider to MIN (far left), then to MAX (far right) to ensure we're at max
    # This handles case where slider starts in middle
    adb.swipe(SLIDER_RIGHT_X, SLIDER_Y, SLIDER_LEFT_X, SLIDER_Y, duration=300)  # Go to min first
    time.sleep(0.3)
    adb.swipe(SLIDER_LEFT_X, SLIDER_Y, SLIDER_RIGHT_X, SLIDER_Y, duration=300)  # Then to max
    time.sleep(0.5)

    # Take screenshot and read time (do it twice for reliability)
    frame = win.get_screenshot_cv2()
    full_seconds_1 = get_training_time(frame, ocr, debug=debug)

    time.sleep(0.3)
    frame = win.get_screenshot_cv2()
    full_seconds_2 = get_training_time(frame, ocr, debug=debug)

    # Use the reading that seems more valid
    full_seconds = max(full_seconds_1, full_seconds_2)

    if full_seconds == 0:
        if debug:
            print("  ERROR: Could not read full training time")
        return False

    if debug:
        print(f"  Full training time: {seconds_to_time_string(full_seconds)}")

    # Check if target exceeds full time
    if target_seconds >= full_seconds:
        if debug:
            print(f"  Target ({target_hours}h) >= full time, keeping slider at max")
        return True

    # Step 2: Calculate target slider position
    target_x = calculate_slider_position(target_seconds, full_seconds)

    if debug:
        ratio = target_seconds / full_seconds
        print(f"Step 2: Target position X={target_x} (ratio={ratio:.2%})")

    # Step 3: Drag slider to target position
    if debug:
        print("Step 3: Dragging slider to target...")

    # Find circle and drag from its current position to target
    drag_slider_to_position(adb, win, target_x, debug=debug)
    time.sleep(0.5)

    # Step 4: Validate and fine-tune
    if debug:
        print("Step 4: Validating and fine-tuning...")

    for attempt in range(30):  # More attempts for fine-tuning
        frame = win.get_screenshot_cv2()
        actual_seconds = get_training_time(frame, ocr, debug=debug)

        if actual_seconds == 0:
            if debug:
                print(f"  Attempt {attempt+1}: OCR failed, skipping")
            continue

        diff = actual_seconds - target_seconds

        if debug:
            print(f"  Attempt {attempt+1}: actual={seconds_to_time_string(actual_seconds)}, diff={diff}s")

        if abs(diff) <= tolerance_seconds:
            if debug:
                print(f"  SUCCESS: Within tolerance ({abs(diff)}s <= {tolerance_seconds}s)")
            return True

        # Fine-tune with +/- buttons
        if diff > 0:
            # Training time too high, reduce quantity
            adb.tap(MINUS_BUTTON_CENTER[0], MINUS_BUTTON_CENTER[1])
            if debug:
                print("  Clicked minus")
        else:
            # Training time too low, increase quantity
            adb.tap(PLUS_BUTTON_CENTER[0], PLUS_BUTTON_CENTER[1])
            if debug:
                print("  Clicked plus")

        time.sleep(0.3)

    if debug:
        print("  WARNING: Could not reach target within 10 attempts")

    return False


# For testing
if __name__ == "__main__":
    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    print("Testing training slider helper...")
    print("Make sure training panel is open with a soldier level selected!\n")

    # Test setting to 4 hours
    success = set_training_quantity(adb, win, target_hours=4.0, debug=True)
    print(f"\nResult: {'SUCCESS' if success else 'FAILED'}")
