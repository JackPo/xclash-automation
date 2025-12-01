"""
Gold coin harvest flow - clicks the gold coin bubble.
"""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.gold_coin_matcher import GoldCoinMatcher


def gold_coin_flow(adb):
    """Click the gold coin harvest bubble."""
    matcher = GoldCoinMatcher()
    matcher.click(adb)
    time.sleep(0.3)
    print("    [GOLD] Clicked harvest bubble")
