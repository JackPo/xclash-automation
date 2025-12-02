"""
Stamina Red Dot Detector - Detects red notification dot on stamina button.

The red dot appears ABOVE and TO THE RIGHT of the stamina number display when free
stamina claim is available (every 4 hours). It overlaps the upper-right corner OUTSIDE
the stamina region itself.

Uses red pixel counting in a specific region above and to the right of the stamina number.
"""

import numpy as np
from config import STAMINA_REGION

# Red pixel detection thresholds
RED_PIXEL_THRESHOLD = 100  # Minimum red pixels to consider dot present (out of 500 total in 25x20)
RED_DOT_SIZE = (25, 20)  # Size of region to check (width, height) - matches template size

# Red dot appears to the RIGHT of stamina bar
# Offset from stamina region START (found via template matching on reference screenshot)
RED_DOT_OFFSET_X = 101  # Pixels to the right of stamina region start
RED_DOT_OFFSET_Y = 20   # Pixels down from stamina region start


def has_stamina_red_dot(frame: np.ndarray, debug: bool = False) -> tuple[bool, int]:
    """
    Check if stamina button has a red notification dot.

    The red dot appears in the upper-right corner, OUTSIDE the stamina region itself.
    Checks a 20x20 pixel region at an offset from the stamina region.

    Red in BGR: B<100, G<100, R>150

    Args:
        frame: BGR numpy array screenshot (full 4K frame)
        debug: If True, prints debug info

    Returns:
        (has_dot, red_pixel_count)
    """
    # Calculate red dot check region (to the right of stamina bar)
    x, y, w, h = STAMINA_REGION

    # Red dot position: offset from stamina region start
    dot_x = x + RED_DOT_OFFSET_X
    dot_y = y + RED_DOT_OFFSET_Y

    # Extract the region where red dot should appear
    dot_w, dot_h = RED_DOT_SIZE
    roi = frame[dot_y:dot_y+dot_h, dot_x:dot_x+dot_w]

    # Red pixel mask: B<100, G<100, R>150
    b, g, r = roi[:, :, 0], roi[:, :, 1], roi[:, :, 2]
    red_mask = (b < 100) & (g < 100) & (r > 150)
    red_count = int(red_mask.sum())

    has_dot = red_count >= RED_PIXEL_THRESHOLD

    if debug:
        dot_w, dot_h = RED_DOT_SIZE
        print(f"  [STAMINA-RED-DOT] Checking region ({dot_x},{dot_y}) size {dot_w}x{dot_h}")
        print(f"  [STAMINA-RED-DOT] Red pixels: {red_count}/{dot_w*dot_h} - {'HAS DOT' if has_dot else 'no dot'}")

    return has_dot, red_count
