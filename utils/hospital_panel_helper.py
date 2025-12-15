"""
Hospital Panel Slider Helper - Multi-row slider control for Hospital healing panel.

Adapts the proven soldier_panel_slider.py pattern for multiple rows.
Each row has its own Y position but same X range for slider.

The hospital panel has multiple soldier type rows, each with:
- Slider circle that moves along X axis
- Same X range for all rows (MIN to MAX)
- Different Y position per row

Uses same template: slider_circle_4k.png
"""

import cv2
import re
import time
from pathlib import Path

# Template path (same as soldier_panel_slider)
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "ground_truth" / "slider_circle_4k.png"
PLUS_TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "ground_truth" / "plus_button_4k.png"

# Slider X range (same for all rows)
# When at MIN, circle is at left end of green bar (~1720)
# When at MAX, circle is at right end of green bar (~2180)
SLIDER_MIN_X = 1720   # Circle center at MIN (leftmost)
SLIDER_MAX_X = 2180   # Circle center at MAX (rightmost)

# Search X range for template matching
# Use full range but require X >= SLIDER_MIN_X to filter false matches
SEARCH_X_START = 1700  # Just before MIN to catch edge cases
SEARCH_X_END = 2220

# Plus button search region (to find rows)
PLUS_SEARCH_X_START = 2200
PLUS_SEARCH_X_END = 2350
PANEL_Y_START = 550
PANEL_Y_END = 1250

# Healing button
HEALING_BUTTON_CLICK = (2148, 1477)
HEALING_TIME_REGION = (1966, 1404, 364, 146)  # x, y, w, h

# Template caches
_slider_template = None
_plus_template = None


def _get_slider_template():
    """Load and cache slider circle template."""
    global _slider_template
    if _slider_template is None:
        _slider_template = cv2.imread(str(TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)
    return _slider_template


def _get_plus_template():
    """Load and cache plus button template."""
    global _plus_template
    if _plus_template is None:
        _plus_template = cv2.imread(str(PLUS_TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)
    return _plus_template


def find_soldier_rows(frame, debug=False):
    """
    Find all row Y positions by detecting plus buttons.

    Args:
        frame: BGR screenshot (4K)
        debug: Enable debug output

    Returns:
        List of Y positions sorted top to bottom
    """
    template = _get_plus_template()
    if template is None:
        if debug:
            print("  ERROR: Could not load plus button template")
        return []

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = template.shape[:2]

    # Search in plus button region
    search_region = gray[PANEL_Y_START:PANEL_Y_END, PLUS_SEARCH_X_START:PLUS_SEARCH_X_END]
    result = cv2.matchTemplate(search_region, template, cv2.TM_SQDIFF_NORMED)

    threshold = 0.05
    rows = []

    # Scan each Y line for best match
    for y in range(result.shape[0]):
        min_x = result[y].argmin()
        min_val = result[y, min_x]
        if min_val < threshold:
            full_y = PANEL_Y_START + y + h // 2

            # Deduplicate within 80px Y
            is_dup = False
            for ry, rs in rows:
                if abs(ry - full_y) < 80:
                    if min_val < rs:
                        rows.remove((ry, rs))
                    else:
                        is_dup = True
                    break
            if not is_dup:
                rows.append((full_y, min_val))

    rows.sort(key=lambda r: r[0])
    result_y = [r[0] for r in rows]

    if debug:
        print(f"  Found {len(result_y)} soldier rows at Y: {result_y}")

    return result_y


def find_slider_circle_at_y(frame, row_y, debug=False):
    """
    Find slider circle X position at a specific row Y.

    Follows same pattern as soldier_panel_slider.find_slider_circle()
    but with parameterized Y.

    Args:
        frame: BGR screenshot (4K)
        row_y: Y position of the row
        debug: Enable debug output

    Returns:
        (x, score) tuple, or (None, score) if not found
    """
    template = _get_slider_template()
    if template is None:
        return None, 1.0

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    h, w = template.shape[:2]

    # Search band around row_y
    y_start = row_y - 50
    y_end = row_y + 50

    search_region = gray[y_start:y_end, SEARCH_X_START:SEARCH_X_END]
    result = cv2.matchTemplate(search_region, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)

    x = SEARCH_X_START + min_loc[0] + w // 2

    # Validate: X must be within valid slider range
    # This filters out false matches with minus button (X ~1679)
    if min_val < 0.1 and x >= SLIDER_MIN_X - 20:
        if debug:
            print(f"  Row Y={row_y}: slider at X={x}, score={min_val:.4f}")
        return x, min_val

    if debug:
        print(f"  Row Y={row_y}: slider not found (x={x}, score={min_val:.4f})")
    return None, min_val


def drag_slider_to_min_at_y(adb, frame, row_y, debug=False):
    """
    Drag slider at row_y to minimum (leftmost) position.

    Args:
        adb: ADBHelper
        frame: BGR screenshot
        row_y: Y position of the row
        debug: Enable debug output

    Returns:
        bool: True if successful
    """
    circle_x, score = find_slider_circle_at_y(frame, row_y, debug=False)
    if circle_x is None:
        if debug:
            print(f"  Row Y={row_y}: slider not found (score={score:.4f})")
        return False

    if debug:
        print(f"  Row Y={row_y}: dragging from X={circle_x} to min X={SLIDER_MIN_X}")

    adb.swipe(circle_x, row_y, SLIDER_MIN_X, row_y, duration=500)
    return True


def drag_slider_to_max_at_y(adb, frame, row_y, debug=False):
    """
    Drag slider at row_y to maximum (rightmost) position.

    Args:
        adb: ADBHelper
        frame: BGR screenshot
        row_y: Y position of the row
        debug: Enable debug output

    Returns:
        bool: True if successful
    """
    circle_x, score = find_slider_circle_at_y(frame, row_y, debug=False)
    if circle_x is None:
        if debug:
            print(f"  Row Y={row_y}: slider not found (score={score:.4f})")
        return False

    if debug:
        print(f"  Row Y={row_y}: dragging from X={circle_x} to max X={SLIDER_MAX_X}")

    adb.swipe(circle_x, row_y, SLIDER_MAX_X, row_y, duration=500)
    return True


def drag_slider_to_position_at_y(adb, frame, row_y, target_x, debug=False):
    """
    Drag slider at row_y to a specific X position.

    Args:
        adb: ADBHelper
        frame: BGR screenshot
        row_y: Y position of the row
        target_x: Target X coordinate
        debug: Enable debug output

    Returns:
        bool: True if successful
    """
    circle_x, score = find_slider_circle_at_y(frame, row_y, debug=False)
    if circle_x is None:
        if debug:
            print(f"  Row Y={row_y}: slider not found (score={score:.4f})")
        return False

    if debug:
        print(f"  Row Y={row_y}: dragging from X={circle_x} to X={target_x}")

    adb.swipe(circle_x, row_y, target_x, row_y, duration=500)
    return True


def calculate_slider_x(ratio):
    """
    Calculate slider X position for a given ratio.

    Args:
        ratio: 0.0 (min) to 1.0 (max)

    Returns:
        X coordinate
    """
    ratio = max(0.0, min(1.0, ratio))
    return SLIDER_MIN_X + int(ratio * (SLIDER_MAX_X - SLIDER_MIN_X))


def reset_all_sliders(adb, win, rows, debug=False):
    """
    Reset all sliders to minimum (zero soldiers selected).

    Args:
        adb: ADBHelper
        win: WindowsScreenshotHelper
        rows: List of row Y positions
        debug: Enable debug output
    """
    if debug:
        print(f"  Resetting {len(rows)} sliders to minimum...")

    for row_y in rows:
        frame = win.get_screenshot_cv2()
        drag_slider_to_min_at_y(adb, frame, row_y, debug=debug)
        time.sleep(0.5)


def parse_healing_time(text):
    """
    Parse healing time text to total seconds.

    Formats:
    - "1d 02:34:52" -> 1 day + 2h 34m 52s
    - "02:34:52" -> 2h 34m 52s
    - "34:52" -> 34m 52s

    Returns:
        Total seconds, or 0 if parsing fails
    """
    if not text:
        return 0

    # Remove emoji and extra text
    text = re.sub(r'[^\d:d ]', '', text.lower()).strip()

    days = 0
    hours = 0
    minutes = 0
    seconds = 0

    # Check for days
    if 'd' in text:
        parts = text.split('d')
        days = int(parts[0].strip()) if parts[0].strip().isdigit() else 0
        text = parts[1].strip() if len(parts) > 1 else ''

    # Parse time portion
    if text:
        time_parts = text.split(':')
        time_parts = [int(p) for p in time_parts if p.isdigit()]

        if len(time_parts) == 3:
            hours, minutes, seconds = time_parts
        elif len(time_parts) == 2:
            minutes, seconds = time_parts
        elif len(time_parts) == 1:
            seconds = time_parts[0]

    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def get_healing_time_seconds(frame, ocr_client, debug=False):
    """
    OCR the healing button and parse time to seconds.

    Args:
        frame: BGR screenshot
        ocr_client: OCRClient instance
        debug: Enable debug output

    Returns:
        Total seconds, or 0 if parsing fails
    """
    x, y, w, h = HEALING_TIME_REGION
    roi = frame[y:y+h, x:x+w]

    text = ocr_client.extract_text(roi)

    if debug:
        safe_text = text.encode('ascii', 'replace').decode('ascii')
        print(f"  Healing OCR: '{safe_text}'")

    seconds = parse_healing_time(text)

    if debug:
        hrs = seconds // 3600
        mins = (seconds % 3600) // 60
        secs = seconds % 60
        print(f"  Parsed: {hrs}h {mins}m {secs}s ({seconds} total seconds)")

    return seconds


def click_healing_button(adb, debug=False):
    """Click the Healing button."""
    x, y = HEALING_BUTTON_CLICK
    if debug:
        print(f"  Clicking Healing button at ({x}, {y})")
    adb.tap(x, y)
