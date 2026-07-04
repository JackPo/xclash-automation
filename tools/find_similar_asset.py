#!/usr/bin/env python3
"""
Find similar images in extracted asset bundles using perceptual hashing.

Usage:
    python tools/find_similar_asset.py templates/ground_truth/back_button_4k.png
    python tools/find_similar_asset.py templates/ground_truth/bag_button_4k.png --top 20
"""

import argparse
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import imagehash
from PIL import Image


ASSETS_DIR = Path(__file__).parent.parent / "asset_bundles_extracted"
CACHE_FILE = Path(__file__).parent.parent / "data" / "asset_hashes.cache"


def compute_hash(image_path: Path) -> tuple[str, imagehash.ImageHash | None]:
    """Compute perceptual hash for an image."""
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if needed (handles RGBA)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparent images
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            phash = imagehash.phash(img, hash_size=16)
            return str(image_path), phash
    except Exception as e:
        return str(image_path), None


def load_or_compute_hashes(assets_dir: Path, use_cache: bool = True) -> dict[str, imagehash.ImageHash]:
    """Load cached hashes or compute them."""
    hashes = {}

    # Try loading cache
    if use_cache and CACHE_FILE.exists():
        print(f"Loading cached hashes from {CACHE_FILE}...")
        try:
            with open(CACHE_FILE, 'r') as f:
                for line in f:
                    parts = line.strip().split('\t')
                    if len(parts) == 2:
                        path, hash_str = parts
                        hashes[path] = imagehash.hex_to_hash(hash_str)
            print(f"  Loaded {len(hashes)} cached hashes")
            return hashes
        except Exception as e:
            print(f"  Cache load failed: {e}, recomputing...")

    # Compute hashes for all assets
    png_files = list(assets_dir.glob("*.png"))
    print(f"Computing hashes for {len(png_files)} images...")

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(compute_hash, p): p for p in png_files}
        completed = 0
        for future in as_completed(futures):
            path, hash_val = future.result()
            if hash_val is not None:
                hashes[path] = hash_val
            completed += 1
            if completed % 1000 == 0:
                print(f"  Processed {completed}/{len(png_files)}...")

    # Save cache
    print(f"Saving {len(hashes)} hashes to cache...")
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        for path, hash_val in hashes.items():
            f.write(f"{path}\t{hash_val}\n")

    return hashes


def find_similar(template_path: Path, hashes: dict[str, imagehash.ImageHash], top_n: int = 10) -> list[tuple[str, int]]:
    """Find most similar images to the template."""
    # Compute template hash
    _, template_hash = compute_hash(template_path)
    if template_hash is None:
        print(f"Error: Could not compute hash for {template_path}")
        return []

    print(f"Template hash: {template_hash}")

    # Find similar
    similarities = []
    for path, asset_hash in hashes.items():
        distance = template_hash - asset_hash  # Hamming distance
        similarities.append((path, distance))

    # Sort by distance (lower = more similar)
    similarities.sort(key=lambda x: x[1])

    return similarities[:top_n]


def main():
    parser = argparse.ArgumentParser(description="Find similar images in extracted assets")
    parser.add_argument("template", help="Path to template image")
    parser.add_argument("--top", type=int, default=10, help="Number of results to show")
    parser.add_argument("--no-cache", action="store_true", help="Don't use cached hashes")
    parser.add_argument("--assets-dir", type=Path, default=ASSETS_DIR, help="Assets directory")
    args = parser.parse_args()

    template_path = Path(args.template)
    if not template_path.exists():
        print(f"Error: Template not found: {template_path}")
        sys.exit(1)

    if not args.assets_dir.exists():
        print(f"Error: Assets directory not found: {args.assets_dir}")
        sys.exit(1)

    # Load or compute hashes
    hashes = load_or_compute_hashes(args.assets_dir, use_cache=not args.no_cache)

    # Find similar
    print(f"\nSearching for images similar to: {template_path.name}")
    results = find_similar(template_path, hashes, args.top)

    print(f"\nTop {len(results)} similar images (lower distance = more similar):")
    print("-" * 80)
    for i, (path, distance) in enumerate(results, 1):
        filename = Path(path).name
        print(f"{i:2}. [dist={distance:3}] {filename}")

    # Print paths for easy viewing
    print("\n" + "=" * 80)
    print("To view these images, run:")
    for path, distance in results[:5]:
        print(f"  # Distance {distance}")
        print(f"  start {path}")


if __name__ == "__main__":
    main()
