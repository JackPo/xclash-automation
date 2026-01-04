"""
Hero Tile Detector - Red dot detection for Fing Hero tiles.

Uses red pixel counting to detect notification dots in hero tiles.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

# Hero grid layout (4K resolution)
# 3 rows x 4 columns grid that appears after clicking Fing Hero button
HERO_TILES = {
    'r1_c1': {'pos': (1374, 211), 'size': (246, 404), 'click': (1497, 413)},
    'r1_c2': {'pos': (1651, 211), 'size': (249, 404), 'click': (1775, 413)},
    'r1_c3': {'pos': (1931, 211), 'size': (250, 404), 'click': (2056, 413)},
    'r1_c4': {'pos': (2208, 211), 'size': (245, 404), 'click': (2330, 413)},
    'r2_c1': {'pos': (1374, 639), 'size': (246, 397), 'click': (1497, 837)},
    'r2_c2': {'pos': (1651, 639), 'size': (249, 397), 'click': (1775, 837)},
    'r2_c3': {'pos': (1931, 639), 'size': (250, 397), 'click': (2056, 837)},
    'r2_c4': {'pos': (2208, 639), 'size': (245, 397), 'click': (2330, 837)},
    'r3_c1': {'pos': (1374, 1067), 'size': (246, 397), 'click': (1497, 1265)},
    'r3_c2': {'pos': (1651, 1067), 'size': (249, 397), 'click': (1775, 1265)},
    'r3_c3': {'pos': (1931, 1067), 'size': (250, 397), 'click': (2056, 1265)},
    'r3_c4': {'pos': (2208, 1067), 'size': (245, 397), 'click': (2330, 1265)},
}

# Red pixel detection thresholds
RED_PIXEL_THRESHOLD = 50  # Minimum red pixels to consider dot present
ROI_SIZE = 40  # Upper-right region size to check


def has_red_dot(tile_img: npt.NDArray[Any]) -> tuple[bool, int]:
    """
    Check if a hero tile has a red notification dot.

    Uses red pixel counting in the upper-right 40x40 region.
    Red in BGR: B<100, G<100, R>150

    Args:
        tile_img: BGR numpy array of the tile

    Returns:
        (has_dot, red_pixel_count)
    """
    # Get upper-right 40x40 region
    roi = tile_img[0:ROI_SIZE, -ROI_SIZE:]

    # Red pixel mask: B<100, G<100, R>150
    b, g, r = roi[:, :, 0], roi[:, :, 1], roi[:, :, 2]
    red_mask = (b < 100) & (g < 100) & (r > 150)
    red_count = int(red_mask.sum())

    return red_count >= RED_PIXEL_THRESHOLD, red_count


def extract_tile(frame: npt.NDArray[Any], tile_name: str) -> npt.NDArray[Any]:
    """
    Extract a hero tile region from a full screenshot.

    Args:
        frame: Full screenshot (BGR numpy array)
        tile_name: Tile identifier (e.g., 'r1_c1')

    Returns:
        Cropped tile image
    """
    tile = HERO_TILES[tile_name]
    x, y = tile['pos']
    w, h = tile['size']
    return frame[y:y+h, x:x+w]


def detect_tiles_with_red_dots(frame: npt.NDArray[Any], debug: bool = False) -> list[dict[str, Any]]:
    """
    Scan all hero tiles and find those with red notification dots.

    Args:
        frame: Full screenshot (BGR numpy array)
        debug: If True, print detection details

    Returns:
        List of dicts with tile info for tiles that have red dots:
        [{'name': 'r1_c2', 'click': (1775, 413), 'red_count': 850}, ...]
    """
    tiles_with_dots = []

    for tile_name, tile_info in HERO_TILES.items():
        tile_img = extract_tile(frame, tile_name)
        has_dot, red_count = has_red_dot(tile_img)

        if debug:
            print(f"  {tile_name}: {red_count} red pixels - {'HAS DOT' if has_dot else 'no dot'}")

        if has_dot:
            tiles_with_dots.append({
                'name': tile_name,
                'click': tile_info['click'],
                'red_count': red_count
            })

    return tiles_with_dots


def get_tile_click_position(tile_name: str) -> tuple[int, int]:
    """Get the click position for a tile."""
    return HERO_TILES[tile_name]['click']


if __name__ == '__main__':
    # Test with current screenshot
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    print("Taking screenshot...")
    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()

    print("\nDetecting red dots on hero tiles:")
    tiles = detect_tiles_with_red_dots(frame, debug=True)

    print(f"\nTiles with red dots: {len(tiles)}")
    for tile in tiles:
        print(f"  {tile['name']} -> click at {tile['click']}")
