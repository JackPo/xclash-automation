"""
Technology Research Arms Race flow - Check research queue and OCR time remaining.

Triggered during Arms Race "Technology Research" event in the last 20 minutes.
Opens the Research Queue panel from town view and reads the time remaining.

Flow sequence:
1. Go to town view
2. Template match town_research_button_4k.png to find research button
3. Click research button to open Research Queue panel
4. Verify panel opened via research_queue_header_4k.png
5. OCR time remaining from fixed region
6. Close panel and return time in seconds

Templates:
- Research button: templates/ground_truth/town_research_button_4k.png (with mask)
- Research Queue header: templates/ground_truth/research_queue_header_4k.png
"""

from __future__ import annotations

import re
import time
import logging
from typing import TYPE_CHECKING

from config import (
    RESEARCH_BUTTON_SEARCH_REGION,
    RESEARCH_QUEUE_HEADER_REGION,
    RESEARCH_QUEUE1_TIME_REGION,
    RESEARCH_QUEUE1_NAME_REGION,
    RESEARCH_QUEUE2_TIME_REGION,
    RESEARCH_QUEUE2_NAME_REGION,
)
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.template_matcher import match_template
from utils.return_to_base_view import return_to_base_view
from utils.view_state_detector import ViewState
from utils.ocr_client import OCRClient
from utils.current_state import update_research_queue

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper


logger = logging.getLogger(__name__)


def parse_time_remaining(text: str) -> int | None:
    """
    Parse time remaining text into seconds.

    Formats:
    - "Time Remaining:HH:MM:SS" -> seconds
    - "Time Remaining:Xd HH:MM:SS" -> seconds
    - "HH:MM:SS" -> seconds
    - "Xd HH:MM:SS" -> seconds

    Returns:
        Time in seconds, or None if parsing fails
    """
    if not text:
        return None

    # Clean up text
    text = text.strip()

    # Remove "Time Remaining:" prefix if present
    text = re.sub(r"Time\s*Remaining\s*:?\s*", "", text, flags=re.IGNORECASE)

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


def technology_research_flow(
    adb: ADBHelper, screenshot_helper: WindowsScreenshotHelper | None = None
) -> int | None:
    """
    Open Research Queue panel and OCR time remaining.

    Args:
        adb: ADBHelper instance
        screenshot_helper: WindowsScreenshotHelper instance (optional)

    Returns:
        Time remaining in seconds for first research item, or None if failed
    """
    win = screenshot_helper if screenshot_helper else WindowsScreenshotHelper()
    ocr = OCRClient()

    # Step 1: Go to town view
    logger.info("Step 1: Going to town view...")
    return_to_base_view(adb, win, target=ViewState.TOWN, debug=False)
    time.sleep(0.5)

    # Step 2: Find research button
    logger.info("Step 2: Looking for research button...")
    frame = win.get_screenshot_cv2()
    if frame is None:
        logger.error("Failed to get screenshot")
        return None

    found, score, center = match_template(
        frame,
        "town_research_button_4k.png",
        search_region=RESEARCH_BUTTON_SEARCH_REGION,
        threshold=0.05,
    )

    if not found:
        logger.warning(f"Research button not found (score={score:.4f})")
        return None

    logger.info(f"Research button found at {center} (score={score:.4f})")

    # Step 3: Click research button
    logger.info(f"Step 3: Clicking research button at {center}")
    adb.tap(*center, source="flow:technology_research:research_button")
    time.sleep(0.7)  # Wait for panel animation

    # Step 4: Verify Research Queue panel opened
    logger.info("Step 4: Verifying Research Queue panel...")
    frame = win.get_screenshot_cv2()
    if frame is None:
        logger.error("Failed to get screenshot after clicking")
        return None

    found, score, _ = match_template(
        frame,
        "research_queue_header_4k.png",
        search_region=RESEARCH_QUEUE_HEADER_REGION,
        threshold=0.05,
    )

    if not found:
        logger.warning(f"Research Queue panel not detected (score={score:.4f})")
        # Try to close any panel that might have opened
        adb.tap(500, 500, source="flow:technology_research:close_unknown")
        time.sleep(0.3)
        return None

    logger.info(f"Research Queue panel verified (score={score:.4f})")

    # Step 5: OCR both research queues
    logger.info("Step 5: OCR research queues...")

    # Queue 1 - currently researching
    x, y, w, h = RESEARCH_QUEUE1_NAME_REGION
    name1_region = frame[y:y+h, x:x+w]
    queue1_name = ocr.extract_text(name1_region)
    logger.info(f"Queue 1 name: '{queue1_name}'")

    x, y, w, h = RESEARCH_QUEUE1_TIME_REGION
    time1_region = frame[y:y+h, x:x+w]
    time1_text = ocr.extract_text(time1_region)
    logger.info(f"Queue 1 time OCR: '{time1_text}'")
    queue1_seconds = parse_time_remaining(time1_text)

    if queue1_seconds is not None:
        h, m, s = queue1_seconds // 3600, (queue1_seconds % 3600) // 60, queue1_seconds % 60
        logger.info(f"Queue 1: {queue1_name} - {h}h {m}m {s}s ({queue1_seconds}s)")

    # Queue 2 - queued research
    x, y, w, h = RESEARCH_QUEUE2_NAME_REGION
    name2_region = frame[y:y+h, x:x+w]
    queue2_name = ocr.extract_text(name2_region)
    logger.info(f"Queue 2 name: '{queue2_name}'")

    x, y, w, h = RESEARCH_QUEUE2_TIME_REGION
    time2_region = frame[y:y+h, x:x+w]
    time2_text = ocr.extract_text(time2_region)
    logger.info(f"Queue 2 time OCR: '{time2_text}'")
    queue2_seconds = parse_time_remaining(time2_text)

    if queue2_seconds is not None:
        h, m, s = queue2_seconds // 3600, (queue2_seconds % 3600) // 60, queue2_seconds % 60
        logger.info(f"Queue 2: {queue2_name} - {h}h {m}m {s}s ({queue2_seconds}s)")

    # Step 6: Save to state for frontend
    if queue1_seconds is not None:
        update_research_queue(
            queue1_seconds=queue1_seconds,
            queue1_name=queue1_name.strip() if queue1_name else None,
            queue2_seconds=queue2_seconds,
            queue2_name=queue2_name.strip() if queue2_name else None,
        )
        logger.info("Saved research queue to state")

    # Step 7: Close panel
    logger.info("Step 7: Closing Research Queue panel...")
    # "Tap to Close" is at the bottom center of the panel
    adb.tap(1920, 1350, source="flow:technology_research:close_panel")
    time.sleep(0.3)

    return queue1_seconds
