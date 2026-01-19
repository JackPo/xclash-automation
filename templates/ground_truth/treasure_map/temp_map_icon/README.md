# Treasure Map Icon Analysis

## Extract Info
- **Position**: (2096, 1540)
- **Size**: 158x162 pixels
- **Source**: 20 back-to-back screenshots from `screenshots/debug/fast_*.png`

## Analysis Results

### Group A - Exact Matches (diff = 0.0000)
**Frames**: 00, 02, 03, 04, 06, 07, 08, 10, 11, 13, 14, 15, 17, 18, 19

These 15 frames have IDENTICAL pixels - the icon is at the same bounce position.
Used for main template: `treasure_map_4k.png` + `treasure_map_mask_4k.png`

### Bounced Frames - No Exact Pairs
**Frames**: 01, 05, 09, 12, 16

These frames have the icon at different bounce positions. No exact pairs found:
- 05 <-> 12: diff = 13.41 (closest but still different)
- 01 <-> 16: diff = 16.12
- 09: diff = 95+ from everything (outlier, icon way off)

### Template Files in This Folder
| File | Description |
|------|-------------|
| `extract_XX.png` | Raw extracts from each frame |
| `tm_groupB_4k.png` | Template from frame 05 (mid-bounce) |
| `tm_groupB_mask_4k.png` | Mask for group B (unreliable) |
| `tm_groupC_4k.png` | Template from frame 01 (high-bounce) |
| `tm_groupC_mask_4k.png` | Mask for group C (unreliable) |
| `treasure_map_high_4k.png` | High bounce template |

## Future Work
Capture more screenshots to find exact pairs for bounced frames (01, 05, 09, 12, 16).
With more samples, we may find frames where the bounce position matches exactly.

## Current Strategy
Use Group A template only - catches 15/20 frames with extreme precision (score < 0.001).
Over 2-3 consecutive screenshots, the bounce will return to Group A position.
