"""
Simple script to take a screenshot and save it to the screenshots folder.
Usage: python scripts/take_screenshot.py [filename]
If no filename provided, uses timestamp.
"""

import sys
import os

# Add project root to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from datetime import datetime
from utils.windows_screenshot_helper import WindowsScreenshotHelper
import cv2

def main():
    # Get filename from command line or use timestamp
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        # Add .png if not present
        if not filename.endswith('.png'):
            filename += '.png'
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'screenshot_{timestamp}.png'

    # Ensure screenshots directory exists
    screenshots_dir = 'screenshots'
    os.makedirs(screenshots_dir, exist_ok=True)

    # Full path
    filepath = os.path.join(screenshots_dir, filename)

    # Take screenshot
    print(f"Taking screenshot...")
    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()

    # Save
    cv2.imwrite(filepath, frame)
    print(f"Saved to: {filepath}")
    print(f"Size: {frame.shape[1]}x{frame.shape[0]}")

if __name__ == '__main__':
    main()
