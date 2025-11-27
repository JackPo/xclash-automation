"""
Equipment enhancement flow - clicks the crossed swords bubble.
"""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.equipment_enhancement_matcher import EquipmentEnhancementMatcher


def equipment_enhancement_flow(adb):
    """Click the equipment enhancement bubble."""
    matcher = EquipmentEnhancementMatcher()
    matcher.click(adb)
    time.sleep(0.3)
