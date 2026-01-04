"""
Handshake icon flow - handles clicking the handshake/union button.

Triggered when daemon detects handshake icon at fixed position.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

# Fixed click coordinates (4K resolution)
CLICK_X = 3165
CLICK_Y = 1843


def handshake_flow(adb: ADBHelper) -> None:
    """
    Handle handshake icon detection.

    Currently just clicks the icon. Future versions can handle
    follow-up dialogs, rewards, etc.

    Args:
        adb: ADBHelper instance
    """
    print(f"    [FLOW] Handshake: clicking ({CLICK_X}, {CLICK_Y})")
    adb.tap(CLICK_X, CLICK_Y)
