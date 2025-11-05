"""
⚠️ DEPRECATED - DO NOT USE ⚠️
Deprecated as of 2025-11-05

This approach has been abandoned due to:
- Tile stitching complexity and unreliable results
- Inconsistent overlap detection between tiles
- Better alternatives needed for map analysis

See .claude/claude.MD for details.

---

Stitch all captured map tiles into one complete map
Uses row-by-row stitching with OpenCV for best results
"""
import cv2
import numpy as np
import os
from pathlib import Path
from datetime import datetime

TILES_DIR = "map_tiles"
OUTPUT_FILE = "full_map_stitched.png"

def load_tile(row, col):
    """Load a single tile image"""
    filename = os.path.join(TILES_DIR, f"tile_{row:02d}_{col:02d}.png")
    if os.path.exists(filename):
        return cv2.imread(filename)
    return None

def stitch_images_opencv(images, mode="horizontal"):
    """Use OpenCV Stitcher to combine images"""
    if not images or len(images) < 2:
        return images[0] if images else None

    # Filter out None images
    images = [img for img in images if img is not None]
    if not images:
        return None

    print(f"    Stitching {len(images)} images...")
    stitcher = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)
    status, stitched = stitcher.stitch(images)

    if status == cv2.Stitcher_OK:
        return stitched
    else:
        error_codes = {
            cv2.Stitcher_ERR_NEED_MORE_IMGS: "Need more images",
            cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL: "Homography estimation failed",
            cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL: "Camera params adjustment failed"
        }
        error_msg = error_codes.get(status, f"Unknown error: {status}")
        print(f"    ERROR: {error_msg}")
        # Fallback: simple concatenation
        return simple_concatenate(images, mode)

def simple_concatenate(images, mode="horizontal"):
    """Fallback: simple concatenation without blending"""
    if not images:
        return None
    if len(images) == 1:
        return images[0]

    if mode == "horizontal":
        # Find minimum height
        min_h = min(img.shape[0] for img in images)
        resized = [img[:min_h] for img in images]
        return np.hstack(resized)
    else:  # vertical
        # Find minimum width
        min_w = min(img.shape[1] for img in images)
        resized = [img[:, :min_w] for img in images]
        return np.vstack(resized)

def find_max_row_col():
    """Find the maximum row and column numbers in the tiles directory"""
    max_row, max_col = -1, -1

    for filename in os.listdir(TILES_DIR):
        if filename.startswith("tile_") and filename.endswith(".png"):
            parts = filename.replace("tile_", "").replace(".png", "").split("_")
            if len(parts) == 2:
                try:
                    row, col = int(parts[0]), int(parts[1])
                    max_row = max(max_row, row)
                    max_col = max(max_col, col)
                except ValueError:
                    continue

    return max_row, max_col

def main():
    print("="*60)
    print("Full Map Stitching")
    print("="*60)

    start_time = datetime.now()

    # Discover tile range
    max_row, max_col = find_max_row_col()
    print(f"\nDetected tile grid: {max_row+1} rows × {max_col+1} columns")
    print(f"Total expected tiles: {(max_row+1) * (max_col+1)}")

    # Count actual tiles
    actual_tiles = len([f for f in os.listdir(TILES_DIR) if f.endswith(".png")])
    print(f"Actual tiles found: {actual_tiles}")

    # Strategy: Stitch in chunks to avoid memory issues
    # 1. Stitch each row horizontally
    # 2. Stitch all rows vertically

    print("\n" + "="*60)
    print("PHASE 1: Stitching rows horizontally")
    print("="*60)

    stitched_rows = []

    for row in range(max_row + 1):
        print(f"\nRow {row}/{max_row}:")

        # Load all tiles for this row
        row_tiles = []
        for col in range(max_col + 1):
            tile = load_tile(row, col)
            if tile is not None:
                row_tiles.append(tile)

        print(f"  Loaded {len(row_tiles)} tiles")

        if not row_tiles:
            print(f"  WARNING: No tiles found for row {row}, skipping")
            continue

        if len(row_tiles) == 1:
            stitched_row = row_tiles[0]
        else:
            # Stitch row in chunks of 5 tiles to avoid memory issues
            chunk_size = 5
            chunks = []

            for i in range(0, len(row_tiles), chunk_size):
                chunk = row_tiles[i:i+chunk_size]
                print(f"  Stitching chunk {i//chunk_size + 1} ({len(chunk)} tiles)...")
                stitched_chunk = stitch_images_opencv(chunk, "horizontal")
                if stitched_chunk is not None:
                    chunks.append(stitched_chunk)

            # Stitch chunks together
            if len(chunks) > 1:
                print(f"  Combining {len(chunks)} chunks...")
                stitched_row = stitch_images_opencv(chunks, "horizontal")
            else:
                stitched_row = chunks[0] if chunks else None

        if stitched_row is not None:
            print(f"  Result: {stitched_row.shape[1]}×{stitched_row.shape[0]}")
            stitched_rows.append(stitched_row)

            # Save intermediate row result
            row_output = f"stitching_tests/row_{row:02d}_stitched.png"
            os.makedirs(os.path.dirname(row_output), exist_ok=True)
            cv2.imwrite(row_output, stitched_row)
            print(f"  Saved: {row_output}")
        else:
            print(f"  ERROR: Failed to stitch row {row}")

    print("\n" + "="*60)
    print(f"PHASE 2: Stitching {len(stitched_rows)} rows vertically")
    print("="*60)

    if not stitched_rows:
        print("ERROR: No rows were successfully stitched!")
        return

    if len(stitched_rows) == 1:
        final_map = stitched_rows[0]
    else:
        # Stitch rows in chunks
        chunk_size = 3
        chunks = []

        for i in range(0, len(stitched_rows), chunk_size):
            chunk = stitched_rows[i:i+chunk_size]
            print(f"\nStitching row chunk {i//chunk_size + 1} ({len(chunk)} rows)...")
            stitched_chunk = stitch_images_opencv(chunk, "vertical")
            if stitched_chunk is not None:
                chunks.append(stitched_chunk)

        # Combine vertical chunks
        if len(chunks) > 1:
            print(f"\nCombining {len(chunks)} vertical chunks...")
            final_map = stitch_images_opencv(chunks, "vertical")
        else:
            final_map = chunks[0] if chunks else None

    if final_map is not None:
        print("\n" + "="*60)
        print("SUCCESS!")
        print("="*60)
        print(f"Final map size: {final_map.shape[1]}×{final_map.shape[0]}")

        # Save final result
        cv2.imwrite(OUTPUT_FILE, final_map)
        print(f"Saved: {OUTPUT_FILE}")

        # Calculate file size
        file_size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
        print(f"File size: {file_size_mb:.2f} MB")
    else:
        print("\nERROR: Final stitching failed!")

    end_time = datetime.now()
    total_time = (end_time - start_time).total_seconds()
    print(f"\nTotal time: {total_time/60:.2f} minutes ({total_time:.1f} seconds)")
    print("="*60)

if __name__ == "__main__":
    main()
