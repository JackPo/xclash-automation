# Claude Instructions for xclash Project

## ⚠️ CRITICAL: Image Analysis Rules

**NEVER read or analyze screenshot images directly.** Always use Gemini via `detect_object.py`:

```bash
# Detect objects in screenshots
python detect_object.py screenshot.png "description of what to find"

# Examples:
python detect_object.py check.png "the World button in lower right"
python detect_object.py check.png "the back button with arrow icon"
```

**Why**: Claude's image analysis is unreliable for game UI detection. Gemini provides accurate bounding boxes and coordinates.

**Template extraction workflow**:
1. Take screenshot with `WindowsScreenshotHelper` (NOT adb_helper)
2. Use `detect_object.py` to find the element and get coordinates
3. Extract template using the returned bounding box
4. Save to `templates/ground_truth/`

## ⚠️ CRITICAL: Screenshot Rules

**ALL screenshot operations MUST use `WindowsScreenshotHelper`** - NOT ADB screenshots.

```python
from utils.windows_screenshot_helper import WindowsScreenshotHelper

win = WindowsScreenshotHelper()
frame = win.get_screenshot_cv2()  # Returns BGR numpy array
```

**Why**:
1. Templates are captured with Windows screenshots. ADB screenshots have different pixel values and will NOT match templates (scores will be ~0.07 instead of 0.00).
2. ADB screenshots are SLOW - performance issues with real-time detection.

**Rules**:
- Detection/matching: Use `WindowsScreenshotHelper`
- Template capture: Use `WindowsScreenshotHelper`
- Actions (tap, swipe): Use `ADBHelper`

**NEVER use `adb.take_screenshot()` in production flows.** No fallbacks. If WindowsScreenshotHelper fails, let it error.

## Project Context

This is an automation project for Clash of Clans using BlueStacks Android emulator.

Key components:
- ADB path: `C:\Program Files\BlueStacks_nxt\hd-adb.exe`
- Device: `emulator-5554` (auto-detected, may vary)
- Screen resolution: **3840x2160 (4K)** - FINAL resolution for all automation
- Python path: `C:\Users\mail\AppData\Local\Programs\Python\Python312\python.exe`
- Tesseract OCR: `C:\Program Files\Tesseract-OCR\tesseract.exe`

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

**For template matching and detection - use Windows screenshot:**
```python
from utils.windows_screenshot_helper import WindowsScreenshotHelper

win = WindowsScreenshotHelper()
frame = win.get_screenshot_cv2()  # BGR numpy array, 3840x2160
```

**For ADB operations (tap, swipe, etc):**
```python
from utils.adb_helper import ADBHelper

adb = ADBHelper()
adb.tap(x, y)
adb.swipe(x1, y1, x2, y2, duration=300)
```

## Template Storage

**CRITICAL: All templates MUST be saved to `templates/ground_truth/` directory.**

**CRITICAL: All templates MUST be captured using `WindowsScreenshotHelper`.**

### Template Naming Convention
- Use descriptive names with resolution suffix: `<element_name>_4k.png`
- Examples:
  - `world_button_4k.png` - World view button (shows map icon, visible when in TOWN)
  - `town_button_4k.png` - Town view button (shows castle icon, visible when in WORLD)
  - `town_button_zoomed_out_4k.png` - Town button when zoomed out (shows map with "Town" text)

### Current Templates
Located in `templates/ground_truth/`:

**View Detection Templates (fixed position 3600,1920 size 240x240):**
- `world_button_4k.png` - World button (map icon) → means currently in TOWN view
- `town_button_4k.png` - Town button (castle icon) → means currently in WORLD view
- `town_button_zoomed_out_4k.png` - Town button zoomed out → means currently in WORLD view

**Icon Detection Templates (fixed positions):**
- `handshake_iter2.png` - Alliance/handshake icon (position: 3088,1780, size: 155x127, threshold: 0.04)
- `treasure_map_4k.png` - Bouncing scroll treasure map (position: 2096,1540, size: 158x162, threshold: 0.05)
- `harvest_box_4k.png` - Harvest box notification (position: 2100,1540, size: 154x157, threshold: 0.1)
- `corn_harvest_bubble_4k.png` - Corn harvest bubble (position: 1884,1260, size: 99x74, threshold: 0.05)
- `gold_coin_tight_4k.png` - Gold coin bubble, tight crop (position: 1369,800, size: 53x43, threshold: 0.06)
- `iron_bar_tight_4k.png` - Iron bar bubble, tight crop (position: 1617,351, size: 46x32, threshold: 0.06)
- `gem_tight_4k.png` - Gem bubble, tight crop (position: 1378,652, size: 54x51, threshold: 0.06)
- `stamina_number_4k.png` - Stamina number region for OCR (position: 69,203, size: 96x60)

**Dialog Templates (search-based):**
- `harvest_surprise_box_4k.png` - Surprise box dialog (791x253, moves vertically)
- `open_button_4k.png` - Open button in dialogs (242x99)
- `back_button_4k.png` - Dark back button (142x136)
- `back_button_light_4k.png` - Light back button (142x136)

**When extracting new templates:**
1. Use `WindowsScreenshotHelper` to capture screenshot
2. Crop the template region
3. Save to `templates/ground_truth/`
4. Use descriptive name with `_4k` suffix
5. Document coordinates and size in this file

## View State Detection & Navigation

Use `utils/view_state_detector.py` for all view detection and navigation:

```python
from utils.view_state_detector import detect_view, go_to_town, go_to_world, ViewState
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.adb_helper import ADBHelper

# Detection (uses Windows screenshot internally)
win = WindowsScreenshotHelper()
frame = win.get_screenshot_cv2()
state, score = detect_view(frame)  # Returns (ViewState.TOWN/WORLD/CHAT/UNKNOWN, score)

# Navigation (uses Windows screenshot for detection, ADB for clicking)
adb = ADBHelper()
go_to_town(adb, debug=True)   # Navigate to TOWN from anywhere
go_to_world(adb, debug=True)  # Navigate to WORLD from anywhere
```

**View Detection Logic:**
- Check corner (3600, 1920) 240x240 for button templates
- `world_button_4k.png` matches → TOWN view (World button visible means you're in Town)
- `town_button_4k.png` matches → WORLD view
- `town_button_zoomed_out_4k.png` matches → WORLD view
- None match → check back button → CHAT view
- Nothing matches → UNKNOWN

**Navigation Logic:**
- TOWN → WORLD: click toggle button (3720, 2040)
- WORLD → TOWN: click toggle button (3720, 2040)
- CHAT → exit: click back button (1407, 2055), then re-detect

## ⚠️ DEPRECATED APPROACHES

The following approaches have been deprecated due to complexity and unreliable results:

### 1. Map Tiling & Stitching (DEPRECATED)
**Status**: Abandoned as of 2025-11-05

**Do not use**: Grid-based screenshot tiling, tile stitching, panorama creation

### 2. Castle Size Matching (DEPRECATED)
**Status**: Abandoned as of 2025-11-05

**Do not use**: Size-based castle matching, scale-dependent templates

### 3. ADB Screenshots for Template Matching (DEPRECATED)
**Status**: Abandoned as of 2025-11-27

**Do not use**: `adb_helper.take_screenshot()` for template matching or detection.
ADB screenshots have different pixel values than Windows screenshots, causing template matching to fail.

**Always use**: `WindowsScreenshotHelper.get_screenshot_cv2()` for all detection/matching.

### 4. Old View Detection Files (DEPRECATED)
**Status**: Removed as of 2025-11-27

**Removed files**:
- `view_detection.py` (moved to deprecated/)
- `utils/view_button_matcher.py` (deleted)
- `utils/world_button_matcher.py` (deleted)
- `utils/town_button_matcher.py` (deleted)

**Use instead**: `utils/view_state_detector.py`

## Game Controls

### World/Town View Switching
Use `utils/view_state_detector.py`:

```python
from utils.view_state_detector import go_to_town, go_to_world
from utils.adb_helper import ADBHelper

adb = ADBHelper()
go_to_town(adb)   # Navigate to town from anywhere
go_to_world(adb)  # Navigate to world from anywhere
```

### Arrow Keys (Windows API)
Arrow key input uses Windows API (not ADB) with foreground focus required.

Location: `send_arrow_proper.py`

### Zoom In/Out (Windows API)
Zoom uses Windows keyboard input (Shift+A/Shift+Z) with foreground focus.

Location: `send_zoom.py`

- Shift+A = Zoom IN
- Shift+Z = Zoom OUT

### Clicking/Tapping (ADB)
```python
from utils.adb_helper import ADBHelper

adb = ADBHelper()
adb.tap(x, y)
adb.swipe(x1, y1, x2, y2, duration=300)
```

### Summary Table

| Control | Method | Focus Required | Implementation |
|---------|--------|----------------|----------------|
| Screenshots (detection) | Windows API | No | `WindowsScreenshotHelper.get_screenshot_cv2()` |
| World/Town Toggle | ADB tap | No | `view_state_detector.go_to_town/world()` |
| UI Clicking | ADB tap | No | `adb_helper.tap(x, y)` |
| Arrow Keys | Win32 API | Yes | `send_arrow_proper.py` |
| Zoom In/Out | Win32 API (Shift+A/Z) | Yes | `send_zoom.py` |
| Map Dragging | ADB swipe | No | `adb_helper.swipe(...)` |

## Stamina Extraction

The daemon extracts stamina using Tesseract OCR from the top-left UI region.

```python
from utils.stamina_extractor import StaminaExtractor
from utils.windows_screenshot_helper import WindowsScreenshotHelper

win = WindowsScreenshotHelper()
frame = win.get_screenshot_cv2()

extractor = StaminaExtractor()
stamina = extractor.extract_stamina(frame)  # Returns int or None
```

**Configuration:**
- Coordinates (4K): (69, 203) size 96x60
- Tesseract config: `--psm 7 -c tessedit_char_whitelist=0123456789`
- No preprocessing needed - works directly on raw crop

**Tesseract Installation:**
- Download from: https://github.com/UB-Mannheim/tesseract/wiki
- Install to: `C:\Program Files\Tesseract-OCR\`
- Required for stamina extraction in daemon

## Icon Daemon

The icon daemon (`scripts/icon_daemon.py`) runs continuously, detecting clickable icons and triggering flows.

### Running the Daemon

```bash
# Normal mode
python scripts/icon_daemon.py

# Debug mode - logs all scores
python scripts/icon_daemon.py --debug

# Custom interval (default 3 seconds)
python scripts/icon_daemon.py --interval 5
```

### Idle Recovery (5 minutes)

When user is idle for 5+ minutes, daemon automatically:
1. Detects current view state
2. If not in TOWN, navigates to TOWN using `go_to_town()`
3. Handles CHAT/WORLD/UNKNOWN states automatically

### Currently Detected Icons

| Icon | Matcher | Threshold | Click Position | Flow |
|------|---------|-----------|----------------|------|
| Handshake | `handshake_icon_matcher.py` | 0.04 | (3165, 1843) | `handshake_flow` |
| Treasure Map | `treasure_map_matcher.py` | 0.05 | (2175, 1621) | `treasure_map_flow` (Step 1 working, Step 2+ needs testing) |
| Harvest Box | `harvest_box_matcher.py` | 0.1 | (2177, 1618) | `harvest_box_flow` ✓ |
| Corn | `corn_harvest_matcher.py` | 0.05 | (1932, 1297) | `corn_harvest_flow` |
| Gold | `gold_coin_matcher.py` | 0.06 | (1395, 835) | `gold_coin_flow` |
| Iron | `iron_bar_matcher.py` | 0.08 | (1639, 377) | `iron_bar_flow` |
| Gem | `gem_matcher.py` | 0.06 | (1405, 696) | `gem_flow` |

### Matcher Thresholds

Thresholds are defined in each matcher file (single source of truth):
- `TM_SQDIFF_NORMED`: Lower score = better match. Threshold is maximum allowed score.
- Typical thresholds: 0.04-0.06 for icons, 0.1 for larger templates
- Edit thresholds in `utils/*_matcher.py` files, NOT in `icon_daemon.py`
- Scores should be ~0.00 for perfect matches (captured with Windows screenshot)
