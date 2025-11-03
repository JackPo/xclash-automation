#!/usr/bin/env python3
"""
XClash Map Calibration Tool
One-time interactive calibration to determine map size and navigation parameters.
Results are saved to map_config.json for reuse.

Usage:
    python calibrate_map.py
"""

import sys
import json
import time
from pathlib import Path
from find_player import ADBController, Config
from game_utils import GameHelper


def wait_for_input(prompt="Press Enter to continue..."):
    """Wait for user input."""
    input(prompt)


def get_int_input(prompt, default=None):
    """Get integer input from user."""
    while True:
        try:
            value = input(prompt)
            if not value and default is not None:
                return default
            return int(value)
        except ValueError:
            print("Please enter a valid number.")


def calibrate_navigation(adb, config):
    """Calibrate map navigation parameters."""
    print("\n" + "="*60)
    print("STEP 1: CALIBRATE EDGE NAVIGATION")
    print("="*60)

    print("\nWe'll determine how many swipes it takes to reach each edge.")
    print("Starting from current position...")
    wait_for_input()

    # Center coordinates for swiping
    center_x = (config.MAP_LEFT + config.MAP_RIGHT) // 2
    center_y = (config.MAP_TOP + config.MAP_BOTTOM) // 2

    # Calibrate LEFT edge
    print("\n--- Finding LEFT edge ---")
    print("We'll swipe left repeatedly until you see the map edge.")
    print("Count the swipes and tell us when you reach the edge.")
    wait_for_input("Press Enter to start swiping left...")

    left_swipes = 0
    while True:
        adb.swipe(
            center_x + config.HORIZONTAL_SCROLL_DISTANCE // 2,
            center_y,
            center_x - config.HORIZONTAL_SCROLL_DISTANCE // 2,
            center_y,
            config.SCROLL_DURATION
        )
        left_swipes += 1
        time.sleep(config.DELAY_AFTER_SWIPE)

        response = input(f"Swipe {left_swipes}. At left edge? (y/n/a=add more): ").lower()
        if response == 'y':
            break
        elif response == 'a':
            # Add a few more for safety
            for i in range(3):
                adb.swipe(
                    center_x + config.HORIZONTAL_SCROLL_DISTANCE // 2,
                    center_y,
                    center_x - config.HORIZONTAL_SCROLL_DISTANCE // 2,
                    center_y,
                    config.SCROLL_DURATION
                )
                left_swipes += 1
                time.sleep(config.DELAY_AFTER_SWIPE)
            break

    print(f"✅ Left edge reached after {left_swipes} swipes")

    # Calibrate TOP edge
    print("\n--- Finding TOP edge ---")
    print("From left edge, now finding top edge...")
    wait_for_input("Press Enter to start swiping up...")

    up_swipes = 0
    while True:
        adb.swipe(
            center_x,
            center_y + config.VERTICAL_SCROLL_DISTANCE // 2,
            center_x,
            center_y - config.VERTICAL_SCROLL_DISTANCE // 2,
            config.SCROLL_DURATION
        )
        up_swipes += 1
        time.sleep(config.DELAY_AFTER_SWIPE)

        response = input(f"Swipe {up_swipes}. At top edge? (y/n/a=add more): ").lower()
        if response == 'y':
            break
        elif response == 'a':
            for i in range(3):
                adb.swipe(
                    center_x,
                    center_y + config.VERTICAL_SCROLL_DISTANCE // 2,
                    center_x,
                    center_y - config.VERTICAL_SCROLL_DISTANCE // 2,
                    config.SCROLL_DURATION
                )
                up_swipes += 1
                time.sleep(config.DELAY_AFTER_SWIPE)
            break

    print(f"✅ Top edge reached after {up_swipes} swipes")
    print(f"\n📍 You are now at TOP-LEFT corner (0,0)")

    return {
        "swipes_to_left_edge": left_swipes,
        "swipes_to_top_edge": up_swipes
    }


def calibrate_map_size(adb, config):
    """Calibrate map dimensions."""
    print("\n" + "="*60)
    print("STEP 2: CALIBRATE MAP SIZE")
    print("="*60)

    center_x = (config.MAP_LEFT + config.MAP_RIGHT) // 2
    center_y = (config.MAP_TOP + config.MAP_BOTTOM) // 2

    # Measure horizontal
    print("\nFrom top-left corner, we'll scroll right until we reach the right edge.")
    print("We'll count how many 'screen-widths' the map is.")
    wait_for_input("Press Enter to start scrolling right...")

    horizontal_steps = 0
    while True:
        adb.swipe(
            center_x - config.HORIZONTAL_SCROLL_DISTANCE // 2,
            center_y,
            center_x + config.HORIZONTAL_SCROLL_DISTANCE // 2,
            center_y,
            config.SCROLL_DURATION
        )
        horizontal_steps += 1
        time.sleep(config.DELAY_AFTER_SWIPE)

        response = input(f"Step {horizontal_steps}. At right edge? (y/n): ").lower()
        if response == 'y':
            break

    print(f"✅ Map width: {horizontal_steps} steps")

    # Go back to left
    print("\nGoing back to left edge...")
    for i in range(horizontal_steps + 2):
        adb.swipe(
            center_x + config.HORIZONTAL_SCROLL_DISTANCE // 2,
            center_y,
            center_x - config.HORIZONTAL_SCROLL_DISTANCE // 2,
            center_y,
            config.SCROLL_DURATION
        )
        time.sleep(config.DELAY_AFTER_SWIPE * 0.5)

    # Measure vertical
    print("\nNow scrolling down to find bottom edge...")
    wait_for_input("Press Enter to start scrolling down...")

    vertical_steps = 0
    while True:
        adb.swipe(
            center_x,
            center_y - config.VERTICAL_SCROLL_DISTANCE // 2,
            center_x,
            center_y + config.VERTICAL_SCROLL_DISTANCE // 2,
            config.SCROLL_DURATION
        )
        vertical_steps += 1
        time.sleep(config.DELAY_AFTER_SWIPE)

        response = input(f"Step {vertical_steps}. At bottom edge? (y/n): ").lower()
        if response == 'y':
            break

    print(f"✅ Map height: {vertical_steps} steps")

    return {
        "horizontal_steps": horizontal_steps,
        "vertical_steps": vertical_steps
    }


def calibrate_scroll_distance(adb, config):
    """Fine-tune scroll distances."""
    print("\n" + "="*60)
    print("STEP 3: VERIFY SCROLL DISTANCES")
    print("="*60)

    print(f"\nCurrent horizontal scroll distance: {config.HORIZONTAL_SCROLL_DISTANCE}px")
    print(f"Current vertical scroll distance: {config.VERTICAL_SCROLL_DISTANCE}px")
    print("\nThese should move the map about 70-80% of screen width/height.")
    print("This creates slight overlap to avoid missing castles at boundaries.")

    adjust = input("\nAre these distances good? (y/n): ").lower()

    if adjust == 'n':
        h_dist = get_int_input(f"Enter horizontal distance [{config.HORIZONTAL_SCROLL_DISTANCE}]: ",
                                config.HORIZONTAL_SCROLL_DISTANCE)
        v_dist = get_int_input(f"Enter vertical distance [{config.VERTICAL_SCROLL_DISTANCE}]: ",
                                config.VERTICAL_SCROLL_DISTANCE)
        return {
            "horizontal_scroll_distance": h_dist,
            "vertical_scroll_distance": v_dist
        }

    return {
        "horizontal_scroll_distance": config.HORIZONTAL_SCROLL_DISTANCE,
        "vertical_scroll_distance": config.VERTICAL_SCROLL_DISTANCE
    }


def save_calibration(calibration_data, output_file="map_config.json"):
    """Save calibration to JSON file."""
    output_path = Path(output_file)

    with open(output_path, 'w') as f:
        json.dump(calibration_data, indent=2, fp=f)

    print(f"\n✅ Calibration saved to: {output_path}")
    print("\n📋 Configuration:")
    print(json.dumps(calibration_data, indent=2))


def main():
    print("="*60)
    print("XCLASH MAP CALIBRATION TOOL")
    print("="*60)
    print("\nThis tool will help you calibrate map navigation parameters.")
    print("You only need to do this ONCE (unless the map changes).")
    print("\nPrerequisites:")
    print("  ✓ BlueStacks running with XClash open")
    print("  ✓ World map visible")
    print("  ✓ Map at any position (we'll navigate from here)")
    print()

    wait_for_input("Ready? Press Enter to begin calibration...")

    try:
        # Initialize
        config = Config()
        adb = ADBController(config)
        game_helper = GameHelper(adb, config)

        # Check/switch to World view
        if not game_helper.switch_to_world_view():
            print("\n⚠️  Warning: Could not confirm World view")
            proceed = input("Continue anyway? (y/n): ").lower()
            if proceed != 'y':
                print("Calibration cancelled")
                return

        # Run calibration steps
        nav_data = calibrate_navigation(adb, config)
        size_data = calibrate_map_size(adb, config)
        scroll_data = calibrate_scroll_distance(adb, config)

        # Combine all data
        calibration = {
            "version": "1.0",
            "calibrated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "screen_resolution": {
                "width": config.SCREEN_WIDTH,
                "height": config.SCREEN_HEIGHT
            },
            "navigation": nav_data,
            "map_size": size_data,
            "scroll_distances": scroll_data,
            "map_boundaries": {
                "left": config.MAP_LEFT,
                "right": config.MAP_RIGHT,
                "top": config.MAP_TOP,
                "bottom": config.MAP_BOTTOM
            },
            "timing": {
                "scroll_duration": config.SCROLL_DURATION,
                "delay_after_swipe": config.DELAY_AFTER_SWIPE,
                "delay_after_screenshot": config.DELAY_AFTER_SCREENSHOT
            }
        }

        # Save
        save_calibration(calibration)

        print("\n" + "="*60)
        print("CALIBRATION COMPLETE!")
        print("="*60)
        print("\nYou can now use find_level20.py with these calibrated settings.")
        print("The map_config.json file will be automatically loaded.")

    except KeyboardInterrupt:
        print("\n\n⚠️  Calibration interrupted")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
