"""
Iron bar harvest flow - just clicks the iron bar bubble.
"""


def iron_bar_flow(adb):
    """
    Click the iron bar harvest bubble.

    Args:
        adb: ADBHelper instance
    """
    adb.tap(1639, 377)
    print("    [IRON] Clicked harvest bubble")
