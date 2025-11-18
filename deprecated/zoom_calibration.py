"""
Zoom Calibration System

Calibrates the map zoom level to match castle template scale (1.0) using:
1. Reset to known state by toggling to WORLD view
2. Initial zoom out (~8 times) to see multiple castles
3. Multi-castle detection to measure actual scale
4. Dynamic zoom adjustment until target scale reached

Handles non-deterministic zoom behavior by always measuring actual results.
"""
from pathlib import Path
import subprocess
import time
import cv2
from typing import Optional

from view_detection import switch_to_view, ViewState
from castle_matcher import CastleMatcher
from find_player import ADBController, Config


def zoom_out_n_times(n: int, delay: float = 0.8) -> None:
    """Execute n zoom out commands with delays."""
    python_exe = r"C:\Users\mail\AppData\Local\Programs\Python\Python312\python.exe"
    for i in range(n):
        print(f"  Zoom out {i+1}/{n}...")
        subprocess.run([python_exe, "send_zoom.py", "out"], check=False)
        if i < n - 1:  # No delay after last zoom
            time.sleep(delay)


def zoom_in_n_times(n: int, delay: float = 0.8) -> None:
    """Execute n zoom in commands with delays."""
    python_exe = r"C:\Users\mail\AppData\Local\Programs\Python\Python312\python.exe"
    for i in range(n):
        print(f"  Zoom in {i+1}/{n}...")
        subprocess.run([python_exe, "send_zoom.py", "in"], check=False)
        if i < n - 1:  # No delay after last zoom
            time.sleep(delay)


def measure_current_scale(
    adb: ADBController,
    matcher: CastleMatcher,
    screenshot_path: Path = Path("temp_calibrate.png")
) -> Optional[float]:
    """
    Measure current zoom scale using castle template matching.

    Returns:
        Current scale factor, or None if detection failed
    """
    adb.screenshot(screenshot_path)
    frame = cv2.imread(str(screenshot_path))

    if frame is None:
        print("  Failed to load screenshot")
        return None

    result = matcher.estimate_scale(frame)

    if result is None:
        print("  No castles detected")
        return None

    print(f"  Detected scale: {result.scale:.3f} (avg_score: {result.avg_score:.3f})")
    return result.scale


def calibrate_zoom(
    adb: ADBController,
    target_scale: float = 1.0,
    tolerance: float = 0.05,
    max_iterations: int = 10,
    initial_zoom_outs: int = 8
) -> bool:
    """
    Calibrate zoom to target scale.

    Strategy:
    1. Toggle to WORLD view (resets camera to your castle at scale 1.0)
    2. Zoom out ~8 times to see multiple castles
    3. Detect 3+ castles and calculate current scale
    4. Dynamically adjust zoom until within tolerance of target

    Args:
        adb: ADBController instance
        target_scale: Target scale factor (default 1.0)
        tolerance: Acceptable deviation from target (default 0.05)
        max_iterations: Maximum adjustment iterations (default 10)
        initial_zoom_outs: Initial zoom outs to perform (default 8)

    Returns:
        True if calibration successful, False otherwise
    """
    print("=" * 60)
    print("ZOOM CALIBRATION")
    print("=" * 60)

    # Step 1: Reset to known state
    print("\n[1] Resetting to WORLD view...")
    if not switch_to_view(adb, ViewState.WORLD):
        print("  Failed to switch to WORLD view")
        return False
    print("  ✓ In WORLD view (camera at your castle, scale ~1.0)")

    # Step 2: Initial zoom out
    print(f"\n[2] Initial zoom out ({initial_zoom_outs}x)...")
    zoom_out_n_times(initial_zoom_outs)
    time.sleep(1.0)  # Wait for zoom animation
    print("  ✓ Initial zoom out complete")

    # Step 3: Create matcher
    matcher = CastleMatcher()

    # Step 4: Iterative calibration
    print(f"\n[3] Calibrating to target scale {target_scale:.2f} (tolerance ±{tolerance:.2f})...")

    for iteration in range(1, max_iterations + 1):
        print(f"\n  Iteration {iteration}/{max_iterations}:")

        # Measure current scale
        current_scale = measure_current_scale(adb, matcher)

        if current_scale is None:
            print("  ⚠ Detection failed, retrying...")
            continue

        # Check if within tolerance
        diff = abs(current_scale - target_scale)
        print(f"  Current: {current_scale:.3f}, Target: {target_scale:.3f}, Diff: {diff:.3f}")

        if diff <= tolerance:
            print(f"\n✓ CALIBRATION SUCCESSFUL!")
            print(f"  Final scale: {current_scale:.3f} (within ±{tolerance:.2f} of target)")
            return True

        # Calculate adjustment
        if current_scale < target_scale:
            # Need to zoom in (castles too small)
            zoom_steps = max(1, int((target_scale - current_scale) / 0.03))
            zoom_steps = min(zoom_steps, 3)  # Cap at 3 steps per iteration
            print(f"  → Zooming IN {zoom_steps}x (castles too small)")
            zoom_in_n_times(zoom_steps)
        else:
            # Need to zoom out (castles too large)
            zoom_steps = max(1, int((current_scale - target_scale) / 0.03))
            zoom_steps = min(zoom_steps, 3)  # Cap at 3 steps per iteration
            print(f"  → Zooming OUT {zoom_steps}x (castles too large)")
            zoom_out_n_times(zoom_steps)

        time.sleep(1.0)  # Wait for zoom animation

    print(f"\n✗ CALIBRATION FAILED after {max_iterations} iterations")
    return False


if __name__ == "__main__":
    config = Config()
    adb = ADBController(config)

    success = calibrate_zoom(adb)

    if success:
        print("\nZoom calibration complete! Ready for navigation.")
    else:
        print("\nZoom calibration failed. Manual adjustment may be needed.")
