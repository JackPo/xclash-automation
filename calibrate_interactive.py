#!/usr/bin/env python3
"""
XClash Interactive Calibration Tool - Phase 1
Pure exploration and discovery of game mechanics and UI.

This tool helps discover:
- World map view detection
- Zoom controls and levels
- Map boundaries and navigation
- UI element locations

All findings are continuously documented to calibration_findings/

Usage:
    python calibrate_interactive.py
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime
from PIL import Image
import pytesseract
from find_player import ADBController, Config


class CalibrationLogger:
    """Manages continuous logging of calibration findings."""

    def __init__(self, base_dir="calibration_findings"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)

        # Create subdirectories
        self.screenshots_dir = self.base_dir / "screenshots"
        self.screenshots_dir.mkdir(exist_ok=True)

        # Log files
        self.main_log = self.base_dir / "calibration_log.txt"
        self.zoom_log = self.base_dir / "zoom_levels_findings.txt"
        self.nav_log = self.base_dir / "navigation_findings.txt"
        self.ui_log = self.base_dir / "ui_elements_findings.txt"

        # Session info
        self.session_start = datetime.now()
        self.screenshot_counter = 0

        self.log_main(f"=== CALIBRATION SESSION STARTED ===")
        self.log_main(f"Timestamp: {self.session_start.isoformat()}")

    def log_main(self, message):
        """Log to main calibration log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        with open(self.main_log, 'a', encoding='utf-8') as f:
            f.write(line)
        print(f"[LOG] {message}")

    def log_zoom(self, level, findings):
        """Log zoom level findings."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        with open(self.zoom_log, 'a', encoding='utf-8') as f:
            f.write(f"\n[{timestamp}] ZOOM LEVEL: {level}\n")
            f.write(f"{findings}\n")
            f.write("-" * 60 + "\n")
        self.log_main(f"Logged zoom level {level} findings")

    def log_nav(self, direction, count, notes=""):
        """Log navigation findings."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        with open(self.nav_log, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {direction}: {count} swipes")
            if notes:
                f.write(f" - {notes}")
            f.write("\n")
        self.log_main(f"Navigation: {direction} = {count} swipes")

    def log_ui(self, element_name, x, y, notes=""):
        """Log UI element location."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        with open(self.ui_log, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {element_name}: ({x}, {y})")
            if notes:
                f.write(f" - {notes}")
            f.write("\n")
        self.log_main(f"UI Element: {element_name} at ({x}, {y})")

    def save_screenshot(self, img, label, metadata=None):
        """Save screenshot with metadata."""
        self.screenshot_counter += 1
        filename = f"{self.screenshot_counter:03d}_{label}.png"
        filepath = self.screenshots_dir / filename

        img.save(filepath)

        # Save metadata
        if metadata:
            meta_file = filepath.with_suffix('.txt')
            with open(meta_file, 'w', encoding='utf-8') as f:
                f.write(f"Screenshot: {filename}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                for key, value in metadata.items():
                    f.write(f"{key}: {value}\n")

        self.log_main(f"Screenshot saved: {filename}")
        return filepath


class InteractiveCalibration:
    """Main interactive calibration tool."""

    def __init__(self):
        self.config = Config()
        self.adb = ADBController(self.config)
        self.logger = CalibrationLogger()

        # Configure Tesseract
        pytesseract.pytesseract.tesseract_cmd = self.config.TESSERACT_CMD

        # Findings accumulator
        self.findings = {
            "session_start": self.logger.session_start.isoformat(),
            "world_toggle": None,
            "zoom_in": None,
            "zoom_out": None,
            "zoom_levels": {},
            "navigation": {},
            "ui_elements": {},
            "notes": []
        }

    def take_screenshot(self, label="screen"):
        """Take screenshot and return PIL Image."""
        temp_path = Path("temp_calib.png")
        self.adb.screenshot(temp_path)
        img = Image.open(temp_path)

        # Save to calibration findings
        self.logger.save_screenshot(img, label)

        temp_path.unlink()
        return img

    def run_ocr_full(self, img):
        """Run OCR on full image and return detailed results."""
        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

        results = []
        n_boxes = len(ocr_data['text'])
        for i in range(n_boxes):
            text = ocr_data['text'][i].strip()
            conf = int(ocr_data['conf'][i])
            if text and conf > 20:  # Lower threshold for discovery
                results.append({
                    'text': text,
                    'confidence': conf,
                    'x': ocr_data['left'][i],
                    'y': ocr_data['top'][i],
                    'width': ocr_data['width'][i],
                    'height': ocr_data['height'][i]
                })

        return results

    def mode_discovery(self):
        """Discovery mode: OCR current screen and show all text."""
        print("\n" + "="*60)
        print("DISCOVERY MODE")
        print("="*60)
        print("Taking screenshot and running OCR...")

        img = self.take_screenshot("discovery")
        ocr_results = self.run_ocr_full(img)

        print(f"\n[OK] Found {len(ocr_results)} text elements\n")

        # Group by regions
        regions = {
            'top_left': [],
            'top_right': [],
            'bottom_left': [],
            'bottom_right': [],
            'center': []
        }

        for item in ocr_results:
            x, y = item['x'], item['y']
            if x < 800 and y < 500:
                region = 'top_left'
            elif x > 1700 and y < 500:
                region = 'top_right'
            elif x < 800 and y > 900:
                region = 'bottom_left'
            elif x > 1700 and y > 900:
                region = 'bottom_right'
            else:
                region = 'center'
            regions[region].append(item)

        # Display by region
        for region_name, items in regions.items():
            if items:
                print(f"\n📍 {region_name.upper().replace('_', ' ')}:")
                for item in sorted(items, key=lambda x: x['confidence'], reverse=True)[:5]:
                    print(f"  [{item['confidence']:3d}%] at ({item['x']:4d}, {item['y']:4d}): '{item['text']}'")

        # Log findings
        self.logger.log_main(f"Discovery scan found {len(ocr_results)} text elements")

        # Look for important keywords
        keywords = ['WORLD', 'TOWN', 'MAP', 'ZOOM', 'ALLIANCE', 'CHAT']
        found_keywords = []
        for item in ocr_results:
            for keyword in keywords:
                if keyword in item['text'].upper():
                    found_keywords.append(f"{keyword} at ({item['x']}, {item['y']})")

        if found_keywords:
            print(f"\n🔍 Important keywords found:")
            for kw in found_keywords:
                print(f"  - {kw}")
                self.logger.log_main(f"Keyword: {kw}")

    def mode_zoom_explorer(self):
        """Zoom explorer mode: Document what's visible at different zoom levels."""
        print("\n" + "="*60)
        print("ZOOM EXPLORER MODE")
        print("="*60)
        print("\nThis mode helps you discover zoom controls and levels.")
        print("\nInstructions:")
        print("1. Manually adjust zoom in the game")
        print("2. Type 'capture' to screenshot and OCR current zoom level")
        print("3. Tell me what you can see (levels? names? both?)")
        print("4. Type 'done' when finished exploring")
        print()

        zoom_level_counter = 1

        while True:
            cmd = input(f"\nZoom Level {zoom_level_counter} > ").strip().lower()

            if cmd == 'done':
                break

            elif cmd == 'capture':
                print("📸 Capturing current zoom level...")
                img = self.take_screenshot(f"zoom_level_{zoom_level_counter}")
                ocr_results = self.run_ocr_full(img)

                print(f"[OK] Detected {len(ocr_results)} text elements")
                print("\nTop 10 detections:")
                for item in sorted(ocr_results, key=lambda x: x['confidence'], reverse=True)[:10]:
                    print(f"  [{item['confidence']:3d}%] '{item['text']}'")

                # Ask user what's visible
                print("\n[Q] What can you see at this zoom level?")
                visible = input("   (e.g., 'castle levels', 'player names', 'both', 'neither'): ").strip()

                # Look for numbers (castle levels)
                numbers = [item['text'] for item in ocr_results if item['text'].isdigit()]
                if numbers:
                    print(f"\n🔢 Numbers detected: {', '.join(numbers[:10])}")

                # Save findings
                findings = f"Visible: {visible}\n"
                findings += f"Total OCR items: {len(ocr_results)}\n"
                findings += f"Numbers detected: {len(numbers)}\n"
                if numbers:
                    findings += f"Sample numbers: {', '.join(numbers[:10])}\n"
                findings += f"Top text: {', '.join([item['text'] for item in sorted(ocr_results, key=lambda x: x['confidence'], reverse=True)[:5]])}\n"

                self.logger.log_zoom(zoom_level_counter, findings)

                # Store in findings
                self.findings['zoom_levels'][f'level_{zoom_level_counter}'] = {
                    'user_description': visible,
                    'ocr_count': len(ocr_results),
                    'numbers_found': len(numbers),
                    'sample_numbers': numbers[:10] if numbers else []
                }

                zoom_level_counter += 1

            elif cmd == 'help':
                print("\nCommands:")
                print("  capture - Take screenshot and OCR")
                print("  done    - Finish zoom exploration")
                print("  help    - Show this help")

            else:
                print("[X] Unknown command. Type 'capture', 'done', or 'help'")

        self.logger.log_main(f"Zoom exploration complete. Tested {zoom_level_counter - 1} zoom levels")

    def mode_navigation_test(self):
        """Navigation test mode: Interactive swipe testing."""
        print("\n" + "="*60)
        print("NAVIGATION TEST MODE")
        print("="*60)
        print("\nTest navigation by swiping in different directions.")
        print("We'll count swipes to reach map edges.")
        print()

        # Center coordinates
        center_x = (self.config.MAP_LEFT + self.config.MAP_RIGHT) // 2
        center_y = (self.config.MAP_TOP + self.config.MAP_BOTTOM) // 2

        print(f"Swipe center point: ({center_x}, {center_y})")
        print("\nCommands:")
        print("  left N   - Swipe left N times")
        print("  right N  - Swipe right N times")
        print("  up N     - Swipe up N times")
        print("  down N   - Swipe down N times")
        print("  record DIRECTION COUNT - Record that edge was reached")
        print("  done     - Finish navigation testing")
        print()

        swipe_count = {'left': 0, 'right': 0, 'up': 0, 'down': 0}

        while True:
            cmd = input("\nNav > ").strip().lower().split()

            if not cmd:
                continue

            if cmd[0] == 'done':
                break

            elif cmd[0] in ['left', 'right', 'up', 'down']:
                direction = cmd[0]
                count = int(cmd[1]) if len(cmd) > 1 else 1

                print(f"Swiping {direction} {count} times...")

                for i in range(count):
                    if direction == 'left':
                        self.adb.swipe(
                            center_x + self.config.HORIZONTAL_SCROLL_DISTANCE // 2,
                            center_y,
                            center_x - self.config.HORIZONTAL_SCROLL_DISTANCE // 2,
                            center_y,
                            self.config.SCROLL_DURATION
                        )
                        swipe_count['left'] += 1
                    elif direction == 'right':
                        self.adb.swipe(
                            center_x - self.config.HORIZONTAL_SCROLL_DISTANCE // 2,
                            center_y,
                            center_x + self.config.HORIZONTAL_SCROLL_DISTANCE // 2,
                            center_y,
                            self.config.SCROLL_DURATION
                        )
                        swipe_count['right'] += 1
                    elif direction == 'up':
                        self.adb.swipe(
                            center_x,
                            center_y + self.config.VERTICAL_SCROLL_DISTANCE // 2,
                            center_x,
                            center_y - self.config.VERTICAL_SCROLL_DISTANCE // 2,
                            self.config.SCROLL_DURATION
                        )
                        swipe_count['up'] += 1
                    elif direction == 'down':
                        self.adb.swipe(
                            center_x,
                            center_y - self.config.VERTICAL_SCROLL_DISTANCE // 2,
                            center_x,
                            center_y + self.config.VERTICAL_SCROLL_DISTANCE // 2,
                            self.config.SCROLL_DURATION
                        )
                        swipe_count['down'] += 1

                    time.sleep(self.config.DELAY_AFTER_SWIPE)

                print(f"Total {direction} swipes so far: {swipe_count[direction]}")

            elif cmd[0] == 'record' and len(cmd) >= 3:
                direction = cmd[1]
                count = int(cmd[2])
                notes = ' '.join(cmd[3:]) if len(cmd) > 3 else "Edge reached"

                self.logger.log_nav(direction, count, notes)
                self.findings['navigation'][f'{direction}_edge'] = count

                print(f"[OK] Recorded: {direction} edge at {count} swipes")

            elif cmd[0] == 'ss':
                self.take_screenshot("nav_test")

            elif cmd[0] == 'help':
                print("\nCommands:")
                print("  left/right/up/down N - Swipe N times")
                print("  record DIRECTION COUNT - Record edge reached")
                print("  ss - Take screenshot")
                print("  done - Finish")

            else:
                print("[X] Unknown command. Type 'help' for commands")

    def mode_button_finder(self):
        """Button finder mode: Click coordinates and verify."""
        print("\n" + "="*60)
        print("BUTTON FINDER MODE")
        print("="*60)
        print("\nTest clicking at specific coordinates to find buttons.")
        print()
        print("Commands:")
        print("  click X Y [LABEL] - Click at coordinates")
        print("  ss - Take screenshot")
        print("  record ELEMENT X Y - Record UI element location")
        print("  done - Finish")
        print()

        while True:
            cmd = input("\nButton > ").strip().split()

            if not cmd:
                continue

            if cmd[0] == 'done':
                break

            elif cmd[0] == 'click' and len(cmd) >= 3:
                x = int(cmd[1])
                y = int(cmd[2])
                label = cmd[3] if len(cmd) > 3 else "click_test"

                print(f"Clicking at ({x}, {y})...")

                # Screenshot before
                before_img = self.take_screenshot(f"before_{label}")

                # Click
                self.adb.tap(x, y)
                time.sleep(1)

                # Screenshot after
                after_img = self.take_screenshot(f"after_{label}")

                print("[OK] Click completed. Check screenshots for changes.")

            elif cmd[0] == 'record' and len(cmd) >= 4:
                element = cmd[1]
                x = int(cmd[2])
                y = int(cmd[3])
                notes = ' '.join(cmd[4:]) if len(cmd) > 4 else ""

                self.logger.log_ui(element, x, y, notes)
                self.findings['ui_elements'][element] = {'x': x, 'y': y, 'notes': notes}

                print(f"[OK] Recorded: {element} at ({x}, {y})")

            elif cmd[0] == 'ss':
                self.take_screenshot("button_finder")

            elif cmd[0] == 'help':
                print("\nCommands:")
                print("  click X Y [LABEL] - Test click")
                print("  record ELEMENT X Y [NOTES] - Record button location")
                print("  ss - Screenshot")
                print("  done - Finish")

            else:
                print("[X] Unknown command. Type 'help' for commands")

    def save_final_findings(self):
        """Save all findings to JSON."""
        findings_file = self.logger.base_dir / "final_findings.json"

        self.findings['session_end'] = datetime.now().isoformat()

        with open(findings_file, 'w') as f:
            json.dump(self.findings, indent=2, fp=f)

        print(f"\n[OK] Final findings saved to: {findings_file}")
        self.logger.log_main("Session complete. Findings saved.")

    def run(self):
        """Main calibration loop."""
        print("="*60)
        print("XCLASH INTERACTIVE CALIBRATION - PHASE 1")
        print("="*60)
        print("\nExploration and Discovery Tool")
        print(f"All findings logged to: {self.logger.base_dir}/")
        print()
        print("Modes:")
        print("  1. Discovery     - OCR current screen, find UI elements")
        print("  2. Zoom Explorer - Test zoom levels, see what's visible")
        print("  3. Navigation    - Test swipes, measure map size")
        print("  4. Button Finder - Click coordinates, locate buttons")
        print("  5. Quit          - Save findings and exit")
        print()

        while True:
            choice = input("\nSelect mode (1-5): ").strip()

            if choice == '1':
                self.mode_discovery()
            elif choice == '2':
                self.mode_zoom_explorer()
            elif choice == '3':
                self.mode_navigation_test()
            elif choice == '4':
                self.mode_button_finder()
            elif choice == '5':
                print("\n💾 Saving findings...")
                self.save_final_findings()
                print("\n👋 Calibration session complete!")
                break
            else:
                print("[X] Invalid choice. Enter 1-5.")


def main():
    try:
        calibration = InteractiveCalibration()
        calibration.run()

    except KeyboardInterrupt:
        print("\n\n[WARN]  Calibration interrupted")
        print("Findings saved in calibration_findings/")
        sys.exit(130)
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
