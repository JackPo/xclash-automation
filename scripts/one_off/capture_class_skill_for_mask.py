"""
Capture ONE popup screenshot at a panned-map position, for diffing against
an existing centered-popup screenshot to build a mask.

Why only one new shot:
We already have many "popup centered on own castle" screenshots from the
daemon's failed quick_production retries (e.g. screenshots/debug/quick_prod/
20260510_134749_04_castle_popup.png). The mask only needs TWO shots with the
same icon on DIFFERENT backgrounds, so we just need one fresh capture where
we've panned the map first.

Procedure (fully automated):
  1. Go TOWN -> WORLD  (centers map on own castle at screen 1920,1080)
  2. Swipe to pan world map by PAN_DELTA
  3. Tap castle at its new screen position
  4. Save the popup screenshot

IMPORTANT: stop the daemon first or this will fight with it.
    python scripts/daemon_cli.py stop
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from utils.adb_helper import ADBHelper  # noqa: E402
from utils.windows_screenshot_helper import WindowsScreenshotHelper  # noqa: E402
from utils.view_state_detector import go_to_town, go_to_world  # noqa: E402

OUT_DIR = REPO_ROOT / "screenshots" / "debug" / "mask_capture"

# Castle is centered after TOWN -> WORLD
CASTLE_CENTER = (1920, 1080)
# Pan offset: drag-from castle to bottom-right => world content moves down-right,
# so castle ends up at (CASTLE + offset) on screen.
PAN_DELTA = (450, 250)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    win = WindowsScreenshotHelper()
    adb = ADBHelper()

    print("[CAPTURE] Step 1: TOWN -> WORLD (centers castle)")
    go_to_town(adb, debug=False)
    time.sleep(1.0)
    go_to_world(adb, debug=False)
    time.sleep(1.5)

    print(f"[CAPTURE] Step 2: pan map by {PAN_DELTA}")
    adb.swipe(
        CASTLE_CENTER[0],
        CASTLE_CENTER[1],
        CASTLE_CENTER[0] + PAN_DELTA[0],
        CASTLE_CENTER[1] + PAN_DELTA[1],
        duration=400,
    )
    time.sleep(1.5)

    castle_now = (CASTLE_CENTER[0] + PAN_DELTA[0], CASTLE_CENTER[1] + PAN_DELTA[1])
    print(f"[CAPTURE] Step 3: tap castle at panned position {castle_now}")
    adb.tap(*castle_now, source="capture:popup_panned")
    time.sleep(1.5)

    shot_path = OUT_DIR / "popup_panned.png"
    cv2.imwrite(str(shot_path), win.get_screenshot_cv2())
    print(f"[CAPTURE] Saved: {shot_path}")
    print()
    print("Next: pair this with an existing centered-popup screenshot, e.g.")
    print("  screenshots/debug/quick_prod/20260510_134749_04_castle_popup.png")
    print()
    print("Then build the mask:")
    print(f"  python scripts/one_off/build_mask.py \\")
    print(f"    --shot1 screenshots/debug/quick_prod/20260510_134749_04_castle_popup.png \\")
    print(f"    --shot2 {shot_path} \\")
    print(f"    --bbox <X> <Y> <W> <H> \\")
    print(f"    --name class_skill_button --force")
    return 0


if __name__ == "__main__":
    sys.exit(main())
