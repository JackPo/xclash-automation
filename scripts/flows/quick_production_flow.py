"""
Quick Production flow - use the Quick Production class skill.

This flow:
1. Navigates to WORLD view (from TOWN)
2. Clicks on own castle to open the castle popup
3. Clicks the "Class Skill" button
4. Waits for Class Skill panel to open
5. Clicks the "Quick Production" Use button
6. Returns to base view

Quick Production grants 24 hours of wheat, iron, and gold production instantly.
Cooldown: ~23.5 hours between uses.

Templates:
- class_skill_header_4k.png (690x92) - panel header verification
- class_skill_button_4k.png (200x160) - button in castle popup
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from config import (
    QUICK_PROD_CASTLE_CLICK,
    QUICK_PROD_CLASS_SKILL_CLICK,
    QUICK_PROD_CLASS_SKILL_REGION,
    QUICK_PROD_HEADER_REGION,
    QUICK_PROD_USE_CLICK,
)
from utils.template_matcher import match_template
from utils.view_state_detector import detect_view, ViewState, go_to_town, go_to_world
from utils.return_to_base_view import return_to_base_view
from utils.windows_screenshot_helper import WindowsScreenshotHelper

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper

# Template matching thresholds
CLASS_SKILL_BUTTON_THRESHOLD = 0.10
CLASS_SKILL_HEADER_THRESHOLD = 0.10


def quick_production_flow(
    adb: ADBHelper,
    win: WindowsScreenshotHelper | None = None,
    debug: bool = False
) -> bool:
    """
    Use the Quick Production class skill.

    Flow: TOWN -> WORLD -> castle click -> Class Skill -> Quick Production Use

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance (optional)
        debug: Enable debug output (default False)

    Returns:
        bool: True if Quick Production was successfully used
    """
    if win is None:
        win = WindowsScreenshotHelper()

    print("    [QUICK-PROD] Starting Quick Production flow...")

    try:
        # Step 1: Navigate to WORLD view
        print("    [QUICK-PROD] Step 1: Navigating to WORLD view...")
        frame = win.get_screenshot_cv2()
        state, score = detect_view(frame)
        print(f"    [QUICK-PROD] Current view: {state.name} (score={score:.4f})")

        if state == ViewState.TOWN:
            # Switch from TOWN to WORLD
            go_to_world(adb, debug=False)
            time.sleep(1.0)
        elif state != ViewState.WORLD:
            # Try to get to a known state first
            go_to_town(adb, debug=False)
            time.sleep(0.5)
            go_to_world(adb, debug=False)
            time.sleep(1.0)

        # Verify we're in WORLD
        frame = win.get_screenshot_cv2()
        state, score = detect_view(frame)
        if state != ViewState.WORLD:
            print(f"    [QUICK-PROD] FAILED: Not in WORLD view (got {state.name})")
            return False

        print("    [QUICK-PROD] Now in WORLD view")

        # Step 2: Click own castle
        print(f"    [QUICK-PROD] Step 2: Clicking castle at {QUICK_PROD_CASTLE_CLICK}...")
        adb.tap(*QUICK_PROD_CASTLE_CLICK, source="flow:quick_prod:castle")
        time.sleep(0.8)

        # Step 3: Verify castle popup opened and click Class Skill button
        print("    [QUICK-PROD] Step 3: Looking for Class Skill button...")
        frame = win.get_screenshot_cv2()

        # Verify Class Skill button is visible
        found, score, center = match_template(
            frame, "class_skill_button_4k.png",
            search_region=QUICK_PROD_CLASS_SKILL_REGION,
            threshold=CLASS_SKILL_BUTTON_THRESHOLD
        )

        if not found:
            print(f"    [QUICK-PROD] FAILED: Class Skill button not found (score={score:.4f})")
            return_to_base_view(adb, win, debug=False)
            return False

        print(f"    [QUICK-PROD] Class Skill button found (score={score:.4f}), clicking...")
        adb.tap(*QUICK_PROD_CLASS_SKILL_CLICK, source="flow:quick_prod:class_skill")
        time.sleep(0.8)

        # Step 4: Verify Class Skill panel opened
        print("    [QUICK-PROD] Step 4: Verifying Class Skill panel...")
        frame = win.get_screenshot_cv2()

        found, score, _ = match_template(
            frame, "class_skill_header_4k.png",
            search_region=QUICK_PROD_HEADER_REGION,
            threshold=CLASS_SKILL_HEADER_THRESHOLD
        )

        if not found:
            print(f"    [QUICK-PROD] FAILED: Class Skill panel not found (score={score:.4f})")
            return_to_base_view(adb, win, debug=False)
            return False

        print(f"    [QUICK-PROD] Class Skill panel open (score={score:.4f})")

        # Step 5: Click Quick Production Use button
        print(f"    [QUICK-PROD] Step 5: Clicking Quick Production Use at {QUICK_PROD_USE_CLICK}...")
        adb.tap(*QUICK_PROD_USE_CLICK, source="flow:quick_prod:use")
        time.sleep(0.5)

        # Step 6: Close panel (tap outside or wait for auto-close)
        print("    [QUICK-PROD] Step 6: Closing panel...")
        # Tap below panel to close it
        adb.tap(1920, 1900, source="flow:quick_prod:close")
        time.sleep(0.5)

        # Step 7: Return to base view
        print("    [QUICK-PROD] Step 7: Returning to base view...")
        return_to_base_view(adb, win, debug=False)

        print("    [QUICK-PROD] Flow complete - Quick Production used!")
        return True

    except Exception as e:
        print(f"    [QUICK-PROD] ERROR: {e}")
        try:
            return_to_base_view(adb, win, debug=False)
        except Exception:
            pass
        return False
