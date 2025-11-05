"""Adjust zoom until castle scale ~ 1.0 using CastleMatcher and ADB pinch gestures."""
import subprocess
import time
from pathlib import Path

import cv2

from castle_matcher import CastleMatcher

ADB = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
DEVICE = "emulator-5554"
TARGET_SCALE = 1.0
TOLERANCE = 0.02
MAX_ITERS = 15
PINCH_DURATION = 300
SCREEN_CENTER = (1280, 720)
START_OFFSET = 120
END_OFFSET = 420

matcher = CastleMatcher()


def adb_pinch(direction: str):
    """Perform a pinch gesture via ADB (in=zoom in, out=zoom out)."""
    cx, cy = SCREEN_CENTER
    if direction == 'in':
        x1_start, y1_start = cx - START_OFFSET, cy
        x2_start, y2_start = cx + START_OFFSET, cy
        x1_end, y1_end = cx - END_OFFSET, cy
        x2_end, y2_end = cx + END_OFFSET, cy
    else:
        x1_start, y1_start = cx - END_OFFSET, cy
        x2_start, y2_start = cx + END_OFFSET, cy
        x1_end, y1_end = cx - START_OFFSET, cy
        x2_end, y2_end = cx + START_OFFSET, cy
    cmd = (
        f"input swipe {x1_start} {y1_start} {x1_end} {y1_end} {PINCH_DURATION}"
        f" & input swipe {x2_start} {y2_start} {x2_end} {y2_end} {PINCH_DURATION}"
    )
    subprocess.run([ADB, '-s', DEVICE, 'shell', cmd], capture_output=True)


def capture_frame(path: Path):
    subprocess.run([ADB, '-s', DEVICE, 'shell', 'screencap', '-p', '/sdcard/temp_zoom_manual.png'], capture_output=True)
    subprocess.run([ADB, '-s', DEVICE, 'pull', '/sdcard/temp_zoom_manual.png', str(path)], capture_output=True)
    return cv2.imread(str(path))


def main():
    print('Refining zoom to match castle scale (ADB pinch gestures)...')
    tmp_path = Path('temp_zoom_manual.png')
    for iteration in range(1, MAX_ITERS + 1):
        frame = capture_frame(tmp_path)
        if frame is None:
            print(f'Iteration {iteration}: failed to capture frame')
            continue
        result = matcher.estimate_scale(frame)
        if not result:
            print(f'Iteration {iteration}: unable to estimate scale, zooming out slightly')
            adb_pinch('out')
            time.sleep(0.6)
            continue
        diff = result.scale - TARGET_SCALE
        width, height = matcher.approximate_castle_dimensions(result.scale)
        print(f'Iteration {iteration}: scale={result.scale:.3f} diff={diff:+.3f} avg={result.avg_score:.3f} approx={width:.1f}x{height:.1f}')
        if abs(diff) <= TOLERANCE:
            print('Target scale reached')
            break
        adb_pinch('in' if diff < 0 else 'out')
        time.sleep(0.6)
    else:
        print('Reached max iterations without hitting target scale')


if __name__ == '__main__':
    main()
