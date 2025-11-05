#!/usr/bin/env python3
"""
XClash Configuration Helper
Test OCR, navigation, and find optimal parameters.

Usage:
    python test_config.py ocr          # Test OCR on current screen
    python test_config.py nav          # Test navigation commands
    python test_config.py screenshot   # Just take a screenshot
"""

import sys
import time
from pathlib import Path
from find_player import ADBController, OCRProcessor, MapNavigator, Config


def test_ocr():
    """Test OCR on current screen."""
    print("🧪 Testing OCR on current screen...")

    config = Config()
    adb = ADBController(config)
    ocr = OCRProcessor(config, debug=True)

    # Take screenshot
    screenshot_path = Path("test_screenshot.png")
    adb.screenshot(screenshot_path)
    print(f"✅ Screenshot saved: {screenshot_path}")

    # Process with OCR
    results = ocr.process_screenshot(screenshot_path)

    print(f"\n📝 OCR Results ({len(results)} items detected):")
    print("=" * 60)

    # Sort by confidence
    for text, conf in sorted(results, key=lambda x: x[1], reverse=True):
        print(f"  [{conf:3d}%] {text}")

    print("=" * 60)
    print(f"\n💡 Tip: Look for player names and numbers below castles")
    print(f"💡 Adjust OCR_CONFIDENCE_THRESHOLD in Config if too noisy")


def test_navigation():
    """Test navigation commands interactively."""
    print("🧪 Navigation Test Mode")
    print("Commands:")
    print("  up    - Swipe up")
    print("  down  - Swipe down")
    print("  left  - Swipe left")
    print("  right - Swipe right")
    print("  tl    - Go to top-left corner")
    print("  ss    - Take screenshot")
    print("  quit  - Exit")
    print()

    config = Config()
    adb = ADBController(config)
    navigator = MapNavigator(adb, config)

    while True:
        cmd = input("Command: ").strip().lower()

        if cmd == "quit":
            break
        elif cmd == "up":
            print("⬆️  Swiping up...")
            center_x = (config.MAP_LEFT + config.MAP_RIGHT) // 2
            center_y = (config.MAP_TOP + config.MAP_BOTTOM) // 2
            adb.swipe(
                center_x,
                center_y + config.VERTICAL_SCROLL_DISTANCE // 2,
                center_x,
                center_y - config.VERTICAL_SCROLL_DISTANCE // 2,
                config.SCROLL_DURATION
            )
            time.sleep(config.DELAY_AFTER_SWIPE)
        elif cmd == "down":
            print("⬇️  Swiping down...")
            navigator.scroll_down()
        elif cmd == "left":
            print("⬅️  Swiping left...")
            navigator.scroll_left()
        elif cmd == "right":
            print("➡️  Swiping right...")
            navigator.scroll_right()
        elif cmd == "tl":
            print("📍 Going to top-left...")
            navigator.go_to_top_left()
        elif cmd == "ss":
            print("📸 Taking screenshot...")
            path = Path(f"nav_test_{int(time.time())}.png")
            adb.screenshot(path)
            print(f"✅ Saved: {path}")
        else:
            print("❌ Unknown command")


def take_screenshot():
    """Just take a screenshot."""
    print("📸 Taking screenshot...")
    config = Config()
    adb = ADBController(config)

    screenshot_path = Path("screenshot.png")
    adb.screenshot(screenshot_path)
    print(f"✅ Screenshot saved: {screenshot_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_config.py ocr          # Test OCR")
        print("  python test_config.py nav          # Test navigation")
        print("  python test_config.py screenshot   # Take screenshot")
        sys.exit(1)

    command = sys.argv[1].lower()

    try:
        if command == "ocr":
            test_ocr()
        elif command == "nav":
            test_navigation()
        elif command in ["screenshot", "ss"]:
            take_screenshot()
        else:
            print(f"❌ Unknown command: {command}")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
