"""
City Construction Arms Race flow - Check construction queue and OCR time remaining.

Triggered during Arms Race "City Construction" event in the last 20 minutes.
Opens the Construction Queue panel from town view and reads the time remaining.

Flow sequence:
1. Go to town view
2. Template match town_hammer_button_4k.png to find construction button
3. Click construction button to open Construction Queue panel
4. Verify panel opened via construction_queue_header_4k.png
5. OCR time remaining from fixed region
6. Close panel and return time in seconds

Templates:
- Construction button: templates/ground_truth/town_hammer_button_4k.png (with mask)
- Construction Queue header: templates/ground_truth/construction_queue_header_4k.png
"""

from __future__ import annotations

import re
import time
import logging
from typing import TYPE_CHECKING

from config import (
    CONSTRUCTION_BUTTON_SEARCH_REGION,
    CONSTRUCTION_QUEUE_HEADER_REGION,
    CONSTRUCTION_QUEUE1_TIME_REGION,
    CONSTRUCTION_QUEUE1_NAME_REGION,
    CONSTRUCTION_QUEUE2_TIME_REGION,
    CONSTRUCTION_QUEUE2_NAME_REGION,
    CONSTRUCTION_QUEUE1_SPEEDUP_CLICK,
    CONSTRUCTION_QUEUE2_SPEEDUP_CLICK,
    CONSTRUCTION_QUICK_SPEEDUP_REGION,
)
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.template_matcher import match_template
from utils.return_to_base_view import return_to_base_view
from utils.view_state_detector import ViewState
from utils.ocr_client import OCRClient
from utils.current_state import update_construction_queue

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper


logger = logging.getLogger(__name__)


def parse_time_remaining(text: str) -> int | None:
    """
    Parse time remaining text into seconds.

    Formats:
    - "Time:HH:MM:SS" -> seconds
    - "Time:Xd HH:MM:SS" -> seconds
    - "HH:MM:SS" -> seconds
    - "Xd HH:MM:SS" -> seconds

    Returns:
        Time in seconds, or None if parsing fails
    """
    if not text:
        return None

    # Clean up text
    text = text.strip()

    # Remove "Time:" prefix if present
    text = re.sub(r"Time\s*:?\s*", "", text, flags=re.IGNORECASE)

    # Try to match patterns
    # Pattern 1: Xd HH:MM:SS (days + time)
    match = re.search(r"(\d+)d\s*(\d{1,2}):(\d{2}):(\d{2})", text)
    if match:
        days = int(match.group(1))
        hours = int(match.group(2))
        minutes = int(match.group(3))
        seconds = int(match.group(4))
        return days * 86400 + hours * 3600 + minutes * 60 + seconds

    # Pattern 2: HH:MM:SS (time only)
    match = re.search(r"(\d{1,2}):(\d{2}):(\d{2})", text)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        return hours * 3600 + minutes * 60 + seconds

    logger.warning(f"Could not parse time from: {text}")
    return None


def city_construction_flow(
    adb: ADBHelper, screenshot_helper: WindowsScreenshotHelper | None = None
) -> int | None:
    """
    Open Construction Queue panel and OCR time remaining.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance (optional)

    Returns:
        Time remaining in seconds for first construction item, or None if failed
    """
    win = screenshot_helper if screenshot_helper else WindowsScreenshotHelper()
    ocr = OCRClient()

    # Step 1: Go to town view
    logger.info("Step 1: Going to town view...")
    return_to_base_view(adb, win, target=ViewState.TOWN, debug=False)
    time.sleep(0.5)

    # Step 2: Find construction button (hammer)
    logger.info("Step 2: Looking for construction button...")
    frame = win.get_screenshot_cv2()
    if frame is None:
        logger.error("Failed to get screenshot")
        return None

    found, score, center = match_template(
        frame,
        "town_hammer_button_4k.png",
        search_region=CONSTRUCTION_BUTTON_SEARCH_REGION,
        threshold=0.05,
    )

    if not found:
        logger.warning(f"Construction button not found (score={score:.4f})")
        return None

    logger.info(f"Construction button found at {center} (score={score:.4f})")

    # Step 3: Click construction button
    logger.info(f"Step 3: Clicking construction button at {center}")
    adb.tap(*center, source="flow:city_construction:construction_button")
    time.sleep(0.7)  # Wait for panel animation

    # Step 4: Verify Construction Queue panel opened
    logger.info("Step 4: Verifying Construction Queue panel...")
    frame = win.get_screenshot_cv2()
    if frame is None:
        logger.error("Failed to get screenshot after clicking")
        return None

    found, score, _ = match_template(
        frame,
        "construction_queue_header_4k.png",
        search_region=CONSTRUCTION_QUEUE_HEADER_REGION,
        threshold=0.05,
    )

    if not found:
        logger.warning(f"Construction Queue panel not detected (score={score:.4f})")
        # Try to close any panel that might have opened
        adb.tap(500, 500, source="flow:city_construction:close_unknown")
        time.sleep(0.3)
        return None

    logger.info(f"Construction Queue panel verified (score={score:.4f})")

    # Step 5: OCR both construction queues
    logger.info("Step 5: OCR construction queues...")

    # Queue 1 - currently upgrading
    x, y, w, h = CONSTRUCTION_QUEUE1_NAME_REGION
    name1_region = frame[y:y+h, x:x+w]
    queue1_name = ocr.extract_text(name1_region)
    logger.info(f"Queue 1 name: '{queue1_name}'")

    x, y, w, h = CONSTRUCTION_QUEUE1_TIME_REGION
    time1_region = frame[y:y+h, x:x+w]
    time1_text = ocr.extract_text(time1_region)
    logger.info(f"Queue 1 time OCR: '{time1_text}'")
    queue1_seconds = parse_time_remaining(time1_text)

    if queue1_seconds is not None:
        h, m, s = queue1_seconds // 3600, (queue1_seconds % 3600) // 60, queue1_seconds % 60
        logger.info(f"Queue 1: {queue1_name} - {h}h {m}m {s}s ({queue1_seconds}s)")

    # Queue 2 - queued construction
    x, y, w, h = CONSTRUCTION_QUEUE2_NAME_REGION
    name2_region = frame[y:y+h, x:x+w]
    queue2_name = ocr.extract_text(name2_region)
    logger.info(f"Queue 2 name: '{queue2_name}'")

    x, y, w, h = CONSTRUCTION_QUEUE2_TIME_REGION
    time2_region = frame[y:y+h, x:x+w]
    time2_text = ocr.extract_text(time2_region)
    logger.info(f"Queue 2 time OCR: '{time2_text}'")
    queue2_seconds = parse_time_remaining(time2_text)

    if queue2_seconds is not None:
        h, m, s = queue2_seconds // 3600, (queue2_seconds % 3600) // 60, queue2_seconds % 60
        logger.info(f"Queue 2: {queue2_name} - {h}h {m}m {s}s ({queue2_seconds}s)")

    # Step 6: Save to state for frontend
    if queue1_seconds is not None:
        update_construction_queue(
            queue1_seconds=queue1_seconds,
            queue1_name=queue1_name.strip() if queue1_name else None,
            queue2_seconds=queue2_seconds,
            queue2_name=queue2_name.strip() if queue2_name else None,
        )
        logger.info("Saved construction queue to state")

    # Step 7: Close panel
    logger.info("Step 7: Closing Construction Queue panel...")
    # "Tap to Close" is at the bottom center of the panel
    adb.tap(1920, 1350, source="flow:city_construction:close_panel")
    time.sleep(0.3)

    return queue1_seconds


def city_construction_speedup_flow(
    adb: ADBHelper, screenshot_helper: WindowsScreenshotHelper | None = None
) -> bool:
    """
    Speed up construction on the smaller queue to earn Arms Race points.

    Flow:
    1. Open Construction Queue panel
    2. OCR both queue times
    3. Pick smaller queue (more efficient use of speedups)
    4. Click Speed Up button
    5. Click Quick Speedup
    6. Click Confirm
    7. If Complete button visible, click it
    8. Close panel

    Returns:
        True if speedup was successful, False otherwise
    """
    win = screenshot_helper if screenshot_helper else WindowsScreenshotHelper()
    ocr = OCRClient()

    # Step 1: Go to town view
    logger.info("Speedup Step 1: Going to town view...")
    return_to_base_view(adb, win, target=ViewState.TOWN, debug=False)
    time.sleep(0.5)

    # Step 2: Open Construction Queue panel
    logger.info("Speedup Step 2: Opening Construction Queue...")
    frame = win.get_screenshot_cv2()
    if frame is None:
        logger.error("Failed to get screenshot")
        return False

    found, score, center = match_template(
        frame, "town_hammer_button_4k.png",
        search_region=CONSTRUCTION_BUTTON_SEARCH_REGION, threshold=0.05,
    )
    if not found:
        logger.warning(f"Construction button not found (score={score:.4f})")
        return False

    adb.tap(*center, source="flow:construction_speedup:construction_button")
    time.sleep(0.8)

    # Step 3: Verify panel and OCR queue times
    logger.info("Speedup Step 3: Reading queue times...")
    frame = win.get_screenshot_cv2()

    found, score, _ = match_template(
        frame, "construction_queue_header_4k.png",
        search_region=CONSTRUCTION_QUEUE_HEADER_REGION, threshold=0.05,
    )
    if not found:
        logger.warning("Construction Queue panel not detected")
        adb.tap(500, 500, source="flow:construction_speedup:close_unknown")
        return False

    # OCR queue 1 time
    x, y, w, h = CONSTRUCTION_QUEUE1_TIME_REGION
    time1_text = ocr.extract_text(frame[y:y+h, x:x+w])
    queue1_seconds = parse_time_remaining(time1_text)
    logger.info(f"Queue 1 time: {queue1_seconds}s ({time1_text})")

    # OCR queue 2 time
    x, y, w, h = CONSTRUCTION_QUEUE2_TIME_REGION
    time2_text = ocr.extract_text(frame[y:y+h, x:x+w])
    queue2_seconds = parse_time_remaining(time2_text)
    logger.info(f"Queue 2 time: {queue2_seconds}s ({time2_text})")

    # Step 4: Pick smaller queue
    if queue1_seconds is None and queue2_seconds is None:
        logger.warning("Could not read either queue time")
        adb.tap(1920, 1350, source="flow:construction_speedup:close_panel")
        return False

    # Default to queue 1 if queue 2 not available
    if queue2_seconds is None:
        target_queue = 1
    elif queue1_seconds is None:
        target_queue = 2
    else:
        target_queue = 1 if queue1_seconds <= queue2_seconds else 2

    speedup_click = CONSTRUCTION_QUEUE1_SPEEDUP_CLICK if target_queue == 1 else CONSTRUCTION_QUEUE2_SPEEDUP_CLICK
    logger.info(f"Speedup Step 4: Using queue {target_queue} (smaller), clicking Speed Up at {speedup_click}")

    adb.tap(*speedup_click, source=f"flow:construction_speedup:speedup_q{target_queue}")
    time.sleep(0.8)

    # Step 5: Find and click Quick Speedup
    logger.info("Speedup Step 5: Clicking Quick Speedup...")
    frame = win.get_screenshot_cv2()

    found, score, center = match_template(
        frame, "quick_speedup_button_4k.png",
        search_region=CONSTRUCTION_QUICK_SPEEDUP_REGION, threshold=0.1,
    )
    if not found:
        logger.warning(f"Quick Speedup button not found (score={score:.4f})")
        adb.tap(1920, 2100, source="flow:construction_speedup:close_dialog")
        time.sleep(0.3)
        adb.tap(1920, 1350, source="flow:construction_speedup:close_panel")
        return False

    adb.tap(*center, source="flow:construction_speedup:quick_speedup")
    time.sleep(0.5)

    # Step 6: Click Confirm
    logger.info("Speedup Step 6: Clicking Confirm...")
    frame = win.get_screenshot_cv2()

    found, score, center = match_template(frame, "confirm_button_4k.png", threshold=0.1)
    if found:
        adb.tap(*center, source="flow:construction_speedup:confirm")
        time.sleep(0.8)
    else:
        logger.warning("Confirm button not found, trying fixed position")
        adb.tap(2141, 1426, source="flow:construction_speedup:confirm_fixed")
        time.sleep(0.8)

    # Step 7: Check for Complete button (construction finished)
    logger.info("Speedup Step 7: Checking for Complete button...")
    frame = win.get_screenshot_cv2()

    # Check if Complete button is visible at the speedup location
    # Using research_complete_button which should be same style
    found, score, center = match_template(
        frame, "research_complete_button_4k.png",
        search_region=(2050, 550, 400, 200), threshold=0.1,
    )
    if found:
        logger.info(f"Complete button found at {center}, clicking...")
        adb.tap(*center, source="flow:construction_speedup:complete")
        time.sleep(0.5)

    # Step 8: Close panel
    logger.info("Speedup Step 8: Closing panel...")
    adb.tap(1920, 1350, source="flow:construction_speedup:close_panel")
    time.sleep(0.3)

    logger.info("Speedup flow complete!")
    return True
