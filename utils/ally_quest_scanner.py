"""
Ally Quest Scanner - Scans all ally quests to find high-value snipe targets.

Scrolls through the Ally Quests tab, recording:
- Quest color (purple = available, gold = in progress with timer)
- Star rating (1-5 stars)
- Timer value (if in progress) or "assist" if available
- Player name

Used to identify high-value quests to snipe when timer is about to complete.

Strategy: Template match Assist button or timer clock icon (fixed X position),
then calculate color box and stars positions relative to the match.
"""

import cv2
import numpy as np
import time
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "ground_truth"

# Entry layout constants (4K resolution)
ENTRY_HEIGHT = 130  # Each entry is ~130 pixels tall
ENTRIES_VISIBLE = 4  # 4 entries visible at once

# Scroll coordinates
SCROLL_X = 1600
SCROLL_START_Y = 1300
SCROLL_END_Y = 910  # Scroll by ~390 pixels (3 entries)

# Search region for Assist buttons and timer clocks (right side of quest list)
SEARCH_X_START = 2150
SEARCH_X_END = 2500
SEARCH_Y_START = 800
SEARCH_Y_END = 1450

# Relative offsets FROM the Assist button/timer clock TOP-LEFT position
# The color box and stars are ABOVE and LEFT of the button (in the player name row)
COLOR_BOX_OFFSET_X = -60   # Left of assist button
COLOR_BOX_OFFSET_Y = -63   # Above assist button
COLOR_BOX_SIZE = 50

STARS_OFFSET_X = -10   # Slightly left of assist button (right of color box)
STARS_OFFSET_Y = -63   # Same row as color box
STARS_WIDTH = 150
STARS_HEIGHT = 50

# Color thresholds (HSV)
# Gold/Orange: H ~10-25, high S, high V
# Purple: H ~130-160, high S
GOLD_HUE_MIN, GOLD_HUE_MAX = 8, 28
PURPLE_HUE_MIN, PURPLE_HUE_MAX = 125, 165


@dataclass
class AllyQuest:
    """Represents an ally quest entry."""
    player_name: str
    color: str  # "gold" (in progress) or "purple" (available)
    stars: int
    timer_seconds: Optional[int]  # None if has Assist button
    entry_y: int  # Y position in current screen
    raw_timer: str  # Raw timer text or "assist"


def load_templates():
    """Load all templates for ally quest scanning."""
    templates = {}

    template_files = {
        "assist": "assist_button_ally_4k.png",
        "clock": "timer_clock_ally_4k.png",
        "star": "star_single_4k.png",
        "purple": "purple_box_ally_4k.png",
        "gold": "gold_box_ally_4k.png",
    }

    for name, filename in template_files.items():
        path = TEMPLATES_DIR / filename
        template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if template is not None:
            templates[name] = template
        else:
            logger.warning(f"Template not found: {path}")

    return templates


def find_all_buttons(frame_gray: np.ndarray, assist_template: np.ndarray,
                     clock_template: np.ndarray, threshold: float = 0.02) -> list[dict]:
    """
    Find all Assist buttons and timer clocks in the frame.
    Returns list of {x, y, type} where type is 'assist' or 'timer'.
    """
    buttons = []

    # Search in the right side of the quest list
    roi = frame_gray[SEARCH_Y_START:SEARCH_Y_END, SEARCH_X_START:SEARCH_X_END]

    # Find Assist buttons
    if assist_template is not None:
        result = cv2.matchTemplate(roi, assist_template, cv2.TM_SQDIFF_NORMED)
        locations = np.where(result <= threshold)
        for pt in zip(*locations[::-1]):
            x = pt[0] + SEARCH_X_START
            y = pt[1] + SEARCH_Y_START
            buttons.append({"x": x, "y": y, "type": "assist", "score": result[pt[1], pt[0]]})

    # Find timer clocks
    if clock_template is not None:
        result = cv2.matchTemplate(roi, clock_template, cv2.TM_SQDIFF_NORMED)
        locations = np.where(result <= threshold)
        for pt in zip(*locations[::-1]):
            x = pt[0] + SEARCH_X_START
            y = pt[1] + SEARCH_Y_START
            buttons.append({"x": x, "y": y, "type": "timer", "score": result[pt[1], pt[0]]})

    # Remove duplicates (buttons within 50 pixels of each other)
    filtered = []
    for btn in sorted(buttons, key=lambda b: b["score"]):
        is_dup = False
        for existing in filtered:
            if abs(btn["y"] - existing["y"]) < 50:
                is_dup = True
                break
        if not is_dup:
            filtered.append(btn)

    return sorted(filtered, key=lambda b: b["y"])


def detect_quest_color(frame_bgr: np.ndarray, button_x: int, button_y: int) -> str:
    """Detect if quest is gold (timer) or purple (assist available) based on button position."""
    # Color box is to the upper-left of the button
    x1 = button_x + COLOR_BOX_OFFSET_X
    y1 = button_y + COLOR_BOX_OFFSET_Y

    # Bounds check
    if x1 < 0 or y1 < 0 or x1 + COLOR_BOX_SIZE > frame_bgr.shape[1] or y1 + COLOR_BOX_SIZE > frame_bgr.shape[0]:
        return "unknown"

    roi = frame_bgr[y1:y1+COLOR_BOX_SIZE, x1:x1+COLOR_BOX_SIZE]

    if roi.size == 0:
        return "unknown"

    # Convert to HSV
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # Look for the most saturated pixels (the colored box, not background)
    sat_mask = hsv[:, :, 1] > 100
    if sat_mask.sum() < 100:  # Not enough saturated pixels
        return "unknown"

    # Get mean hue of saturated pixels only
    mean_hue = hsv[:, :, 0][sat_mask].mean()

    if GOLD_HUE_MIN <= mean_hue <= GOLD_HUE_MAX:
        return "gold"
    elif PURPLE_HUE_MIN <= mean_hue <= PURPLE_HUE_MAX:
        return "purple"
    else:
        return "unknown"


def count_stars(frame_gray: np.ndarray, button_x: int, button_y: int,
                star_template: np.ndarray, threshold: float = 0.08) -> int:
    """Count number of yellow stars using template matching."""
    x1 = button_x + STARS_OFFSET_X
    y1 = button_y + STARS_OFFSET_Y

    # Bounds check
    if x1 < 0 or y1 < 0 or star_template is None:
        return 0

    x2 = min(x1 + STARS_WIDTH, frame_gray.shape[1])
    y2 = min(y1 + STARS_HEIGHT, frame_gray.shape[0])

    roi = frame_gray[y1:y2, x1:x2]

    if roi.size == 0 or roi.shape[0] < star_template.shape[0] or roi.shape[1] < star_template.shape[1]:
        return 0

    # Template match for stars
    result = cv2.matchTemplate(roi, star_template, cv2.TM_SQDIFF_NORMED)

    # Find all matches below threshold
    locations = np.where(result <= threshold)
    matches = list(zip(*locations[::-1]))

    # Remove duplicates (stars are ~40px apart)
    unique = []
    for m in sorted(matches, key=lambda p: p[0]):
        if not unique or abs(m[0] - unique[-1][0]) > 30:
            unique.append(m)

    return min(5, len(unique))


def extract_entry_signature(frame_gray: np.ndarray, button_y: int) -> bytes:
    """Extract a signature from entry for duplicate detection."""
    # Use the player avatar area (left side of entry, same row as button)
    x1 = 1350
    y1 = button_y - 30

    if y1 < 0:
        return b""

    roi = frame_gray[y1:y1+80, x1:x1+100]

    if roi.size == 0:
        return b""

    # Downsample and hash
    small = cv2.resize(roi, (20, 16))
    return small.tobytes()


def scan_visible_entries(frame: np.ndarray, frame_gray: np.ndarray,
                         templates: dict) -> list[dict]:
    """Scan all visible entries on current screen using template matching."""
    entries = []

    # Find all buttons/timers
    buttons = find_all_buttons(frame_gray, templates.get("assist"), templates.get("clock"))

    for i, btn in enumerate(buttons):
        color = detect_quest_color(frame, btn["x"], btn["y"])
        stars = count_stars(frame_gray, btn["x"], btn["y"], templates.get("star"))
        signature = extract_entry_signature(frame_gray, btn["y"])

        entry = {
            "index": i,
            "button_x": btn["x"],
            "button_y": btn["y"],
            "color": color,
            "stars": stars,
            "has_assist": btn["type"] == "assist",
            "timer_seconds": None if btn["type"] == "assist" else -1,
            "signature": signature,
        }
        entries.append(entry)

    return entries


def scan_all_ally_quests(adb, win, max_scrolls: int = 10, debug: bool = False) -> list[dict]:
    """
    Scroll through all ally quests and collect info.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        max_scrolls: Maximum number of scroll iterations
        debug: Save debug screenshots

    Returns:
        List of quest dicts with color, stars, has_assist, timer info
    """
    # Load templates
    templates = load_templates()

    all_quests = []
    seen_signatures = set()
    consecutive_no_new = 0

    for scroll_iter in range(max_scrolls + 1):
        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if debug:
            debug_path = Path("screenshots/debug")
            debug_path.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(debug_path / f"ally_scan_iter{scroll_iter}.png"), frame)

        entries = scan_visible_entries(frame, frame_gray, templates)

        new_count = 0
        for entry in entries:
            sig = entry["signature"]
            if sig and sig not in seen_signatures:
                seen_signatures.add(sig)
                all_quests.append(entry)
                new_count += 1

                if debug:
                    logger.info(f"Entry {len(all_quests)}: color={entry['color']}, "
                               f"stars={entry['stars']}, assist={entry['has_assist']}")

        logger.info(f"Scroll {scroll_iter}: found {new_count} new entries, {len(all_quests)} total")

        # Check if we've reached the end
        if new_count == 0:
            consecutive_no_new += 1
            if consecutive_no_new >= 2:
                logger.info("Reached end of list (no new entries for 2 scrolls)")
                break
        else:
            consecutive_no_new = 0

        # Scroll down for next iteration (except on potential last)
        if scroll_iter < max_scrolls:
            adb.swipe(SCROLL_X, SCROLL_START_Y, SCROLL_X, SCROLL_END_Y, duration=400)
            time.sleep(0.5)

    return all_quests


def find_snipe_targets(quests: list[dict], min_stars: int = 4) -> list[dict]:
    """Find high-value quests with timers that are worth sniping."""
    targets = []

    for quest in quests:
        # Look for gold (timer) quests with high stars
        if quest["color"] == "gold" and quest["stars"] >= min_stars:
            targets.append(quest)

    # Sort by stars (highest first)
    targets.sort(key=lambda x: x["stars"], reverse=True)

    return targets


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper
    from utils.view_state_detector import go_to_town

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    # Navigate to tavern ally quests
    print("Navigating to Tavern...")
    go_to_town(adb)
    time.sleep(0.5)

    print("Opening Tavern...")
    adb.tap(80, 1220)
    time.sleep(1.5)

    print("Clicking Ally Quests tab...")
    adb.tap(2200, 755)
    time.sleep(1.0)

    # Scroll to top first
    print("Scrolling to top...")
    for _ in range(5):
        adb.swipe(SCROLL_X, 900, SCROLL_X, 1500, duration=300)
        time.sleep(0.3)
    time.sleep(0.5)

    # Scan all quests
    print("\nScanning all ally quests...")
    quests = scan_all_ally_quests(adb, win, debug=True)

    print(f"\n=== SCAN RESULTS ===")
    print(f"Total quests found: {len(quests)}")

    # Summary by type
    gold_count = sum(1 for q in quests if q["color"] == "gold")
    purple_count = sum(1 for q in quests if q["color"] == "purple")
    print(f"Gold (timer): {gold_count}")
    print(f"Purple (assist): {purple_count}")

    # High value targets
    targets = find_snipe_targets(quests, min_stars=4)
    print(f"\nHigh-value snipe targets (4+ stars with timer): {len(targets)}")
    for t in targets:
        print(f"  - {t['stars']} stars, color={t['color']}")
