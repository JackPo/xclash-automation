"""
Hero Selector - Shared hero selection logic for rally/team-up flows.

Detects Zz sleep icons at fixed slot positions and selects the rightmost idle hero.
Used by both elite_zombie_flow and treasure_map_flow.

Zz Icon Slot Positions (4K resolution):
- Slot 3 (rightmost): (1946, 1851) size 40x36
- Slot 2 (middle): (1697, 1851) size 40x36
- Slot 1 (leftmost): (1447, 1851) size 40x36

Detection uses TM_SQDIFF_NORMED with threshold 0.1.
"""

import cv2
import numpy as np
from pathlib import Path


class HeroSelector:
    """Select rightmost idle hero based on Zz icon detection."""

    # Zz icon template
    TEMPLATE_PATH = Path('templates/ground_truth/zz_icon_template_4k.png')

    # Detection threshold (TM_SQDIFF_NORMED - lower = better match)
    THRESHOLD = 0.1

    # Fixed slot positions (x, y, w, h) and click centers
    # Ordered from rightmost to leftmost for priority selection
    SLOTS = [
        {'id': 3, 'pos': (1946, 1851), 'size': (40, 36), 'click': (1966, 1869)},  # rightmost
        {'id': 2, 'pos': (1697, 1851), 'size': (40, 36), 'click': (1717, 1869)},  # middle
        {'id': 1, 'pos': (1447, 1851), 'size': (40, 36), 'click': (1467, 1869)},  # leftmost
    ]

    def __init__(self):
        """Initialize the hero selector."""
        self.template = cv2.imread(str(self.TEMPLATE_PATH), cv2.IMREAD_COLOR)
        if self.template is None:
            raise FileNotFoundError(f"Template not found: {self.TEMPLATE_PATH}")

    def check_slot_has_zz(self, frame: np.ndarray, slot: dict) -> tuple[bool, float]:
        """
        Check if a slot has Zz icon (hero is idle).

        Args:
            frame: BGR numpy array (4K screenshot)
            slot: Slot dict with 'pos' and 'size'

        Returns:
            (is_idle, score) - is_idle=True if Zz present, score for debugging
        """
        x, y = slot['pos']
        w, h = slot['size']

        roi = frame[y:y+h, x:x+w]

        result = cv2.matchTemplate(roi, self.template, cv2.TM_SQDIFF_NORMED)
        min_val, _, _, _ = cv2.minMaxLoc(result)
        score = float(min_val)

        is_idle = score < self.THRESHOLD
        return is_idle, score

    def find_rightmost_idle(self, frame: np.ndarray, zz_mode: str = 'require') -> dict | None:
        """
        Find the rightmost hero based on Zz icon strategy.
        Used by: treasure_map_flow

        Args:
            frame: BGR numpy array (4K screenshot)
            zz_mode: Hero selection strategy:
                - 'require': ONLY return heroes WITH Zz. Return None if no Zz found.
                - 'prefer': PREFER heroes with Zz, but fallback to any hero if no Zz exists.
                - 'ignore': ALWAYS return first hero regardless of Zz status.

        Returns:
            Slot dict if found, None if no heroes available (only possible in 'require' mode)
        """
        if zz_mode == 'ignore':
            # Just return rightmost slot immediately
            return self.SLOTS[0]  # First element is rightmost

        # For 'require' and 'prefer': search for Zz heroes first
        for slot in self.SLOTS:  # Already ordered rightmost first
            is_idle, score = self.check_slot_has_zz(frame, slot)
            if is_idle:
                return slot

        # No Zz found
        if zz_mode == 'require':
            return None  # Must have Zz, return None
        else:  # zz_mode == 'prefer'
            return self.SLOTS[0]  # Fallback to rightmost slot

        return None

    def find_leftmost_idle(self, frame: np.ndarray, zz_mode: str = 'require') -> dict | None:
        """
        Find the leftmost hero based on Zz icon strategy.
        Used by: elite_zombie_flow, rally_join_flow

        Args:
            frame: BGR numpy array (4K screenshot)
            zz_mode: Hero selection strategy:
                - 'require': ONLY return heroes WITH Zz. Return None if no Zz found.
                - 'prefer': PREFER heroes with Zz, but fallback to any hero if no Zz exists.
                - 'ignore': ALWAYS return first hero regardless of Zz status.

        Returns:
            Slot dict if found, None if no heroes available (only possible in 'require' mode)
        """
        if zz_mode == 'ignore':
            # Just return leftmost slot immediately
            return self.SLOTS[-1]  # Last element is leftmost

        # For 'require' and 'prefer': search for Zz heroes first
        for slot in reversed(self.SLOTS):  # Reversed = leftmost first
            is_idle, score = self.check_slot_has_zz(frame, slot)
            if is_idle:
                return slot

        # No Zz found
        if zz_mode == 'require':
            return None  # Must have Zz, return None
        else:  # zz_mode == 'prefer'
            return self.SLOTS[-1]  # Fallback to leftmost slot

        return None

    def find_any_idle(self, frame: np.ndarray, zz_mode: str = 'require') -> dict | None:
        """
        Find ANY idle hero (first one with Zz icon found, no position preference).
        Used by: rally_join_flow during Union Boss mode

        Unlike find_leftmost_idle/find_rightmost_idle, this doesn't prefer any position.
        It just returns the first idle hero found (slot 3, 2, or 1).

        Args:
            frame: BGR numpy array (4K screenshot)
            zz_mode: Hero selection strategy:
                - 'require': ONLY return heroes WITH Zz. Return None if no Zz found.
                - 'prefer': PREFER heroes with Zz, but fallback to any hero if no Zz exists.
                - 'ignore': ALWAYS return first hero regardless of Zz status.

        Returns:
            Slot dict if found, None if no heroes available (only possible in 'require' mode)
        """
        if zz_mode == 'ignore':
            return self.SLOTS[0]  # Return first slot (rightmost)

        for slot in self.SLOTS:  # Checks 3, 2, 1
            is_idle, score = self.check_slot_has_zz(frame, slot)
            if is_idle:
                return slot

        if zz_mode == 'require':
            return None
        else:  # prefer
            return self.SLOTS[0]

    def get_all_slot_status(self, frame: np.ndarray) -> list[dict]:
        """
        Get status of all slots (for debugging).

        Args:
            frame: BGR numpy array (4K screenshot)

        Returns:
            List of dicts with slot info and status
        """
        results = []
        for slot in self.SLOTS:
            is_idle, score = self.check_slot_has_zz(frame, slot)
            results.append({
                'id': slot['id'],
                'pos': slot['pos'],
                'click': slot['click'],
                'score': score,
                'is_idle': is_idle,
            })
        return results


def find_rightmost_zz(frame: np.ndarray) -> int | None:
    """
    Convenience function to find rightmost idle hero slot.

    Args:
        frame: BGR numpy array (4K screenshot)

    Returns:
        Slot ID (1, 2, or 3) if found, None if all busy
    """
    selector = HeroSelector()
    slot = selector.find_rightmost_idle(frame)
    return slot['id'] if slot else None


def get_slot_click_position(slot_id: int) -> tuple[int, int]:
    """
    Get click position for a slot ID.

    Args:
        slot_id: 1, 2, or 3

    Returns:
        (x, y) click position
    """
    for slot in HeroSelector.SLOTS:
        if slot['id'] == slot_id:
            return slot['click']
    raise ValueError(f"Invalid slot_id: {slot_id}")


if __name__ == "__main__":
    # Test the hero selector
    from windows_screenshot_helper import WindowsScreenshotHelper

    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()

    selector = HeroSelector()
    print("Hero Slot Status:")
    print("=" * 50)

    for status in selector.get_all_slot_status(frame):
        idle_str = "Zz PRESENT (idle)" if status['is_idle'] else "NO Zz (busy)"
        print(f"Slot {status['id']}: score={status['score']:.4f} -> {idle_str}")

    print("=" * 50)

    rightmost = selector.find_rightmost_idle(frame)
    if rightmost:
        print(f"\nRightmost idle: Slot {rightmost['id']} -> click at {rightmost['click']}")
    else:
        print("\nNo idle heroes found!")
