#!/usr/bin/env python3
"""
Test Windows screenshot capture of BlueStacks window using mss.
"""
import mss
import mss.tools
import win32gui
import win32con
from PIL import Image
import numpy as np


def find_bluestacks_window():
    """Find BlueStacks window handle."""
    hwnd = win32gui.FindWindow(None, "BlueStacks App Player")
    if not hwnd:
        print("ERROR: BlueStacks window not found!")
        print("Make sure BlueStacks is running.")
        return None

    print(f"Found BlueStacks window: {hwnd}")
    return hwnd


def get_client_rect(hwnd):
    """Get CLIENT rectangle (game content only, no title bar/borders)."""
    # Get client rect in window coordinates
    client_rect = win32gui.GetClientRect(hwnd)
    print(f"Client rect (relative): {client_rect}")

    # Convert top-left corner to screen coordinates
    left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
    right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))

    print(f"Client rect (screen coords): ({left}, {top}, {right}, {bottom})")
    print(f"  Left: {left}, Top: {top}")
    print(f"  Right: {right}, Bottom: {bottom}")
    print(f"  Width: {right - left}, Height: {bottom - top}")

    return left, top, right, bottom


def capture_window_mss(hwnd):
    """Capture window CLIENT AREA using mss library."""
    left, top, right, bottom = get_client_rect(hwnd)

    # mss uses monitor dict with top, left, width, height
    monitor = {
        "top": top,
        "left": left,
        "width": right - left,
        "height": bottom - top
    }

    print(f"\nCapturing with mss...")
    print(f"  Monitor config: {monitor}")

    with mss.mss() as sct:
        screenshot = sct.grab(monitor)

        # Convert to PIL Image
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        print(f"  Captured size: {img.size}")

        return img, screenshot


def main():
    print("Testing Windows screenshot capture of BlueStacks...")
    print("=" * 60)

    # Find BlueStacks window
    hwnd = find_bluestacks_window()
    if not hwnd:
        return

    # Capture using mss
    img, raw_screenshot = capture_window_mss(hwnd)

    # Save screenshot
    output_path = "templates/ground_truth/bluestacks_windows_capture.png"
    img.save(output_path)
    print(f"\nSaved to: {output_path}")
    print(f"Image size: {img.size}")
    print(f"Image mode: {img.mode}")

    # Check if image is all black (indicates capture failed)
    img_array = np.array(img)
    avg_brightness = img_array.mean()
    print(f"\nAverage brightness: {avg_brightness:.1f}/255")

    if avg_brightness < 10:
        print("WARNING: Image appears to be mostly black!")
        print("This likely means mss captured the window frame but not the game content.")
        print("You may need to use scrcpy as a mirror window instead.")
    else:
        print("SUCCESS: Image contains visible content!")

    print("\n" + "=" * 60)
    print("Test complete. Check the saved image.")


if __name__ == "__main__":
    main()
