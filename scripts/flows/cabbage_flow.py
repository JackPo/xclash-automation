"""
Cabbage harvest flow - clicks the cabbage bubble.
"""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.cabbage_matcher import CabbageMatcher


def cabbage_flow(adb):
    """Click the cabbage bubble."""
    matcher = CabbageMatcher()
    matcher.click(adb)
    time.sleep(0.3)
