"""
Arms Race data collector for automated event metadata extraction.

Collects chest thresholds and header templates for each event type
when the data is missing. Persists to JSON for permanent storage.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

from utils.arms_race import ARMS_RACE_EVENTS, get_arms_race_status, is_event_data_complete
from utils.arms_race_ocr import (
    get_chest_thresholds,
    detect_active_event,
    is_arms_race_panel_open,
    TITLE_REGION,
    extract_region,
)

logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"
EVENTS_JSON_PATH = DATA_DIR / "arms_race_events.json"

# Events icon click position (to open events panel) - right side of screen
EVENTS_ICON_CLICK = (3718, 632)

# Arms Race icon position and click
ARMS_RACE_ICON_POSITION = (1512, 1935)
ARMS_RACE_ICON_CLICK = (1625, 2044)  # Center of icon


def should_collect_event_data(event_name: str) -> bool:
    """
    Check if we need to collect data for this event.

    Returns True if chest3 threshold is None (data not collected).
    """
    # First check in-memory
    if is_event_data_complete(event_name):
        return False

    # Then check persisted JSON
    data = load_persisted_data()
    if event_name in data:
        event_data = data[event_name]
        if event_data.get("chest3") is not None:
            return False

    return True


def load_persisted_data() -> dict[str, Any]:
    """Load persisted event data from JSON."""
    if not EVENTS_JSON_PATH.exists():
        return {}

    try:
        with open(EVENTS_JSON_PATH, "r") as f:
            result: dict[str, Any] = json.load(f)
            return result
    except (json.JSONDecodeError, IOError):
        return {}


def save_persisted_data(data: dict[str, Any]) -> bool:
    """Save event data to JSON."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(EVENTS_JSON_PATH, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except IOError as e:
        logger.error(f"Failed to save event data: {e}")
        return False


def update_in_memory_data(event_name: str, chest1: int, chest2: int, chest3: int) -> None:
    """Update the in-memory ARMS_RACE_EVENTS dict."""
    if event_name in ARMS_RACE_EVENTS:
        event_data = ARMS_RACE_EVENTS[event_name]
        if isinstance(event_data, dict):
            event_data["chest1"] = chest1
            event_data["chest2"] = chest2
            event_data["chest3"] = chest3
            logger.info(f"Updated in-memory data for {event_name}: {chest1}/{chest2}/{chest3}")


def save_header_template(frame: npt.NDArray[Any], event_name: str) -> bool:
    """
    Extract and save the header template for an event.

    Returns True if saved successfully.
    """
    # Generate template filename
    filename = event_name.lower().replace(" ", "_") + "_4k.png"
    template_path = TEMPLATE_DIR / filename

    # Extract title region
    title_roi = extract_region(frame, TITLE_REGION)
    if title_roi.size == 0:
        logger.error(f"Failed to extract title region for {event_name}")
        return False

    # Save template
    try:
        cv2.imwrite(str(template_path), title_roi)
        logger.info(f"Saved header template: {template_path}")

        # Update metadata
        if event_name in ARMS_RACE_EVENTS:
            event_data = ARMS_RACE_EVENTS[event_name]
            if isinstance(event_data, dict):
                event_data["header_template"] = filename

        return True
    except Exception as e:
        logger.error(f"Failed to save header template: {e}")
        return False


def navigate_to_arms_race(adb: ADBHelper, win: WindowsScreenshotHelper, debug: bool = False) -> bool:
    """
    Navigate to the Arms Race panel.

    Returns True if successfully opened Arms Race panel.
    """
    from utils.view_state_detector import go_to_town, detect_view, ViewState

    # First ensure we're in TOWN view
    frame = win.get_screenshot_cv2()
    state, _ = detect_view(frame)

    if state != ViewState.TOWN:
        logger.info("Not in TOWN view, navigating...")
        go_to_town(adb, debug=debug)
        time.sleep(1)

    # Click Events icon to open events panel
    logger.info(f"Clicking Events icon at {EVENTS_ICON_CLICK}")
    adb.tap(*EVENTS_ICON_CLICK)
    time.sleep(1.5)

    # Take screenshot and check if we need to click Arms Race
    frame = win.get_screenshot_cv2()

    # Check if Arms Race panel is already open
    if is_arms_race_panel_open(frame):
        logger.info("Arms Race panel is open")
        return True

    # Click Arms Race icon on bottom bar
    logger.info(f"Clicking Arms Race icon at {ARMS_RACE_ICON_CLICK}")
    adb.tap(*ARMS_RACE_ICON_CLICK)
    time.sleep(1.5)

    # Verify
    frame = win.get_screenshot_cv2()
    if is_arms_race_panel_open(frame):
        logger.info("Arms Race panel opened successfully")
        return True

    logger.warning("Failed to open Arms Race panel")
    return False


def collect_event_data(
    adb: ADBHelper,
    win: WindowsScreenshotHelper,
    expected_event: str | None = None,
    debug: bool = False,
) -> dict[str, Any] | None:
    """
    Navigate to Arms Race and extract event metadata via OCR.

    Uses expected_event from scheduler to save template even if detection fails
    (solves the Catch-22: can't detect without template, can't capture without detecting).

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        expected_event: Event name from scheduler (used for template capture)
        debug: Enable debug logging

    Returns dict with event_name, chest1, chest2, chest3 or None on failure.
    """
    # Navigate to Arms Race panel
    if not navigate_to_arms_race(adb, win, debug):
        return None

    # Take screenshot
    frame = win.get_screenshot_cv2()

    # FIRST: Save header template using EXPECTED event (not detected)
    # This solves the Catch-22 where detection requires template to exist
    if expected_event:
        template_name = expected_event.lower().replace(" ", "_") + "_4k.png"
        template_path = TEMPLATE_DIR / template_name
        if not template_path.exists():
            logger.info(f"Capturing header template for {expected_event} (template missing)")
            save_header_template(frame, expected_event)

    # NOW try to detect which event is active (should work after template saved)
    event_name, score = detect_active_event(frame)

    if event_name is None:
        # Detection failed even after saving template - use expected event
        if expected_event:
            logger.warning(f"Detection failed, using expected event: {expected_event}")
            event_name = expected_event
        else:
            logger.warning(f"Could not detect active event and no expected event provided")
            return None
    elif score > 0.1:
        logger.warning(f"Poor detection score ({score:.4f}), using expected event: {expected_event}")
        event_name = expected_event if expected_event else event_name
    else:
        logger.info(f"Detected event: {event_name} (score={score:.4f})")

        # Verify detection matches expected
        if expected_event and event_name != expected_event:
            logger.warning(f"Event mismatch: detected {event_name}, expected {expected_event}")

    # Extract chest thresholds
    thresholds = get_chest_thresholds(frame)

    if thresholds["chest3"] is None:
        logger.warning("Failed to extract chest3 threshold")
        return None

    return {
        "event_name": event_name,
        "chest1": thresholds["chest1"],
        "chest2": thresholds["chest2"],
        "chest3": thresholds["chest3"],
    }


def save_event_metadata(event_name: str, chest1: int, chest2: int, chest3: int) -> bool:
    """
    Persist collected data for an event.

    Updates both in-memory dict and JSON file.
    """
    # Update in-memory
    update_in_memory_data(event_name, chest1, chest2, chest3)

    # Load existing JSON data
    data = load_persisted_data()

    # Update with new data
    data[event_name] = {
        "chest1": chest1,
        "chest2": chest2,
        "chest3": chest3,
    }

    # Save
    if save_persisted_data(data):
        logger.info(f"Persisted data for {event_name}: {chest1}/{chest2}/{chest3}")
        return True

    return False


def collect_and_save_current_event(
    adb: ADBHelper, win: WindowsScreenshotHelper, debug: bool = False
) -> bool:
    """
    Collect data for the current event if missing.

    This is the main entry point for the daemon to call.

    Returns True if data was collected and saved, False otherwise.
    """
    # Get current event from scheduler
    status = get_arms_race_status()
    current_event = status["current"]

    # Check if we need to collect
    if not should_collect_event_data(current_event):
        if debug:
            logger.debug(f"Data already exists for {current_event}")
        return False

    logger.info(f"Collecting missing data for {current_event}...")

    # Collect - pass expected_event to solve Catch-22 template issue
    data = collect_event_data(adb, win, expected_event=current_event, debug=debug)
    if data is None:
        logger.error(f"Failed to collect data for {current_event}")
        return False

    # Verify we got the right event
    if data["event_name"] != current_event:
        logger.warning(f"Event mismatch: expected {current_event}, got {data['event_name']}")
        # Still save it - we got valid data for some event

    # Save
    return save_event_metadata(
        data["event_name"],
        data["chest1"],
        data["chest2"],
        data["chest3"],
    )


def load_persisted_into_memory() -> None:
    """
    Load persisted JSON data into the in-memory ARMS_RACE_EVENTS dict.

    Call this at daemon startup to restore previously collected data.
    """
    data = load_persisted_data()

    for event_name, persisted_event_data in data.items():
        if event_name in ARMS_RACE_EVENTS:
            if not isinstance(persisted_event_data, dict):
                continue
            chest1 = persisted_event_data.get("chest1")
            chest2 = persisted_event_data.get("chest2")
            chest3 = persisted_event_data.get("chest3")

            if chest3 is not None:
                in_memory_event_data = ARMS_RACE_EVENTS[event_name]
                if isinstance(in_memory_event_data, dict):
                    in_memory_event_data["chest1"] = chest1
                    in_memory_event_data["chest2"] = chest2
                    in_memory_event_data["chest3"] = chest3
                    logger.debug(f"Loaded persisted data for {event_name}: {chest1}/{chest2}/{chest3}")


def get_collection_status() -> dict[str, bool]:
    """Get collection status for all events."""
    return {
        event_name: is_event_data_complete(event_name)
        for event_name in ARMS_RACE_EVENTS
    }


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    print("=== Arms Race Data Collection Status ===\n")

    # Load any persisted data
    load_persisted_into_memory()

    # Show status
    status = get_collection_status()
    for event_name, complete in status.items():
        meta_raw = ARMS_RACE_EVENTS.get(event_name, {})
        meta: dict[str, Any] = meta_raw if isinstance(meta_raw, dict) else {}
        if complete:
            print(f"[x] {event_name}: {meta.get('chest1')}/{meta.get('chest2')}/{meta.get('chest3')}")
        else:
            print(f"[ ] {event_name}: Not collected")

    # Show current event
    print("\n=== Current Event ===")
    current = get_arms_race_status()
    print(f"Event: {current['current']}")
    print(f"Needs collection: {should_collect_event_data(current['current'])}")

    # Option to collect
    if len(sys.argv) > 1 and sys.argv[1] == "--collect":
        from utils.adb_helper import ADBHelper
        from utils.windows_screenshot_helper import WindowsScreenshotHelper

        print("\n=== Collecting Data ===")
        adb = ADBHelper()
        win = WindowsScreenshotHelper()

        success = collect_and_save_current_event(adb, win, debug=True)
        print(f"Collection {'succeeded' if success else 'failed'}")
