"""
View state detector and navigator.

Detection - Button location (3600, 1920) 240x240:
- world_button_4k.png matches -> TOWN view
- town_button_4k.png matches -> WORLD view
- town_button_zoomed_out_4k.png matches -> WORLD view

CHAT detection - Chat header at (1854, 36) 123x59:
- chat_header_4k.png matches -> CHAT view (NOT back button!)

Navigation paths:
- TOWN -> WORLD: click (3720, 2040) - center of World button
- WORLD -> TOWN: click (3720, 2040) - center of Town button
- CHAT -> exit: click back button at (1407, 2055), then re-detect
"""
from enum import Enum
import numpy as np
import time

from utils.template_matcher import match_template_fixed, match_template


class ViewState(Enum):
    TOWN = "town"
    WORLD = "world"
    CHAT = "chat"
    UNKNOWN = "unknown"


# Fixed coordinates for detection
BUTTON_X = 3600
BUTTON_Y = 1920
BUTTON_W = 240
BUTTON_H = 240

# Chat header coordinates (top of chat panel)
CHAT_HEADER_X = 1854
CHAT_HEADER_Y = 36
CHAT_HEADER_W = 123
CHAT_HEADER_H = 59

# Import from centralized config
from config import BACK_BUTTON_CLICK, TOGGLE_BUTTON_CLICK
from utils.ui_helpers import click_back

THRESHOLD = 0.05  # For TM_SQDIFF_NORMED (lower = better match)
CHAT_THRESHOLD = 0.05  # For chat header detection


def detect_view(frame: np.ndarray, debug: bool = False) -> tuple[ViewState, float]:
    """
    Detect view state by comparing corner to templates.

    Returns (ViewState, best_score)
    """
    if frame is None:
        return ViewState.UNKNOWN, 1.0

    # Templates to check for main view
    templates = [
        ("world_button_4k.png", ViewState.TOWN),
        ("town_button_4k.png", ViewState.WORLD),
        ("town_button_zoomed_out_4k.png", ViewState.WORLD),
    ]

    for template_name, state in templates:
        found, score, _ = match_template_fixed(
            frame,
            template_name,
            position=(BUTTON_X, BUTTON_Y),
            size=(BUTTON_W, BUTTON_H),
            threshold=THRESHOLD
        )

        if debug:
            print(f"{template_name}: {score:.4f}")

        if found:
            return state, score

    # Check for CHAT state using Chat header template (NOT back button!)
    found, score, _ = match_template_fixed(
        frame,
        "chat_header_4k.png",
        position=(CHAT_HEADER_X, CHAT_HEADER_Y),
        size=(CHAT_HEADER_W, CHAT_HEADER_H),
        threshold=CHAT_THRESHOLD
    )

    if debug:
        print(f"chat_header_4k.png: {score:.4f}")

    if found:
        return ViewState.CHAT, score

    return ViewState.UNKNOWN, 1.0


def navigate_to(adb, target: ViewState, max_attempts: int = 5, debug: bool = False) -> bool:
    """
    Navigate from current view to target view.

    Args:
        adb: ADBHelper instance
        target: ViewState to navigate to (TOWN or WORLD)
        max_attempts: Max clicks before giving up
        debug: Print debug info

    Returns:
        True if reached target, False if failed
    """
    from utils.windows_screenshot_helper import WindowsScreenshotHelper
    win = WindowsScreenshotHelper()

    for attempt in range(max_attempts):
        # Take screenshot with Windows (matches templates) and detect
        frame = win.get_screenshot_cv2()
        current, score = detect_view(frame, debug=debug)

        if debug:
            print(f"[{attempt+1}] Current: {current.value}, Target: {target.value}")

        # Already at target
        if current == target:
            if debug:
                print(f"Reached {target.value}")
            return True

        # In CHAT - click back button to exit
        if current == ViewState.CHAT:
            if debug:
                print(f"In CHAT, clicking back button at {BACK_BUTTON_CLICK}")
            click_back(adb)
            time.sleep(0.5)
            continue

        # In TOWN, want WORLD - click toggle button
        if current == ViewState.TOWN and target == ViewState.WORLD:
            if debug:
                print(f"TOWN->WORLD, clicking toggle at {TOGGLE_BUTTON_CLICK}")
            adb.tap(*TOGGLE_BUTTON_CLICK)
            time.sleep(1.0)
            continue

        # In WORLD, want TOWN - click toggle button
        if current == ViewState.WORLD and target == ViewState.TOWN:
            if debug:
                print(f"WORLD->TOWN, clicking toggle at {TOGGLE_BUTTON_CLICK}")
            adb.tap(*TOGGLE_BUTTON_CLICK)
            time.sleep(1.0)
            continue

        # UNKNOWN state - likely a dialog/popup blocking the view
        if current == ViewState.UNKNOWN:
            from utils.safe_grass_matcher import find_safe_grass
            from utils.safe_ground_matcher import find_safe_ground
            from utils.template_matcher import match_template

            # FIRST: Check for back button with HIGH CERTAINTY (masked template)
            # This catches dialogs/menus that need back button to close
            back_found, back_score, back_pos = match_template(
                frame, "back_button_union_4k.png", threshold=0.98
            )
            if back_found:
                if debug:
                    print(f"UNKNOWN state, back button detected (score={back_score:.4f}) - clicking at {BACK_BUTTON_CLICK}")
                click_back(adb)
                time.sleep(0.5)
                continue

            # If no back button, check grass/ground for floating popups
            grass_pos = find_safe_grass(frame, debug=False)
            if grass_pos:
                if debug:
                    print(f"UNKNOWN state, grass detected (WORLD) - clicking at {grass_pos} to dismiss popup")
                adb.tap(*grass_pos)
                time.sleep(0.5)
                continue

            ground_pos = find_safe_ground(frame, debug=False)
            if ground_pos:
                if debug:
                    print(f"UNKNOWN state, ground detected (TOWN) - clicking at {ground_pos} to dismiss popup")
                adb.tap(*ground_pos)
                time.sleep(0.5)
                continue

            # Nothing found - try back button anyway as last resort
            if debug:
                print(f"UNKNOWN state, nothing detected - trying back button at {BACK_BUTTON_CLICK}")
            click_back(adb)
            time.sleep(0.5)
            continue

    if debug:
        print(f"Failed to reach {target.value} after {max_attempts} attempts")
    return False


def go_to_town(adb, debug: bool = False) -> bool:
    """Navigate to TOWN view."""
    return navigate_to(adb, ViewState.TOWN, debug=debug)


def go_to_world(adb, debug: bool = False) -> bool:
    """Navigate to WORLD view."""
    return navigate_to(adb, ViewState.WORLD, debug=debug)


def exit_chat(adb, debug: bool = False) -> ViewState:
    """
    Exit CHAT view by clicking back button until we're in TOWN or WORLD.

    Returns the final ViewState reached.
    """
    from utils.windows_screenshot_helper import WindowsScreenshotHelper
    win = WindowsScreenshotHelper()

    for _ in range(5):
        frame = win.get_screenshot_cv2()
        current, _ = detect_view(frame, debug=debug)

        if current in (ViewState.TOWN, ViewState.WORLD):
            return current

        # Click back button
        click_back(adb)
        time.sleep(0.5)

    return ViewState.UNKNOWN


if __name__ == "__main__":
    import sys
    from pathlib import Path
    import cv2

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from utils.adb_helper import ADBHelper

    adb = ADBHelper()
    adb.take_screenshot("view_check.png")

    frame = cv2.imread("view_check.png")
    state, score = detect_view(frame, debug=True)
    print(f"\nCurrent view: {state.value} (score={score:.4f}")

    # Test navigation
    if len(sys.argv) > 1:
        target = sys.argv[1].lower()
        if target == "town":
            print("\nNavigating to TOWN...")
            success = go_to_town(adb, debug=True)
            print(f"Success: {success}")
        elif target == "world":
            print("\nNavigating to WORLD...")
            success = go_to_world(adb, debug=True)
            print(f"Success: {success}")
