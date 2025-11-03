#!/usr/bin/env python3
"""
Zoom discovery using minitouch for true multi-touch pinch gestures

This script successfully zooms in/out on the XClash game map using minitouch.
Minitouch provides proper multi-touch support via ADB, enabling pinch gestures.

Usage:
    python discover_zoom_adb.py

The script will:
1. Close any open dialogs
2. Take an initial screenshot
3. Zoom out 3 times (can be adjusted)
4. Zoom in 2 times (can be adjusted)
5. Take screenshots and run OCR after each zoom
6. Save results to zoom_discovery_adb/ directory

Note: Requires minitouch to be installed on the device at /data/local/tmp/minitouch
"""

import time
import subprocess
from pathlib import Path
from PIL import Image
import pytesseract
from find_player import ADBController, Config

def zoom_out(adb):
    """Zoom out using minitouch pinch-in (fingers move together)"""
    # minitouch coordinate space: 32767x32767
    # Screen: 2560x1440, so center is 1280x720
    # Convert: x_mt = (x_screen / 2560) * 32767

    # REDUCED ZOOM: Smaller finger movement for gentler zoom
    # Screen coords for horizontal pinch at Y=720:
    # Start: finger0=1000, finger1=1560 (560 pixels apart)
    # End: finger0=1180, finger1=1380 (200 pixels apart)

    # Convert to minitouch coords:
    # 1000 -> 12800, 1560 -> 19968, center Y 720 -> 9216
    # 1180 -> 15104, 1380 -> 17664

    commands = """d 0 12800 9216 50
d 1 19968 9216 50
c
w 15
m 0 13952 9216 50
m 1 18816 9216 50
c
w 15
m 0 15104 9216 50
m 1 17664 9216 50
c
w 15
u 0
u 1
c
"""

    cmd = [adb.adb, "-s", adb.device, "shell", "/data/local/tmp/minitouch -i"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        proc.communicate(input=commands, timeout=2)
    except:
        proc.kill()

def zoom_in(adb):
    """Zoom in using minitouch pinch-out (fingers move apart)"""
    # Reverse of zoom_out - fingers start together, move apart

    commands = """d 0 15104 9216 50
d 1 17664 9216 50
c
w 15
m 0 13952 9216 50
m 1 18816 9216 50
c
w 15
m 0 12800 9216 50
m 1 19968 9216 50
c
w 15
u 0
u 1
c
"""

    cmd = [adb.adb, "-s", adb.device, "shell", "/data/local/tmp/minitouch -i"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        proc.communicate(input=commands, timeout=2)
    except:
        proc.kill()

def close_dialogs(adb):
    """Close any open dialogs with BACK key"""
    cmd = [adb.adb, "-s", adb.device, "shell", "input", "keyevent", "4"]
    subprocess.run(cmd)
    time.sleep(0.5)

def discover_zoom():
    config = Config()
    adb = ADBController(config)
    pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

    output_dir = Path("zoom_discovery_adb")
    output_dir.mkdir(exist_ok=True)

    log = open(output_dir / "zoom_log.txt", 'w', encoding='utf-8')

    # Close any open dialogs first
    print("Closing any open dialogs...")
    close_dialogs(adb)
    time.sleep(1)

    def capture_and_ocr(prefix, num):
        filename = f"{prefix}_{num:02d}.png"
        filepath = output_dir / filename
        adb.screenshot(filepath)

        img = Image.open(filepath)
        text = pytesseract.image_to_string(img, config='--psm 6')

        log.write(f"{filename}: {repr(text.strip()[:100])}\n")
        log.flush()
        print(f"  {filename}: {len(text.strip())} chars")

    print("Zoom Discovery - BlueStacks Keyboard Shortcuts")
    print("Using Shift+Z (zoom out) and Shift+A (zoom in) via ADB")
    print()

    # Initial
    print("Initial screenshot...")
    capture_and_ocr("initial", 0)
    time.sleep(0.5)

    # TEST MODE: Just 3 zoom out, 2 zoom in
    print("\n=== TEST: ZOOM OUT 3x (minitouch pinch-in) ===")
    for i in range(1, 4):
        print(f"  {i}/3...")
        zoom_out(adb)
        time.sleep(1.0)
        capture_and_ocr("zoom_out", i)

    time.sleep(2)

    print("\n=== TEST: ZOOM IN 2x (minitouch pinch-out) ===")
    for i in range(1, 3):
        print(f"  {i}/2...")
        zoom_in(adb)
        time.sleep(1.0)
        capture_and_ocr("zoom_in", i)

    log.close()
    print(f"\nDone! Check {output_dir}/")

if __name__ == "__main__":
    discover_zoom()
