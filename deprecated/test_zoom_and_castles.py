"""
Test zoom out and castle detection separately.

Step 1: Reset to WORLD view and zoom out 8 times
Step 2: Capture screenshot and test castle template matching
"""
from pathlib import Path
import subprocess
import time
import cv2

from view_detection import switch_to_view, ViewState
from castle_matcher import CastleMatcher
from find_player import ADBController, Config


def main():
    config = Config()
    adb = ADBController(config)

    print("=" * 60)
    print("STEP 1: Reset to WORLD view and zoom out")
    print("=" * 60)

    # Reset to WORLD view
    print("\n[1] Switching to WORLD view...")
    if not switch_to_view(adb, ViewState.WORLD):
        print("  Failed to switch to WORLD view")
        return
    print("  [OK] In WORLD view")

    # Zoom out 8 times
    print("\n[2] Zooming out 8 times...")
    python_exe = r"C:\Users\mail\AppData\Local\Programs\Python\Python312\python.exe"

    for i in range(8):
        print(f"  Zoom out {i+1}/8...")
        subprocess.run([python_exe, "send_zoom.py", "out"], check=False)
        if i < 7:
            time.sleep(0.8)

    print("  [OK] Zoom out complete")

    # Wait for animation
    time.sleep(1.0)

    # Capture screenshot
    print("\n[3] Capturing screenshot...")
    screenshot_path = Path("test_castle_detection.png")
    adb.screenshot(screenshot_path)
    print(f"  [OK] Screenshot saved: {screenshot_path}")

    print("\n" + "=" * 60)
    print("STEP 2: Test castle template matching")
    print("=" * 60)

    # Load screenshot
    frame = cv2.imread(str(screenshot_path))
    if frame is None:
        print("  [FAIL] Failed to load screenshot")
        return

    # Test castle matcher
    print("\n[4] Running castle matcher...")
    matcher = CastleMatcher()
    result = matcher.estimate_scale(frame)

    if result is None:
        print("  [FAIL] No castles detected!")
        print("\n  Castle matcher returned None. Possible issues:")
        print("  - Castle templates may not match current game graphics")
        print("  - Zoom level too far out (castles too small)")
        print("  - No castles visible in current view")
        return

    # Display results
    print(f"\n  [OK] Castle detection successful!")
    print(f"  Scale: {result.scale:.3f}")
    print(f"  Average Score: {result.avg_score:.3f}")
    print(f"  Best Candidate: {result.best_candidate:.3f}")

    print(f"\n  Top 5 scale matches:")
    sorted_metrics = sorted(result.metrics, key=lambda x: x[1], reverse=True)[:5]
    for scale, avg, peak in sorted_metrics:
        print(f"    Scale {scale:.2f}: avg={avg:.3f}, peak={peak:.3f}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print(f"\nScreenshot saved to: {screenshot_path}")
    print("Review the screenshot to verify castles are visible.")
    print(f"\nDetected scale: {result.scale:.3f}")
    print(f"Target scale: 1.0")
    print(f"Difference: {abs(result.scale - 1.0):.3f}")


if __name__ == "__main__":
    main()
