"""
Gem harvest flow - clicks the gem bubble.
"""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.gem_matcher import GemMatcher


def gem_flow(adb):
    """Click the gem harvest bubble."""
    matcher = GemMatcher()
    matcher.click(adb)
    time.sleep(0.3)
    print("    [GEM] Clicked harvest bubble")
