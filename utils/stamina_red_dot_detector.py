"""
Stamina Red Dot Detector - Detects red notification dot on stamina button.

The red dot appears on the stamina display when free stamina claim is available (every 4 hours).
Uses red pixel counting in the upper-right corner of the stamina region.
"""

import numpy as np
from config import STAMINA_REGION

# Red pixel detection thresholds
RED_PIXEL_THRESHOLD = 30  # Minimum red pixels to consider dot present
ROI_SIZE = 25  # Upper-right region size to check (smaller than hero tiles)


def has_stamina_red_dot(frame: np.ndarray, debug: bool = False) -> tuple[bool, int]:
    """
    Check if stamina button has a red notification dot.

    Uses red pixel counting in the upper-right corner of the stamina region.
    Red in BGR: B<100, G<100, R>150

    Args:
        frame: BGR numpy array screenshot (full 4K frame)
        debug: If True, prints debug info

    Returns:
        (has_dot, red_pixel_count)
    """
    # Extract stamina region
    x, y, w, h = STAMINA_REGION
    stamina_img = frame[y:y+h, x:x+w]

    # Get upper-right corner for red dot check
    roi = stamina_img[0:ROI_SIZE, -ROI_SIZE:]

    # Red pixel mask: B<100, G<100, R>150
    b, g, r = roi[:, :, 0], roi[:, :, 1], roi[:, :, 2]
    red_mask = (b < 100) & (g < 100) & (r > 150)
    red_count = int(red_mask.sum())

    has_dot = red_count >= RED_PIXEL_THRESHOLD

    if debug:
        print(f"  [STAMINA-RED-DOT] Red pixels: {red_count} - {'HAS DOT' if has_dot else 'no dot'}")

    return has_dot, red_count
