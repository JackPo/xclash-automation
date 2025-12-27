"""
Tavern Quest Flow - Claim completed quests and start gold scroll quests.

Entry: Assumes Tavern is already open.
Exit: Back to base view.

Tab Detection:
- tavern_my_quests_active_4k.png → My Quests is active
- tavern_ally_quests_active_4k.png → Ally Quests is active

My Quests:
- Column-restricted Claim button detection (X: 2100-2500, full Y)
- Click each Claim button found
- Find Gold Scroll Lv4 rewards and click their Go buttons
- Scroll and repeat until no more actions available
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

_script_dir = Path(__file__).parent.parent.parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

import cv2
import numpy as np
import time
import logging

from utils.adb_helper import ADBHelper
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.return_to_base_view import return_to_base_view

logger = logging.getLogger(__name__)

# Timing constants
CLAIM_POLL_INTERVAL = 0.5  # seconds between polls
PRE_ARRIVAL_BUFFER = 15    # seconds before completion to navigate to tavern
SHORT_TIMER_THRESHOLD = 30 # seconds - timer considered "about to complete"

# Template paths
TEMPLATE_DIR = "templates/ground_truth"
MY_QUESTS_ACTIVE_TEMPLATE = f"{TEMPLATE_DIR}/tavern_my_quests_active_4k.png"
ALLY_QUESTS_ACTIVE_TEMPLATE = f"{TEMPLATE_DIR}/tavern_ally_quests_active_4k.png"
CLAIM_BUTTON_TEMPLATE = f"{TEMPLATE_DIR}/claim_button_tavern_4k.png"
GOLD_SCROLL_LV4_TEMPLATE = f"{TEMPLATE_DIR}/gold_scroll_lv4_4k.png"
GO_BUTTON_TEMPLATE = f"{TEMPLATE_DIR}/go_button_4k.png"
QUESTION_MARK_TILE_TEMPLATE = f"{TEMPLATE_DIR}/quest_question_tile_4k.png"

# Bounty Quest dialog templates
BOUNTY_QUEST_TITLE_TEMPLATE = f"{TEMPLATE_DIR}/bounty_quest_title_4k.png"
AUTO_DISPATCH_BUTTON_TEMPLATE = f"{TEMPLATE_DIR}/auto_dispatch_button_4k.png"
PROCEED_BUTTON_TEMPLATE = f"{TEMPLATE_DIR}/proceed_button_4k.png"

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

# Gold scroll and Go button detection
GOLD_SCROLL_THRESHOLD = 0.003  # Very strict - gold scroll Lv4 is unique
GO_BUTTON_THRESHOLD = 0.02
GO_BUTTON_X_START = 2100  # Go buttons are in same column as Claim
GO_BUTTON_X_END = 2500
Y_TOLERANCE = 80  # Y tolerance for matching scroll with Go button on same row

# Question mark tile detection
QUESTION_MARK_THRESHOLD = 0.02  # Similar to gold scroll

# Scroll parameters - grab center and drag up to scroll down
SCROLL_START_Y = 1400  # Center of quest list
SCROLL_END_Y = 800     # Drag to top to scroll content down (reveal more below)
SCROLL_X = 1920        # Center X
SCROLL_DURATION = 500  # ms - longer for smoother scroll


def load_template_gray(path: str) -> np.ndarray:
    """Load template as grayscale."""
    template = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if template is None:
        raise FileNotFoundError(f"Template not found: {path}")
    return template


# =============================================================================
# Time and VS Day Helpers
# =============================================================================

def _is_after_quest_start_time() -> bool:
    """
    Check if current time is in the allowed quest start window.

    Allowed window: 10:30 PM Pacific until server reset (6 PM Pacific next day)
    Blocked window: 6 PM Pacific to 10:30 PM Pacific (4.5 hours)

    This means quests can be started from 10:30 PM through the night and next day
    until 6 PM when the server resets.
    """
    try:
        import pytz
        from config import TAVERN_QUEST_START_HOUR, TAVERN_QUEST_START_MINUTE, TAVERN_SERVER_RESET_HOUR
    except ImportError:
        # Fallback defaults if config not available
        TAVERN_QUEST_START_HOUR = 22
        TAVERN_QUEST_START_MINUTE = 30
        TAVERN_SERVER_RESET_HOUR = 18

    try:
        pacific = pytz.timezone('America/Los_Angeles')
        now = datetime.now(pacific)

        # Blocked window: from server reset (18:00) to quest start time (22:30)
        # If hour is between reset and start hour, we're blocked
        if TAVERN_SERVER_RESET_HOUR <= now.hour < TAVERN_QUEST_START_HOUR:
            return False
        # If hour equals start hour but before start minute, still blocked
        if now.hour == TAVERN_QUEST_START_HOUR and now.minute < TAVERN_QUEST_START_MINUTE:
            return False

        # All other times are allowed (22:30 to 17:59 next day)
        return True
    except Exception as e:
        logger.warning(f"Time check failed: {e}, defaulting to True")
        return True  # Fail open - allow quest starts if time check fails


def _should_start_question_mark_quests() -> bool:
    """
    Check if question mark quests should be started (not on Day 6).

    Day 6 is the day before chest opening (Day 7), so we save question mark
    rewards for the chest opening day to maximize rewards.
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

def _get_scheduler():
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


def find_quest_timers(frame: np.ndarray, frame_gray: np.ndarray, ocr=None) -> list[dict]:
    """
    Find all quest timers in the current view.

    Returns list of dicts with:
    - clock_pos: (x, y) position of clock icon
    - timer_region: (x, y, w, h) region of timer text
    - timer_text: OCR'd timer string (e.g., "01:57:17")
    - seconds: parsed time in seconds (or None if parsing failed)
    """
    clock_template = load_template_gray(QUEST_CLOCK_ICON_TEMPLATE)
    result = cv2.matchTemplate(frame_gray, clock_template, cv2.TM_SQDIFF_NORMED)

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
    filtered = []
    for x, y, score in matches:
        is_distinct = True
        for fx, fy, _ in filtered:
            if abs(x - fx) < 50 and abs(y - fy) < 50:
                is_distinct = False
                break
        if is_distinct:
            filtered.append((x, y, score))

    timers = []
    for clock_x, clock_y, _ in filtered:
        timer_x = clock_x + TIMER_OFFSET_X
        timer_y = clock_y
        timer_region = (timer_x, timer_y, TIMER_WIDTH, TIMER_HEIGHT)

        timer_text = None
        seconds = None

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


def scan_quest_timers(frame: np.ndarray, ocr) -> list[datetime]:
    """
    Scan tavern screen, OCR all timers, calculate completion times.
    Does NOT save - caller should accumulate and save once at the end.

    Args:
        frame: Screenshot of tavern screen (BGR numpy array)
        ocr: OCR client instance (e.g., OCRClient)

    Returns:
        List of datetime objects for when each quest will complete
    """
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    timers = find_quest_timers(frame, frame_gray, ocr=ocr)
    now = datetime.now()

    completions = []
    for t in timers:
        if t['seconds'] is not None:
            completion_time = now + timedelta(seconds=t['seconds'])
            completions.append(completion_time)
            logger.info(f"Quest timer: {t['timer_text']} -> completes at {completion_time.strftime('%H:%M:%S')}")

    return completions


def scan_and_schedule_quest_completions(frame: np.ndarray, ocr) -> list[datetime]:
    """
    Scan tavern screen, OCR all timers, calculate completion times, and save.
    Use scan_quest_timers() if you need to accumulate across multiple screens.

    Args:
        frame: Screenshot of tavern screen (BGR numpy array)
        ocr: OCR client instance (e.g., OCRClient)

    Returns:
        List of datetime objects for when each quest will complete
    """
    completions = scan_quest_timers(frame, ocr)
    save_quest_schedule(completions)
    return completions


def check_tab_active(frame_gray: np.ndarray, template: np.ndarray, region: tuple) -> tuple[bool, float]:
    """Check if a tab is active by matching template in region."""
    x, y, w, h = region
    roi = frame_gray[y:y+h, x:x+w]

    # Resize template if needed
    if roi.shape != template.shape:
        template_resized = cv2.resize(template, (roi.shape[1], roi.shape[0]))
    else:
        template_resized = template

    result = cv2.matchTemplate(roi, template_resized, cv2.TM_SQDIFF_NORMED)
    score = result[0, 0]

    return score < 0.02, score  # Active if score < 0.02


def find_claim_buttons(frame_gray: np.ndarray, template: np.ndarray) -> list[tuple[int, int]]:
    """
    Find all Claim buttons by scanning column (X: 2100-2500, full Y).
    Returns list of (x, y) click positions.
    """
    # Extract column ROI
    column_roi = frame_gray[:, CLAIM_X_START:CLAIM_X_END]

    result = cv2.matchTemplate(column_roi, template, cv2.TM_SQDIFF_NORMED)

    # Find all matches below threshold
    locations = np.where(result < CLAIM_THRESHOLD)

    if len(locations[0]) == 0:
        return []

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
    filtered = []
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

    return filtered


def find_gold_scroll_go_buttons(frame_gray: np.ndarray) -> list[tuple[int, int]]:
    """
    Find Go buttons for quests that have Gold Scroll Lv4 rewards.

    Logic:
    1. Find all Gold Scroll Lv4 icons in the frame
    2. Find all Go buttons in the rightmost column
    3. Match scrolls with Go buttons on the same Y-axis (within tolerance)
    4. Return click positions for matched Go buttons
    """
    gold_scroll_template = load_template_gray(GOLD_SCROLL_LV4_TEMPLATE)
    go_button_template = load_template_gray(GO_BUTTON_TEMPLATE)

    # Find all gold scroll positions
    scroll_result = cv2.matchTemplate(frame_gray, gold_scroll_template, cv2.TM_SQDIFF_NORMED)
    scroll_locations = np.where(scroll_result < GOLD_SCROLL_THRESHOLD)

    scroll_h, scroll_w = gold_scroll_template.shape[:2]
    scrolls = []
    for y, x in zip(scroll_locations[0], scroll_locations[1]):
        score = scroll_result[y, x]
        center_y = y + scroll_h // 2
        scrolls.append((x, center_y, score))

    # Non-maximum suppression for scrolls (min spacing 100px)
    scrolls.sort(key=lambda s: s[2])  # Sort by score
    filtered_scrolls = []
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

    logger.debug(f"Found {len(filtered_scrolls)} Gold Scroll Lv4 icons")

    # Find all Go buttons in the right column
    column_roi = frame_gray[:, GO_BUTTON_X_START:GO_BUTTON_X_END]
    go_result = cv2.matchTemplate(column_roi, go_button_template, cv2.TM_SQDIFF_NORMED)
    go_locations = np.where(go_result < GO_BUTTON_THRESHOLD)

    go_h, go_w = go_button_template.shape[:2]
    go_buttons = []
    for y, x in zip(go_locations[0], go_locations[1]):
        score = go_result[y, x]
        # Convert to full frame coords
        full_x = GO_BUTTON_X_START + x + go_w // 2
        center_y = y + go_h // 2
        go_buttons.append((full_x, center_y, score))

    # Non-maximum suppression for Go buttons
    go_buttons.sort(key=lambda g: g[2])
    filtered_go = []
    for x, y, score in go_buttons:
        is_distinct = True
        for fx, fy, _ in filtered_go:
            if abs(y - fy) < 80:
                is_distinct = False
                break
        if is_distinct:
            filtered_go.append((x, y, score))

    if not filtered_go:
        return []

    logger.debug(f"Found {len(filtered_go)} Go buttons")

    # Match scrolls with Go buttons on same row (Y within tolerance)
    matched_go_buttons = []
    for scroll_x, scroll_y, _ in filtered_scrolls:
        for go_x, go_y, _ in filtered_go:
            if abs(scroll_y - go_y) <= Y_TOLERANCE:
                # Found a match! Add Go button click position
                matched_go_buttons.append((go_x, go_y))
                logger.debug(f"Matched: Scroll Y={scroll_y} with Go Y={go_y}")
                break  # One Go per scroll

    # Sort by Y position (top to bottom)
    matched_go_buttons.sort(key=lambda b: b[1])

    return matched_go_buttons


def find_question_mark_go_buttons(frame_gray: np.ndarray) -> list[tuple[int, int]]:
    """
    Find Go buttons for quests that have question mark reward tiles.

    Logic (same as gold scroll):
    1. Find all question mark tiles in the frame
    2. Find all Go buttons in the rightmost column
    3. Match tiles with Go buttons on the same Y-axis (within tolerance)
    4. Return click positions for matched Go buttons
    """
    try:
        question_mark_template = load_template_gray(QUESTION_MARK_TILE_TEMPLATE)
    except FileNotFoundError:
        logger.warning("Question mark tile template not found")
        return []

    go_button_template = load_template_gray(GO_BUTTON_TEMPLATE)

    # Find all question mark tile positions
    tile_result = cv2.matchTemplate(frame_gray, question_mark_template, cv2.TM_SQDIFF_NORMED)
    tile_locations = np.where(tile_result < QUESTION_MARK_THRESHOLD)

    tile_h, tile_w = question_mark_template.shape[:2]
    tiles = []
    for y, x in zip(tile_locations[0], tile_locations[1]):
        score = tile_result[y, x]
        center_y = y + tile_h // 2
        tiles.append((x, center_y, score))

    # Non-maximum suppression for tiles (min spacing 100px)
    tiles.sort(key=lambda t: t[2])  # Sort by score
    filtered_tiles = []
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

    # Find all Go buttons in the right column
    column_roi = frame_gray[:, GO_BUTTON_X_START:GO_BUTTON_X_END]
    go_result = cv2.matchTemplate(column_roi, go_button_template, cv2.TM_SQDIFF_NORMED)
    go_locations = np.where(go_result < GO_BUTTON_THRESHOLD)

    go_h, go_w = go_button_template.shape[:2]
    go_buttons = []
    for y, x in zip(go_locations[0], go_locations[1]):
        score = go_result[y, x]
        # Convert to full frame coords
        full_x = GO_BUTTON_X_START + x + go_w // 2
        center_y = y + go_h // 2
        go_buttons.append((full_x, center_y, score))

    # Non-maximum suppression for Go buttons
    go_buttons.sort(key=lambda g: g[2])
    filtered_go = []
    for x, y, score in go_buttons:
        is_distinct = True
        for fx, fy, _ in filtered_go:
            if abs(y - fy) < 80:
                is_distinct = False
                break
        if is_distinct:
            filtered_go.append((x, y, score))

    if not filtered_go:
        return []

    logger.debug(f"Found {len(filtered_go)} Go buttons")

    # Match tiles with Go buttons on same row (Y within tolerance)
    matched_go_buttons = []
    for tile_x, tile_y, _ in filtered_tiles:
        for go_x, go_y, _ in filtered_go:
            if abs(tile_y - go_y) <= Y_TOLERANCE:
                # Found a match! Add Go button click position
                matched_go_buttons.append((go_x, go_y))
                logger.debug(f"Matched: Question mark Y={tile_y} with Go Y={go_y}")
                break  # One Go per tile

    # Sort by Y position (top to bottom)
    matched_go_buttons.sort(key=lambda b: b[1])

    return matched_go_buttons


def is_in_tavern(frame_gray: np.ndarray) -> tuple[bool, str]:
    """
    Verify we're in Tavern by checking if either tab template matches.
    Returns (is_in_tavern, active_tab) where active_tab is 'my_quests', 'ally_quests', or None.
    """
    my_quests_active_template = load_template_gray(MY_QUESTS_ACTIVE_TEMPLATE)
    ally_quests_active_template = load_template_gray(ALLY_QUESTS_ACTIVE_TEMPLATE)
    my_quests_inactive_template = load_template_gray(f"{TEMPLATE_DIR}/tavern_my_quests_4k.png")
    ally_quests_inactive_template = load_template_gray(f"{TEMPLATE_DIR}/tavern_ally_quests_4k.png")

    # Check My Quests region for either active or inactive template
    my_active, my_active_score = check_tab_active(frame_gray, my_quests_active_template, MY_QUESTS_TAB_REGION)
    my_inactive, my_inactive_score = check_tab_active(frame_gray, my_quests_inactive_template, MY_QUESTS_TAB_REGION)

    # Check Ally Quests region for either active or inactive template
    ally_active, ally_active_score = check_tab_active(frame_gray, ally_quests_active_template, ALLY_QUESTS_TAB_REGION)
    ally_inactive, ally_inactive_score = check_tab_active(frame_gray, ally_quests_inactive_template, ALLY_QUESTS_TAB_REGION)

    logger.debug(f"Tab scores - My active:{my_active_score:.4f} inactive:{my_inactive_score:.4f}, "
                 f"Ally active:{ally_active_score:.4f} inactive:{ally_inactive_score:.4f}")

    # Must have at least one tab matching (active or inactive) in each position
    my_quests_visible = my_active or my_inactive
    ally_quests_visible = ally_active or ally_inactive

    if not (my_quests_visible and ally_quests_visible):
        return False, None

    # Determine which tab is active
    if my_active:
        return True, "my_quests"
    elif ally_active:
        return True, "ally_quests"
    else:
        # Both inactive? Shouldn't happen but default to my_quests
        return True, "my_quests"


# Back button position for dismissing popups
BACK_BUTTON_CLICK = (1407, 2055)


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
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Check if we can see Tavern tabs
        in_tavern, active_tab = is_in_tavern(frame_gray)
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
        adb.tap(*BACK_BUTTON_CLICK)
        time.sleep(0.5)

    logger.warning(f"[POPUP] Failed to return to Tavern after {max_attempts} attempts")
    return False


def handle_bounty_quest_dialog(adb: ADBHelper, win: WindowsScreenshotHelper, debug: bool = False) -> bool:
    """
    Handle the Bounty Quest dialog that appears after clicking Go on a gold scroll quest.

    Flow:
    1. Verify Bounty Quest dialog is open (check title)
    2. Click Auto Dispatch button
    3. Click Proceed button

    Returns True if dialog was handled, False if not in dialog.
    """
    frame = win.get_screenshot_cv2()
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Check for Bounty Quest title
    bounty_title_template = load_template_gray(BOUNTY_QUEST_TITLE_TEMPLATE)
    result = cv2.matchTemplate(frame_gray, bounty_title_template, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)

    if min_val > BOUNTY_QUEST_THRESHOLD:
        logger.debug(f"Bounty Quest dialog not detected (score={min_val:.4f})")
        return False

    logger.info(f"Bounty Quest dialog detected (score={min_val:.4f})")

    # Click Auto Dispatch
    logger.info(f"Clicking Auto Dispatch at {AUTO_DISPATCH_CLICK}")
    adb.tap(*AUTO_DISPATCH_CLICK)
    time.sleep(0.8)

    # Click Proceed
    logger.info(f"Clicking Proceed at {PROCEED_CLICK}")
    adb.tap(*PROCEED_CLICK)
    time.sleep(0.8)

    logger.info("Bounty Quest started")
    return True


# =============================================================================
# Scheduled Claim Flow (pre-position and poll)
# =============================================================================

def poll_for_claim_button(adb: ADBHelper, win: WindowsScreenshotHelper, ocr, debug: bool = False) -> int:
    """
    Poll for Claim button every 0.5s. Clicks immediately when found.

    Exit conditions:
    - Claim found → click it, dismiss popup, return to polling (may have more claims)
    - No timer < 30s visible → exit immediately

    Returns:
        Number of claims made
    """
    claim_template = load_template_gray(CLAIM_BUTTON_TEMPLATE)
    claims_made = 0

    while True:
        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Check for Claim button FIRST
        claim_buttons = find_claim_buttons(frame_gray, claim_template)
        if claim_buttons:
            x, y = claim_buttons[0]
            logger.info(f"[POLL] Claim button found at ({x}, {y}), clicking!")
            adb.tap(x, y)
            claims_made += 1
            time.sleep(0.5)  # Wait for rewards popup to appear

            # Dismiss popup by polling until we see Tavern tabs again
            logger.info("[POLL] Waiting for popup to dismiss...")
            if not wait_for_tavern_tabs(adb, win, max_attempts=10, debug=debug):
                # Exited Tavern or couldn't dismiss - abort
                logger.warning("[POLL] Could not return to Tavern after claim, aborting")
                return claims_made

            continue  # Keep polling for more claims

        # Check for timers < 30s - exit if none
        timers = find_quest_timers(frame, frame_gray, ocr=ocr)
        has_short_timer = any(t['seconds'] is not None and t['seconds'] < SHORT_TIMER_THRESHOLD for t in timers)

        if debug:
            timer_strs = [f"{t['timer_text']}({t['seconds']}s)" for t in timers if t['seconds'] is not None]
            logger.debug(f"[POLL] Timers: {timer_strs}, has_short={has_short_timer}")

        if not has_short_timer:
            logger.info(f"[POLL] No timers < {SHORT_TIMER_THRESHOLD}s, exiting poll loop. Claims made: {claims_made}")
            return claims_made

        time.sleep(CLAIM_POLL_INTERVAL)


def tavern_quest_claim_flow(adb: ADBHelper, win: WindowsScreenshotHelper = None, ocr=None, debug: bool = False) -> dict:
    """
    Navigate to tavern, verify timer < 30s exists, poll for Claim button.

    This is the scheduled flow triggered by the daemon 15 seconds before a quest completes.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (optional, creates one if not provided)
        ocr: OCR client instance (optional, creates OCRClient if not provided)
        debug: Enable debug logging

    Returns:
        dict with 'claims' count and 'success' bool
    """
    if win is None:
        win = WindowsScreenshotHelper()
    if ocr is None:
        from utils.ocr_client import OCRClient
        ocr = OCRClient()

    logger.info("=== TAVERN QUEST CLAIM FLOW START ===")

    # Step 1: Navigate to TOWN (tavern button only visible in TOWN)
    from utils.view_state_detector import go_to_town
    logger.info("Step 1: Navigating to TOWN view")
    if not go_to_town(adb, debug=debug):
        logger.warning("Failed to navigate to TOWN! Aborting.")
        return {"claims": 0, "success": False}

    # Step 2: Click tavern button to open
    TAVERN_BUTTON_CLICK = (80, 1220)
    logger.info(f"Step 2: Clicking Tavern button at {TAVERN_BUTTON_CLICK}")
    adb.tap(*TAVERN_BUTTON_CLICK)
    time.sleep(1.5)  # Wait for tavern to open

    # Step 3: Verify we're in Tavern on My Quests tab
    frame = win.get_screenshot_cv2()
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    in_tavern, active_tab = is_in_tavern(frame_gray)
    if not in_tavern:
        logger.warning("Not in Tavern after clicking button! Aborting.")
        return_to_base_view(adb, win, debug=debug)
        return {"claims": 0, "success": False}

    # Switch to My Quests if needed
    if active_tab != "my_quests":
        logger.info(f"Switching to My Quests tab (current: {active_tab})")
        adb.tap(*MY_QUESTS_CLICK)
        time.sleep(0.5)

    # Step 4: Check for timer < 30s
    frame = win.get_screenshot_cv2()
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    timers = find_quest_timers(frame, frame_gray, ocr=ocr)

    has_short_timer = any(t['seconds'] is not None and t['seconds'] < SHORT_TIMER_THRESHOLD for t in timers)

    if not has_short_timer:
        logger.info(f"No timers < {SHORT_TIMER_THRESHOLD}s found, exiting immediately")
        # Still update schedule with current timers
        scan_and_schedule_quest_completions(frame, ocr)
        return_to_base_view(adb, win, debug=debug)
        return {"claims": 0, "success": True}

    logger.info(f"Found timer(s) < {SHORT_TIMER_THRESHOLD}s, starting poll loop")

    # Step 4: Poll for Claim button
    claims = poll_for_claim_button(adb, win, ocr, debug=debug)

    # Step 5: Update schedule with remaining timers
    frame = win.get_screenshot_cv2()
    scan_and_schedule_quest_completions(frame, ocr)

    # Step 6: Return to base view
    logger.info("Returning to base view")
    return_to_base_view(adb, win, debug=debug)

    logger.info(f"=== TAVERN QUEST CLAIM FLOW END === Claims: {claims}")
    return {"claims": claims, "success": True}


def tavern_scan_flow(adb: ADBHelper, win: WindowsScreenshotHelper = None, ocr=None, debug: bool = False) -> dict:
    """
    Periodic tavern scan flow - runs every 30 minutes.

    1. Navigate to TOWN
    2. Open tavern
    3. Claim any completed quests (Claim buttons)
    4. OCR all quest timers and update schedule
    5. Return to base view

    This keeps the schedule file fresh for the 15-second pre-arrival trigger.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (optional)
        ocr: OCR client instance (optional)
        debug: Enable debug logging

    Returns:
        dict with 'claims' count and 'success' bool
    """
    if win is None:
        win = WindowsScreenshotHelper()
    if ocr is None:
        from utils.ocr_client import OCRClient
        ocr = OCRClient()

    logger.info("=== TAVERN SCAN FLOW START ===")

    # Step 1: Navigate to TOWN
    from utils.view_state_detector import go_to_town
    logger.info("Step 1: Navigating to TOWN view")
    if not go_to_town(adb, debug=debug):
        logger.warning("Failed to navigate to TOWN! Aborting.")
        return {"claims": 0, "success": False}

    # Step 2: Click tavern button
    TAVERN_BUTTON_CLICK = (80, 1220)
    logger.info(f"Step 2: Clicking Tavern button at {TAVERN_BUTTON_CLICK}")
    adb.tap(*TAVERN_BUTTON_CLICK)
    time.sleep(1.5)

    # Step 3: Verify we're in Tavern
    frame = win.get_screenshot_cv2()
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    in_tavern, active_tab = is_in_tavern(frame_gray)
    if not in_tavern:
        logger.warning("Not in Tavern after clicking button! Aborting.")
        return_to_base_view(adb, win, debug=debug)
        return {"claims": 0, "success": False}

    # Switch to My Quests if needed
    if active_tab != "my_quests":
        logger.info(f"Switching to My Quests tab (current: {active_tab})")
        adb.tap(*MY_QUESTS_CLICK)
        time.sleep(0.5)

    # Step 4: Process claims and timers across all screens (scroll through list)
    claim_template = load_template_gray(CLAIM_BUTTON_TEMPLATE)
    total_claims = 0
    all_completions = []
    max_scroll_iterations = 3  # Scroll up to 3 times to cover full list

    for scroll_iter in range(max_scroll_iterations + 1):  # +1 for initial screen
        logger.info(f"Step 4.{scroll_iter + 1}: Processing screen {scroll_iter + 1}")

        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Process all Claim buttons on current screen
        while True:
            claim_buttons = find_claim_buttons(frame_gray, claim_template)
            if not claim_buttons:
                break

            x, y = claim_buttons[0]
            logger.info(f"Claiming completed quest at ({x}, {y})")
            adb.tap(x, y)
            total_claims += 1
            time.sleep(0.5)  # Wait for rewards popup to appear

            # Dismiss popup by polling until we see Tavern tabs again
            logger.info("Waiting for popup to dismiss...")
            if not wait_for_tavern_tabs(adb, win, max_attempts=10, debug=debug):
                # Exited Tavern or couldn't dismiss - abort this screen
                logger.warning("Could not return to Tavern after claim, aborting scan")
                # Try to save what we have so far
                if all_completions:
                    save_quest_schedule(all_completions)
                return_to_base_view(adb, win, debug=debug)
                return {"claims": total_claims, "scheduled": len(all_completions), "success": False}

            # Re-screenshot for next claim on same screen
            frame = win.get_screenshot_cv2()
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Scan timers on current screen (don't save yet - accumulate first)
        completions = scan_quest_timers(frame, ocr)
        if completions:
            all_completions.extend(completions)
            logger.info(f"Found {len(completions)} timer(s) on screen {scroll_iter + 1}")

        # Scroll down for next iteration (except on last iteration)
        if scroll_iter < max_scroll_iterations:
            logger.info(f"Scrolling down...")
            # Slower scroll (500ms) + longer wait (1s) to let UI settle
            adb.swipe(1920, 1500, 1920, 900, duration=500)
            time.sleep(1.0)

    # Save all completions at once - dedup logic in scheduler will merge duplicates
    save_quest_schedule(all_completions)
    # Get actual unique count from scheduler
    unique_completions = load_quest_schedule()
    logger.info(f"Step 5: Total claims: {total_claims}, Unique scheduled: {len(unique_completions)} (from {len(all_completions)} detected)")

    # Step 6: Return to base view
    logger.info("Returning to base view")
    return_to_base_view(adb, win, debug=debug)

    logger.info(f"=== TAVERN SCAN FLOW END === Claims: {total_claims}, Scheduled: {len(unique_completions)}")
    return {"claims": total_claims, "scheduled": len(unique_completions), "success": True}


def run_my_quests_flow(adb: ADBHelper, win: WindowsScreenshotHelper, debug: bool = False) -> dict:
    """
    Claim ONE completed quest OR click Go for gold scroll quests.

    After clicking a Claim button, immediately exits (returns with claimed=True)
    so the caller can restart the flow fresh. This avoids UI display glitches
    that can cause missed claims.

    Returns dict with:
        - claims: number of claims made (0 or 1)
        - go_clicks: number of Go clicks made
        - claimed: True if a claim was made (caller should restart flow)
    """
    logger.info("Starting My Quests flow")

    # Load templates
    my_quests_active_template = load_template_gray(MY_QUESTS_ACTIVE_TEMPLATE)
    claim_template = load_template_gray(CLAIM_BUTTON_TEMPLATE)

    total_claims = 0
    total_go_clicks = 0
    no_action_count = 0
    max_no_action = 2  # Stop after 2 consecutive scrolls with no actions

    while no_action_count < max_no_action:
        # Take screenshot
        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # FIRST: Verify we're in Tavern
        in_tavern, active_tab = is_in_tavern(frame_gray)
        if not in_tavern:
            logger.warning("Not in Tavern! Aborting My Quests flow.")
            return {"claims": total_claims, "go_clicks": total_go_clicks, "claimed": total_claims > 0}

        # Check if My Quests tab is active
        if active_tab != "my_quests":
            logger.info(f"My Quests tab not active (active={active_tab}), clicking to switch")
            adb.tap(*MY_QUESTS_CLICK)
            time.sleep(0.5)
            continue

        # Find Claim buttons
        claim_buttons = find_claim_buttons(frame_gray, claim_template)

        # Find Go buttons for gold scroll quests
        gold_scroll_go_buttons = find_gold_scroll_go_buttons(frame_gray)

        # Find Go buttons for question mark quests (only if not Day 6 and allowed)
        question_mark_go_buttons = []
        if _should_start_question_mark_quests():
            question_mark_go_buttons = find_question_mark_go_buttons(frame_gray)

        if debug:
            logger.debug(f"Found {len(claim_buttons)} Claim buttons, "
                        f"{len(gold_scroll_go_buttons)} Gold Scroll Go buttons, "
                        f"{len(question_mark_go_buttons)} Question Mark Go buttons")

        # Priority 1: Click Claim buttons first (no time restriction)
        if claim_buttons:
            x, y = claim_buttons[0]
            logger.info(f"Clicking Claim at ({x}, {y})")
            adb.tap(x, y)
            time.sleep(0.5)  # Wait for rewards popup to appear
            total_claims += 1
            no_action_count = 0  # Reset scroll counter

            # Dismiss popup by polling until we see Tavern tabs again
            logger.info("Waiting for popup to dismiss...")
            if not wait_for_tavern_tabs(adb, win, max_attempts=10, debug=debug):
                # Exited Tavern or couldn't dismiss - abort
                logger.warning("Could not return to Tavern after claim, aborting")
                return {"claims": total_claims, "go_clicks": total_go_clicks, "claimed": True}

            # Continue loop to re-scan for more claims
            continue

        # Priority 2: Click Go for gold scroll quests (time gated)
        if gold_scroll_go_buttons and _is_after_quest_start_time():
            no_action_count = 0
            x, y = gold_scroll_go_buttons[0]
            logger.info(f"Clicking Go for gold scroll quest at ({x}, {y})")
            adb.tap(x, y)
            time.sleep(1.0)  # Wait for Bounty Quest dialog
            total_go_clicks += 1

            # Handle Bounty Quest dialog (Auto Dispatch + Proceed)
            if handle_bounty_quest_dialog(adb, win, debug):
                logger.info("Bounty Quest started successfully")
                # Dialog dismissed, we're back in tavern - continue loop
                time.sleep(0.5)
                continue
            else:
                # Dialog not detected - might have navigated elsewhere
                logger.warning("Bounty Quest dialog not detected after clicking Go")
                return {"claims": total_claims, "go_clicks": total_go_clicks, "claimed": False}
        elif gold_scroll_go_buttons:
            # Gold scroll quests found but before start time
            logger.debug("Gold scroll Go buttons found but before quest start time - skipping")

        # Priority 3: Click Go for question mark quests (time gated, Day 6 excluded)
        if question_mark_go_buttons and _is_after_quest_start_time():
            no_action_count = 0
            x, y = question_mark_go_buttons[0]
            logger.info(f"Clicking Go for question mark quest at ({x}, {y})")
            adb.tap(x, y)
            time.sleep(1.0)  # Wait for Bounty Quest dialog
            total_go_clicks += 1

            # Handle Bounty Quest dialog (Auto Dispatch + Proceed)
            if handle_bounty_quest_dialog(adb, win, debug):
                logger.info("Question mark Bounty Quest started successfully")
                # Dialog dismissed, we're back in tavern - continue loop
                time.sleep(0.5)
                continue
            else:
                # Dialog not detected - might have navigated elsewhere
                logger.warning("Bounty Quest dialog not detected after clicking Go")
                return {"claims": total_claims, "go_clicks": total_go_clicks, "claimed": False}
        elif question_mark_go_buttons:
            # Question mark quests found but before start time
            logger.debug("Question mark Go buttons found but before quest start time - skipping")

        # No actions found - scroll
        logger.info("No actionable buttons found (Claim/Go), scrolling...")
        no_action_count += 1

        # Scroll down
        adb.swipe(SCROLL_X, SCROLL_START_Y, SCROLL_X, SCROLL_END_Y, SCROLL_DURATION)
        time.sleep(0.5)

    logger.info(f"My Quests flow complete. Claims: {total_claims}, Go clicks: {total_go_clicks}")
    return {"claims": total_claims, "go_clicks": total_go_clicks, "claimed": False}


def run_tavern_quest_flow(adb: ADBHelper = None, win: WindowsScreenshotHelper = None, debug: bool = False) -> dict:
    """
    Main tavern quest flow with double-pass strategy.

    Opens tavern from TOWN, claims quests, and if any claim is made,
    exits completely and re-runs the flow. This avoids UI display glitches
    that can cause missed claims.

    Does TWO passes back-to-back to ensure nothing is missed.

    Returns dict with claim counts and go clicks.
    """
    if adb is None:
        adb = ADBHelper()
    if win is None:
        win = WindowsScreenshotHelper()

    from utils.view_state_detector import go_to_town

    results = {
        "my_quests_claims": 0,
        "my_quests_go_clicks": 0,
        "ally_quests_claims": 0,
    }

    TAVERN_BUTTON_CLICK = (80, 1220)
    MAX_PASSES = 2  # Run flow twice back-to-back

    for pass_num in range(1, MAX_PASSES + 1):
        logger.info(f"=== TAVERN QUEST FLOW PASS {pass_num}/{MAX_PASSES} ===")

        # Step 1: Navigate to TOWN
        logger.info("Navigating to TOWN view")
        if not go_to_town(adb, debug=debug):
            logger.warning("Failed to navigate to TOWN! Aborting.")
            return results

        # Step 2: Click tavern button to open
        logger.info(f"Clicking Tavern button at {TAVERN_BUTTON_CLICK}")
        adb.tap(*TAVERN_BUTTON_CLICK)
        time.sleep(1.5)  # Wait for tavern to open

        # Step 3: Verify we're in Tavern
        frame = win.get_screenshot_cv2()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        in_tavern, active_tab = is_in_tavern(frame_gray)
        if not in_tavern:
            logger.warning("Not in Tavern after clicking button! Aborting pass.")
            return_to_base_view(adb, win, debug=debug)
            continue  # Try next pass

        # Switch to My Quests if needed
        if active_tab != "my_quests":
            logger.info(f"Switching to My Quests tab (current: {active_tab})")
            adb.tap(*MY_QUESTS_CLICK)
            time.sleep(0.5)

        # Step 4: Run My Quests flow
        my_quests_result = run_my_quests_flow(adb, win, debug)
        results["my_quests_claims"] += my_quests_result["claims"]
        results["my_quests_go_clicks"] += my_quests_result["go_clicks"]

        # Step 5: Exit tavern completely after this pass
        logger.info(f"Pass {pass_num} complete - returning to base view")
        return_to_base_view(adb, win, debug=debug)

        # If a claim was made, the next pass will catch any remaining claims
        if my_quests_result.get("claimed", False):
            logger.info("Claim was made - next pass will verify nothing was missed")

    # Ally Quests flow - TBD by user
    # More complex logic, not just clicking all Assist buttons
    logger.info("Ally Quests flow not implemented yet (TBD)")

    logger.info(f"=== TAVERN QUEST FLOW COMPLETE === Total claims: {results['my_quests_claims']}")
    return results


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    parser = argparse.ArgumentParser(description="Tavern Quest Flow")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--my-quests-only", action="store_true", help="Only run My Quests flow")
    args = parser.parse_args()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    if args.my_quests_only:
        claims = run_my_quests_flow(adb, win, debug=args.debug)
        print(f"My Quests claims: {claims}")
    else:
        results = run_tavern_quest_flow(adb, win, debug=args.debug)
        print(f"Results: {results}")
