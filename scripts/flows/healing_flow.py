"""
Healing Flow - Heal wounded soldiers at the hospital.

Called when healing panel is ALREADY OPEN (icon_daemon clicked the bubble).

Now uses hospital_healing_flow which supports multiple soldier rows
and heals in 1-hour batches.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from scripts.flows.hospital_healing_flow import hospital_healing_flow


def healing_flow(adb: ADBHelper, target_hours: float = 1.0, debug: bool = True) -> bool:
    """
    Heal wounded soldiers at the hospital.

    ASSUMES: Healing panel is already open (called from icon_daemon after bubble click).

    Args:
        adb: ADBHelper instance
        target_hours: float - target healing time in hours (default 1.0)
        debug: bool - enable debug logging

    Returns:
        bool: True if healing started successfully
    """
    win = WindowsScreenshotHelper()
    max_heal_seconds = int(target_hours * 3600)
    return hospital_healing_flow(adb, win, max_heal_seconds=max_heal_seconds, debug=debug)


if __name__ == "__main__":
    adb = ADBHelper()
    success = healing_flow(adb, target_hours=1.0, debug=True)
    print(f"\nResult: {'SUCCESS' if success else 'FAILED'}")
