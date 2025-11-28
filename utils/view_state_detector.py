"""
View state detector and navigator.

Detection - Button location (3600, 1920) 240x240:
- world_button_4k.png matches -> TOWN view
- town_button_4k.png matches -> WORLD view
- town_button_zoomed_out_4k.png matches -> WORLD view
- back_button_4k.png matches -> CHAT view

Navigation paths:
- TOWN -> WORLD: click (3720, 2040) - center of World button
- WORLD -> TOWN: click (3720, 2040) - center of Town button
- CHAT -> exit: click back button at (1407, 2055), then re-detect
"""
from pathlib import Path
from enum import Enum
import cv2
import numpy as np
import time


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

BACK_X = 1300
BACK_Y = 1950
BACK_W = 220
BACK_H = 220

# Click coordinates
TOGGLE_BUTTON_CLICK = (3720, 2040)  # Center of World/Town button
BACK_BUTTON_CLICK = (1407, 2055)    # Center of back button

THRESHOLD = 0.01  # For TM_SQDIFF_NORMED (lower = better match)
BACK_THRESHOLD = 0.7  # For TM_CCOEFF_NORMED (higher = better match)

BASE_DIR = Path(__file__).resolve().parent.parent / "templates" / "ground_truth"


def detect_view(frame: np.ndarray, debug: bool = False) -> tuple[ViewState, float]:
    """
    Detect view state by comparing corner to templates.

    Returns (ViewState, best_score)
    """
    if frame is None:
        return ViewState.UNKNOWN, 1.0

    # Extract button ROI
    roi = frame[BUTTON_Y:BUTTON_Y+BUTTON_H, BUTTON_X:BUTTON_X+BUTTON_W]
    if len(roi.shape) == 3:
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    else:
        roi_gray = roi

    # Load and compare templates
    templates = {
        "world_button_4k.png": ViewState.TOWN,
        "town_button_4k.png": ViewState.WORLD,
        "town_button_zoomed_out_4k.png": ViewState.WORLD,
    }

    for template_name, state in templates.items():
        template_path = BASE_DIR / template_name
        if not template_path.exists():
            continue
        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            continue

        result = cv2.matchTemplate(roi_gray, template, cv2.TM_SQDIFF_NORMED)
        score, _, _, _ = cv2.minMaxLoc(result)

        if debug:
            print(f"{template_name}: {score:.4f}")

        if score <= THRESHOLD:
            return state, score

    # Check back button area
    back_roi = frame[BACK_Y:BACK_Y+BACK_H, BACK_X:BACK_X+BACK_W]
    if len(back_roi.shape) == 3:
        back_gray = cv2.cvtColor(back_roi, cv2.COLOR_BGR2GRAY)
    else:
        back_gray = back_roi

    for back_name in ["back_button_4k.png", "back_button_light_4k.png"]:
        template_path = BASE_DIR / back_name
        if not template_path.exists():
            continue
        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            continue

        result = cv2.matchTemplate(back_gray, template, cv2.TM_CCOEFF_NORMED)
        _, score, _, _ = cv2.minMaxLoc(result)

        if debug:
            print(f"{back_name}: {score:.4f}")

        if score >= BACK_THRESHOLD:
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
            adb.tap(*BACK_BUTTON_CLICK)
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

        # UNKNOWN state - try clicking back button
        if current == ViewState.UNKNOWN:
            if debug:
                print(f"UNKNOWN state, trying back button")
            adb.tap(*BACK_BUTTON_CLICK)
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
        adb.tap(*BACK_BUTTON_CLICK)
        time.sleep(0.5)

    return ViewState.UNKNOWN


if __name__ == "__main__":
    import sys
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
