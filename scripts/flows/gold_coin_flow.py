"""
Gold coin harvest flow - just clicks the gold coin bubble.
"""


def gold_coin_flow(adb):
    """
    Click the gold coin harvest bubble.

    Args:
        adb: ADBHelper instance
    """
    adb.tap(1395, 835)
    print("    [GOLD] Clicked harvest bubble")
