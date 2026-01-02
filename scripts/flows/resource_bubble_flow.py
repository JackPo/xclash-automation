"""
Generic resource bubble flow - clicks any resource bubble if present.

This is a unified flow that can handle corn, gold, iron, gem, cabbage, equipment bubbles.
Individual flow files are kept for backward compatibility but can migrate to use this.

Usage:
    from scripts.flows.resource_bubble_flow import resource_bubble_flow
    from utils.bubble_matcher import create_bubble_matcher

    # Use with generic matcher
    corn_matcher = create_bubble_matcher('corn')
    success = resource_bubble_flow(adb, corn_matcher, "CORN", win)

    # Or use convenience functions
    from scripts.flows.resource_bubble_flow import (
        corn_flow, gold_flow, iron_flow, gem_flow, cabbage_flow, equipment_flow
    )
    success = corn_flow(adb, win)
"""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.windows_screenshot_helper import WindowsScreenshotHelper


def resource_bubble_flow(adb, matcher, name: str, win=None) -> bool:
    """
    Generic flow to click a resource bubble if present.

    Args:
        adb: ADBHelper instance
        matcher: Any matcher with is_present(frame) and click(adb) methods
        name: Display name for logging (e.g., "CORN", "GOLD")
        win: WindowsScreenshotHelper instance (optional)

    Returns:
        bool: True if bubble was clicked, False if not present
    """
    if win is None:
        win = WindowsScreenshotHelper()

    frame = win.get_screenshot_cv2()

    is_present, score = matcher.is_present(frame)
    if not is_present:
        print(f"    [{name}] Not present (score={score:.3f})")
        return False

    matcher.click(adb)
    time.sleep(0.3)
    print(f"    [{name}] Clicked harvest bubble (score={score:.3f})")
    return True


# Convenience functions that maintain backward compatibility
# These can be imported directly as drop-in replacements

def corn_flow(adb, win=None) -> bool:
    """Click the corn harvest bubble if present."""
    from utils.bubble_matcher import create_bubble_matcher
    return resource_bubble_flow(adb, create_bubble_matcher('corn'), "CORN", win)


def gold_flow(adb, win=None) -> bool:
    """Click the gold coin bubble if present."""
    from utils.bubble_matcher import create_bubble_matcher
    return resource_bubble_flow(adb, create_bubble_matcher('gold'), "GOLD", win)


def iron_flow(adb, win=None) -> bool:
    """Click the iron bar bubble if present."""
    from utils.bubble_matcher import create_bubble_matcher
    return resource_bubble_flow(adb, create_bubble_matcher('iron'), "IRON", win)


def gem_flow(adb, win=None) -> bool:
    """Click the gem bubble if present."""
    from utils.bubble_matcher import create_bubble_matcher
    return resource_bubble_flow(adb, create_bubble_matcher('gem'), "GEM", win)


def cabbage_flow(adb, win=None) -> bool:
    """Click the cabbage bubble if present."""
    from utils.bubble_matcher import create_bubble_matcher
    return resource_bubble_flow(adb, create_bubble_matcher('cabbage'), "CABBAGE", win)


def equipment_flow(adb, win=None) -> bool:
    """Click the equipment enhancement bubble if present."""
    from utils.bubble_matcher import create_bubble_matcher
    return resource_bubble_flow(adb, create_bubble_matcher('equipment'), "EQUIPMENT", win)
