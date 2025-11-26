"""
Treasure map icon flow - handles clicking the bouncing treasure map.

Triggered when daemon detects treasure map icon at fixed position.
"""

# Fixed click coordinates (4K resolution)
CLICK_X = 2175
CLICK_Y = 1621


def treasure_map_flow(adb):
    """
    Handle treasure map icon detection.

    Currently just clicks the icon. Future versions can handle
    follow-up dialogs, rewards, etc.

    Args:
        adb: ADBHelper instance
    """
    print(f"    [FLOW] Treasure map: clicking ({CLICK_X}, {CLICK_Y})")
    adb.tap(CLICK_X, CLICK_Y)
