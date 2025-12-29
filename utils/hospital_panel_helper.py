"""
Hospital Panel Slider Helper - Multi-row slider control for Hospital healing panel.

Pattern (same as soldier_panel_slider but with dynamic row detection):
1. Detect plus button to find row position (plus_x, plus_y)
2. Calculate slider_y = plus_y + SLIDER_Y_OFFSET (fixed offset)
3. Calculate slider X range relative to plus button
4. Find slider circle X position
5. Swipe from (circle_x, slider_y) to (target_x, slider_y)
"""

import cv2
import re
import time
from pathlib import Path

# Template paths - Hospital uses SCALED (0.8x) versions of button templates
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"
SLIDER_TEMPLATE_PATH = TEMPLATE_DIR / "hospital_slider_circle_4k.png"
PLUS_TEMPLATE_PATH = TEMPLATE_DIR / "hospital_plus_button_4k.png"

# FIXED OFFSETS relative to plus button position
# Hospital: Plus at (2258, 698), Minus at (1617, 698) - SAME Y level
SLIDER_Y_OFFSET = 0        # Slider Y is SAME as plus button Y (both at 698)
MINUS_X_OFFSET = -641      # Minus is 641 pixels LEFT of plus (2258 - 1617 = 641)

# Slider X range - padding from button CENTERS to get onto slider bar
# Minus button is ~80px wide, plus button is ~77px wide (scaled templates)
SLIDER_MIN_PADDING = 60    # From minus center to slider bar start
SLIDER_MAX_PADDING = 60    # From plus center to slider bar end

# Panel search region (Y range for finding plus buttons - excludes Healing button)
# Plus buttons are in a narrow X column, scan full Y range to find all rows
PANEL_Y_START = 550
PANEL_Y_END = 1200  # Extended to cover all 3 rows (was 800, missed rows at Y=912, Y=1130)
PANEL_X_START = 2150  # Narrow to plus button column only
PANEL_X_END = 2350

# Healing button
HEALING_BUTTON_CLICK = (2148, 1477)
HEALING_TIME_REGION = (1966, 1404, 364, 146)  # x, y, w, h

# Safety limits
MAX_SAFE_HEAL_SECONDS = 5400  # 90 minutes

# Scroll region
SCROLL_CENTER_X = 1920
SCROLL_TOP_Y = 700
SCROLL_BOTTOM_Y = 1100

# Template caches
_slider_template = None
_plus_template = None


def _get_slider_template():
    global _slider_template
    if _slider_template is None:
        _slider_template = cv2.imread(str(SLIDER_TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)
    return _slider_template


def _get_plus_template():
    global _plus_template
    if _plus_template is None:
        _plus_template = cv2.imread(str(PLUS_TEMPLATE_PATH), cv2.IMREAD_GRAYSCALE)
    return _plus_template


def find_plus_buttons(frame, debug=False):
    """
    Find all plus button positions in the hospital panel.

    Returns list of (plus_x, plus_y, score) for each row found.
    """
    plus_template = _get_plus_template()
    if plus_template is None:
        if debug:
            print("  ERROR: Could not load plus button template")
        return []

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = plus_template.shape

    # Search in panel region
    search_region = gray[PANEL_Y_START:PANEL_Y_END, PANEL_X_START:PANEL_X_END]
    result = cv2.matchTemplate(search_region, plus_template, cv2.TM_SQDIFF_NORMED)

    threshold = 0.02  # Strict threshold to filter false positives
    buttons = []

    # Scan for matches
    for y in range(result.shape[0]):
        min_x = result[y].argmin()
        min_val = result[y, min_x]
        if min_val < threshold:
            full_x = PANEL_X_START + min_x + w // 2
            full_y = PANEL_Y_START + y + h // 2

            # Deduplicate within 80px Y
            is_dup = False
            for i, (bx, by, bs) in enumerate(buttons):
                if abs(by - full_y) < 80:
                    if min_val < bs:
                        buttons[i] = (full_x, full_y, min_val)
                    is_dup = True
                    break
            if not is_dup:
                buttons.append((full_x, full_y, min_val))

    buttons.sort(key=lambda b: b[1])  # Sort by Y

    if debug:
        print(f"  Found {len(buttons)} plus buttons:")
        for i, (x, y, s) in enumerate(buttons):
            print(f"    Row {i+1}: plus at ({x}, {y}), score={s:.4f}")

    return buttons


def find_slider_circle(frame, plus_x, plus_y, debug=False):
    """
    Find slider circle X position for a row.

    Args:
        frame: BGR screenshot
        plus_x: X position of the plus button (to constrain search)
        plus_y: Y position of the plus button for this row

    Returns:
        (circle_x, score) or (None, score) if not found
    """
    template = _get_slider_template()
    if template is None:
        return None, 1.0

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    h, w = template.shape

    # Calculate slider Y from plus button Y
    slider_y = plus_y + SLIDER_Y_OFFSET

    # Search ONLY between minus and plus buttons (not full panel width)
    x_start = plus_x + MINUS_X_OFFSET - 50  # A bit left of minus button
    x_end = plus_x + 50                      # A bit right of plus button
    y_start = slider_y - 50
    y_end = slider_y + 50

    search_region = gray[y_start:y_end, x_start:x_end]
    result = cv2.matchTemplate(search_region, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)

    circle_x = x_start + min_loc[0] + w // 2

    if min_val < 0.1:
        if debug:
            print(f"  Slider circle at X={circle_x}, score={min_val:.4f}")
        return circle_x, min_val

    if debug:
        print(f"  Slider circle not found (score={min_val:.4f})")
    return None, min_val


def get_slider_y(plus_y):
    """Get the slider Y coordinate for a row given its plus button Y."""
    return plus_y + SLIDER_Y_OFFSET


def get_slider_min_x(plus_x):
    """Get the slider minimum X (leftmost position) for a row."""
    return plus_x + MINUS_X_OFFSET + SLIDER_MIN_PADDING


def get_slider_max_x(plus_x):
    """Get the slider maximum X (rightmost position) for a row."""
    return plus_x - SLIDER_MAX_PADDING


def drag_slider_to_min(adb, frame, plus_x, plus_y, debug=False):
    """
    Drag slider to minimum (leftmost) position.

    Args:
        adb: ADBHelper
        frame: BGR screenshot
        plus_x, plus_y: Plus button position for this row

    Returns:
        bool: True if successful
    """
    circle_x, score = find_slider_circle(frame, plus_x, plus_y, debug=False)
    if circle_x is None:
        if debug:
            print(f"  Slider not found (score={score:.4f})")
        return False

    slider_y = get_slider_y(plus_y)
    target_x = get_slider_min_x(plus_x)

    if debug:
        print(f"  Dragging from ({circle_x}, {slider_y}) to ({target_x}, {slider_y})")

    adb.swipe(circle_x, slider_y, target_x, slider_y, duration=500)
    return True


def drag_slider_to_max(adb, frame, plus_x, plus_y, debug=False):
    """
    Drag slider to maximum (rightmost) position.
    """
    circle_x, score = find_slider_circle(frame, plus_x, plus_y, debug=False)
    if circle_x is None:
        if debug:
            print(f"  Slider not found (score={score:.4f})")
        return False

    slider_y = get_slider_y(plus_y)
    target_x = get_slider_max_x(plus_x)

    if debug:
        print(f"  Dragging from ({circle_x}, {slider_y}) to ({target_x}, {slider_y})")

    adb.swipe(circle_x, slider_y, target_x, slider_y, duration=500)
    return True


def drag_slider_to_position(adb, frame, plus_x, plus_y, target_x, debug=False):
    """
    Drag slider to a specific X position.
    """
    circle_x, score = find_slider_circle(frame, plus_x, plus_y, debug=False)
    if circle_x is None:
        if debug:
            print(f"  Slider not found (score={score:.4f})")
        return False

    slider_y = get_slider_y(plus_y)

    if debug:
        print(f"  Dragging from ({circle_x}, {slider_y}) to ({target_x}, {slider_y})")

    adb.swipe(circle_x, slider_y, target_x, slider_y, duration=500)
    return True


def calculate_slider_x(plus_x, ratio):
    """
    Calculate slider X position for a given ratio.

    Args:
        plus_x: Plus button X position
        ratio: 0.0 (min) to 1.0 (max)

    Returns:
        X coordinate
    """
    ratio = max(0.0, min(1.0, ratio))
    min_x = get_slider_min_x(plus_x)
    max_x = get_slider_max_x(plus_x)
    return min_x + int(ratio * (max_x - min_x))


def reset_all_sliders(adb, win, buttons, debug=False):
    """
    Reset all sliders to minimum.

    Args:
        adb: ADBHelper
        win: WindowsScreenshotHelper
        buttons: List of (plus_x, plus_y, score) from find_plus_buttons
    """
    if debug:
        print(f"  Resetting {len(buttons)} sliders to minimum...")

    for plus_x, plus_y, _ in buttons:
        frame = win.get_screenshot_cv2()
        drag_slider_to_min(adb, frame, plus_x, plus_y, debug=debug)
        time.sleep(0.5)


# === OCR and Healing Functions ===

def parse_healing_time(text):
    """Parse healing time text to total seconds."""
    if not text:
        return 0

    text = re.sub(r'[^\d:d ]', '', text.lower()).strip()

    days = hours = minutes = seconds = 0

    if 'd' in text:
        parts = text.split('d')
        days = int(parts[0].strip()) if parts[0].strip().isdigit() else 0
        text = parts[1].strip() if len(parts) > 1 else ''

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
    """OCR the healing button and parse time to seconds."""
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


def scroll_panel_down(adb, debug=False):
    """Scroll the hospital panel down."""
    if debug:
        print(f"  Scrolling panel down")
    adb.swipe(SCROLL_CENTER_X, SCROLL_BOTTOM_Y, SCROLL_CENTER_X, SCROLL_TOP_Y, duration=300)
