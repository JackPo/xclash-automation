# Claude Instructions for xclash Project

## CRITICAL: Image Viewing Policy

**NEVER use the Read tool directly to view images (PNG, JPG, etc.)** - this causes system crashes.

**ALWAYS use the Task tool with a general-purpose agent to view images** instead.

### Example - WRONG ❌:
```
Read(screenshot.png)  # This will crash!
```

### Example - CORRECT ✓:
```
Task(
  subagent_type="general-purpose",
  model="haiku",
  description="View screenshot",
  prompt="Please read and examine the file 'screenshot.png' and describe what you see..."
)
```

This applies to ALL image files including:
- Screenshots (.png)
- Debug visualizations (.png)
- Templates (.png)
- Any other image formats (.jpg, .jpeg, etc.)

## Project Context

This is an automation project for Clash of Clans using BlueStacks Android emulator.

Key components:
- ADB path: `C:\Program Files\BlueStacks_nxt\hd-adb.exe`
- Device: `emulator-5554` (auto-detected, may vary)
- Screen resolution: **3840x2160 (4K)** - FINAL resolution for all automation
- Python path: `C:\Users\mail\AppData\Local\Programs\Python\Python312\python.exe`

## BlueStacks Setup

### Initial Setup
Run `setup_bluestacks.py` to configure BlueStacks with the correct resolution:

```bash
python setup_bluestacks.py
```

This script:
- Auto-detects active BlueStacks device (prioritizes emulator-XXXX over IP connections)
- Sets resolution to 4K (3840x2160) using **required two-step process**:
  1. Set to 3088x1440 (intermediate step - REQUIRED, direct 4K doesn't work)
  2. Wait 1 second
  3. Set to 3840x2160 (final 4K resolution)
  4. Wait 1 second
  5. Set density to 560 DPI

**IMPORTANT**: The two-step resolution process is empirically verified as necessary.
Direct setting to 4K does NOT work reliably - the resolution will not stick properly.

All templates and coordinates are calibrated for 3840x2160 resolution.

### Taking Screenshots

Use the centralized `adb_helper.py` utility for all ADB operations:

**Command-line usage:**
```bash
# Take screenshot (creates both full 4K + LLM-friendly scaled version)
python adb_helper.py screenshot output.png

# Check ADB connection and resolution
python adb_helper.py check
```

**Python usage:**
```python
from adb_helper import ADBHelper

adb = ADBHelper()  # Auto-detects and connects to device

# Take screenshot - returns paths to both versions
full_path, llm_path = adb.take_screenshot("screenshot.png")
# Creates: screenshot.png (3840x2160, ~1.2MB)
#          screenshot_llm.png (1920x1080, ~0.5MB)

# Check connection status
if adb.ensure_connected():
    print(f"Connected to {adb.device}")
    print(f"Resolution: {adb.get_screen_size()}")
```

**Screenshot features:**
- Captures full 4K resolution (3840x2160)
- Automatically creates scaled LLM version (1920x1080, 50% size)
- LLM version well under 5MB limit (~0.5MB with optimization)
- Uses `exec-out screencap` for direct capture (no device temp files)
- High-quality LANCZOS resampling for scaling
- Returns paths to both files

**DO NOT** use scattered screenshot methods - always use `adb_helper.py`.

## ⚠️ DEPRECATED APPROACHES

The following approaches have been deprecated due to complexity and unreliable results:

### 1. Map Tiling & Stitching (DEPRECATED)
**Status**: Abandoned as of 2025-11-05

**Affected files**:
- `capture_full_map.py` - Grid-based tile capture
- `stitch_test_3x3.py` - 3×3 stitching test
- `stitch_full_map.py` - Full map stitching
- `map_tiles/` directory - Captured tiles

**Reasons for deprecation**:
- Tile stitching too complex (OpenCV feature matching unreliable)
- Inconsistent overlap detection between tiles
- Template matching produced poor alignment
- Better alternatives needed for map analysis

**Do not use**: Grid-based screenshot tiling, tile stitching, panorama creation

### 2. Castle Size Matching (DEPRECATED)
**Status**: Abandoned as of 2025-11-05

**What's deprecated**:
- Template matching based on exact castle pixel sizes
- Scale-dependent castle detection
- Zoom-level-dependent castle templates
- Any code that matches castles by comparing exact dimensions

**Reasons for deprecation**:
- Too brittle - sensitive to zoom levels
- Required precise zoom calibration
- Failed with slight size variations
- Not robust for real-world gameplay scenarios

**Do not use**: Size-based castle matching, scale-dependent templates

## Minimap Viewport & Zoom Levels

**🚨 CRITICAL CONCEPT - Viewport Area Direction:**

The viewport area is the size of the cyan rectangle visible in the minimap (226×226 pixel minimap region at top-right).

**Viewport area = width × height of cyan rectangle in pixels**

### UNDERSTANDING ZOOM DIRECTION (READ THIS CAREFULLY):

- **LARGE viewport area = MORE of the map is visible = ZOOMED OUT**
- **SMALL viewport area = LESS of the map is visible = ZOOMED IN**

### Examples:

| Viewport Area | Zoom Level | State | Map Visibility |
|---------------|------------|-------|----------------|
| 1334 pixels | Level 33 | ZOOMED OUT | Seeing LOTS of map |
| 420 pixels | Level 20 | ZOOMED IN | Seeing LESS map |
| 12 pixels | Level 5 | VERY ZOOMED IN | Seeing tiny area |

### To Change Zoom:

**Going from 1334 pixels → 420 pixels:**
- Current: 1334 pixels (big viewport, seeing lots of map)
- Target: 420 pixels (smaller viewport, seeing less map)
- **Action: ZOOM IN (Shift+A)** ← Make viewport smaller

**Going from 420 pixels → 1334 pixels:**
- Current: 420 pixels (small viewport, seeing less map)
- Target: 1334 pixels (bigger viewport, seeing lots of map)
- **Action: ZOOM OUT (Shift+Z)** ← Make viewport bigger

### 33 Calibrated Zoom Levels:

The system has 33 distinct zoom levels (0-39, with gaps). Each level corresponds to a specific viewport area in pixels.

**Key levels:**
- Level 5: 12 pixels (very zoomed in)
- Level 20: 420 pixels (optimal for castle detection)
- Level 33: 1403 pixels (zoomed out)

Use `minimap_navigator.py` for zoom detection and navigation:

```python
from minimap_navigator import MinimapNavigator
from view_detection import ViewDetector

nav = MinimapNavigator()
detector = ViewDetector()

# Detect current zoom level
result = detector.detect_from_frame(frame)
area = result.minimap_viewport.area
level = nav.detect_zoom_level(area)

# Get zoom level data
data = nav.get_zoom_data(20)  # Level 20
print(data.viewport_area)  # 420 pixels
```

## Game Controls

### World/Town View Switching (ADB)
Use the `view_detection.py` utility for switching between WORLD and TOWN views.

```python
from view_detection import switch_to_view, ViewState, detect_current_view
from find_player import ADBController, Config

config = Config()
adb = ADBController(config)

# Detect current view
current = detect_current_view(adb)  # Returns CURRENT view (e.g., ViewState.WORLD)

# Switch to WORLD view
switch_to_view(adb, ViewState.WORLD)

# Switch to TOWN view
switch_to_view(adb, ViewState.TOWN)
```

**⚠️ CRITICAL Understanding:**
- The button shows your DESTINATION (where you CAN GO), not your current state
- When IN World view → button displays "TOWN"
- When IN Town view → button displays "WORLD"
- The API handles this inversion automatically
- `ViewState.WORLD` means you ARE CURRENTLY in World view

**How clicking works**:
- Clicks at position (2460, 1315) which is x_frac=0.75, y_frac=0.5 of the button
- This single position toggles between WORLD ↔ TOWN states
- No need to click different sides - same position works for both directions

See `templates/buttons/WORLD_TOWN_DETECTION.md` for full documentation.

### Arrow Keys (Windows API)
Arrow key input uses Windows API (not ADB) with foreground focus required.

Location: `send_arrow_proper.py`

```python
import win32api
import win32con
import win32gui

# Must bring BlueStacks window to foreground
hwnd = win32gui.FindWindow(None, "BlueStacks App Player")
win32gui.SetForegroundWindow(hwnd)

# Send arrow key
VK_LEFT = 0x25   # Left arrow
VK_UP = 0x26     # Up arrow
VK_RIGHT = 0x27  # Right arrow
VK_DOWN = 0x28   # Down arrow

# Press and release
win32api.keybd_event(VK_RIGHT, 0, 0, 0)  # Press
win32api.keybd_event(VK_RIGHT, 0, win32con.KEYEVENT_KEYUP, 0)  # Release
```

**Key points**:
- BlueStacks window MUST have foreground focus
- Cannot send arrow keys to background window
- ADB input commands do NOT work for arrow keys in this game

### Zoom In/Out (Windows API)
Zoom uses Windows keyboard input (Shift+A/Shift+Z) with foreground focus.

Location: `send_zoom.py`

```python
# Zoom in: Shift+A
python send_zoom.py in

# Zoom out: Shift+Z
python send_zoom.py out
```

**Key points**:
- Shift+A = Zoom IN
- Shift+Z = Zoom OUT
- Requires foreground focus like arrow keys
- ADB input does NOT work for zoom

### Clicking/Tapping (ADB)
For clicking UI elements, use the centralized `adb_helper.py`:

```python
from adb_helper import ADBHelper

adb = ADBHelper()  # Auto-connects to device

# Click at specific coordinates
adb.tap(x, y)

# Swipe (for dragging)
adb.swipe(x1, y1, x2, y2, duration=300)
```

**Key points**:
- ADB tap works for clicking buttons, UI elements
- No foreground focus required
- Coordinates are absolute (3840x2160 for 4K screen)
- For World/Town toggle: use `view_detection.py` utility instead of raw tapping
- Always use `adb_helper.py` for ADB operations

### Summary Table

| Control | Method | Focus Required | Implementation |
|---------|--------|----------------|----------------|
| Screenshots | ADB exec-out | No | `adb_helper.py screenshot <path>` |
| World/Town Toggle | ADB tap | No | `view_detection.py` |
| UI Clicking | ADB tap | No | `adb_helper.py` → `adb.tap(x, y)` |
| Arrow Keys | Win32 API | Yes | `send_arrow_proper.py` |
| Zoom In/Out | Win32 API (Shift+A/Z) | Yes | `send_zoom.py` |
| Map Dragging | ADB swipe | No | `adb_helper.py` → `adb.swipe(...)` |
