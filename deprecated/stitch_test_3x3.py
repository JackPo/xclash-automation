"""
⚠️ DEPRECATED - DO NOT USE ⚠️
Deprecated as of 2025-11-05

This approach has been abandoned due to:
- Tile stitching complexity and unreliable results
- Inconsistent overlap detection
- Template matching poor alignment

See .claude/claude.MD for details.

---

Test tile stitching on a 3x3 grid
Tests both template matching and OpenCV Stitcher approaches
"""
import cv2
import numpy as np
import os
from pathlib import Path

TILES_DIR = "map_tiles"
OUTPUT_DIR = "stitching_tests"

def load_tile(row, col):
    """Load a single tile image"""
    filename = os.path.join(TILES_DIR, f"tile_{row:02d}_{col:02d}.png")
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Tile not found: {filename}")
    return cv2.imread(filename)

def find_horizontal_overlap(img1, img2, search_width=0.4):
    """
    Find horizontal overlap between two images using template matching
    Returns: (overlap_pixels, confidence)
    """
    h1, w1 = img1.shape[:2]
    h2, w2 = img2.shape[:2]

    # Extract search regions
    search_w = int(w1 * search_width)
    right_strip = img1[:, -search_w:]
    left_strip = img2[:, :search_w]

    best_overlap = 0
    best_score = -1

    # Try different overlap amounts
    for overlap in range(10, search_w, 5):
        if overlap >= min(w1, w2):
            break

        template = img1[:, -overlap:]
        target = img2[:, :overlap]

        # Resize to match if needed
        if template.shape != target.shape:
            continue

        # Calculate similarity (normalized correlation)
        result = cv2.matchTemplate(target, template, cv2.TM_CCOEFF_NORMED)
        score = result[0, 0] if result.size > 0 else 0

        if score > best_score:
            best_score = score
            best_overlap = overlap

    return best_overlap, best_score

def find_vertical_overlap(img1, img2, search_height=0.4):
    """
    Find vertical overlap between two images using template matching
    Returns: (overlap_pixels, confidence)
    """
    h1, w1 = img1.shape[:2]
    h2, w2 = img2.shape[:2]

    # Extract search regions
    search_h = int(h1 * search_height)
    bottom_strip = img1[-search_h:, :]
    top_strip = img2[:search_h, :]

    best_overlap = 0
    best_score = -1

    # Try different overlap amounts
    for overlap in range(10, search_h, 5):
        if overlap >= min(h1, h2):
            break

        template = img1[-overlap:, :]
        target = img2[:overlap, :]

        # Resize to match if needed
        if template.shape != target.shape:
            continue

        # Calculate similarity
        result = cv2.matchTemplate(target, template, cv2.TM_CCOEFF_NORMED)
        score = result[0, 0] if result.size > 0 else 0

        if score > best_score:
            best_score = score
            best_overlap = overlap

    return best_overlap, best_score

def stitch_row_template_matching(tiles):
    """Stitch a row of tiles using template matching"""
    if not tiles:
        return None

    result = tiles[0].copy()

    for i in range(1, len(tiles)):
        overlap, confidence = find_horizontal_overlap(result, tiles[i])
        print(f"  Tile {i}: overlap={overlap}px, confidence={confidence:.3f}")

        # Blend overlapping region
        if overlap > 0:
            # Alpha blend in overlap region
            h = min(result.shape[0], tiles[i].shape[0])
            blend_region = np.zeros((h, overlap, 3), dtype=np.float32)

            for x in range(overlap):
                alpha = x / overlap
                blend_region[:, x] = (1 - alpha) * result[:h, -overlap + x] + alpha * tiles[i][:h, x]

            # Combine images
            result = result[:h, :-overlap]
            tiles[i] = tiles[i][:h, :]
            result = np.hstack([result, blend_region.astype(np.uint8), tiles[i][:, overlap:]])
        else:
            # No overlap detected, just concatenate
            h = min(result.shape[0], tiles[i].shape[0])
            result = np.hstack([result[:h], tiles[i][:h]])

    return result

def stitch_vertical_template_matching(rows):
    """Stitch rows vertically using template matching"""
    if not rows:
        return None

    result = rows[0].copy()

    for i in range(1, len(rows)):
        overlap, confidence = find_vertical_overlap(result, rows[i])
        print(f"  Row {i}: overlap={overlap}px, confidence={confidence:.3f}")

        # Blend overlapping region
        if overlap > 0:
            # Alpha blend in overlap region
            w = min(result.shape[1], rows[i].shape[1])
            blend_region = np.zeros((overlap, w, 3), dtype=np.float32)

            for y in range(overlap):
                alpha = y / overlap
                blend_region[y, :] = (1 - alpha) * result[-overlap + y, :w] + alpha * rows[i][y, :w]

            # Combine images
            result = result[:-overlap, :w]
            rows[i] = rows[i][:, :w]
            result = np.vstack([result, blend_region.astype(np.uint8), rows[i][overlap:, :]])
        else:
            # No overlap detected, just concatenate
            w = min(result.shape[1], rows[i].shape[1])
            result = np.vstack([result[:, :w], rows[i][:, :w]])

    return result

def stitch_opencv_builtin(images):
    """Use OpenCV's built-in Stitcher class"""
    stitcher = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)
    status, stitched = stitcher.stitch(images)

    if status == cv2.Stitcher_OK:
        return stitched, "Success"
    else:
        error_codes = {
            cv2.Stitcher_ERR_NEED_MORE_IMGS: "Need more images",
            cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL: "Homography estimation failed",
            cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL: "Camera params adjustment failed"
        }
        return None, error_codes.get(status, f"Unknown error: {status}")

def main():
    print("="*60)
    print("3x3 Tile Stitching Test")
    print("="*60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load 3x3 grid of tiles
    print("\nLoading 3x3 tile grid...")
    tiles_grid = []
    for row in range(3):
        row_tiles = []
        for col in range(3):
            try:
                tile = load_tile(row, col)
                row_tiles.append(tile)
                print(f"  Loaded tile_{row:02d}_{col:02d}.png ({tile.shape[1]}x{tile.shape[0]})")
            except FileNotFoundError as e:
                print(f"  ERROR: {e}")
                return
        tiles_grid.append(row_tiles)

    # Method 1: Template Matching
    print("\n" + "="*60)
    print("METHOD 1: Template Matching")
    print("="*60)

    print("\nStitching rows horizontally...")
    stitched_rows = []
    for i, row_tiles in enumerate(tiles_grid):
        print(f"Row {i}:")
        stitched_row = stitch_row_template_matching(row_tiles)
        stitched_rows.append(stitched_row)
        print(f"  Result: {stitched_row.shape[1]}x{stitched_row.shape[0]}")

    print("\nStitching rows vertically...")
    result_template = stitch_vertical_template_matching(stitched_rows)
    print(f"Final result: {result_template.shape[1]}x{result_template.shape[0]}")

    # Save result
    output_path = os.path.join(OUTPUT_DIR, "test_3x3_template_matching.png")
    cv2.imwrite(output_path, result_template)
    print(f"\nSaved: {output_path}")

    # Method 2: OpenCV Stitcher
    print("\n" + "="*60)
    print("METHOD 2: OpenCV Built-in Stitcher")
    print("="*60)

    # Flatten tile grid for stitcher
    all_tiles = [tile for row in tiles_grid for tile in row]
    print(f"\nStitching {len(all_tiles)} tiles...")
    result_opencv, status = stitch_opencv_builtin(all_tiles)

    if result_opencv is not None:
        print(f"Success! Result: {result_opencv.shape[1]}x{result_opencv.shape[0]}")
        output_path = os.path.join(OUTPUT_DIR, "test_3x3_opencv_stitcher.png")
        cv2.imwrite(output_path, result_opencv)
        print(f"Saved: {output_path}")
    else:
        print(f"Failed: {status}")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Template Matching: Success ({result_template.shape[1]}x{result_template.shape[0]})")
    if result_opencv is not None:
        print(f"OpenCV Stitcher: Success ({result_opencv.shape[1]}x{result_opencv.shape[0]})")
    else:
        print(f"OpenCV Stitcher: Failed ({status})")
    print(f"\nResults saved to: {OUTPUT_DIR}/")
    print("="*60)

if __name__ == "__main__":
    main()
