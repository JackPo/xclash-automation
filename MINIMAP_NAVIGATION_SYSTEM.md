# Minimap Navigation System - Complete Documentation

## Overview

Complete minimap-based navigation system for Clash of Clans automation using calibrated zoom levels and viewport detection.

**CRITICAL: This system is the result of extensive calibration and testing. DO NOT re-calibrate or modify the calibration data without understanding the full system.**

---

## Architecture

```
Calibration Data (zoom_calibration_matrix_clean.json)
    ↓
MinimapNavigator (minimap_navigator.py)
    ↓
Navigation Functions:
  - detect_zoom_level()        → Identify current zoom from viewport area
  - calculate_zoom_adjustment() → Calculate zoom in/out steps needed
  - calculate_movement()        → Calculate arrow movements for position
```

---

## Calibration System

### Files

1. **`calibrate_navigation.py`** - Calibration script (21.7 minutes runtime)
   - Auto-switches to WORLD view
   - Zooms out until minimap appears
   - Tests all 40 zoom levels (0-39)
   - Records viewport dimensions and arrow deltas at each level
   - Requires 3 consecutive unchanged viewport areas to confirm max zoom

2. **`zoom_calibration_matrix.json`** - Raw calibration output (40 levels)
   - Contains duplicates where zoom failed
   - **DO NOT USE DIRECTLY** - use cleaned version

3. **`zoom_calibration_matrix_clean.json`** - Cleaned calibration (33 unique levels)
   - Removed 7 duplicate levels: [1, 6, 9, 10, 14, 17, 25]
   - Each level has unique viewport dimensions
   - **THIS IS THE FILE TO USE**

### Calibration Data Structure

```json
{
  "calibration_timestamp": "2025-11-05 09:59:44",
  "calibration_method": "comprehensive_zoom_matrix_cleaned",
  "cleaned_total_levels": 33,
  "removed_duplicate_levels": [1, 6, 9, 10, 14, 17, 25],
  "zoom_levels": [
    {
      "level": 0,
      "viewport": {
        "x": 111, "y": 131,
        "width": 5, "height": 17,
        "area": 85,              // Key for zoom detection
        "area_pct": 0.17,
        "center_x": 113, "center_y": 139,
        "corners": {...}
      },
      "arrow_deltas": {
        "right": {"dx": 4, "dy": 0},    // Minimap pixels moved per arrow press
        "left": {"dx": -7, "dy": 0},    // Note: Asymmetric values
        "down": {"dx": -4, "dy": 7},
        "up": {"dx": -4, "dy": -4}
      }
    },
    // ... 32 more levels
  ]
}
```

---

## Key Concepts

### Zoom Levels

- **Total Unique Levels**: 33 (levels 0-39 with gaps)
- **Available Levels**: [0, 2, 3, 4, 5, 7, 8, 11, 12, 13, 15, 16, 18, 19, 20, 21, 22, 23, 24, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39]
- **Missing Levels**: [1, 6, 9, 10, 14, 17, 25] (duplicates removed)

### Zoom Direction

- **Higher level number = MORE ZOOMED OUT**
  - Level 0: 85 pixels (0.17% of minimap) - Most zoomed IN
  - Level 39: 2059 pixels (4.03% of minimap) - Most zoomed OUT

### Viewport Area

- **Minimap Size**: 226×226 pixels (constant)
- **Viewport Rectangle**: Cyan/bright blue rectangle in minimap
- **Area = width × height** (in pixels)
- **Used for zoom detection** (most reliable metric)

### Arrow Deltas

- **Asymmetric Values**: RIGHT ≠ LEFT, UP ≠ DOWN
  - Example Level 0: RIGHT=+4, LEFT=-7, UP=-4, DOWN=+7
- **Units**: Minimap pixels moved per arrow key press
- **Varies by zoom level**: Higher zoom = larger deltas

---

## MinimapNavigator API

### Initialization

```python
from minimap_navigator import MinimapNavigator

nav = MinimapNavigator()  # Uses zoom_calibration_matrix_clean.json by default
```

### Core Functions

#### 1. Detect Current Zoom Level

```python
viewport_area = 207  # From minimap viewport detection
zoom_level = nav.detect_zoom_level(viewport_area, tolerance=10)
# Returns: 8 (or None if no match)
```

**How it works:**
- Compares viewport_area against all calibration levels
- Finds closest match within tolerance (default 10 pixels)
- Returns zoom level number

#### 2. Calculate Zoom Adjustment

```python
current_area = 207    # Current viewport area (Level 8)
target_area = 1000    # Desired viewport area (Level 30)

adjustment = nav.calculate_zoom_adjustment(current_area, target_area)
# Returns: {
#   'zoom_in': 0,
#   'zoom_out': 22,
#   'current_level': 8,
#   'target_level': 30
# }
```

**Usage:**
```python
for _ in range(adjustment['zoom_out']):
    send_zoom('out')
    time.sleep(1.5)

for _ in range(adjustment['zoom_in']):
    send_zoom('in')
    time.sleep(1.5)
```

#### 3. Calculate Arrow Movements

```python
zoom_level = 15
current_pos = (113, 139)  # Current viewport center in minimap coords
target_pos = (150, 180)   # Target position

movements = nav.calculate_movement(zoom_level, current_pos, target_pos)
# Returns: {
#   'right': 4,
#   'left': 0,
#   'up': 0,
#   'down': 5
# }
```

**Usage:**
```python
for _ in range(movements['right']):
    send_arrow('right')
    time.sleep(1.0)

for _ in range(movements['down']):
    send_arrow('down')
    time.sleep(1.0)
```

#### 4. Get Zoom Data

```python
data = nav.get_zoom_data(zoom_level=15)
# Returns: ZoomLevelData with viewport_area, arrow deltas, etc.
```

#### 5. Find Zoom by Area Percentage

```python
zoom_level = nav.get_zoom_level_by_area(area_pct=0.82)
# Returns: 20 (closest level to 0.82%)
```

---

## Integration with View Detection

### Complete Navigation Example

```python
from find_player import ADBController, Config
from view_detection import ViewDetector, switch_to_view, ViewState
from minimap_navigator import MinimapNavigator
import cv2

# Initialize
config = Config()
adb = ADBController(config)
detector = ViewDetector()
nav = MinimapNavigator()

# 1. Ensure in WORLD view (minimap only visible in world view)
switch_to_view(adb, ViewState.WORLD)

# 2. Get current state
adb.screenshot('temp.png')
frame = cv2.imread('temp.png')
result = detector.detect_from_frame(frame)

if not result.minimap_present:
    print("ERROR: Minimap not visible!")
    exit(1)

# 3. Detect current zoom
current_viewport = result.minimap_viewport
current_area = current_viewport.area
current_zoom = nav.detect_zoom_level(current_area)
print(f"Current zoom: Level {current_zoom} ({current_area} pixels)")

# 4. Adjust zoom to target level
target_zoom = 20  # Target zoom level
target_area = nav.get_zoom_data(target_zoom).viewport_area
adjustment = nav.calculate_zoom_adjustment(current_area, target_area)

print(f"Zooming from Level {adjustment['current_level']} to Level {adjustment['target_level']}")

from send_zoom import send_zoom
import time

for _ in range(adjustment['zoom_out']):
    send_zoom('out')
    time.sleep(1.5)

for _ in range(adjustment['zoom_in']):
    send_zoom('in')
    time.sleep(1.5)

# 5. Navigate to target position
target_pos = (150, 180)  # Target in minimap coordinates

adb.screenshot('temp.png')
frame = cv2.imread('temp.png')
result = detector.detect_from_frame(frame)
current_pos = (result.minimap_viewport.center_x, result.minimap_viewport.center_y)

movements = nav.calculate_movement(target_zoom, current_pos, target_pos)
print(f"Moving: {movements}")

from send_arrow_proper import send_arrow

for _ in range(movements['right']):
    send_arrow('right')
    time.sleep(1.0)

for _ in range(movements['left']):
    send_arrow('left')
    time.sleep(1.0)

for _ in range(movements['down']):
    send_arrow('down')
    time.sleep(1.0)

for _ in range(movements['up']):
    send_arrow('up')
    time.sleep(1.0)

print("Navigation complete!")
```

---

## Important Notes & Gotchas

### DO NOT Re-Calibrate Unless:

1. **Screen resolution changes** (currently 2560×1440)
2. **Game updates** change minimap behavior
3. **Minimap size changes** (currently 226×226)

**Re-calibration takes 21.7 minutes and requires manual supervision.**

### Zoom Behavior

1. **Zoom sometimes fails** - This is why we have duplicate detection
   - Original calibration had 7 failed zoom levels
   - Cleaned calibration removed these duplicates

2. **Zoom requires foreground focus**
   - Uses Windows keyboard input (Shift+Z / Shift+A)
   - See `send_zoom.py` for implementation

3. **Wait times matter**
   - Minimum 1.5s after zoom commands
   - Minimum 1.0s after arrow commands

### Arrow Movement Asymmetry

**Arrow deltas are NOT symmetric:**
- RIGHT=+4 does NOT mean LEFT=-4
- Example Level 0: RIGHT=+4, LEFT=-7

**Why?** The game's viewport movement is asymmetric, possibly due to:
- Edge handling near map boundaries
- Viewport centering behavior
- Game engine quirks

**Solution:** Use separate deltas for each direction (already implemented)

### Coordinate Systems

1. **Minimap Coordinates**: (0, 0) to (226, 226)
   - Used for viewport center positions
   - Used for navigation calculations

2. **Screen Coordinates**: (0, 0) to (2560, 1440)
   - Used for button clicking
   - Minimap location: (2334, 0)

3. **Viewport Coordinates**: Relative to minimap
   - `viewport.x, viewport.y` = top-left corner in minimap
   - `viewport.center_x, viewport.center_y` = center position

---

## Troubleshooting

### "Zoom level X not in calibration data"

**Cause:** Trying to use a removed duplicate level [1, 6, 9, 10, 14, 17, 25]

**Solution:** Use `nav.list_zoom_levels()` to see available levels

### "Viewport area doesn't match any zoom level"

**Cause:** Area outside tolerance range (±10 pixels by default)

**Solutions:**
- Increase tolerance: `detect_zoom_level(area, tolerance=20)`
- Check if minimap is actually visible
- Verify viewport detection is working

### Navigation is inaccurate

**Possible causes:**
1. **Wrong zoom level** - Verify current zoom matches calculation
2. **Viewport shifted during navigation** - Re-detect position between moves
3. **Zoom level changed** - Confirm zoom level before navigation
4. **Edge of map** - Arrow behavior different at boundaries

**Solution:** Re-detect viewport position after each navigation step

---

## Files Reference

### Core System
- `minimap_navigator.py` - Main navigation module (USE THIS)
- `zoom_calibration_matrix_clean.json` - Cleaned calibration data (USE THIS)
- `calibrate_navigation.py` - Calibration script (DO NOT RUN unless recalibrating)

### Dependencies
- `view_detection.py` - WORLD/TOWN detection and minimap viewport detection
- `send_zoom.py` - Zoom in/out commands (Shift+A / Shift+Z)
- `send_arrow_proper.py` - Arrow key navigation (Win32 API)
- `button_matcher.py` - Template matching for buttons (uses TM_CCORR_NORMED)

### Deprecated/Reference
- `zoom_calibration_matrix.json` - Raw calibration (HAS DUPLICATES - DO NOT USE)
- `calibration_log.txt` - Detailed calibration log

---

## Testing

Run the demo to verify system:

```bash
python minimap_navigator.py
```

**Expected output:**
- 33 unique zoom levels
- Sample calibration data for levels 0, 20, 30
- Zoom detection demo (5 test areas)
- Zoom adjustment demo (Level 8 → 30 = 22 steps)
- Movement calculation demo (4 RIGHT + 5 DOWN)

---

## Version History

- **2025-11-05**: Initial calibration and system creation
  - 40 zoom levels calibrated (21.7 minutes)
  - 7 duplicates removed
  - 33 unique zoom levels confirmed
  - Zoom detection and adjustment added
  - Full documentation created

---

## Future Improvements

### Potential Enhancements

1. **Adaptive wait times** - Adjust based on zoom level
2. **Edge detection** - Handle map boundaries specially
3. **Multi-step navigation** - Break long movements into segments
4. **Verification loops** - Re-check position after navigation
5. **Error recovery** - Detect and recover from failed zooms

### DO NOT IMPLEMENT Unless Needed

- **Sub-pixel accuracy** - Current rounding is sufficient
- **Bezier navigation** - Linear arrow movements work fine
- **Predictive zoom** - Current detection is fast enough

---

## Support

**If something breaks:**

1. Check `calibration_log.txt` for calibration details
2. Verify `zoom_calibration_matrix_clean.json` exists and has 33 levels
3. Run `python minimap_navigator.py` to test system
4. Check that minimap is visible (WORLD view only)
5. Verify screen resolution is 2560×1440

**Last resort:** Re-run calibration (21.7 minutes):
```bash
python calibrate_navigation.py
```

Then clean the data:
```python
python -c "
import json
from pathlib import Path

with open('zoom_calibration_matrix.json') as f:
    data = json.load(f)

seen = set()
clean = []
for level in data['zoom_levels']:
    vp = level['viewport']
    key = (vp['width'], vp['height'], vp['area'])
    if key not in seen:
        seen.add(key)
        clean.append(level)

data['zoom_levels'] = clean
data['cleaned_total_levels'] = len(clean)

with open('zoom_calibration_matrix_clean.json', 'w') as f:
    json.dump(data, f, indent=2)
"
```

---

**END OF DOCUMENTATION**
