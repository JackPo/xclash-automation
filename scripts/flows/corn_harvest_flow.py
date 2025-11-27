"""
Corn harvest flow - just clicks the corn bubble.
"""


def corn_harvest_flow(adb):
    """
    Click the corn harvest bubble.

    Args:
        adb: ADBHelper instance
    """
    # Click at fixed position (center of detected bubble)
    adb.tap(1151, 967)
    print("    [CORN] Clicked harvest bubble")
