"""Extract rally plus button template from Windows screenshot."""
import cv2
from utils.windows_screenshot_helper import WindowsScreenshotHelper

# Take Windows screenshot
win = WindowsScreenshotHelper()
frame = win.get_screenshot_cv2()

if frame is None:
    print("ERROR: Could not get Windows screenshot")
    exit(1)

print(f"Screenshot size: {frame.shape}")
print("\nTo extract the plus button:")
print("1. Visually locate the plus button in the current screenshot")
print("2. Use fixed X=1405 (from docs)")
print("3. Extract 127x132 region")
print("\nWaiting for manual extraction...")
print("\nOr save current screenshot to screenshots/ for manual inspection")

# Save current screenshot for manual inspection
import time
timestamp = time.strftime("%Y%m%d_%H%M%S")
cv2.imwrite(f"screenshots/rally_windows_{timestamp}.png", frame)
print(f"\nSaved to: screenshots/rally_windows_{timestamp}.png")
print("Manually inspect and provide Y coordinate for extraction")
