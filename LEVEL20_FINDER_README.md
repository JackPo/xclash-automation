# XClash Level 20 Castle Finder

Two-phase approach to finding players:
1. **Phase 1 (This tool)**: Scan map at zoomed-out level, find all castle level 20s
2. **Phase 2 (Future)**: Zoom in on level 20 locations to check player names

## Quick Start

### Step 1: One-Time Calibration

Run this ONCE to determine your map size and navigation parameters:

```bash
python calibrate_map.py
# or double-click: calibrate.bat
```

This interactive script will:
- Guide you to find map edges (left, top, right, bottom)
- Measure map dimensions
- Save settings to `map_config.json`

**You only need to do this once!** The settings are saved and reused.

### Step 2: Find Level 20 Castles

```bash
python find_level20.py --run-id scan001
# or: find_level20.bat scan001
```

This will:
- Navigate to top-left corner automatically
- Scan entire map in zigzag pattern
- Save screenshot whenever "20" is detected
- Track coordinates for each level 20 castle
- Create results file: `scan001_level20_results.json`

## How It Works

### Architecture

```
Phase 1 (Zoomed Out):
  - See castle levels but not names
  - Fast scan to find all level 20s
  - Save screenshots + coordinates

Phase 2 (Future - Zoomed In):
  - Navigate to each level 20
  - Zoom in to see player names
  - OCR for specific player
```

### Why This Approach?

1. **Efficient filtering**: Only ~5-10% of castles are level 20
2. **Zoom trade-off**: Can't see both level and name at same zoom
3. **Coordinate tracking**: Save locations for later investigation
4. **Reusability**: Multiple searches without re-scanning

## Output Files

### Directory Structure

```
scan001_level20/              # Screenshots directory
  ├── r0_c0.png              # Row 0, Column 0
  ├── r0_c5.png              # Level 20 found here
  ├── r2_c3.png
  └── ...

scan001_level20_results.json  # Coordinate tracking file
map_config.json               # Calibration (created once)
```

### Results JSON Format

```json
{
  "run_id": "scan001",
  "started_at": "2025-11-02T...",
  "completed_at": "2025-11-02T...",
  "total_scans": 80,
  "level20_found": 7,
  "map_config": "MapConfig(grid=10×8, ...)",
  "castles": [
    {
      "id": 1,
      "position": {
        "grid_row": 0,
        "grid_col": 5,
        "screen_center_x": 1280,
        "screen_center_y": 720,
        "description": "Row 0, Column 5"
      },
      "screenshot": "r0_c5.png",
      "ocr_text": ["20", "Lv 20"],
      "all_text": ["Alliance", "20", "Power", ...]
    },
    ...
  ]
}
```

## Usage Examples

### Basic Scan

```bash
# Run calibration once
python calibrate_map.py

# Run level 20 finder
python find_level20.py --run-id myscan
```

### Debug Mode (save all screenshots)

```bash
python find_level20.py --run-id debug001 --debug
```

Saves every screenshot even if no level 20 found (useful for troubleshooting).

### Multiple Runs

```bash
python find_level20.py --run-id morning_scan
python find_level20.py --run-id evening_scan
python find_level20.py --run-id weekend_scan
```

Each run creates its own directory and results file.

## Prerequisites

### Before Calibration
1. BlueStacks running with XClash open
2. World map visible
3. Map can be at any position (script will navigate)

### Before Level 20 Scan
1. Completed calibration (map_config.json exists)
2. BlueStacks running with XClash open
3. **Zoom level set to show castle levels** (numbers visible below castles)
4. World map visible

## Calibration Details

### What Gets Calibrated?

1. **Navigation to corner**
   - How many swipes needed to reach left edge
   - How many swipes needed to reach top edge

2. **Map dimensions**
   - Width in "screen-widths"
   - Height in "screen-heights"

3. **Scroll distances**
   - Horizontal scroll distance (pixels)
   - Vertical scroll distance (pixels)
   - Should create ~20% overlap between views

### When to Re-Calibrate?

- Game updates that change map size
- Changing BlueStacks resolution
- Navigation seems off (not reaching edges, skipping areas)

Just delete `map_config.json` and run calibration again.

## Troubleshooting

### "Map config not found"

**Solution:** Run calibration first:
```bash
python calibrate_map.py
```

### Not Finding Level 20s (But You Know They Exist)

**Possible causes:**
1. **Wrong zoom level** - Must see castle level numbers (not player names)
2. **OCR confidence too high** - Check test_config.py to verify OCR is working
3. **Map moved during scan** - Don't touch game during scanning

**Debug:**
```bash
# Test OCR on current screen
python test_config.py ocr

# Look for "20" or similar numbers in output
# If numbers not detected, adjust zoom level
```

### Navigation Not Working

**Solution:**
1. Re-run calibration: `python calibrate_map.py`
2. Make sure you're at world map (not city view)
3. Check BlueStacks is connected: `adb devices`

### Finding Too Many False Positives

The OCR might detect "20" in other contexts (like "2025", "200k power", etc.).

**Solutions:**
1. Phase 2 will verify by zooming in and checking names
2. For now, manually review screenshots in `{run_id}_level20/` folder
3. Filter results JSON by looking at `ocr_text` field

## Configuration

### Adjusting Scan Parameters

Edit `find_level20.py` Config class:

```python
# Timing adjustments (if map scrolls slowly)
DELAY_AFTER_SWIPE = 0.8        # Increase if map hasn't settled
DELAY_AFTER_SCREENSHOT = 0.3   # Increase if screenshots are blurry
DELAY_BETWEEN_SCANS = 0.2      # General delay between scans

# OCR confidence
OCR_CONFIDENCE_THRESHOLD = 30  # Lower = more detections (more false positives)
```

### Map Boundaries

If UI elements are blocking the map:

```python
# In Config class
MAP_LEFT = 400    # Increase if left UI blocking
MAP_RIGHT = 2160  # Decrease if right UI blocking
MAP_TOP = 200     # Increase if top UI blocking
MAP_BOTTOM = 1240 # Decrease if bottom UI blocking
```

## Performance

- **Calibration**: ~5-10 minutes (one-time)
- **Level 20 scan**: ~2-3 minutes for 80-100 views
- **Disk space**: ~5-15MB per run (depends on level 20 count)

## Next Steps: Phase 2 (Future Enhancement)

**Goal**: Find specific player among level 20 castles

**Approach**:
1. Load `scan001_level20_results.json`
2. For each castle location:
   - Navigate to coordinates
   - Zoom IN to see player names
   - OCR for player name
   - If found, report location and stop

**Command** (future):
```bash
python find_player_at_level20.py --run-id scan001 --player "PlayerName"
```

## Files Overview

| File | Purpose |
|------|---------|
| `calibrate_map.py` | One-time map calibration |
| `find_level20.py` | Phase 1: Find all level 20 castles |
| `map_config.json` | Saved calibration data |
| `{RUN_ID}_level20/` | Screenshots of level 20 castles |
| `{RUN_ID}_level20_results.json` | Coordinates and metadata |
| `calibrate.bat` | Windows shortcut for calibration |
| `find_level20.bat` | Windows shortcut for scanning |

## Tips

1. **Run during low activity** - Map won't move from other events
2. **Multiple runs** - Map changes as players move, scan periodically
3. **Backup results** - Keep `{RUN_ID}_level20_results.json` files for historical tracking
4. **Review screenshots** - Quickly scan through `{RUN_ID}_level20/` folder to spot patterns

## Known Limitations

1. **Manual zoom adjustment** - Must set zoom level manually before scan
2. **False positives** - OCR might detect "20" in other contexts
3. **Map changes** - Players can upgrade/downgrade castles between scans
4. **No name detection yet** - Phase 2 not implemented (coming soon)

## Support

If things aren't working:
1. Check BlueStacks is running: `adb devices`
2. Test OCR: `python test_config.py ocr`
3. Test navigation: `python test_config.py nav`
4. Re-run calibration if navigation seems off
