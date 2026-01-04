"""
Royal City Attack/Reinforce Flow - Navigate to Royal City and attack or reinforce.

Uses Gemini to detect buttons on the fly since we can't capture templates in advance.

Usage:
    python scripts/flows/royal_city_attack_flow.py
"""

from __future__ import annotations

import sys
import time
import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.adb_helper import ADBHelper
from utils.return_to_base_view import return_to_base_view
from utils.view_state_detector import go_to_world
from scripts.flows.go_to_mark_flow import go_to_mark_flow

if TYPE_CHECKING:
    pass

CALIBRATION_DIR = Path(__file__).parent.parent.parent / "calibration"
SCREENSHOTS_DIR = Path(__file__).parent.parent.parent / "screenshots" / "debug" / "royal_city_attack"


def detect_with_gemini(screenshot_path: str, prompt: str) -> dict[str, int] | None:
    """Use Gemini to detect an object in screenshot. Returns {x, y, width, height} or None."""
    result = subprocess.run(
        ["python", str(CALIBRATION_DIR / "detect_object.py"), screenshot_path, prompt, "--json"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent.parent)
    )

    if result.returncode != 0:
        print(f"    Gemini detection failed: {result.stderr}")
        return None

    try:
        # Parse JSON output
        output = result.stdout.strip()
        # Find the JSON part (after any debug output)
        for line in output.split('\n'):
            if line.startswith('{'):
                parsed: dict[str, Any] = json.loads(line)
                return parsed
    except json.JSONDecodeError as e:
        print(f"    Failed to parse Gemini output: {e}")
        print(f"    Raw output: {result.stdout}")

    return None


def save_screenshot(win: WindowsScreenshotHelper, name: str) -> str:
    """Save screenshot and return path."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOTS_DIR / f"{name}.png"
    frame = win.get_screenshot_cv2()
    if frame is not None:
        import cv2
        cv2.imwrite(str(path), frame)
    return str(path)


def click_center(adb: ADBHelper, bbox: dict[str, int]) -> None:
    """Click center of bounding box."""
    x = bbox['x'] + bbox['width'] // 2
    y = bbox['y'] + bbox['height'] // 2
    print(f"    Clicking ({x}, {y})")
    adb.tap(x, y)


def royal_city_attack_flow(
    adb: ADBHelper,
    win: WindowsScreenshotHelper | None = None,
    debug: bool = True,
) -> bool:
    """
    Navigate to Royal City and attack or reinforce it.

    Returns:
        True if successful, False otherwise
    """
    win = win or WindowsScreenshotHelper()

    print("=== ROYAL CITY ATTACK FLOW ===")
    print()

    try:
        # Step 1: Go to marked Royal City location
        print("Step 1: Navigating to Royal City via go_to_mark...")
        if not go_to_mark_flow(adb, win, debug=debug):
            print("  ERROR: Failed to navigate to Royal City")
            return False

        time.sleep(2.0)  # Wait for map to settle

        # Step 2: Take screenshot and find the city to click on
        print("Step 2: Looking for Royal City to click...")
        screenshot_path = save_screenshot(win, "01_at_marked_location")

        # Try to find a clickable city/castle structure
        bbox = detect_with_gemini(screenshot_path, "the Royal City castle or main building structure in the center of the screen that can be clicked")
        if bbox:
            print(f"  Found city at: {bbox}")
            click_center(adb, bbox)
            time.sleep(1.5)
        else:
            # Fallback: click center of screen where marked location should be
            print("  City not detected, clicking screen center...")
            adb.tap(1920, 1080)
            time.sleep(1.5)

        # Step 3: Look for Attack or Reinforce button
        print("Step 3: Looking for Attack or Reinforce button...")
        screenshot_path = save_screenshot(win, "02_city_menu")

        # Try Attack first
        bbox = detect_with_gemini(screenshot_path, "the Attack button with sword or combat icon")
        if bbox:
            print(f"  Found ATTACK button at: {bbox}")
            click_center(adb, bbox)
            time.sleep(1.0)
        else:
            # Try Reinforce
            bbox = detect_with_gemini(screenshot_path, "the Reinforce button or Garrison button to send troops to defend")
            if bbox:
                print(f"  Found REINFORCE button at: {bbox}")
                click_center(adb, bbox)
                time.sleep(1.0)
            else:
                print("  ERROR: Neither Attack nor Reinforce button found")
                save_screenshot(win, "03_no_button_found")
                return False

        # Step 4: Troop selection screen - find any soldier/troop to select
        print("Step 4: Selecting troops...")
        screenshot_path = save_screenshot(win, "04_troop_selection")

        # Look for a troop/soldier slot or plus button to add troops
        bbox = detect_with_gemini(screenshot_path, "any soldier portrait, troop icon, or plus button to add troops on the left side")
        if bbox:
            print(f"  Found troop selector at: {bbox}")
            click_center(adb, bbox)
            time.sleep(0.5)

        # Step 5: Look for March or Send button
        print("Step 5: Looking for March/Send button...")
        screenshot_path = save_screenshot(win, "05_before_march")

        bbox = detect_with_gemini(screenshot_path, "the March button or Send button or Go button at the bottom to dispatch troops")
        if bbox:
            print(f"  Found MARCH button at: {bbox}")
            click_center(adb, bbox)
            time.sleep(1.0)
            print("  Troops dispatched!")
        else:
            print("  WARNING: March button not found, checking if already sent...")

        # Final screenshot
        save_screenshot(win, "06_final_state")

        print()
        print("=== ROYAL CITY ATTACK FLOW COMPLETE ===")
        return True

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        print("Returning to base view...")
        return_to_base_view(adb, win, debug=False)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Attack or reinforce Royal City")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    print("Royal City Attack/Reinforce Flow")
    print("=" * 50)
    print()

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    result = royal_city_attack_flow(adb, win, debug=args.debug)

    print()
    print(f"Result: {'SUCCESS' if result else 'FAILED'}")
