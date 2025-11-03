# XClash Zoom Functionality

## Overview
Successfully implemented zoom in/out functionality for the XClash game running on BlueStacks emulator using minitouch for proper multi-touch pinch gestures.

## Working Solution: `discover_zoom_adb.py`

### How It Works
- Uses **minitouch** - a tool that provides true multi-touch support via ADB
- Simulates pinch gestures with two virtual fingers
- Pinch-in (fingers move together) = zoom out
- Pinch-out (fingers move apart) = zoom in

### Key Features
- Closes dialogs automatically before zooming
- Takes screenshots after each zoom step
- Runs OCR on each screenshot to detect text
- Saves all results to `zoom_discovery_adb/` directory
- Configurable zoom sensitivity and steps

### Usage
```bash
python discover_zoom_adb.py
```

### Requirements
- minitouch must be installed on the device at `/data/local/tmp/minitouch`
- Run `setup_minitouch.py` to install if not present
- ADB connection to BlueStacks (127.0.0.1:5555)

## Zoom Configuration

### Current Settings (Reduced sensitivity for gentler zoom)
- **Zoom Out**: Fingers start 560px apart, end 200px apart
- **Zoom In**: Reverse of zoom out
- **Movement steps**: 3 steps per zoom (reduced from 5 for gentler effect)
- **Wait time**: 15ms between steps, 1 second after zoom

### Minitouch Coordinates
- Coordinate space: 32767 x 32767
- Conversion: `x_mt = (x_screen / 2560) * 32767`
- Center point: (1280, 720) screen → (16384, 9216) minitouch

## Test Results

### What Works
- ✅ Minitouch pinch gestures successfully zoom in/out
- ✅ Screenshots capture zoom changes
- ✅ OCR detects player names and UI elements at various zoom levels

### Zoom Behavior
- **Initial state**: Close-up view with castles and player names visible
- **After zoom out**: More area visible, more castles appear
- **Fully zoomed out**: Kingdom/territory borders visible
- **After zoom in**: Returns to closer view

### OCR Detection Quality by Zoom Level
- **Close zoom** (initial): ~500-700 chars detected, player names readable
- **Medium zoom**: ~200-450 chars, some names still visible
- **Far zoom**: ~0-100 chars, text too small to read

## Failed Approaches (Removed)

The following methods were attempted but did not work:

1. **discover_zoom.py** - ADB swipe gestures (too simple, not true pinch)
2. **discover_zoom_v2.py** - Keyboard shortcuts via pyautogui (window activation issues)
3. **discover_zoom_manual.py** - Manual intervention approach
4. **test_keyboard_zoom.py** - Direct keyboard event testing
5. **test_zoom_methods.py** - Various zoom method experiments

All non-working scripts have been removed from the repository.

## Next Steps

### For Player Finding
- Determine optimal zoom level for player name detection
- Balance between:
  - **More zoomed in**: Better OCR accuracy, fewer players visible
  - **More zoomed out**: More players visible, worse OCR accuracy
- Implement systematic map scanning at optimal zoom

### Improvements
- Fine-tune zoom sensitivity (currently reduced but may need further adjustment)
- Add zoom level detection (how many times we've zoomed)
- Implement zoom reset (return to default zoom level)
- Add zoom limits (don't zoom out/in too far)

## Files
- `discover_zoom_adb.py` - Main working zoom script
- `setup_minitouch.py` - Install minitouch on device
- `zoom_discovery_adb/` - Test results directory
- `ZOOM_README.md` - This documentation

## Technical Details

### Minitouch Commands
```
d <id> <x> <y> <pressure>  # Touch down
m <id> <x> <y> <pressure>  # Move finger
u <id>                      # Touch up
c                           # Commit (execute commands)
w <ms>                      # Wait
```

### Example Zoom Out Sequence
```
d 0 12800 9216 50    # Finger 0 down at left position
d 1 19968 9216 50    # Finger 1 down at right position
c                     # Commit
w 15                  # Wait 15ms
m 0 13952 9216 50    # Move fingers closer together
m 1 18816 9216 50
c
w 15
m 0 15104 9216 50    # Continue moving together
m 1 17664 9216 50
c
w 15
u 0                   # Release both fingers
u 1
c
```

## Last Updated
2025-11-02
