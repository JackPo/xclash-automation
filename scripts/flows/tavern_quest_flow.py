"""
Tavern Quest Flow - claim, scan, dispatch, and ally-assist workflows.

Key dispatch rules:
- Dispatch start window is time-gated in Pacific time:
  `TAVERN_QUEST_START_*` until `TAVERN_SERVER_RESET_HOUR`.
- A successful dispatch records `last_dispatch` in scheduler state and enforces
  a minimum gap (`TAVERN_MIN_DISPATCH_GAP_MINUTES`) before the next dispatch.
- On configured VS days (`VS_QUESTION_MARK_SKIP_DAYS`), question-mark quests
  are skipped and only gold-scroll dispatches are considered.
- Reward-template matching is constrained to quest-row Y range to avoid header
  false positives; Go taps use fixed Go-column X with detected row Y.

All matching uses COLOR images (no grayscale).
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta
import json
from typing import TYPE_CHECKING, Any

_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import cv2
import numpy as np
import numpy.typing as npt
import time
import logging

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.template_matcher import match_template

# Debug screenshot helper
DEBUG_DIR = Path(__file__).parent.parent.parent / "screenshots" / "debug"

def _save_debug(frame: npt.NDArray[Any], step: str) -> None:
    """Save debug screenshot with timestamp and step name."""
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S_%f")[:-3]
    path = DEBUG_DIR / f"tavern_{ts}_{step}.png"
    cv2.imwrite(str(path), frame)
    logger.info(f"[TAVERN DEBUG] Saved: {path.name}")

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper
    from utils.scheduler import DaemonScheduler
    from utils.ocr_client import OCRClient

from utils.return_to_base_view import return_to_base_view

logger = logging.getLogger(__name__)

# Timing constants
CLAIM_POLL_INTERVAL = 0.5  # seconds between polls
PRE_ARRIVAL_BUFFER = 5     # seconds before completion to navigate to tavern
SHORT_TIMER_THRESHOLD = 30 # seconds - timer considered "about to complete"
CLAIM_SHORT_WAIT_THRESHOLD_SECONDS = 10  # Wait/poll only when OCR timer <= this value

# Template paths (absolute paths from project root)
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "ground_truth"
MY_QUESTS_ACTIVE_TEMPLATE = str(TEMPLATE_DIR / "tavern_my_quests_active_4k.png")
ALLY_QUESTS_ACTIVE_TEMPLATE = str(TEMPLATE_DIR / "tavern_ally_quests_active_4k.png")
CLAIM_BUTTON_TEMPLATE = str(TEMPLATE_DIR / "claim_button_tavern_4k.png")
GOLD_SCROLL_TEMPLATE = str(TEMPLATE_DIR / "gold_scroll_4k.png")
GOLD_SCROLL_MASK = str(TEMPLATE_DIR / "gold_scroll_mask_4k.png")
QUESTION_MARK_TILE_TEMPLATE = str(TEMPLATE_DIR / "quest_question_tile_4k.png")

# Bounty Quest dialog templates
BOUNTY_QUEST_TITLE_TEMPLATE = str(TEMPLATE_DIR / "bounty_quest_title_4k.png")
AUTO_DISPATCH_BUTTON_TEMPLATE = str(TEMPLATE_DIR / "auto_dispatch_button_4k.png")
PROCEED_BUTTON_TEMPLATE = str(TEMPLATE_DIR / "proceed_button_4k.png")

# Bounty Quest button click positions (center of buttons)
AUTO_DISPATCH_CLICK = (1670, 1770)
PROCEED_CLICK = (2150, 1770)
BOUNTY_QUEST_THRESHOLD = 0.02

# Quest timer detection
QUEST_CLOCK_ICON_TEMPLATE = f"{TEMPLATE_DIR}/quest_clock_icon_4k.png"
QUEST_CLOCK_THRESHOLD = 0.01  # Very strict - only real clocks
TIMER_OFFSET_X = 60  # Timer text starts 60px right of clock icon
TIMER_WIDTH = 160
TIMER_HEIGHT = 60

# Tab regions and click positions (4K)
MY_QUESTS_TAB_REGION = (1505, 723, 299, 65)  # x, y, w, h
ALLY_QUESTS_TAB_REGION = (2054, 723, 299, 65)
MY_QUESTS_CLICK = (1654, 755)
ALLY_QUESTS_CLICK = (2203, 755)

# Claim button detection - column restricted
CLAIM_X_START = 2100
CLAIM_X_END = 2500
CLAIM_THRESHOLD = 0.02  # Strict threshold to avoid false positives

# Gold scroll and Go button detection (masked matching + color gate)
GOLD_SCROLL_THRESHOLD = 0.92  # TM_CCORR_NORMED with mask - higher is better
GO_BUTTON_CLICK_X = 2320  # Fixed Go button column center in 4K Tavern list
# Restrict reward-template matching to quest list rows only.
# Prevents false positives from similar icons in top/header UI.
QUEST_LIST_Y_MIN = 820
QUEST_LIST_Y_MAX = 1850
# Gold scroll icon should be in the left quest-icon column (not reward/Go area).
QUEST_ICON_X_MIN = 1300
QUEST_ICON_X_MAX = 1750
# Gold icon color gate to reject purple/non-gold scroll rows.
GOLD_ICON_ORANGE_MIN_RATIO = 0.42
GOLD_ICON_PURPLE_MAX_RATIO = 0.20
# Go-button presence gate (blue button in Go column on same row)
GO_BUTTON_BLUE_MIN_RATIO = 0.15
GO_BUTTON_BLUE_MIN_COMPONENT_AREA = 3000
GO_BUTTON_ROI_HALF_WIDTH = 150
GO_BUTTON_ROI_HALF_HEIGHT = 60

# Question mark tile detection
QUESTION_MARK_THRESHOLD = 0.02  # Similar to gold scroll

# Scroll parameters - grab center and drag up to scroll down
SCROLL_START_Y = 1400  # Center of quest list
SCROLL_END_Y = 800     # Drag to top to scroll content down (reveal more below)
SCROLL_X = 1920        # Center X
SCROLL_DURATION = 500  # ms - longer for smoother scroll


def load_template_color(path: str) -> npt.NDArray[Any]:
    """Load template as COLOR (BGR)."""
    template = cv2.imread(path, cv2.IMREAD_COLOR)
    if template is None:
        raise FileNotFoundError(f"Template not found: {path}")
    return template


# =============================================================================
# Time and VS Day Helpers
# =============================================================================

def _is_after_quest_start_time() -> bool:
    """
    Check if current time is in the allowed quest start window.

    Allowed window: configured tavern start time (TAVERN_QUEST_START_*) until
    server reset (TAVERN_SERVER_RESET_HOUR, Pacific time).

    Blocked window: from server reset until the next configured start time.
    """
    try:
        import pytz
        from config import TAVERN_QUEST_START_HOUR, TAVERN_QUEST_START_MINUTE, TAVERN_SERVER_RESET_HOUR
    except ImportError:
        # Fallback defaults if config not available
        TAVERN_QUEST_START_HOUR = 1
        TAVERN_QUEST_START_MINUTE = 0
        TAVERN_SERVER_RESET_HOUR = 18

    try:
        pacific = pytz.timezone('America/Los_Angeles')
        now = datetime.now(pacific)

        # Blocked window: from server reset to quest start time.
        # Handle overnight wrap (e.g., reset at 18:00, start at 01:00 next day).
        if TAVERN_SERVER_RESET_HOUR > TAVERN_QUEST_START_HOUR:
            # Overnight: blocked from reset to midnight OR midnight to start
            if now.hour >= TAVERN_SERVER_RESET_HOUR:
                return False  # After reset, before midnight
            if now.hour < TAVERN_QUEST_START_HOUR:
                return False  # After midnight, before start hour
            if now.hour == TAVERN_QUEST_START_HOUR and now.minute < TAVERN_QUEST_START_MINUTE:
                return False  # Start hour but before start minute
        else:
            # Same day: blocked from reset to start (original logic)
            if TAVERN_SERVER_RESET_HOUR <= now.hour < TAVERN_QUEST_START_HOUR:
                return False
            if now.hour == TAVERN_QUEST_START_HOUR and now.minute < TAVERN_QUEST_START_MINUTE:
                return False

        return True
    except Exception as e:
        logger.warning(f"Time check failed: {e}, defaulting to True")
        return True  # Fail open - allow quest starts if time check fails


def _should_start_question_mark_quests() -> bool:
    """
    Check if question mark quests should be started on this VS day.

    Configured skip days are defined in `VS_QUESTION_MARK_SKIP_DAYS`
    (currently Day 3 and Day 6).
    """
    try:
        from utils.arms_race import get_arms_race_status
        from config import VS_QUESTION_MARK_SKIP_DAYS
    except ImportError:
        # Fallback if imports fail - allow question mark quests
        return True

    try:
        status = get_arms_race_status()
        current_day = status.get('day', 0)

        if current_day in VS_QUESTION_MARK_SKIP_DAYS:
            logger.info(f"Day {current_day} is in VS_QUESTION_MARK_SKIP_DAYS - skipping question mark quests")
            return False
        return True
    except Exception as e:
        logger.warning(f"VS day check failed: {e}, defaulting to True")
        return True  # Fail open - allow question mark quests if check fails


# =============================================================================
# Schedule Helpers (delegating to unified scheduler)
# =============================================================================

def _get_scheduler() -> DaemonScheduler:
    """Get the unified scheduler instance."""
    from utils.scheduler import get_scheduler
    return get_scheduler()


def save_quest_schedule(completions: list[datetime]) -> None:
    """Save quest completion times to unified scheduler."""
    scheduler = _get_scheduler()
    scheduler.set_tavern_completions(completions)


def load_quest_schedule() -> list[datetime]:
    """Load quest completion times from unified scheduler."""
    scheduler = _get_scheduler()
    return scheduler.get_tavern_completions()


def get_next_completion() -> datetime | None:
    """Get the next upcoming completion time, or None if no completions scheduled."""
    scheduler = _get_scheduler()
    return scheduler.get_next_tavern_completion()


def is_completion_imminent(buffer_seconds: int = PRE_ARRIVAL_BUFFER) -> bool:
    """Check if any quest completion is within buffer_seconds."""
    scheduler = _get_scheduler()
    return scheduler.is_tavern_completion_imminent(buffer_seconds)


def parse_timer_string(timer_str: str) -> int | None:
    """
    Parse timer string like "01:57:17" into total seconds.
    Returns None if parsing fails.
    """
    if not timer_str:
        return None

    # Clean up the string
    timer_str = timer_str.strip()

    # Try HH:MM:SS format
    parts = timer_str.split(":")
    if len(parts) == 3:
        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        except ValueError:
            pass

    # Try MM:SS format
    if len(parts) == 2:
        try:
            minutes = int(parts[0])
            seconds = int(parts[1])
            return minutes * 60 + seconds
        except ValueError:
            pass

    return None


def find_quest_timers(frame: npt.NDArray[Any], ocr: OCRClient | None = None) -> list[dict[str, Any]]:
    """
    Find all quest timers in the current view (COLOR matching).

    Returns list of dicts with:
    - clock_pos: (x, y) position of clock icon
    - timer_region: (x, y, w, h) region of timer text
    - timer_text: OCR'd timer string (e.g., "01:57:17")
    - seconds: parsed time in seconds (or None if parsing failed)
    """
    clock_template = load_template_color(QUEST_CLOCK_ICON_TEMPLATE)
    result = cv2.matchTemplate(frame, clock_template, cv2.TM_SQDIFF_NORMED)

    locations = np.where(result < QUEST_CLOCK_THRESHOLD)

    if len(locations[0]) == 0:
        return []

    # Collect matches with non-max suppression
    h, w = clock_template.shape[:2]
    matches = []
    for y, x in zip(locations[0], locations[1]):
        score = result[y, x]
        matches.append((x, y, score))

    matches.sort(key=lambda m: m[2])
    filtered: list[tuple[Any, Any, Any]] = []
    for x, y, score in matches:
        is_distinct = True
        for fx, fy, _ in filtered:
            if abs(x - fx) < 50 and abs(y - fy) < 50:
                is_distinct = False
                break
        if is_distinct:
            filtered.append((x, y, score))

    timers: list[dict[str, Any]] = []
    for clock_x, clock_y, _ in filtered:
        timer_x = clock_x + TIMER_OFFSET_X
        timer_y = clock_y
        timer_region = (timer_x, timer_y, TIMER_WIDTH, TIMER_HEIGHT)

        timer_text: str | None = None
        seconds: int | None = None

        if ocr is not None:
            try:
                timer_text = ocr.extract_text(frame, region=timer_region)
                seconds = parse_timer_string(timer_text)
            except Exception as e:
                logger.warning(f"OCR failed for timer at ({timer_x}, {timer_y}): {e}")

        timers.append({
            "clock_pos": (clock_x, clock_y),
            "timer_region": timer_region,
            "timer_text": timer_text,
            "seconds": seconds,
        })

    # Sort by Y position (top to bottom)
    timers.sort(key=lambda t: t["clock_pos"][1])

    return timers


def scan_quest_timers(frame: npt.NDArray[Any], ocr: OCRClient, screenshot_time: datetime | None = None) -> list[datetime]:
    """
    Scan tavern screen, OCR all timers, calculate completion times (COLOR matching).
    Does NOT save - caller should accumulate and save once at the end.

    Args:
        frame: Screenshot of tavern screen (BGR numpy array)
        ocr: OCR client instance (e.g., OCRClient)
        screenshot_time: When the screenshot was taken (for accurate timing).
                         If None, uses current time (less accurate due to OCR delay).

    Returns:
        List of datetime objects for when each quest will complete
    """
    timers = find_quest_timers(frame, ocr=ocr)

    # Use screenshot time if provided, otherwise use current time (introduces drift)
    base_time = screenshot_time if screenshot_time is not None else datetime.now()
    if screenshot_time is not None:
        drift = (datetime.now() - screenshot_time).total_seconds()
        logger.debug(f"Using screenshot_time, OCR took {drift:.1f}s")

    completions = []
    for t in timers:
        if t['seconds'] is not None:
            completion_time = base_time + timedelta(seconds=t['seconds'])
            completions.append(completion_time)
            logger.info(f"Quest timer: {t['timer_text']} -> completes at {completion_time.strftime('%H:%M:%S')}")

    return completions


def scan_and_schedule_quest_completions(frame: npt.NDArray[Any], ocr: OCRClient, screenshot_time: datetime | None = None) -> list[datetime]:
    """
    Scan tavern screen, OCR all timers, calculate completion times, and save.
    Use scan_quest_timers() if you need to accumulate across multiple screens.

    Args:
        frame: Screenshot of tavern screen (BGR numpy array)
        ocr: OCR client instance (e.g., OCRClient)
        screenshot_time: When the screenshot was taken (for accurate timing)

    Returns:
        List of datetime objects for when each quest will complete
    """
    completions = scan_quest_timers(frame, ocr, screenshot_time=screenshot_time)
    save_quest_schedule(completions)
    return completions


def check_tab_active(frame: npt.NDArray[Any], template: npt.NDArray[Any], region: tuple[int, int, int, int]) -> tuple[bool, float]:
    """Check if a tab is active by matching template in region (COLOR matching)."""
    x, y, w, h = region
    roi = frame[y:y+h, x:x+w]

    # Resize template if needed (compare h,w since color is 3D)
    if roi.shape[:2] != template.shape[:2]:
        template_resized = cv2.resize(template, (roi.shape[1], roi.shape[0]))
    else:
        template_resized = template

    result = cv2.matchTemplate(roi, template_resized, cv2.TM_SQDIFF_NORMED)
    score = result[0, 0]

    return score < 0.03, score  # Active if score < 0.03 (relaxed from 0.02)


def find_claim_buttons(frame: npt.NDArray[Any], template: npt.NDArray[Any]) -> list[tuple[int, int]]:
    """
    Find all Claim buttons by scanning column (X: 2100-2500, full Y) (COLOR matching).
    Returns list of (x, y) click positions.
    """
    buttons, _ = find_claim_buttons_with_score(frame, template)
    return buttons


def find_claim_buttons_with_score(frame: npt.NDArray[Any], template: npt.NDArray[Any]) -> tuple[list[tuple[int, int]], float]:
    """
    Find all Claim buttons by scanning column (X: 2100-2500, full Y) (COLOR matching).
    Returns (list of (x, y) click positions, best_score).
    best_score is the minimum score found (lower = better match for SQDIFF_NORMED).
    """
    # Extract column ROI
    column_roi = frame[:, CLAIM_X_START:CLAIM_X_END]

    result = cv2.matchTemplate(column_roi, template, cv2.TM_SQDIFF_NORMED)

    # Get best score in the entire search region (for debugging)
    best_score = float(result.min())

    # Find all matches below threshold
    locations = np.where(result < CLAIM_THRESHOLD)

    if len(locations[0]) == 0:
        return [], best_score

    # Get template dimensions for click center calculation
    th, tw = template.shape[:2]

    # Collect all match positions with scores
    matches = []
    for y, x in zip(locations[0], locations[1]):
        score = result[y, x]
        # Convert back to full frame coordinates
        full_x = CLAIM_X_START + x + tw // 2
        full_y = y + th // 2
        matches.append((full_x, full_y, score))

    # Sort by Y position
    matches.sort(key=lambda m: m[1])

    # Non-maximum suppression - keep distinct Y positions (min spacing 100px)
    filtered: list[tuple[int, int]] = []
    min_spacing = 100

    for full_x, full_y, score in matches:
        # Check if this Y is far enough from all kept positions
        is_distinct = True
        for _, kept_y in filtered:
            if abs(full_y - kept_y) < min_spacing:
                is_distinct = False
                break

        if is_distinct:
            filtered.append((full_x, full_y))

    return filtered, best_score


def find_gold_scroll_go_buttons(frame: npt.NDArray[Any]) -> list[tuple[int, int]]:
    """
    Find Go click targets for quests that have Gold Scroll rewards (any level, COLOR matching with mask).

    Logic:
    1. Find all Gold Scroll icons using masked matching (ignores level text)
    2. Use quest row Y from each scroll with fixed Go column X
    3. Return click positions sorted top-to-bottom
    """
    gold_scroll_template = load_template_color(GOLD_SCROLL_TEMPLATE)
    gold_scroll_mask = cv2.imread(GOLD_SCROLL_MASK, cv2.IMREAD_GRAYSCALE)

    # Find all gold scroll positions using masked matching (TM_CCORR_NORMED - higher is better)
    scroll_result = cv2.matchTemplate(frame, gold_scroll_template, cv2.TM_CCORR_NORMED, mask=gold_scroll_mask)
    scroll_locations = np.where(scroll_result >= GOLD_SCROLL_THRESHOLD)

    scroll_h, scroll_w = gold_scroll_template.shape[:2]
    scrolls = []
    for y, x in zip(scroll_locations[0], scroll_locations[1]):
        score = scroll_result[y, x]
        center_x = x + scroll_w // 2
        center_y = y + scroll_h // 2
        if center_x < QUEST_ICON_X_MIN or center_x > QUEST_ICON_X_MAX:
            continue
        if center_y < QUEST_LIST_Y_MIN or center_y > QUEST_LIST_Y_MAX:
            continue
        if not _row_has_go_button(frame, center_y):
            continue
        if not _is_gold_quest_icon(frame, x, y, scroll_w, scroll_h):
            continue
        scrolls.append((x, center_y, score))

    # Non-maximum suppression for scrolls (min spacing 100px)
    scrolls.sort(key=lambda s: -s[2])  # Sort by score (highest first for CCORR)
    filtered_scrolls: list[tuple[Any, Any, Any]] = []
    for x, y, score in scrolls:
        is_distinct = True
        for fx, fy, _ in filtered_scrolls:
            if abs(y - fy) < 100 and abs(x - fx) < 100:
                is_distinct = False
                break
        if is_distinct:
            filtered_scrolls.append((x, y, score))

    if not filtered_scrolls:
        return []

    logger.debug(f"Found {len(filtered_scrolls)} Gold Scroll icons (any level)")

    matched_go_buttons = [(GO_BUTTON_CLICK_X, int(scroll_y)) for _, scroll_y, _ in filtered_scrolls]

    # Sort by Y position (top to bottom)
    matched_go_buttons.sort(key=lambda b: b[1])

    # De-dup near-identical rows by Y only (we only click fixed Go-column X).
    deduped_go_buttons: list[tuple[int, int]] = []
    min_row_spacing = 80
    for x, y in matched_go_buttons:
        if all(abs(y - kept_y) >= min_row_spacing for _, kept_y in deduped_go_buttons):
            deduped_go_buttons.append((x, y))

    return deduped_go_buttons


def _is_gold_quest_icon(
    frame: npt.NDArray[Any],
    x: int,
    y: int,
    icon_w: int,
    icon_h: int,
) -> bool:
    """
    Validate that a matched quest icon is truly gold-toned.

    This rejects purple/non-gold quest rows that can pass masked template
    matching on shape alone.
    """
    h, w = frame.shape[:2]
    if x < 0 or y < 0 or x + icon_w > w or y + icon_h > h:
        return False

    roi = frame[y:y + icon_h, x:x + icon_w]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # Gold/orange hue band
    orange_mask = (
        (hsv[:, :, 0] >= 5) & (hsv[:, :, 0] <= 35) &
        (hsv[:, :, 1] >= 80) & (hsv[:, :, 2] >= 80)
    )
    # Purple hue band
    purple_mask = (
        (hsv[:, :, 0] >= 120) & (hsv[:, :, 0] <= 170) &
        (hsv[:, :, 1] >= 60) & (hsv[:, :, 2] >= 50)
    )

    orange_ratio = float(np.count_nonzero(orange_mask)) / float(orange_mask.size)
    purple_ratio = float(np.count_nonzero(purple_mask)) / float(purple_mask.size)

    return orange_ratio >= GOLD_ICON_ORANGE_MIN_RATIO and purple_ratio <= GOLD_ICON_PURPLE_MAX_RATIO


def find_question_mark_go_buttons(frame: npt.NDArray[Any]) -> list[tuple[int, int]]:
    """
    Find Go click targets for quests that have question mark reward tiles (COLOR matching).

    Logic:
    1. Find all question mark tiles in the frame
    2. Use quest row Y from each tile with fixed Go column X
    3. Return click positions sorted top-to-bottom
    """
    try:
        question_mark_template = load_template_color(QUESTION_MARK_TILE_TEMPLATE)
    except FileNotFoundError:
        logger.warning("Question mark tile template not found")
        return []

    # Find all question mark tile positions (COLOR)
    tile_result = cv2.matchTemplate(frame, question_mark_template, cv2.TM_SQDIFF_NORMED)
    tile_locations = np.where(tile_result < QUESTION_MARK_THRESHOLD)

    tile_h, tile_w = question_mark_template.shape[:2]
    tiles = []
    for y, x in zip(tile_locations[0], tile_locations[1]):
        score = tile_result[y, x]
        center_x = x + tile_w // 2
        center_y = y + tile_h // 2
        if center_x < QUEST_ICON_X_MIN or center_x > QUEST_ICON_X_MAX:
            continue
        if center_y < QUEST_LIST_Y_MIN or center_y > QUEST_LIST_Y_MAX:
            continue
        if not _row_has_go_button(frame, center_y):
            continue
        tiles.append((x, center_y, score))

    # Non-maximum suppression for tiles (min spacing 100px)
    tiles.sort(key=lambda t: t[2])  # Sort by score
    filtered_tiles: list[tuple[Any, Any, Any]] = []
    for x, y, score in tiles:
        is_distinct = True
        for fx, fy, _ in filtered_tiles:
            if abs(y - fy) < 100 and abs(x - fx) < 100:
                is_distinct = False
                break
        if is_distinct:
            filtered_tiles.append((x, y, score))

    if not filtered_tiles:
        return []

    logger.debug(f"Found {len(filtered_tiles)} question mark tiles")

    matched_go_buttons_qmark = [(GO_BUTTON_CLICK_X, int(tile_y)) for _, tile_y, _ in filtered_tiles]

    # Sort by Y position (top to bottom)
    matched_go_buttons_qmark.sort(key=lambda b: b[1])

    return matched_go_buttons_qmark


def _row_has_go_button(frame: npt.NDArray[Any], row_y: int) -> bool:
    """
    Check whether a quest row has a visible blue Go button in the Go column.

    This prevents reward-icon false positives from clicking rows that have no
    actionable Go button (for example clipped bottom rows or timer rows).
    """
    h, w = frame.shape[:2]
    x0 = max(0, GO_BUTTON_CLICK_X - GO_BUTTON_ROI_HALF_WIDTH)
    x1 = min(w, GO_BUTTON_CLICK_X + GO_BUTTON_ROI_HALF_WIDTH)
    y0 = max(0, row_y - GO_BUTTON_ROI_HALF_HEIGHT)
    y1 = min(h, row_y + GO_BUTTON_ROI_HALF_HEIGHT)
    if x1 <= x0 or y1 <= y0:
        return False

    roi = frame[y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    blue_mask = (
        (hsv[:, :, 0] >= 85) & (hsv[:, :, 0] <= 135) &
        (hsv[:, :, 1] >= 70) & (hsv[:, :, 2] >= 70)
    )

    blue_ratio = float(np.count_nonzero(blue_mask)) / float(blue_mask.size)
    if blue_ratio < GO_BUTTON_BLUE_MIN_RATIO:
        return False

    # Require one reasonably large blue connected component (button body).
    blue_u8 = (blue_mask.astype(np.uint8)) * 255
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(blue_u8, connectivity=8)
    largest_area = int(stats[1:, cv2.CC_STAT_AREA].max()) if num_labels > 1 else 0
    return largest_area >= GO_BUTTON_BLUE_MIN_COMPONENT_AREA


def is_in_tavern(frame: npt.NDArray[Any]) -> tuple[bool, str | None]:
    """
    Verify we're in Tavern by checking if either tab template matches (COLOR matching).
    Returns (is_in_tavern, active_tab) where active_tab is 'my_quests', 'ally_quests', or None.
    """
    my_quests_active_template = load_template_color(MY_QUESTS_ACTIVE_TEMPLATE)
    ally_quests_active_template = load_template_color(ALLY_QUESTS_ACTIVE_TEMPLATE)
    my_quests_inactive_template = load_template_color(f"{TEMPLATE_DIR}/tavern_my_quests_4k.png")
    ally_quests_inactive_template = load_template_color(f"{TEMPLATE_DIR}/tavern_ally_quests_4k.png")

    # Check My Quests region for either active or inactive template (COLOR)
    my_active, my_active_score = check_tab_active(frame, my_quests_active_template, MY_QUESTS_TAB_REGION)
    my_inactive, my_inactive_score = check_tab_active(frame, my_quests_inactive_template, MY_QUESTS_TAB_REGION)

    # Check Ally Quests region for either active or inactive template (COLOR)
    ally_active, ally_active_score = check_tab_active(frame, ally_quests_active_template, ALLY_QUESTS_TAB_REGION)
    ally_inactive, ally_inactive_score = check_tab_active(frame, ally_quests_inactive_template, ALLY_QUESTS_TAB_REGION)

    logger.debug(f"Tab scores - My active:{my_active_score:.4f} inactive:{my_inactive_score:.4f}, "
                 f"Ally active:{ally_active_score:.4f} inactive:{ally_inactive_score:.4f}")

    # Must have at least one tab matching (active or inactive) in each position
    my_quests_visible = my_active or my_inactive
    ally_quests_visible = ally_active or ally_inactive

    if not (my_quests_visible and ally_quests_visible):
        # Log WARNINGS when failing so we can diagnose
        logger.warning(f"[TAVERN] Detection FAILED - my_visible={my_quests_visible}, ally_visible={ally_quests_visible}")
        logger.warning(f"[TAVERN] Scores: my_active={my_active_score:.4f}, my_inactive={my_inactive_score:.4f}, "
                      f"ally_active={ally_active_score:.4f}, ally_inactive={ally_inactive_score:.4f}")
        return False, None

    # Determine which tab is active
    if my_active:
        return True, "my_quests"
    elif ally_active:
        return True, "ally_quests"
    else:
        # Both inactive? Shouldn't happen but default to my_quests
        return True, "my_quests"


# Import back button from centralized config
from config import BACK_BUTTON_CLICK
from utils.ui_helpers import click_back


def wait_for_tavern_tabs(adb: ADBHelper, win: WindowsScreenshotHelper,
                         max_attempts: int = 10, debug: bool = False) -> bool:
    """
    Poll until we can see the Tavern tabs (My Quests / Ally Quests).

    If tabs not visible, clicks back button and checks again.
    Used after clicking Claim to dismiss the rewards popup.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        max_attempts: Maximum number of back button clicks before giving up
        debug: Enable debug logging

    Returns:
        True if back in Tavern (tabs visible), False if gave up or exited to TOWN/WORLD
    """
    from utils.view_state_detector import detect_view, ViewState

    for attempt in range(max_attempts):
        frame = win.get_screenshot_cv2()

        # Check if we can see Tavern tabs (COLOR)
        in_tavern, active_tab = is_in_tavern(frame)
        if in_tavern:
            if debug:
                logger.debug(f"[POPUP] Back in Tavern after {attempt} clicks (tab={active_tab})")
            return True

        # Check if we exited to TOWN/WORLD (popup dismissed us out of Tavern entirely)
        view_state, _ = detect_view(frame)
        if view_state in (ViewState.TOWN, ViewState.WORLD):
            logger.warning(f"[POPUP] Exited to {view_state.name} - Tavern closed unexpectedly")
            return False

        # Still in popup - click back button to dismiss
        if debug:
            logger.debug(f"[POPUP] Attempt {attempt + 1}/{max_attempts}: Tabs not visible, clicking back")
        click_back(adb)
        time.sleep(0.5)

    logger.warning(f"[POPUP] Failed to return to Tavern after {max_attempts} attempts")
    return False


def wait_for_tavern_open(win: WindowsScreenshotHelper, max_attempts: int = 10,
                          poll_interval: float = 0.2, debug: bool = False) -> tuple[bool, str | None]:
    """
    Poll until tavern UI is visible after clicking tavern button.

    Unlike wait_for_tavern_tabs, this doesn't click back - just waits for UI to load.

    Args:
        win: WindowsScreenshotHelper instance
        max_attempts: Maximum number of polls (default 10 = 2s max wait)
        poll_interval: Seconds between polls (default 0.2s)
        debug: Enable debug logging

    Returns:
        Tuple of (in_tavern, active_tab) - same as is_in_tavern()
    """
    for attempt in range(max_attempts):
        frame = win.get_screenshot_cv2()
        in_tavern, active_tab = is_in_tavern(frame)

        if in_tavern:
            if debug or attempt > 0:
                logger.info(f"Tavern opened after {attempt + 1} polls ({(attempt + 1) * poll_interval:.1f}s)")
            return True, active_tab

        if attempt < max_attempts - 1:
            time.sleep(poll_interval)

    logger.warning(f"Tavern did not open after {max_attempts} polls ({max_attempts * poll_interval:.1f}s)")
    return False, None


# =============================================================================
# TAVERN OPEN HELPER
# =============================================================================

TAVERN_BUTTON_CLICK = (80, 1220)


def _open_tavern(adb: ADBHelper, win: WindowsScreenshotHelper, target_tab: str = "my_quests", debug: bool = False) -> bool:
    """
    Navigate to TOWN and open tavern to specified tab.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        target_tab: "my_quests" or "ally_quests"
        debug: Enable debug screenshots

    Returns:
        True if tavern opened successfully, False otherwise
    """
    from utils.view_state_detector import go_to_town
    from utils.return_to_base_view import return_to_base_view

    # Dismiss any blocking popups first (promo, webview, etc.)
    return_to_base_view(adb, win, debug=False)
    time.sleep(0.3)

    # Retry loop - try up to 3 times with recovery between attempts
    in_tavern = False
    active_tab = None
    max_attempts = 3

    for attempt in range(max_attempts):
        # Navigate to TOWN first
        if not go_to_town(adb, debug=debug):
            logger.warning(f"Failed to navigate to TOWN (attempt {attempt + 1}/{max_attempts})")
            return_to_base_view(adb, win, debug=False)
            time.sleep(0.5)
            continue

        # Click tavern button
        logger.info(f"Clicking Tavern button at {TAVERN_BUTTON_CLICK} (attempt {attempt + 1}/{max_attempts})")
        adb.tap(*TAVERN_BUTTON_CLICK, source="flow:tavern_quest:open_tavern")

        # Small delay to let animation start before polling
        time.sleep(0.3)

        # Poll for tavern to open (increased from 2s to 4s to handle slow animations)
        in_tavern, active_tab = wait_for_tavern_open(win, max_attempts=20, poll_interval=0.2, debug=debug)

        if in_tavern:
            break

        # Failed - recover and retry
        logger.warning(f"Tavern did not open (attempt {attempt + 1}/{max_attempts}), recovering...")
        return_to_base_view(adb, win, debug=False)
        time.sleep(0.5)

    if not in_tavern:
        logger.warning(f"Tavern failed to open after {max_attempts} attempts")
        return False

    # Switch tab if needed
    if target_tab == "my_quests" and active_tab != "my_quests":
        logger.info("Switching to My Quests tab")
        adb.tap(*MY_QUESTS_CLICK, source="flow:tavern_quest:switch_my_quests")
        time.sleep(0.5)
    elif target_tab == "ally_quests" and active_tab != "ally_quests":
        logger.info("Switching to Ally Quests tab")
        adb.tap(*ALLY_QUESTS_CLICK, source="flow:tavern_quest:switch_ally_quests")
        time.sleep(0.5)

    return True


# =============================================================================
# MODE: CLAIM - Click Claim buttons, timer-gated OCR wait, no Go buttons
# =============================================================================

def _run_claim_mode(adb: ADBHelper, win: WindowsScreenshotHelper, debug: bool = False) -> dict[str, Any]:
    """
    CLAIM mode: Find and click Claim buttons only.

    Flow (strict):
    1) Check top immediately for Claim
    2) If none, OCR timers; if any <= 10s, wait/poll for Claim
    3) If still none, scroll down and repeat immediate Claim check
    4) If still none, OCR timers again; if any <= 10s, wait/poll
    5) Exit if no Claim found

    Returns:
        {"claims": N, "mode": "claim"}
    """
    logger.info("=== TAVERN CLAIM MODE ===")

    if not _open_tavern(adb, win, target_tab="my_quests", debug=debug):
        return {"claims": 0, "mode": "claim", "error": "tavern_open_failed"}

    claim_template = load_template_color(CLAIM_BUTTON_TEMPLATE)
    logger.info(f"[CLAIM] Template size: {claim_template.shape[1]}x{claim_template.shape[0]}")
    # OCR is required for the timer-under-10s decision path.
    ocr: OCRClient | None = None
    try:
        from utils.ocr_client import OCRClient as _OCRClient
        ocr = _OCRClient()
        _OCRClient.require_server(auto_start=True)
        logger.info("[CLAIM] OCR server ready for timer checks")
    except Exception as e:
        logger.warning(f"[CLAIM] OCR unavailable ({e}) - timer waiting path disabled")

    total_claims = 0

    def _ensure_tavern_my_quests(tag: str) -> bool:
        frame_local = win.get_screenshot_cv2()
        in_tavern, active_tab = is_in_tavern(frame_local)
        if not in_tavern:
            logger.warning(f"[CLAIM:{tag}] Lost tavern view")
            _save_debug(frame_local, f"claim_{tag}_LOST_TAVERN")
            # Common case after a claim: reward overlay blocks tab detection.
            if wait_for_tavern_tabs(adb, win, max_attempts=8, debug=debug):
                frame_local = win.get_screenshot_cv2()
                in_tavern, active_tab = is_in_tavern(frame_local)
                if in_tavern:
                    logger.info(f"[CLAIM:{tag}] Recovered tavern view after popup dismissal")
                else:
                    logger.warning(f"[CLAIM:{tag}] Tabs reported recovered, but tavern detection still failed")
            if not in_tavern:
                logger.warning(f"[CLAIM:{tag}] Re-opening Tavern to continue claim cycle")
                if not _open_tavern(adb, win, target_tab="my_quests", debug=debug):
                    return False
                frame_local = win.get_screenshot_cv2()
                in_tavern, active_tab = is_in_tavern(frame_local)
                if not in_tavern:
                    return False
        if active_tab != "my_quests":
            logger.info(f"[CLAIM:{tag}] Switching from {active_tab} to my_quests")
            adb.tap(*MY_QUESTS_CLICK, source="flow:tavern_quest:switch_my_quests")
            time.sleep(0.5)
        return True

    def _same_row_claim_present(
        claim_buttons: list[tuple[int, int]],
        expected_y: int,
        y_tolerance: int = 70,
    ) -> bool:
        """Check whether a detected claim button still exists on the same quest row."""
        return any(abs(btn_y - expected_y) <= y_tolerance for _, btn_y in claim_buttons)

    def _click_claim(claim_x: int, claim_y: int, tag: str) -> bool:
        logger.info(f"[CLAIM:{tag}] Clicking Claim at ({claim_x}, {claim_y})")
        frame_local = win.get_screenshot_cv2()
        _save_debug(frame_local, f"claim_{tag}_PRE_CLAIM_at_{claim_x}_{claim_y}")

        verify_frame = frame_local
        for tap_attempt in range(1, 4):
            adb.tap(claim_x, claim_y, source="flow:tavern_quest:claim")
            time.sleep(0.35)

            verify_frame = win.get_screenshot_cv2()
            _save_debug(verify_frame, f"claim_{tag}_POST_CLAIM_tap_attempt_{tap_attempt}")
            verify_buttons, _ = find_claim_buttons_with_score(verify_frame, claim_template)
            in_tavern_now, _ = is_in_tavern(verify_frame)
            same_row_still_present = _same_row_claim_present(verify_buttons, claim_y)

            # Most important guard: if the same claim row is still present,
            # this was an early/failed tap. Never back out in this case.
            if same_row_still_present:
                logger.info(
                    f"[CLAIM:{tag}] Claim still present on same row after tap attempt "
                    f"{tap_attempt}/3; likely not ready yet"
                )
                _save_debug(verify_frame, f"claim_{tag}_NOT_READY_YET_attempt_{tap_attempt}")
                if tap_attempt < 3:
                    time.sleep(0.35)
                    continue
                return False

            # Success path without popup: still in tavern and target row claim disappeared.
            if in_tavern_now:
                logger.info(f"[CLAIM:{tag}] Claim accepted in-tavern on attempt {tap_attempt}")
                _save_debug(verify_frame, f"claim_{tag}_after_claim_in_tavern")
                # Ensure reward overlays are dismissed so next cycle can detect tavern tabs.
                if not wait_for_tavern_tabs(adb, win, max_attempts=8, debug=debug):
                    logger.warning(f"[CLAIM:{tag}] Could not stabilize tavern after in-tavern claim")
                    return False
                return True

            # Not in tavern means popup/dialog likely appeared; dismiss and verify.
            logger.info(f"[CLAIM:{tag}] Waiting to return to tavern after tap attempt {tap_attempt}")
            if not wait_for_tavern_tabs(adb, win, max_attempts=15, debug=debug):
                logger.warning(f"[CLAIM:{tag}] Could not return to tavern after claim popup")
                stuck_frame = win.get_screenshot_cv2()
                _save_debug(stuck_frame, f"claim_{tag}_POPUP_STUCK")
                return False

            after_popup = win.get_screenshot_cv2()
            _save_debug(after_popup, f"claim_{tag}_after_popup_attempt_{tap_attempt}")
            post_buttons, _ = find_claim_buttons_with_score(after_popup, claim_template)
            if _same_row_claim_present(post_buttons, claim_y):
                logger.info(
                    f"[CLAIM:{tag}] Same-row claim still visible after popup dismiss "
                    f"(attempt {tap_attempt}/3)"
                )
                _save_debug(after_popup, f"claim_{tag}_NOT_READY_POST_POPUP_attempt_{tap_attempt}")
                if tap_attempt < 3:
                    time.sleep(0.35)
                    continue
                return False

            logger.info(f"[CLAIM:{tag}] Claim completed after popup on attempt {tap_attempt}")
            return True

        logger.warning(f"[CLAIM:{tag}] Claim tap exhausted retries without success")
        _save_debug(verify_frame, f"claim_{tag}_NOT_READY_YET_exhausted")
        return False

    def _immediate_claim_check(tag: str) -> bool:
        frame_local = win.get_screenshot_cv2()
        _save_debug(frame_local, f"claim_{tag}_immediate_check")
        claim_buttons, best_score = find_claim_buttons_with_score(frame_local, claim_template)
        if claim_buttons:
            logger.info(
                f"[CLAIM:{tag}] Immediate claim found ({len(claim_buttons)} buttons, best_score={best_score:.4f})"
            )
            claim_x, claim_y = claim_buttons[0]
            return _click_claim(claim_x, claim_y, tag)

        logger.info(f"[CLAIM:{tag}] No immediate claim button (best_score={best_score:.4f})")
        return False

    def _get_shortest_timer_seconds(tag: str) -> int | None:
        frame_local = win.get_screenshot_cv2()
        _save_debug(frame_local, f"claim_{tag}_timer_scan")

        if ocr is None:
            logger.warning(f"[CLAIM:{tag}] OCR unavailable - cannot evaluate timer threshold")
            return None

        timers = find_quest_timers(frame_local, ocr=ocr)
        valid_seconds = [t["seconds"] for t in timers if t["seconds"] is not None]
        timer_texts = [t["timer_text"] for t in timers if t["timer_text"]]
        if timer_texts:
            logger.info(f"[CLAIM:{tag}] OCR timers: {timer_texts}")
        else:
            logger.info(f"[CLAIM:{tag}] No OCR timer text found")

        if not valid_seconds:
            return None

        shortest = min(valid_seconds)
        logger.info(f"[CLAIM:{tag}] Shortest timer={shortest}s")
        return shortest

    def _wait_and_poll_for_claim(tag: str, timeout_s: float) -> bool:
        start = time.time()
        poll_count = 0
        best_score = 1.0
        logger.info(f"[CLAIM:{tag}] Waiting/polling for up to {timeout_s:.1f}s")

        while time.time() - start < timeout_s:
            frame_local = win.get_screenshot_cv2()
            claim_buttons, score = find_claim_buttons_with_score(frame_local, claim_template)
            poll_count += 1
            if score < best_score:
                best_score = score

            if claim_buttons:
                claim_x, claim_y = claim_buttons[0]
                logger.info(
                    f"[CLAIM:{tag}] Claim appeared after {poll_count} polls "
                    f"({time.time() - start:.1f}s), best_score={best_score:.4f}"
                )
                if _click_claim(claim_x, claim_y, tag):
                    return True
                logger.info(
                    f"[CLAIM:{tag}] Claim tap failed/not-ready after poll detect; continuing to poll"
                )
                time.sleep(0.2)
                continue

            time.sleep(0.2)

        timeout_frame = win.get_screenshot_cv2()
        _save_debug(timeout_frame, f"claim_{tag}_wait_timeout_best_{best_score:.4f}")
        logger.info(
            f"[CLAIM:{tag}] No claim appeared during wait ({poll_count} polls, best_score={best_score:.4f})"
        )
        return False

    # Allow a few cycles so we can claim multiple ready quests in one invocation.
    for cycle in range(1, 6):
        logger.info(f"[CLAIM] ===== Cycle {cycle} =====")
        if not _ensure_tavern_my_quests(f"top_c{cycle}"):
            break

        # TOP PASS: immediate claim first
        if _immediate_claim_check(f"top_c{cycle}"):
            total_claims += 1
            continue

        # TOP PASS: if no claim, OCR timers and wait only when <= 10s
        top_shortest = _get_shortest_timer_seconds(f"top_c{cycle}")
        if top_shortest is not None and top_shortest <= CLAIM_SHORT_WAIT_THRESHOLD_SECONDS:
            wait_for = min(max(float(top_shortest) + 2.0, 3.0), 15.0)
            logger.info(
                f"[CLAIM:top_c{cycle}] Timer <= {CLAIM_SHORT_WAIT_THRESHOLD_SECONDS}s "
                f"({top_shortest}s), waiting/polling"
            )
            if _wait_and_poll_for_claim(f"top_c{cycle}", wait_for):
                total_claims += 1
                continue

        # No top claim path succeeded -> scroll down
        logger.info(f"[CLAIM] No top claim path succeeded, scrolling down for bottom pass")
        for _ in range(3):
            adb.swipe(SCROLL_X, SCROLL_START_Y, SCROLL_X, SCROLL_END_Y, SCROLL_DURATION)
            time.sleep(0.2)

        if not _ensure_tavern_my_quests(f"bottom_c{cycle}"):
            break

        # BOTTOM PASS: immediate claim first
        if _immediate_claim_check(f"bottom_c{cycle}"):
            total_claims += 1
            # Return to top for next cycle (fresh pass order)
            for _ in range(3):
                adb.swipe(SCROLL_X, SCROLL_END_Y, SCROLL_X, SCROLL_START_Y, SCROLL_DURATION)
                time.sleep(0.2)
            continue

        # BOTTOM PASS: if no claim, OCR timers and wait only when <= 10s
        bottom_shortest = _get_shortest_timer_seconds(f"bottom_c{cycle}")
        if bottom_shortest is not None and bottom_shortest <= CLAIM_SHORT_WAIT_THRESHOLD_SECONDS:
            wait_for = min(max(float(bottom_shortest) + 2.0, 3.0), 15.0)
            logger.info(
                f"[CLAIM:bottom_c{cycle}] Timer <= {CLAIM_SHORT_WAIT_THRESHOLD_SECONDS}s "
                f"({bottom_shortest}s), waiting/polling"
            )
            if _wait_and_poll_for_claim(f"bottom_c{cycle}", wait_for):
                total_claims += 1
                for _ in range(3):
                    adb.swipe(SCROLL_X, SCROLL_END_Y, SCROLL_X, SCROLL_START_Y, SCROLL_DURATION)
                    time.sleep(0.2)
                continue

        # As requested: if no claim and no <=10s timer wait success at bottom, exit.
        logger.info("[CLAIM] Bottom pass has no claim and no actionable <=10s timer wait success; exiting")
        break

    logger.info(f"[CLAIM] === CLAIM MODE COMPLETE: {total_claims} claims ===")
    # Exit tavern
    return_to_base_view(adb, win, debug=debug, respect_idle=False)
    return {"claims": total_claims, "mode": "claim"}


# =============================================================================
# MODE: SCAN - OCR timers only, no clicking
# =============================================================================

def _run_scan_mode(adb: ADBHelper, win: WindowsScreenshotHelper, ocr: OCRClient, debug: bool = False) -> dict[str, Any]:
    """
    SCAN mode: Scroll through quests and OCR timers.

    Behavior:
    - OCRs active quest timers and saves completion schedule.
    - Always runs a DISPATCH follow-up attempt after scan, regardless of whether
      active timers were found. Dispatch-mode gating (time window + min gap)
      controls whether starts actually occur.

    Returns:
        {"completions": [datetime, ...], "mode": "scan"}
    """
    logger.info("=== TAVERN SCAN MODE ===")

    if not _open_tavern(adb, win, target_tab="my_quests", debug=debug):
        return {"completions": [], "mode": "scan", "error": "tavern_open_failed"}

    frames_for_ocr: list[tuple[npt.NDArray[Any], datetime]] = []  # (frame, screenshot_time)
    scroll_count = 0
    max_scrolls = 3  # Scroll down 3 times to capture all quests

    # Capture initial frame with timestamp
    screenshot_time = datetime.now()
    frame = win.get_screenshot_cv2()
    in_tavern, _ = is_in_tavern(frame)
    if in_tavern:
        frames_for_ocr.append((frame.copy(), screenshot_time))

    # Scroll and capture
    while scroll_count < max_scrolls and in_tavern:
        adb.swipe(SCROLL_X, SCROLL_START_Y, SCROLL_X, SCROLL_END_Y, SCROLL_DURATION)
        time.sleep(0.5)
        scroll_count += 1

        screenshot_time = datetime.now()
        frame = win.get_screenshot_cv2()
        in_tavern, _ = is_in_tavern(frame)
        if in_tavern:
            frames_for_ocr.append((frame.copy(), screenshot_time))

    # OCR all collected frames (using screenshot_time for accurate completion times)
    all_completions: list[datetime] = []
    logger.info(f"OCR scanning {len(frames_for_ocr)} frames...")
    for saved_frame, frame_time in frames_for_ocr:
        completions = scan_quest_timers(saved_frame, ocr, screenshot_time=frame_time)
        if completions:
            all_completions.extend(completions)

    # Save completions to scheduler if any timers were detected
    if all_completions:
        save_quest_schedule(all_completions)
        logger.info(f"Saved {len(all_completions)} timer completion(s) to scheduler")
    else:
        logger.info("No active quest timers detected in scan")

    # Always run dispatch follow-up after scan (requested behavior).
    logger.info("Running DISPATCH follow-up after scan")
    return_to_base_view(adb, win, debug=debug, respect_idle=False)
    dispatch_result = _run_dispatch_mode(adb, win, debug=debug)
    return {"completions": all_completions, "mode": "scan", "dispatch_triggered": True, **dispatch_result}


# =============================================================================
# MODE: DISPATCH - Click Go buttons only, no OCR, no Claims
# =============================================================================

def _run_dispatch_mode(adb: ADBHelper, win: WindowsScreenshotHelper, debug: bool = False) -> dict[str, Any]:
    """
    DISPATCH mode: Find and click Go buttons to start new quests.

    Behavior:
    - Enforces dispatch start time window in Pacific time.
    - Enforces minimum minutes between successful dispatches.
    - Prioritizes gold-scroll quests, then question-mark quests (when allowed).
    - Saves debug screenshots for key dispatch steps when `debug=True`.
    - A post-dispatch transition can leave tavern view; this may happen after a
      successful dispatch depending on game UI transition/popups.

    Does NOT: Click Claim buttons, OCR timers.

    Returns:
        {"dispatches": N, "mode": "dispatch"}
    """
    logger.info("=== TAVERN DISPATCH MODE ===")
    if debug:
        _save_debug(win.get_screenshot_cv2(), "dispatch_00_start")

    # Check time restriction
    if not _is_after_quest_start_time():
        logger.info("Before quest start time - skipping dispatch")
        return {"dispatches": 0, "mode": "dispatch", "skipped": "before_start_time"}

    # Check dispatch gap (configured minutes between successful dispatches)
    from config import TAVERN_MIN_DISPATCH_GAP_MINUTES
    scheduler = _get_scheduler()
    last_dispatch = scheduler.get_last_tavern_dispatch()
    if last_dispatch:
        minutes_since = (datetime.now() - last_dispatch).total_seconds() / 60
        if minutes_since < TAVERN_MIN_DISPATCH_GAP_MINUTES:
            logger.info(f"Skipping dispatch: only {minutes_since:.0f} min since last dispatch (need {TAVERN_MIN_DISPATCH_GAP_MINUTES})")
            return {"dispatches": 0, "mode": "dispatch", "skipped": "too_soon"}

    if not _open_tavern(adb, win, target_tab="my_quests", debug=debug):
        return {"dispatches": 0, "mode": "dispatch", "error": "tavern_open_failed"}

    total_dispatches = 0
    no_action_count = 0
    max_no_action = 2
    loop_idx = 0

    while no_action_count < max_no_action:
        loop_idx += 1
        frame = win.get_screenshot_cv2()
        if debug:
            _save_debug(frame, f"dispatch_{loop_idx:02d}_loop")

        # Verify still in tavern
        in_tavern, active_tab = is_in_tavern(frame)
        if not in_tavern:
            logger.warning("Lost tavern view - aborting dispatch mode")
            _save_debug(frame, f"dispatch_{loop_idx:02d}_lost_tavern")
            break

        # Switch to My Quests if needed
        if active_tab != "my_quests":
            if debug:
                _save_debug(frame, f"dispatch_{loop_idx:02d}_switch_to_my_quests")
            adb.tap(*MY_QUESTS_CLICK, source="flow:tavern_quest:switch_my_quests")
            time.sleep(0.5)
            continue

        # Find Go buttons (gold scroll quests)
        gold_go_buttons = find_gold_scroll_go_buttons(frame)

        # Find Go buttons (question mark quests)
        question_go_buttons = []
        if _should_start_question_mark_quests():
            question_go_buttons = find_question_mark_go_buttons(frame)

        action_succeeded = False

        # Try all candidates in priority order (gold first, then question mark).
        # If one row fails to open Bounty Quest, keep trying the remaining rows.
        candidates: list[tuple[str, list[tuple[int, int]], str]] = [
            ("gold", gold_go_buttons, "flow:tavern_quest:go_gold"),
            ("question", question_go_buttons, "flow:tavern_quest:go_question"),
        ]
        for quest_type, buttons, tap_source in candidates:
            for idx, (x, y) in enumerate(buttons, start=1):
                logger.info(f"Clicking Go for {quest_type} quest at ({x}, {y}) [candidate {idx}/{len(buttons)}]")
                if debug:
                    _save_debug(frame, f"dispatch_{loop_idx:02d}_{quest_type}_go_before_tap_{idx:02d}")
                adb.tap(x, y, source=tap_source)
                time.sleep(1.0)
                if debug:
                    _save_debug(win.get_screenshot_cv2(), f"dispatch_{loop_idx:02d}_{quest_type}_go_after_tap_{idx:02d}")

                if handle_bounty_quest_dialog(
                    adb,
                    win,
                    debug,
                    context_tag=f"dispatch_{loop_idx:02d}_{quest_type}_{idx:02d}",
                ):
                    total_dispatches += 1
                    scheduler.record_tavern_dispatch()  # Record dispatch time
                    no_action_count = 0
                    action_succeeded = True
                    time.sleep(0.5)
                    break

                logger.warning(f"Bounty Quest dialog not detected for {quest_type} candidate {idx}, trying next")

                # If we left tavern after a bad click, stop dispatch mode cleanly.
                post_frame = win.get_screenshot_cv2()
                post_in_tavern, _ = is_in_tavern(post_frame)
                if not post_in_tavern:
                    logger.warning("Lost tavern view after failed candidate click - aborting dispatch mode")
                    _save_debug(post_frame, f"dispatch_{loop_idx:02d}_{quest_type}_{idx:02d}_lost_tavern")
                    return_to_base_view(adb, win, debug=debug, respect_idle=False)
                    return {"dispatches": total_dispatches, "mode": "dispatch", "error": "lost_tavern_after_failed_click"}

            if action_succeeded:
                break

        if action_succeeded:
            continue

        # No Go buttons found - scroll
        no_action_count += 1
        if no_action_count < max_no_action:
            if debug:
                _save_debug(frame, f"dispatch_{loop_idx:02d}_no_go_scroll")
            adb.swipe(SCROLL_X, SCROLL_START_Y, SCROLL_X, SCROLL_END_Y, SCROLL_DURATION)
            time.sleep(0.5)

    # Exit tavern
    return_to_base_view(adb, win, debug=debug, respect_idle=False)

    logger.info(f"DISPATCH mode complete: {total_dispatches} quests started")
    return {"dispatches": total_dispatches, "mode": "dispatch"}


# =============================================================================
# MODE: ALLY - Assist ally quests, skip if 5/5
# =============================================================================

def _run_ally_mode(adb: ADBHelper, win: WindowsScreenshotHelper, debug: bool = False) -> dict[str, Any]:
    """
    ALLY mode: Assist gold 5-star ally quests.

    Checks if 5/5 BEFORE opening tavern - skips entirely if maxed.

    Returns:
        {"assists": N, "mode": "ally", "skipped": bool}
    """
    from utils.current_state import is_tavern_assists_maxed

    logger.info("=== TAVERN ALLY MODE ===")

    # Check if already maxed BEFORE opening tavern
    if is_tavern_assists_maxed():
        logger.info("Ally assists already maxed (5/5) - skipping entirely")
        return {"assists": 0, "mode": "ally", "skipped": True}

    if not _open_tavern(adb, win, target_tab="ally_quests", debug=debug):
        return {"assists": 0, "mode": "ally", "error": "tavern_open_failed"}

    # Delegate to existing ally quests flow
    ally_result = run_ally_quests_flow(adb, win, debug=debug)

    # Exit tavern
    return_to_base_view(adb, win, debug=debug, respect_idle=False)

    assists = ally_result.get("assists", 0)
    logger.info(f"ALLY mode complete: {assists} assists")
    return {"assists": assists, "mode": "ally", "skipped": False}


def handle_bounty_quest_dialog(
    adb: ADBHelper,
    win: WindowsScreenshotHelper,
    debug: bool = False,
    context_tag: str = "dispatch",
) -> bool:
    """
    Handle the Bounty Quest dialog that appears after clicking Go on a gold scroll quest (COLOR matching).

    Flow:
    1. Verify Bounty Quest dialog is open (check title)
    2. Click Auto Dispatch button
    3. Click Proceed button

    Returns True if dialog was handled, False if not in dialog.
    """
    frame = win.get_screenshot_cv2()
    if debug:
        _save_debug(frame, f"{context_tag}_bounty_check")

    # Check for Bounty Quest title (COLOR)
    bounty_title_template = load_template_color(BOUNTY_QUEST_TITLE_TEMPLATE)
    result = cv2.matchTemplate(frame, bounty_title_template, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)

    if min_val > BOUNTY_QUEST_THRESHOLD:
        logger.debug(f"Bounty Quest dialog not detected (score={min_val:.4f})")
        _save_debug(frame, f"{context_tag}_bounty_not_found_s{int(min_val * 10000)}")
        return False

    logger.info(f"Bounty Quest dialog detected (score={min_val:.4f})")
    if debug:
        _save_debug(frame, f"{context_tag}_bounty_found_s{int(min_val * 10000)}")

    # Click Auto Dispatch
    logger.info(f"Clicking Auto Dispatch at {AUTO_DISPATCH_CLICK}")
    adb.tap(*AUTO_DISPATCH_CLICK, source="flow:tavern_quest:auto_dispatch")
    time.sleep(0.8)
    if debug:
        _save_debug(win.get_screenshot_cv2(), f"{context_tag}_after_auto_dispatch")

    # Click Proceed
    logger.info(f"Clicking Proceed at {PROCEED_CLICK}")
    adb.tap(*PROCEED_CLICK, source="flow:tavern_quest:proceed")
    time.sleep(0.8)
    if debug:
        _save_debug(win.get_screenshot_cv2(), f"{context_tag}_after_proceed")

    logger.info("Bounty Quest started")
    return True


# =============================================================================
# Scheduled Claim Flow (pre-position and poll)
# =============================================================================

def poll_for_claim_button(adb: ADBHelper, win: WindowsScreenshotHelper, ocr: OCRClient, debug: bool = False) -> int:
    """
    Poll for Claim button every 0.5s. Clicks immediately when found (COLOR matching).

    Exit conditions:
    - Claim found → click it, dismiss popup, return to polling (may have more claims)
    - No timer < 30s visible → exit immediately

    Returns:
        Number of claims made
    """
    claim_template = load_template_color(CLAIM_BUTTON_TEMPLATE)
    logger.info(f"[POLL] Starting claim poll, template size: {claim_template.shape[1]}x{claim_template.shape[0]}")
    claims_made = 0
    poll_count = 0

    # Save initial state
    frame = win.get_screenshot_cv2()
    _save_debug(frame, "poll_00_initial")

    while True:
        frame = win.get_screenshot_cv2()
        poll_count += 1

        # Check for Claim button FIRST (COLOR)
        claim_buttons, best_score = find_claim_buttons_with_score(frame, claim_template)
        if claim_buttons:
            x, y = claim_buttons[0]
            logger.info(f"[POLL] Claim button found at ({x}, {y}) after {poll_count} polls, score={best_score:.4f}, clicking!")
            _save_debug(frame, f"poll_{claims_made+1:02d}_FOUND_at_{x}_{y}")
            adb.tap(x, y, source="flow:tavern_quest:poll_claim")
            claims_made += 1
            time.sleep(0.5)  # Wait for rewards popup to appear

            # Dismiss popup by polling until we see Tavern tabs again
            logger.info("[POLL] Waiting for popup to dismiss...")
            if not wait_for_tavern_tabs(adb, win, max_attempts=10, debug=debug):
                # Exited Tavern or couldn't dismiss - abort
                logger.warning("[POLL] Could not return to Tavern after claim, aborting")
                frame = win.get_screenshot_cv2()
                _save_debug(frame, f"poll_{claims_made:02d}_POPUP_STUCK")
                return claims_made

            # Save state after returning
            frame = win.get_screenshot_cv2()
            _save_debug(frame, f"poll_{claims_made:02d}_after_popup")
            continue  # Keep polling for more claims

        # Check for timers < 30s - exit if none (COLOR)
        timers = find_quest_timers(frame, ocr=ocr)
        has_short_timer = any(t['seconds'] is not None and t['seconds'] < SHORT_TIMER_THRESHOLD for t in timers)

        timer_strs = [f"{t['timer_text']}({t['seconds']}s)" for t in timers if t['seconds'] is not None]
        logger.info(f"[POLL] #{poll_count}: No claim (best_score={best_score:.4f}), timers: {timer_strs}, has_short={has_short_timer}")

        if not has_short_timer:
            logger.info(f"[POLL] No timers < {SHORT_TIMER_THRESHOLD}s, exiting poll loop. Claims made: {claims_made}")
            _save_debug(frame, f"poll_EXIT_no_short_timer")
            return claims_made

        time.sleep(CLAIM_POLL_INTERVAL)


def tavern_quest_claim_flow(adb: ADBHelper, win: WindowsScreenshotHelper | None = None, ocr: OCRClient | None = None, debug: bool = False) -> dict[str, Any]:
    """
    DEPRECATED: Use run_tavern_quest_flow instead.

    run_tavern_quest_flow does everything this function does PLUS:
    - Go button clicking for gold scroll quests
    - Go button clicking for question mark quests
    - Double-pass strategy to avoid UI glitches missing claims
    - Timer scanning for scheduler

    This function is kept for backward compatibility but should not be used.
    """
    logger.warning("tavern_quest_claim_flow is DEPRECATED - use run_tavern_quest_flow instead")
    return run_tavern_quest_flow(adb, win, debug=debug)


def run_my_quests_flow(adb: ADBHelper, win: WindowsScreenshotHelper, ocr: OCRClient | None = None, debug: bool = False) -> dict[str, Any]:
    """
    Claim ONE completed quest OR click Go for gold scroll quests.

    After clicking a Claim button, immediately exits (returns with claimed=True)
    so the caller can restart the flow fresh. This avoids UI display glitches
    that can cause missed claims.

    Also scans quest timers and returns completion times for scheduler update.

    Returns dict with:
        - claims: number of claims made (0 or 1)
        - go_clicks: number of Go clicks made
        - claimed: True if a claim was made (caller should restart flow)
        - completions: list of datetime objects for quest completion times
    """
    # Initialize OCR for timer scanning
    if ocr is None:
        from utils.ocr_client import OCRClient
        ocr = OCRClient()

    logger.info("Starting My Quests flow")

    # Load templates (COLOR)
    _my_quests_active_template = load_template_color(MY_QUESTS_ACTIVE_TEMPLATE)
    claim_template = load_template_color(CLAIM_BUTTON_TEMPLATE)

    total_claims = 0
    total_go_clicks = 0
    no_action_count = 0
    max_no_action = 2  # Stop after 2 consecutive scrolls with no actions
    all_completions: list[datetime] = []  # Accumulate timer completions for scheduler
    frames_for_ocr: list[tuple[npt.NDArray[Any], datetime]] = []  # (frame, screenshot_time) for deferred OCR

    def _process_deferred_ocr() -> None:
        """Process all saved frames for OCR and add to all_completions."""
        nonlocal all_completions
        if frames_for_ocr:
            logger.info(f"Processing {len(frames_for_ocr)} frames for timer OCR...")
            for saved_frame, frame_time in frames_for_ocr:
                completions = scan_quest_timers(saved_frame, ocr, screenshot_time=frame_time)
                if completions:
                    all_completions.extend(completions)
            if all_completions:
                logger.info(f"Found {len(all_completions)} timer completion(s)")

    iteration = 0
    while no_action_count < max_no_action:
        iteration += 1
        # Take screenshot with timestamp for accurate timer calculation
        screenshot_time = datetime.now()
        frame = win.get_screenshot_cv2()
        _save_debug(frame, f"myq_iter{iteration:02d}_scan")

        # Save frame + timestamp for deferred OCR BEFORE checking for actions
        # This ensures we capture all timer data regardless of whether we find claim/go buttons
        frames_for_ocr.append((frame.copy(), screenshot_time))

        # FIRST: Verify we're in Tavern (COLOR)
        in_tavern, active_tab = is_in_tavern(frame)
        logger.info(f"[MyQ iter {iteration}] in_tavern={in_tavern}, active_tab={active_tab}")
        if not in_tavern:
            logger.warning("Not in Tavern! Aborting My Quests flow.")
            _save_debug(frame, f"myq_iter{iteration:02d}_NOT_IN_TAVERN")
            _process_deferred_ocr()
            return {"claims": total_claims, "go_clicks": total_go_clicks, "claimed": total_claims > 0, "completions": all_completions}

        # Check if My Quests tab is active
        if active_tab != "my_quests":
            logger.info(f"My Quests tab not active (active={active_tab}), clicking to switch")
            adb.tap(*MY_QUESTS_CLICK, source="flow:tavern_quest:switch_my_quests")
            time.sleep(0.5)
            continue

        # Find Claim buttons (COLOR)
        claim_buttons = find_claim_buttons(frame, claim_template)

        # Find Go buttons for gold scroll quests (COLOR)
        gold_scroll_go_buttons = find_gold_scroll_go_buttons(frame)

        # Find Go buttons for question mark quests (only if not Day 6 and allowed) (COLOR)
        question_mark_go_buttons = []
        if _should_start_question_mark_quests():
            question_mark_go_buttons = find_question_mark_go_buttons(frame)

        logger.info(f"[MyQ iter {iteration}] Found: {len(claim_buttons)} Claim, "
                    f"{len(gold_scroll_go_buttons)} Gold Go, "
                    f"{len(question_mark_go_buttons)} QMark Go")

        # Priority 1: Click Claim buttons first (no time restriction)
        if claim_buttons:
            x, y = claim_buttons[0]
            logger.info(f"Clicking Claim at ({x}, {y})")
            _save_debug(frame, f"myq_iter{iteration:02d}_PRE_CLAIM_at_{x}_{y}")
            adb.tap(x, y, source="flow:tavern_quest:claim_button")
            time.sleep(0.5)  # Wait for rewards popup to appear
            total_claims += 1
            no_action_count = 0  # Reset scroll counter

            # DEBUG: Screenshot after claim click
            frame = win.get_screenshot_cv2()
            _save_debug(frame, f"myq_iter{iteration:02d}_POST_CLAIM_after_tap")

            # Dismiss popup by polling until we see Tavern tabs again
            logger.info("Waiting for popup to dismiss...")
            if not wait_for_tavern_tabs(adb, win, max_attempts=10, debug=debug):
                # Exited Tavern or couldn't dismiss - abort
                logger.warning("Could not return to Tavern after claim, aborting")
                _process_deferred_ocr()
                return {"claims": total_claims, "go_clicks": total_go_clicks, "claimed": True, "completions": all_completions}

            # Continue loop to re-scan for more claims
            continue

        # Priority 2: Click Go for gold scroll quests (time gated)
        if gold_scroll_go_buttons and _is_after_quest_start_time():
            no_action_count = 0
            x, y = gold_scroll_go_buttons[0]
            logger.info(f"Clicking Go for gold scroll quest at ({x}, {y})")
            adb.tap(x, y, source="flow:tavern_quest:go_gold_scroll")
            time.sleep(1.0)  # Wait for Bounty Quest dialog
            total_go_clicks += 1

            # DEBUG: Screenshot after Go click
            frame = win.get_screenshot_cv2()
            _save_debug(frame, f"myq_iter{iteration:02d}_after_go_gold")

            # Handle Bounty Quest dialog (Auto Dispatch + Proceed)
            if handle_bounty_quest_dialog(adb, win, debug):
                logger.info("Bounty Quest started successfully")
                # Dialog dismissed, we're back in tavern - continue loop
                time.sleep(0.5)
                continue
            else:
                # Dialog not detected - might have navigated elsewhere
                logger.warning("Bounty Quest dialog not detected after clicking Go")
                _process_deferred_ocr()
                return {"claims": total_claims, "go_clicks": total_go_clicks, "claimed": False, "completions": all_completions}
        elif gold_scroll_go_buttons:
            # Gold scroll quests found but before start time
            logger.debug("Gold scroll Go buttons found but before quest start time - skipping")

        # Priority 3: Click Go for question mark quests (time gated, Day 6 excluded)
        if question_mark_go_buttons and _is_after_quest_start_time():
            no_action_count = 0
            x, y = question_mark_go_buttons[0]
            logger.info(f"Clicking Go for question mark quest at ({x}, {y})")
            adb.tap(x, y, source="flow:tavern_quest:go_question_mark")
            time.sleep(1.0)  # Wait for Bounty Quest dialog
            total_go_clicks += 1

            # DEBUG: Screenshot after Go click
            frame = win.get_screenshot_cv2()
            _save_debug(frame, f"myq_iter{iteration:02d}_after_go_qmark")

            # Handle Bounty Quest dialog (Auto Dispatch + Proceed)
            if handle_bounty_quest_dialog(adb, win, debug):
                logger.info("Question mark Bounty Quest started successfully")
                # Dialog dismissed, we're back in tavern - continue loop
                time.sleep(0.5)
                continue
            else:
                # Dialog not detected - might have navigated elsewhere
                logger.warning("Bounty Quest dialog not detected after clicking Go")
                _process_deferred_ocr()
                return {"claims": total_claims, "go_clicks": total_go_clicks, "claimed": False, "completions": all_completions}
        elif question_mark_go_buttons:
            # Question mark quests found but before start time
            logger.debug("Question mark Go buttons found but before quest start time - skipping")

        # RETRY: If no claim buttons found, retry a couple times (UI may still be rendering)
        if not claim_buttons:
            for retry in range(2):
                time.sleep(0.2)
                retry_frame = win.get_screenshot_cv2()
                claim_buttons = find_claim_buttons(retry_frame, claim_template)
                if claim_buttons:
                    logger.info(f"[MyQ iter {iteration}] Found {len(claim_buttons)} Claim on retry {retry+1}")
                    # Process claim - click it
                    x, y = claim_buttons[0]
                    logger.info(f"Clicking Claim at ({x}, {y}) [retry]")
                    _save_debug(retry_frame, f"myq_iter{iteration:02d}_PRE_CLAIM_retry{retry+1}_at_{x}_{y}")
                    adb.tap(x, y, source="flow:tavern_quest:claim_button_retry")
                    time.sleep(0.5)
                    total_claims += 1
                    no_action_count = 0
                    frame = win.get_screenshot_cv2()
                    _save_debug(frame, f"myq_iter{iteration:02d}_POST_CLAIM_retry{retry+1}")
                    if not wait_for_tavern_tabs(adb, win, max_attempts=10, debug=debug):
                        _process_deferred_ocr()
                        return {"claims": total_claims, "go_clicks": total_go_clicks, "claimed": True, "completions": all_completions}
                    break
            # If claim found on retry, continue to re-scan
            if claim_buttons:
                continue

        # No actions found - scroll
        logger.info("No actionable buttons found (Claim/Go), scrolling...")
        no_action_count += 1

        # Scroll down
        adb.swipe(SCROLL_X, SCROLL_START_Y, SCROLL_X, SCROLL_END_Y, SCROLL_DURATION)
        time.sleep(0.5)

        # DEBUG: Screenshot after scroll
        frame = win.get_screenshot_cv2()
        _save_debug(frame, f"myq_iter{iteration:02d}_after_scroll")

    # Deferred OCR: Process all collected frames for timer scanning
    _process_deferred_ocr()

    logger.info(f"My Quests flow complete. Claims: {total_claims}, Go clicks: {total_go_clicks}, Timers: {len(all_completions)}")
    return {"claims": total_claims, "go_clicks": total_go_clicks, "claimed": False, "completions": all_completions}


def _is_ally_assists_maxed_today() -> bool:
    """Check if ally assists are already maxed for today (from stored state)."""
    from utils.current_state import is_tavern_assists_maxed
    return is_tavern_assists_maxed()


def _update_tavern_counters(assist_current: int, assist_max: int = 5,
                            plunder_current: int | None = None, plunder_max: int = 5) -> None:
    """Update tavern quest counters in stored state."""
    from utils.current_state import update_tavern_quests
    update_tavern_quests(assist_current, assist_max, plunder_current, plunder_max)


def run_ally_quests_flow(adb: ADBHelper, win: WindowsScreenshotHelper, debug: bool = False) -> dict[str, Any]:
    """
    Assist gold 5-star ally quests.

    Logic:
    1. Check if already maxed today (skip entirely if so)
    2. Read Assist Allies counter
    3. If >= 5, mark maxed and skip
    4. Click Ally Quests tab
    5. Find gold 5-star quests and click assist
    6. Repeat until maxed or no targets

    Returns dict with:
        - assists: number of assists made
        - reason: 'maxed_today', 'maxed', 'no_targets', 'completed'
    """
    from utils.tavern_counter_reader import read_assist_counter, read_plunder_counter
    from utils.ally_quest_scanner import (
        load_templates as load_ally_templates,
        find_all_buttons,
        detect_quest_color,
        count_stars,
    )

    MIN_STARS = 4  # Assist gold 4+ star quests
    ASSIST_BUTTON_CENTER_OFFSET = (125, 50)  # Center of 249x100 assist button

    logger.info("Starting Ally Quests flow")

    # Take screenshot and verify tavern with retries
    in_tavern = False
    active_tab = None
    for retry in range(3):
        frame = win.get_screenshot_cv2()
        in_tavern, active_tab = is_in_tavern(frame)
        if in_tavern:
            break
        if retry < 2:
            logger.info(f"[ALLY] Tavern detection retry {retry + 1}/3")
            time.sleep(0.3)

    _save_debug(frame, "ally_00_initial")

    if not in_tavern:
        _save_debug(frame, "ally_TAVERN_DETECTION_FAILED")
        logger.warning("Not in Tavern for Ally Quests flow after 3 retries")
        return {"assists": 0, "reason": "not_in_tavern"}

    # Check each counter SEPARATELY - only OCR if not already maxed for today
    from utils.current_state import is_tavern_assists_maxed, is_tavern_plunder_maxed, get_tavern_quests

    assists_already_maxed = is_tavern_assists_maxed()
    plunder_already_maxed = is_tavern_plunder_maxed()

    # Get cached values for counters that are already maxed
    cached = get_tavern_quests()
    assist_current, assist_max = None, 5
    plunder_current, plunder_max = None, 5

    if assists_already_maxed:
        # Use cached value, skip OCR
        cached_assist = cached.get("assist_allies", {})
        assist_current = cached_assist.get("current", 5)
        assist_max = cached_assist.get("max", 5)
        logger.info(f"Assist Allies: {assist_current}/{assist_max} (cached, maxed)")
    else:
        # OCR fresh value
        assist_counter = read_assist_counter(frame)
        if assist_counter is None:
            logger.warning("Could not read assist counter")
            return {"assists": 0, "reason": "counter_read_failed"}
        assist_current, assist_max = assist_counter
        logger.info(f"Assist Allies: {assist_current}/{assist_max} (fresh OCR)")

    if plunder_already_maxed:
        # Use cached value, skip OCR
        cached_plunder = cached.get("plunder_others", {})
        plunder_current = cached_plunder.get("current", 5)
        plunder_max = cached_plunder.get("max", 5)
        logger.info(f"Plunder Others: {plunder_current}/{plunder_max} (cached, maxed)")
    else:
        # OCR fresh value
        plunder_counter = read_plunder_counter(frame)
        plunder_current = plunder_counter[0] if plunder_counter else None
        plunder_max = plunder_counter[1] if plunder_counter else 5
        logger.info(f"Plunder Others: {plunder_current}/{plunder_max} (fresh OCR)")

    # Update state with both counters
    _update_tavern_counters(assist_current, assist_max, plunder_current, plunder_max)

    if assist_current >= assist_max:
        logger.info("Already at max assists for today")
        return {"assists": 0, "reason": "maxed"}

    # Click Ally Quests tab
    logger.info("Clicking Ally Quests tab")
    adb.tap(*ALLY_QUESTS_CLICK, source="flow:tavern_quest:ally_tab")
    time.sleep(1.0)

    # Load ally quest templates
    ally_templates = load_ally_templates()
    assists_made = 0

    # Assist loop
    for iteration in range(assist_max - assist_current):
        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _save_debug(frame, f"ally_{iteration+1:02d}_scan")

        # Find assist buttons
        buttons = find_all_buttons(
            frame_gray, ally_templates.get("assist"), ally_templates.get("clock")
        )

        # Filter for gold 4+ star quests with assist buttons
        target = None
        logger.info(f"Found {len(buttons)} buttons total")
        for btn in buttons:
            color = detect_quest_color(frame_gray, btn["x"], btn["y"], ally_templates)
            stars = count_stars(frame_gray, btn["x"], btn["y"], ally_templates)

            # Always log ALL quests found
            logger.info(f"  Quest Y={btn['y']}: type={btn['type']}, color={color}, stars={stars}")

            if btn["type"] != "assist":
                continue

            if color == "gold" and stars >= MIN_STARS:
                target = btn
                logger.info(f"  -> TARGET: gold {stars}-star quest at Y={btn['y']}")
                break

        if target is None:
            logger.info(f"No gold {MIN_STARS}+ star quests with assist button found")
            break

        # Click the assist button center
        click_x = target["x"] + ASSIST_BUTTON_CENTER_OFFSET[0]
        click_y = target["y"] + ASSIST_BUTTON_CENTER_OFFSET[1]

        logger.info(f"Clicking assist at ({click_x}, {click_y})")
        adb.tap(click_x, click_y, source="flow:tavern_quest:ally_assist")
        assists_made += 1
        time.sleep(0.5)

        # Wait for popup to dismiss
        if not wait_for_tavern_tabs(adb, win, max_attempts=10, debug=debug):
            logger.warning("Could not return to Tavern after assist")
            break

        # Re-read counter to check if maxed and update state
        frame = win.get_screenshot_cv2()
        assist_counter = read_assist_counter(frame)
        if assist_counter:
            assist_current, assist_max = assist_counter
            _update_tavern_counters(assist_current, assist_max, plunder_current, plunder_max)
            if assist_current >= assist_max:
                logger.info("Reached max assists")
                break

    reason = "maxed" if assist_counter and assist_counter[0] >= assist_counter[1] else "completed"
    logger.info(f"Ally Quests flow complete. Assists: {assists_made}, reason: {reason}")
    return {"assists": assists_made, "reason": reason}


def run_tavern_quest_flow(
    adb: ADBHelper | None = None,
    win: WindowsScreenshotHelper | None = None,
    ocr: OCRClient | None = None,
    mode: str = "claim",
    debug: bool = False
) -> dict[str, Any]:
    """
    Main tavern quest flow with mode-based operation.

    Modes:
        "claim"    - Claim buttons with top/bottom pass and OCR timer-gated wait, no Go buttons
        "scan"     - Scroll and OCR timers only, no clicking
        "dispatch" - Click Go buttons to start quests, no OCR, no Claims
        "ally"     - Assist ally quests, skips if already 5/5

    Args:
        adb: ADBHelper instance (created if None)
        win: WindowsScreenshotHelper instance (created if None)
        ocr: OCRClient instance (created if None, only needed for scan mode)
        mode: Operation mode - "claim", "scan", "dispatch", or "ally"
        debug: Enable debug screenshots

    Returns:
        Dict with mode-specific results
    """
    from utils.adb_helper import ADBHelper as ADBHelperClass
    from utils.windows_screenshot_helper import WindowsScreenshotHelper as WinSSHelper

    if adb is None:
        adb = ADBHelperClass()
    if win is None:
        win = WinSSHelper()

    logger.info(f"Tavern Quest Flow - mode={mode}")

    if mode == "claim":
        result = _run_claim_mode(adb, win, debug=debug)
        # Record claims to scheduler for tracking
        claims = result.get("claims", 0)
        if claims > 0:
            from utils.scheduler import DaemonScheduler
            scheduler = DaemonScheduler()
            scheduler.record_tavern_claims(claims)
        return result

    elif mode == "scan":
        if ocr is None:
            from utils.ocr_client import OCRClient
            ocr = OCRClient()
        return _run_scan_mode(adb, win, ocr, debug=debug)

    elif mode == "dispatch":
        return _run_dispatch_mode(adb, win, debug=debug)

    elif mode == "ally":
        return _run_ally_mode(adb, win, debug=debug)

    else:
        logger.error(f"Unknown tavern mode: {mode}")
        return {"error": f"unknown_mode:{mode}"}


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    parser = argparse.ArgumentParser(description="Tavern Quest Flow")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--mode", choices=["claim", "scan", "dispatch", "ally"],
                        default="claim", help="Flow mode (default: claim)")
    args = parser.parse_args()

    from utils.adb_helper import ADBHelper
    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    results = run_tavern_quest_flow(adb, win, mode=args.mode, debug=args.debug)
    print(f"Results: {results}")
