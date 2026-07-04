# Extracted Game Assets Analysis

## Overview

Analysis of 35,062 PNG images extracted from X-Clash Unity asset bundles to determine if they could improve template matching performance over screenshot-based templates.

**Date**: 2026-02-07

**Conclusion**: Screenshot-based templates work **significantly better** than extracted assets for template matching (51x better in tests). Extracted assets lack in-game rendering effects.

---

## Extracted Assets Location

```
C:\Users\mail\xclash\asset_bundles_extracted\
```

- **35,062 PNG files** (~2GB total)
- Named by Unity path ID (e.g., `-3177723797856428210_Sprite.png`)
- No descriptive names - requires similarity search to find specific assets

### Asset Types Found

| Type | Description | Example |
|------|-------------|---------|
| `*_Sprite.png` | Individual sprites (icons, buttons, UI elements) | Back button, flags, icons |
| `*_Texture2D.png` | Texture atlases (multiple sprites combined) | Building collections, hero portraits |
| `*_dup1.png` etc. | Duplicate extractions from different bundles | Same sprite in multiple asset bundles |

### Asset Size Distribution

| Size Range | Count | Typical Content |
|------------|-------|-----------------|
| < 1KB | ~2,000 | Tiny icons, single-color sprites |
| 1-10KB | ~6,600 | Small UI elements, icons |
| 10-50KB | ~8,000 | Buttons, medium icons |
| 50KB-1MB | ~15,000 | Large sprites, UI panels |
| > 1MB | ~3,400 | Texture atlases, splash art |

---

## Similarity Search Tool

Created `tools/find_similar_asset.py` to find assets similar to existing templates.

### Usage

```bash
# Find assets similar to a template
python tools/find_similar_asset.py templates/ground_truth/back_button_4k.png

# Show more results
python tools/find_similar_asset.py templates/ground_truth/back_button_4k.png --top 20

# Force recompute hashes (skip cache)
python tools/find_similar_asset.py templates/ground_truth/back_button_4k.png --no-cache
```

### How It Works

1. Computes perceptual hash (pHash) for all 35K assets (cached in `data/asset_hashes.cache`)
2. Computes pHash for input template
3. Finds assets with lowest Hamming distance (most similar)
4. Returns top N candidates with similarity scores

### Output Example

```
Searching for images similar to: back_button_4k.png
Template hash: aaa8d51a74aab955c956c6c7b61d973cd992f0d1d2458d06e706f338d918ccc3

Top 15 similar images (lower distance = more similar):
--------------------------------------------------------------------------------
 1. [dist= 88] -7987881569885483792_Sprite.png
 2. [dist= 90] -3177723797856428210_Sprite.png  <-- This is the back button!
 3. [dist= 90] -4598175054501692454_Sprite.png
```

### Limitations

- High distance values (88-100) are common - pHash works best on visually distinct images
- Small/simple icons may not match well
- Text-based UI elements won't be found (text is rendered at runtime)

---

## Template Matching Comparison

### Test Setup

- **Test image**: Union panel screenshot with back button visible
- **Original template**: `back_button_union_4k.png` (screenshot-based)
- **Extracted asset**: `-3177723797856428210_Sprite.png` (scaled to match size)
- **Method**: `cv2.TM_SQDIFF_NORMED` (lower score = better match)

### Results

| Template | Score | Location | Correct? |
|----------|-------|----------|----------|
| Screenshot-based | **0.001053** | (1396, 2047) | ✓ Yes |
| Extracted asset | 0.053978 | (1837, 1789) | ✗ No |

**Screenshot template is 51x better!**

### Why Screenshots Work Better

1. **Rendering Effects**: Screenshots capture actual in-game appearance including:
   - Lighting and shadows
   - Post-processing effects
   - Anti-aliasing
   - Color grading

2. **Exact Match**: Template matching finds pixel-level similarity - screenshots match the rendered output exactly

3. **Extracted Assets Are Raw**: The extracted sprites are "clean" but don't include:
   - In-game shading
   - UI layer effects
   - Dynamic color adjustments

---

## Test Results by Template Type

### 1. Back Button (`back_button_4k.png`)

- **Match found**: `-3177723797856428210_Sprite.png`
- **Performance**: Screenshot 51x better
- **Verdict**: Keep screenshot template

### 2. Bag Button (`bag_button_4k.png`)

- **Match found**: None (perceptual hash couldn't find it)
- **Reason**: Icon is too small/simple for pHash similarity
- **Verdict**: N/A - screenshot template is only option

### 3. Use Button (`use_button_4k.png`)

- **Match found**: None
- **Reason**: Contains dynamic text ("Purchase 300") - text is rendered at runtime, not in asset bundles
- **Verdict**: N/A - text buttons can only be screenshot-based

---

## When Extracted Assets ARE Useful

Despite being worse for template matching, extracted assets are valuable for:

### 1. Asset Discovery
Find what sprites exist in the game:
```bash
# Find all flag sprites
ls asset_bundles_extracted/ | grep -i flag

# Find large UI elements
ls -la asset_bundles_extracted/ | awk '$5 > 100000' | head -20
```

### 2. Creating Masks
Extracted assets have transparent backgrounds - useful for:
- Understanding sprite boundaries
- Creating mask templates for masked matching
- Documenting UI element shapes

### 3. Reference Documentation
- Catalog available game icons
- Understand UI component library
- Reference for manual template creation

### 4. Non-Rendered Elements
Some assets might work well if they appear without rendering effects:
- Simple solid-color icons
- Loading indicators
- Debug UI elements

---

## File Locations

| Path | Description |
|------|-------------|
| `asset_bundles_extracted/` | 35,062 extracted PNG files |
| `data/asset_hashes.cache` | Cached perceptual hashes (~7MB) |
| `tools/find_similar_asset.py` | Similarity search tool |
| `templates/ground_truth/` | Screenshot-based templates (keep using these) |

---

## Recommendations

1. **Keep using screenshot-based templates** - they work significantly better

2. **Use similarity tool for exploration** - find what assets exist, not for replacement

3. **Don't bulk-replace templates** - extracted assets will degrade matching performance

4. **Consider extracted assets for masks** - transparent backgrounds are useful

5. **Text buttons require screenshots** - dynamic text isn't in asset bundles

---

## Dependencies

```bash
pip install imagehash Pillow
```

---

## Related Documentation

- `docs/GAME_DATA_STORAGE.md` - Local game data analysis
- `.claude/skills/template-catalog/` - Template positions and thresholds
- `.claude/skills/screenshot-detection/` - Template extraction from screenshots
