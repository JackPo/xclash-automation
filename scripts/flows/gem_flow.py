"""
Gem harvest flow - just clicks the gem bubble.
"""


def gem_flow(adb):
    """
    Click the gem harvest bubble.

    Args:
        adb: ADBHelper instance
    """
    adb.tap(787, 427)
    print("    [GEM] Clicked harvest bubble")
