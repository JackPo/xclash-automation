"""
Gem harvest flow - just clicks the gem bubble.
"""


def gem_flow(adb):
    """
    Click the gem harvest bubble.

    Args:
        adb: ADBHelper instance
    """
    adb.tap(1405, 696)
    print("    [GEM] Clicked harvest bubble")
