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
from utils.current_state import update_quick_production

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

    Flow: TOWN -> WORLD (centers on castle) -> click center -> Class Skill -> Quick Production Use

    IMPORTANT: Must go TOWN -> WORLD to center the map on own castle.
    After centering, castle is at screen center (1920, 1080).

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
        # Step 1: Go to TOWN first (required for centering)
        print("    [QUICK-PROD] Step 1: Going to TOWN...")
        go_to_town(adb, debug=False)
        time.sleep(1.0)

        # Step 2: Go to WORLD - this centers the map on own castle
        print("    [QUICK-PROD] Step 2: Going to WORLD (centers on castle)...")
        go_to_world(adb, debug=False)
        time.sleep(1.0)

        # Step 3: Click center of screen to open own castle popup
        # After TOWN->WORLD, castle is at screen center
        SCREEN_CENTER = (1920, 1080)
        print(f"    [QUICK-PROD] Step 3: Clicking castle at center {SCREEN_CENTER}...")
        adb.tap(*SCREEN_CENTER, source="flow:quick_prod:castle")
        time.sleep(1.0)

        # Step 4: Find and click Class Skill button
        print("    [QUICK-PROD] Step 4: Looking for Class Skill button...")
        frame = win.get_screenshot_cv2()

        found, score, center = match_template(
            frame, "class_skill_button_4k.png",
            threshold=CLASS_SKILL_BUTTON_THRESHOLD
        )

        if not found:
            print(f"    [QUICK-PROD] FAILED: Class Skill button not found (score={score:.4f})")
            return_to_base_view(adb, win, debug=False)
            return False

        print(f"    [QUICK-PROD] Class Skill button found at {center} (score={score:.4f}), clicking...")
        adb.tap(*center, source="flow:quick_prod:class_skill")
        time.sleep(1.0)

        # Step 5: Verify Class Skill panel opened
        print("    [QUICK-PROD] Step 5: Verifying Class Skill panel...")
        frame = win.get_screenshot_cv2()

        found, score, _ = match_template(
            frame, "class_skill_header_4k.png",
            threshold=CLASS_SKILL_HEADER_THRESHOLD
        )

        if not found:
            print(f"    [QUICK-PROD] FAILED: Class Skill panel not found (score={score:.4f})")
            return_to_base_view(adb, win, debug=False)
            return False

        print(f"    [QUICK-PROD] Class Skill panel open (score={score:.4f})")

        # Step 6: Click Quick Production Use button (third row)
        print(f"    [QUICK-PROD] Step 6: Clicking Quick Production Use at {QUICK_PROD_USE_CLICK}...")
        adb.tap(*QUICK_PROD_USE_CLICK, source="flow:quick_prod:use")
        time.sleep(1.0)

        # Step 7: Tap to close reward popup
        print("    [QUICK-PROD] Step 7: Closing reward popup...")
        adb.tap(1920, 1500, source="flow:quick_prod:close")
        time.sleep(0.5)

        # Step 8: Return to base view
        print("    [QUICK-PROD] Step 8: Returning to base view...")
        return_to_base_view(adb, win, debug=False)

        # Update state with next available time (24 hours from now)
        update_quick_production(success=True)

        print("    [QUICK-PROD] Flow complete - Quick Production used!")
        return True

    except Exception as e:
        print(f"    [QUICK-PROD] ERROR: {e}")
        try:
            return_to_base_view(adb, win, debug=False)
        except Exception:
            pass
        return False
