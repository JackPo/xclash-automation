"""
Corn harvest flow - clicks the corn bubble.
"""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.corn_harvest_matcher import CornHarvestMatcher


def corn_harvest_flow(adb):
    """Click the corn harvest bubble."""
    matcher = CornHarvestMatcher()
    matcher.click(adb)
    time.sleep(0.3)
    print("    [CORN] Clicked harvest bubble")
