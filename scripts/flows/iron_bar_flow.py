"""
Iron bar harvest flow - clicks the iron bar bubble.
"""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.iron_bar_matcher import IronBarMatcher


def iron_bar_flow(adb):
    """Click the iron bar harvest bubble."""
    matcher = IronBarMatcher()
    matcher.click(adb)
    time.sleep(0.3)
    print("    [IRON] Clicked harvest bubble")
