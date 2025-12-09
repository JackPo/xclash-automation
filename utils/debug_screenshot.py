"""
Shared debug screenshot utility for all flows.

Usage:
    from utils.debug_screenshot import save_debug_screenshot

    # Save with flow name as subdirectory
    save_debug_screenshot(frame, "barracks", "FAIL_step0_panel_not_open")
    # Saves to: templates/debug/barracks/20251209_060553_FAIL_step0_panel_not_open.png

    save_debug_screenshot(frame, "upgrade", "FAIL_no_tiles")
    # Saves to: templates/debug/upgrade/20251209_060553_FAIL_no_tiles.png
"""

from pathlib import Path
from datetime import datetime
import cv2

# Base debug directory
DEBUG_BASE = Path(__file__).parent.parent / "templates" / "debug"


def save_debug_screenshot(frame, flow_name: str, label: str) -> str:
    """
    Save debug screenshot with timestamp and label.

    Args:
        frame: BGR numpy array screenshot
        flow_name: Name of the flow (used as subdirectory, e.g., "barracks", "upgrade", "rally")
        label: Description label for filename (e.g., "FAIL_step0_panel_not_open")

    Returns:
        str: Path to saved file
    """
    # Create subdirectory for this flow
    debug_dir = DEBUG_BASE / flow_name
    debug_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = debug_dir / f"{timestamp}_{label}.png"

    # Save
    cv2.imwrite(str(filepath), frame)

    return str(filepath)
