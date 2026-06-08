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


# ---------------------------------------------------------------------------
# Level-based detection (replaces red-dot detection as the primary signal).
#
# Red dots became unreliable once most heroes were maxed -- some maxed heroes
# still show transient dots, and some upgradable heroes don't. The true
# signal is "is this hero below max level (150)?". We crop the "Lv. NNN"
# banner at the bottom of each tile and OCR the digits.
# ---------------------------------------------------------------------------

# Fraction of tile height where the "Lv. NNN" banner sits. Determined
# empirically from the in-game UI; the banner is the yellow strip near
# the bottom of each card.
_LV_BAND_Y_FRAC = 0.78
_LV_BAND_H_FRAC = 0.14

MAX_HERO_LEVEL = 150


def extract_level_band(frame: "npt.NDArray[Any]", tile_name: str) -> "npt.NDArray[Any]":
    """Crop the 'Lv. NNN' banner at the bottom of a tile."""
    t = HERO_TILES[tile_name]
    x, y = t['pos']
    w, h = t['size']
    band_y = y + int(h * _LV_BAND_Y_FRAC)
    band_h = int(h * _LV_BAND_H_FRAC)
    return frame[band_y:band_y+band_h, x:x+w]


# OCR refusal patterns. Qwen-VL sometimes refuses or hedges instead of
# returning a number when the crop has no readable digits (e.g. when the
# crop landed on a hero body instead of the Lv banner). These look like
# "I cannot read", "I'm sorry", "as an AI" -- always longer than a level
# number, always contain words. If we see any of these we must NOT extract
# stray digits from them, because the digits-only prompt can also make the
# model HALLUCINATE a number like '234' when there's nothing to read.
# Treat refusals -- AND any response that's clearly natural language --
# as "unreadable".
_OCR_REFUSAL_MARKERS = (
    "cannot", "can't", "sorry", "unable", "as an ai", "i don't",
    "no text", "no number", "not readable",
)


def _looks_like_refusal_or_prose(text: str) -> bool:
    """True if the OCR output looks like model refusal/prose rather than a
    digit-only level reading."""
    t = text.lower()
    if any(m in t for m in _OCR_REFUSAL_MARKERS):
        return True
    # A real reading is at most 3 digits + optional 'Lv.' prefix; anything
    # over ~12 chars is prose, not a number.
    if len(t.strip()) > 12:
        return True
    return False


def read_tile_level(
    frame: "npt.NDArray[Any]",
    tile_name: str,
    ocr_client: Any = None,
) -> int | None:
    """
    OCR the level number for one tile. Returns None if unreadable.
    Pass an OCRClient instance to share state across tiles (faster).
    """
    band = extract_level_band(frame, tile_name)
    if ocr_client is None:
        from utils.ocr_client import ocr_extract_text
        text = ocr_extract_text(band, prompt="Read the level number. Return only digits. Example: 150")
    else:
        text = ocr_client.extract_text(band, prompt="Read the level number. Return only digits. Example: 150")
    if not text:
        return None
    if _looks_like_refusal_or_prose(text):
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    try:
        level = int(digits)
    except ValueError:
        return None
    # In-game max is 150; anything above is hallucination or stray digits.
    if level > MAX_HERO_LEVEL:
        return None
    return level


def detect_sub_max_tiles(
    frame: "npt.NDArray[Any]",
    max_level: int = MAX_HERO_LEVEL,
    debug: bool = False,
) -> list[dict[str, Any]]:
    """
    Scan all visible tiles, return those whose OCR'd level is below max_level.
    A tile whose level can't be read is treated as level=max (skipped) -- we
    don't want to waste taps on garbled tiles.
    """
    from utils.ocr_client import OCRClient
    client = OCRClient()
    out: list[dict[str, Any]] = []
    for tile_name, tile_info in HERO_TILES.items():
        level = read_tile_level(frame, tile_name, ocr_client=client)
        if debug:
            print(f"  {tile_name}: level={level}")
        if level is not None and level < max_level:
            out.append({
                'name': tile_name,
                'click': tile_info['click'],
                'level': level,
            })
    return out


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
