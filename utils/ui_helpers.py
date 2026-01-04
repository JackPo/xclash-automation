"""
UI Helpers - Centralized functions for common UI interactions.

These helpers wrap common tap operations to:
1. Centralize coordinate constants (single source of truth)
2. Provide semantic function names instead of raw tap calls
3. Make flows easier to read and maintain

Use these instead of hardcoding coordinates in flows.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from config import BACK_BUTTON_CLICK, TOGGLE_BUTTON_CLICK

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper


def click_back(adb: ADBHelper) -> None:
    """
    Click the back button once.

    Use this to:
    - Close a popup/dialog
    - Exit one level from a menu/panel
    - Dismiss a notification

    This is a single click - it does NOT verify the popup closed.
    For verified closure, use back_from_chat_flow or return_to_base_view.

    Args:
        adb: ADBHelper instance
    """
    adb.tap(*BACK_BUTTON_CLICK)


def close_popup(adb: ADBHelper, clicks: int = 1, delay: float = 0.3) -> None:
    """
    Click back button N times with delay between clicks.

    Use this when you need to close multiple nested dialogs
    or when a single click might not be enough.

    Args:
        adb: ADBHelper instance
        clicks: Number of back button clicks
        delay: Seconds to wait between clicks
    """
    for i in range(clicks):
        click_back(adb)
        if i < clicks - 1:  # Don't delay after last click
            time.sleep(delay)


def click_toggle(adb: ADBHelper) -> None:
    """
    Click the World/Town toggle button.

    This switches between TOWN and WORLD views.
    For verified navigation, use go_to_town() or go_to_world() from view_state_detector.

    Args:
        adb: ADBHelper instance
    """
    adb.tap(*TOGGLE_BUTTON_CLICK)
