# View Detection Reference Tests

This directory contains reference screenshots with expected detection results for regression testing.

## Ground Truth Templates

All templates are stored in `templates/ground_truth/`:
- `world_button.png` - 160x160 square, extracted from (2400, 1280) - Button shows "WORLD" when in TOWN view
- `town_button.png` - 160x160 square, extracted from (2400, 1280) - Button shows "TOWN" when in WORLD view (zoomed in)
- `town_button_zoomed_out.png` - 160x160 square, extracted from (2400, 1280) - Button variant when in WORLD view AND zoomed out (minimap visible)
- `minimap_base.png` - 226x226 square, extracted from (2334, 0) - Minimap template for detection

## Reference Screenshots

### reference_world_view_zoomed_in.png

**Game State:**
- Currently in: WORLD view
- Zoom level: Zoomed in (minimap not visible)
- Button shows: "TOWN" (destination you can switch to)
- Button template matched: `town_button.png`

**Expected Detection Results:**
```
VIEW DETECTION:
  State: WORLD
  Score: 0.9999 (99.99%)
  Minimap Present (from button): False

MINIMAP DETECTION:
  Score: 0.0620 (6.2%)
  Present: False
```

**Why these results:**
- View score is 99.99% because the TOWN button template matches perfectly
- State is WORLD because we invert the button label (button shows TOWN → currently in WORLD)
- Minimap present is False because regular town_button.png matched, not town_button_zoomed_out.png
- Minimap score is 6.2% because we're zoomed in, so minimap is not visible

### reference_world_view_zoomed_out.png

**Game State:**
- Currently in: WORLD view
- Zoom level: Zoomed OUT (minimap visible)
- Button shows: "TOWN" but different appearance (zoomed out variant)
- Button template matched: `town_button_zoomed_out.png`

**Expected Detection Results:**
```
VIEW DETECTION:
  State: WORLD
  Score: 0.9529 (95.29%)
  Minimap Present (from button): True

  Minimap Viewport (Yellow Rectangle):
    Position: (4, 25)
    Size: 166x197
    Area: 32702 pixels (64.0% of minimap)
    Center: (87, 123)
    Zoom: OUT (larger area = more zoomed out)
```

**Why these results:**
- View score is 95.29% because the zoomed-out TOWN button variant matches
- State is WORLD because button shows TOWN (inverted logic)
- Minimap present is True because `town_button_zoomed_out.png` template matched
- Yellow rectangle shows viewport covering 64% of minimap = fairly zoomed OUT
- Larger yellow rectangle area = more zoomed out (viewing larger portion of world map)
- Smaller yellow rectangle area = more zoomed in (viewing smaller portion of world map)

## Running Tests

```bash
python view_detection.py --test
```

This will display current detection scores which should match the reference values above.

## Template Extraction Details

**Button Templates (160x160):**
- Coordinate: x=2400, y=1280, size=160x160
- Extraction: `frame[1280:1440, 2400:2560]` gives 160x160 square icon region
- The button itself is 460x160, but we extract only the square icon portion

**Minimap Template (226x226):**
- Coordinate: x=2334, y=0, size=226x226
- Extraction: `frame[0:226, 2334:2560]` gives 226x226 square minimap region
- Auto-detected using edge detection on upper-right corner

## Thresholds

- View detection: 0.90 (90%) minimum confidence
- Minimap detection: 0.7 (70%) minimum confidence (deprecated - use button variant instead)

Scores above these thresholds indicate positive detection.

## Minimap Viewport Detection

The yellow rectangle in the minimap provides two key pieces of information:

1. **Position**: Where you are on the world map (center_x, center_y)
2. **Zoom Level**: How zoomed in/out you are (based on area)

**Area interpretation:**
- **Larger area** (>50% of minimap) = **More zoomed OUT** (viewing large portion of world)
- **Smaller area** (<50% of minimap) = **More zoomed IN** (viewing small portion of world)

The yellow rectangle represents your current viewport on the world map - what portion of the map you can see on screen.
