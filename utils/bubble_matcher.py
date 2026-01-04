"""
Generic bubble matcher for resource harvest detection.

This provides a unified interface for all bubble matchers (corn, gold, iron, gem, cabbage, equipment).
Individual matcher files are kept for backward compatibility but can migrate to use this.

Usage:
    from utils.bubble_matcher import BubbleMatcher, create_bubble_matcher

    # Create matcher from config key
    corn_matcher = create_bubble_matcher('corn')
    gold_matcher = create_bubble_matcher('gold')

    # Or use directly
    matcher = BubbleMatcher(
        config_key='corn',
        template_name='corn_harvest_bubble_4k.png',
        threshold=0.06
    )
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt

from utils.template_matcher import match_template

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper


# Mapping of config keys to their bubble config and template names
BUBBLE_CONFIGS = {
    'corn': {
        'config_import': 'CORN_BUBBLE',
        'template': 'corn_harvest_bubble_4k.png',
        'threshold_key': 'corn',
        'default_threshold': 0.06,
    },
    'gold': {
        'config_import': 'GOLD_BUBBLE',
        'template': 'gold_coin_tight_4k.png',
        'threshold_key': 'gold',
        'default_threshold': 0.06,
    },
    'iron': {
        'config_import': 'IRON_BUBBLE',
        'template': 'iron_bar_tight_4k.png',
        'threshold_key': 'iron',
        'default_threshold': 0.08,
    },
    'gem': {
        'config_import': 'GEM_BUBBLE',
        'template': 'gem_tight_4k.png',
        'threshold_key': 'gem',
        'default_threshold': 0.13,
    },
    'cabbage': {
        'config_import': 'CABBAGE_BUBBLE',
        'template': 'cabbage_tight_4k.png',
        'threshold_key': 'cabbage',
        'default_threshold': 0.05,
    },
    'equipment': {
        'config_import': 'EQUIPMENT_BUBBLE',
        'template': 'sword_tight_4k.png',
        'threshold_key': 'equipment',
        'default_threshold': 0.06,
    },
}


class BubbleMatcher:
    """
    Generic presence detector for resource bubbles at configurable locations.

    This class can replace all individual bubble matchers (corn, gold, iron, gem, cabbage, equipment).
    """

    def __init__(
        self,
        region: tuple[int, int, int, int],
        click_pos: tuple[int, int],
        template_name: str,
        threshold: float = 0.06,
        name: str = "bubble"
    ) -> None:
        """
        Initialize bubble detector.

        Args:
            region: (x, y, width, height) for template detection
            click_pos: (x, y) coordinates for clicking
            template_name: Template filename in templates/ground_truth/
            threshold: Maximum difference score (TM_SQDIFF_NORMED)
            name: Display name for logging
        """
        self.icon_x = region[0]
        self.icon_y = region[1]
        self.icon_width = region[2]
        self.icon_height = region[3]
        self.click_x = click_pos[0]
        self.click_y = click_pos[1]
        self.template_name = template_name
        self.threshold = threshold
        self.name = name

    def is_present(self, frame: npt.NDArray[Any], save_debug: bool = False) -> tuple[bool, float]:
        """
        Check if bubble is present at FIXED location.

        Args:
            frame: BGR image frame from screenshot
            save_debug: Ignored (kept for backward compatibility)

        Returns:
            Tuple of (is_present, score)
        """
        if frame is None or frame.size == 0:
            return False, 1.0

        is_present, score, _ = match_template(frame, self.template_name, search_region=(self.icon_x, self.icon_y, self.icon_width, self.icon_height),
            threshold=self.threshold
        )

        return is_present, score

    def click(self, adb_helper: ADBHelper) -> None:
        """Click at the FIXED bubble center position."""
        adb_helper.tap(self.click_x, self.click_y)


def create_bubble_matcher(config_key: str, threshold: float | None = None) -> BubbleMatcher:
    """
    Factory function to create a BubbleMatcher from a config key.

    Args:
        config_key: One of 'corn', 'gold', 'iron', 'gem', 'cabbage', 'equipment'
        threshold: Optional override for default threshold

    Returns:
        Configured BubbleMatcher instance

    Raises:
        ValueError: If config_key is not recognized
    """
    if config_key not in BUBBLE_CONFIGS:
        raise ValueError(f"Unknown bubble config key: {config_key}. "
                         f"Valid keys: {list(BUBBLE_CONFIGS.keys())}")

    cfg = BUBBLE_CONFIGS[config_key]

    # Import the config dynamically
    import config as config_module
    bubble_config: dict[str, Any] = getattr(config_module, str(cfg['config_import']))
    thresholds: dict[str, float] = getattr(config_module, 'THRESHOLDS', {})

    # Get region and click from bubble config
    region: tuple[int, int, int, int] = bubble_config['region']
    click_pos: tuple[int, int] = bubble_config['click']

    # Get threshold (parameter > config > default)
    final_threshold: float
    if threshold is None:
        default = cfg['default_threshold']
        final_threshold = thresholds.get(str(cfg['threshold_key']), float(default) if isinstance(default, (int, float)) else 0.06)
    else:
        final_threshold = threshold

    return BubbleMatcher(
        region=region,
        click_pos=click_pos,
        template_name=str(cfg['template']),
        threshold=final_threshold,
        name=config_key
    )
