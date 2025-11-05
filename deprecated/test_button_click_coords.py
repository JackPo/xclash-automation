"""Test button detection and show where we would click"""
import sys
sys.path.insert(0, '.')

from button_matcher import ButtonMatcher
from pathlib import Path
import cv2
import numpy as np
import subprocess

def capture_screenshot():
    """Capture screenshot from BlueStacks via ADB"""
    adb_path = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
    device = "emulator-5554"

    temp_file = "temp_screenshot.png"

    # Capture to device
    result = subprocess.run(
        [adb_path, "-s", device, "shell", "screencap", "/sdcard/temp.png"],
        capture_output=True
    )
    if result.returncode != 0:
        print(f"ERROR: Failed to capture screenshot: {result.stderr.decode()}")
        return None

    # Pull from device
    result = subprocess.run(
        [adb_path, "-s", device, "pull", "/sdcard/temp.png", temp_file],
        capture_output=True
    )
    if result.returncode != 0:
        print(f"ERROR: Failed to pull screenshot: {result.stderr.decode()}")
        return None

    # Read image
    frame = cv2.imread(temp_file)
    return frame

def main():
    print("Initializing ButtonMatcher...")
    template_dir = Path(__file__).parent / "templates" / "buttons"
    debug_dir = Path(__file__).parent / "templates" / "debug"
    matcher = ButtonMatcher(template_dir=template_dir, debug_dir=debug_dir, threshold=0.85)

    print("\nCapturing screenshot...")
    frame = capture_screenshot()
    if frame is None:
        print("ERROR: Could not capture screenshot")
        return

    print(f"Screenshot size: {frame.shape[1]}x{frame.shape[0]}")

    # Detect current button state
    print("\nDetecting button...")
    result = matcher.match(frame)

    if result is None:
        print("ERROR: No button detected!")
        return

    # Extract data from TemplateMatch dataclass
    label = result.label
    score = result.score
    x, y = result.top_left
    x2, y2 = result.bottom_right
    w = x2 - x
    h = y2 - y

    print(f"Detected: {label} (score: {score:.3f})")
    print(f"Button bounds: x={x}, y={y}, w={w}, h={h}")
    print(f"Button region: ({x}, {y}) to ({x2}, {y2})")

    # Calculate where we would click for each state
    print("\n=== Click Coordinates ===")

    # For WORLD state (we'd want to switch to TOWN - click left side)
    print("\nIf switching FROM WORLD TO TOWN:")
    x_fracs = [0.18, 0.1, 0.02]
    y_fracs = [0.7, 0.8, 0.6]
    for xf, yf in zip(x_fracs, y_fracs):
        click_x = int(x + w * xf)
        click_y = int(y + h * yf)
        print(f"  Try {x_fracs.index(xf)+1}: ({click_x}, {click_y}) - x_frac={xf}, y_frac={yf}")

    # For TOWN state (we'd want to switch to WORLD - click right side)
    print("\nIf switching FROM TOWN TO WORLD:")
    x_fracs = [0.82, 0.9, 0.98]
    y_fracs = [0.7, 0.8, 0.6]
    for xf, yf in zip(x_fracs, y_fracs):
        click_x = int(x + w * xf)
        click_y = int(y + h * yf)
        print(f"  Try {x_fracs.index(xf)+1}: ({click_x}, {click_y}) - x_frac={xf}, y_frac={yf}")

    # Draw visualization
    print("\nCreating visualization...")
    vis = frame.copy()

    # Draw button bounds
    cv2.rectangle(vis, (x, y), (x+w, y+h), (0, 255, 0), 2)

    # Draw TOWN click points (left side - blue)
    x_fracs_town = [0.18, 0.1, 0.02]
    y_fracs_town = [0.7, 0.8, 0.6]
    for i, (xf, yf) in enumerate(zip(x_fracs_town, y_fracs_town)):
        click_x = int(x + w * xf)
        click_y = int(y + h * yf)
        cv2.circle(vis, (click_x, click_y), 5, (255, 0, 0), -1)  # Blue
        cv2.putText(vis, f"T{i+1}", (click_x+10, click_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

    # Draw WORLD click points (right side - red)
    x_fracs_world = [0.82, 0.9, 0.98]
    y_fracs_world = [0.7, 0.8, 0.6]
    for i, (xf, yf) in enumerate(zip(x_fracs_world, y_fracs_world)):
        click_x = int(x + w * xf)
        click_y = int(y + h * yf)
        cv2.circle(vis, (click_x, click_y), 5, (0, 0, 255), -1)  # Red
        cv2.putText(vis, f"W{i+1}", (click_x+10, click_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    # Add label
    cv2.putText(vis, f"Current: {label} ({score:.2f})", (x, y-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # Save full visualization
    output_file = "button_click_coords_vis.png"
    cv2.imwrite(output_file, vis)
    print(f"\nVisualization saved to: {output_file}")
    print("  Blue circles (T1, T2, T3) = TOWN click points (left side)")
    print("  Red circles (W1, W2, W3) = WORLD click points (right side)")
    print("  Green box = detected button bounds")

    # Also save a zoomed in version
    padding = 100
    y1 = max(0, y - padding)
    y2 = min(frame.shape[0], y + h + padding)
    x1 = max(0, x - padding)
    x2 = min(frame.shape[1], x + w + padding)

    zoomed = vis[y1:y2, x1:x2].copy()
    zoomed_file = "button_click_coords_zoomed.png"
    cv2.imwrite(zoomed_file, zoomed)
    print(f"\nZoomed view saved to: {zoomed_file}")

if __name__ == "__main__":
    main()
