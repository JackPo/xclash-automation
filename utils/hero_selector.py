"""
Hero Selector - Shared hero selection logic for rally/team-up flows.

Uses template_matcher for fixed-position detection.

Detects Zz sleep icons at fixed slot positions and selects the rightmost idle hero.
Used by both elite_zombie_flow and treasure_map_flow.

Zz Icon Slot Positions (4K resolution):
- Slot 3 (rightmost): (1946, 1851) size 40x36
- Slot 2 (middle): (1697, 1851) size 40x36
- Slot 1 (leftmost): (1447, 1851) size 40x36

Detection uses TM_SQDIFF_NORMED with threshold 0.1.
"""

from __future__ import annotations

from typing import Any, TypedDict

import numpy as np
import numpy.typing as npt

from utils.template_matcher import match_template


class SlotInfo(TypedDict):
    id: int
    pos: tuple[int, int]
    size: tuple[int, int]
    click: tuple[int, int]


class SlotStatus(TypedDict):
    id: int
    pos: tuple[int, int]
    click: tuple[int, int]
    score: float
    is_idle: bool


class HeroSelector:
    """Select rightmost idle hero based on Zz icon detection."""

    TEMPLATE_NAME = "zz_icon_template_4k.png"
    THRESHOLD = 0.1

    SLOTS: list[SlotInfo] = [
        {'id': 3, 'pos': (1946, 1851), 'size': (40, 36), 'click': (1966, 1869)},
        {'id': 2, 'pos': (1697, 1851), 'size': (40, 36), 'click': (1717, 1869)},
        {'id': 1, 'pos': (1447, 1851), 'size': (40, 36), 'click': (1467, 1869)},
    ]

    def __init__(self) -> None:
        pass

    def check_slot_has_zz(self, frame: npt.NDArray[Any], slot: SlotInfo) -> tuple[bool, float]:
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

        found, score, _ = match_template(frame, self.TEMPLATE_NAME, search_region=(x, y, w, h),
            threshold=self.THRESHOLD
        )

        return found, score

    def find_rightmost_idle(self, frame: npt.NDArray[Any], zz_mode: str = 'require') -> SlotInfo | None:
        """
        Find the rightmost hero based on Zz icon strategy.
        Used by: treasure_map_flow

        Args:
            frame: BGR numpy array (4K screenshot)
            zz_mode: Hero selection strategy:
                - 'require': ONLY return heroes WITH Zz. Return None if no Zz found.
                - 'prefer': PREFER heroes with Zz, but fallback to any hero if no Zz exists.
                - 'ignore': ALWAYS return first hero regardless of Zz status.
                - 'avoid': ONLY return heroes WITHOUT Zz (busy). Return None if all have Zz.

        Returns:
            Slot dict if found, None if no heroes available (only possible in 'require'/'avoid' mode)
        """
        if zz_mode == 'ignore':
            return self.SLOTS[0]

        if zz_mode == 'avoid':
            for slot in self.SLOTS:
                is_idle, _ = self.check_slot_has_zz(frame, slot)
                if not is_idle:
                    return slot
            return None

        for slot in self.SLOTS:
            is_idle, _ = self.check_slot_has_zz(frame, slot)
            if is_idle:
                return slot

        if zz_mode == 'require':
            return None
        else:
            return self.SLOTS[0]

    def find_leftmost_idle(self, frame: npt.NDArray[Any], zz_mode: str = 'require') -> SlotInfo | None:
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
            return self.SLOTS[-1]

        for slot in reversed(self.SLOTS):
            is_idle, _ = self.check_slot_has_zz(frame, slot)
            if is_idle:
                return slot

        if zz_mode == 'require':
            return None
        else:
            return self.SLOTS[-1]

    def find_any_idle(self, frame: npt.NDArray[Any], zz_mode: str = 'require') -> SlotInfo | None:
        """
        Find ANY idle hero (first one with Zz icon found, no position preference).
        Used by: rally_join_flow during Union Boss mode

        Args:
            frame: BGR numpy array (4K screenshot)
            zz_mode: Hero selection strategy

        Returns:
            Slot dict if found, None if no heroes available (only possible in 'require' mode)
        """
        if zz_mode == 'ignore':
            return self.SLOTS[0]

        for slot in self.SLOTS:
            is_idle, _ = self.check_slot_has_zz(frame, slot)
            if is_idle:
                return slot

        if zz_mode == 'require':
            return None
        else:
            return self.SLOTS[0]

    def get_all_slot_status(self, frame: npt.NDArray[Any]) -> list[SlotStatus]:
        """
        Get status of all slots (for debugging).
        """
        results: list[SlotStatus] = []
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


def find_rightmost_zz(frame: npt.NDArray[Any]) -> int | None:
    """
    Convenience function to find rightmost idle hero slot.

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
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

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
