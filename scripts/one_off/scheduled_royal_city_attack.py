"""
Scheduled Royal City Attack - Waits until 6:05 AM PT then launches Claude CLI to handle it.

Usage:
    python scripts/one_off/scheduled_royal_city_attack.py
"""

import sys
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Target time: 6:05 AM Pacific Time
TARGET_HOUR = 6
TARGET_MINUTE = 5

PROMPT = '''You are automating a game task. Your goal is to:

1. Navigate to the Royal City using the mark system
2. Attack OR Reinforce the Royal City with ANY available soldiers
3. Return to base view when done

## Available Tools

You have access to these Python utilities (already imported in the codebase):

```python
from utils.adb_helper import ADBHelper
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from scripts.flows.go_to_mark_flow import go_to_mark_flow
from utils.return_to_base_view import return_to_base_view

adb = ADBHelper()  # Use adb.tap(x, y) to click
win = WindowsScreenshotHelper()  # Use win.get_screenshot_cv2() for screenshots
```

## Step-by-step approach:

1. First run `go_to_mark_flow(adb)` to navigate to the marked Royal City location
2. Take a screenshot to see the current state
3. Click on the Royal City building/structure in the center of the screen
4. Take another screenshot to see the menu options
5. Look for an "Attack" or "Reinforce" button and click it
6. On the troop selection screen, select any available troops
7. Click the "March" or "Send" button
8. Use `return_to_base_view(adb, win)` to clean up

## Important:
- The Royal City protection has just ended, so Attack or Reinforce should now be available
- Take screenshots frequently to see what's on screen
- Use Gemini via `python calibration/detect_object.py screenshot.png "description"` to find elements
- If you can't find a button, try clicking around the center of the screen where the city is

Start by running the go_to_mark_flow, then take a screenshot and figure out what to do next.
'''


def get_seconds_until_target():
    """Calculate seconds until target time (6:05 AM local time)."""
    now = datetime.now()
    target = now.replace(hour=TARGET_HOUR, minute=TARGET_MINUTE, second=0, microsecond=0)

    # If target time already passed today, schedule for tomorrow
    if target <= now:
        target += timedelta(days=1)

    delta = target - now
    return delta.total_seconds(), target


def main():
    print("=" * 60)
    print("SCHEDULED ROYAL CITY ATTACK")
    print("=" * 60)
    print()

    seconds_until, target_time = get_seconds_until_target()

    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target time:  {target_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Waiting:      {seconds_until:.0f} seconds ({seconds_until/60:.1f} minutes)")
    print()
    print("Press Ctrl+C to cancel")
    print()

    # Wait with periodic status updates
    start_time = time.time()
    last_status = 0
    while True:
        elapsed = time.time() - start_time
        remaining = seconds_until - elapsed

        if remaining <= 0:
            break

        # Print status every 5 minutes
        minutes_remaining = int(remaining / 60)
        if minutes_remaining != last_status and minutes_remaining % 5 == 0:
            print(f"  {minutes_remaining} minutes remaining...")
            last_status = minutes_remaining

        # Sleep in small increments to allow Ctrl+C
        time.sleep(min(30, remaining))

    print()
    print("=" * 60)
    print(f"TARGET TIME REACHED: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)
    print()

    # Launch Claude CLI with the prompt
    print("Launching Claude CLI to handle Royal City attack...")
    print()

    # Change to xclash directory
    xclash_dir = Path(__file__).parent.parent.parent

    # Run claude with the prompt
    subprocess.run(
        ["claude", "-p", PROMPT],
        cwd=str(xclash_dir),
        shell=True
    )

    print()
    print("=" * 60)
    print("Claude CLI session completed")
    print("=" * 60)


if __name__ == "__main__":
    main()
