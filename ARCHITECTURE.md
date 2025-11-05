# XClash Automation System - Complete Architecture

## Table of Contents
1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [Data Flow](#data-flow)
4. [Core Modules](#core-modules)
5. [Calibration System](#calibration-system)
6. [Navigation System](#navigation-system)
7. [Castle Search System](#castle-search-system)
8. [Complete Workflow](#complete-workflow)
9. [File Structure](#file-structure)
10. [Dependencies](#dependencies)

---

## System Overview

**Purpose**: Automated castle searching in Clash of Clans using minimap-based navigation and template matching.

**High-Level Flow**:
```
User Input (level range, name)
    ↓
View Detection & Switch to WORLD
    ↓
Zoom to Ideal Level
    ↓
Navigate to Start Position (0, 0)
    ↓
Zigzag Search Pattern:
  - Detect castles in viewport
  - Filter by level
  - Click each castle
  - OCR name
  - Compare with target
  - Zoom back to saved position
  - Move to next viewport
    ↓
Return: Castle Found / Not Found
```

---

## Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     USER INTERFACE                          │
│  find_castle_by_level.py (level_range, target_name)        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   ORCHESTRATION LAYER                       │
│  - Search Strategy (zigzag pattern)                        │
│  - State Management (current position, castles checked)    │
│  - Error Recovery (retry logic, position restoration)      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────┬──────────────┬──────────────┬───────────────┐
│   VIEW       │  NAVIGATION  │   CASTLE     │    OCR        │
│  DETECTION   │   SYSTEM     │  DETECTION   │   SYSTEM      │
└──────────────┴──────────────┴──────────────┴───────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   CONTROL LAYER                             │
│  ADB (screenshots, taps) + Win32 (keyboard)                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                BLUESTACKS EMULATOR                          │
│             Clash of Clans (2560×1440)                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Phase 1: Initialization & Setup

```
1. User provides search criteria
   ↓
2. Load calibration data (zoom_calibration_matrix_clean.json)
   ↓
3. Initialize components:
   - ADBController (screenshots, taps)
   - ViewDetector (WORLD/TOWN detection)
   - MinimapNavigator (movement calculations)
   - CastleDetector (template matching)
   - CastleNameReader (OCR)
   ↓
4. Detect current state:
   - Take screenshot
   - Detect view (WORLD/TOWN)
   - Detect minimap viewport (if WORLD)
   - Detect current zoom level
```

### Phase 2: Navigation to Start Position

```
5. Switch to WORLD view (if needed)
   - Detect button via template matching
   - Click button if in TOWN
   - Wait for transition
   - Verify WORLD view
   ↓
6. Adjust to ideal zoom level
   - Detect current zoom (from viewport area)
   - Calculate zoom steps needed
   - Execute zoom in/out commands
   - Verify zoom level reached
   ↓
7. Navigate to top-left corner
   - Get current viewport center (x, y)
   - Calculate arrows to reach (0, 0)
   - Execute arrow commands
   - Verify position reached
```

### Phase 3: Castle Search Loop

```
8. For each viewport in zigzag pattern:

   a. Capture & Analyze Viewport
      - Screenshot current view
      - Detect viewport position from minimap
      - Find all castles in screenshot
      - Filter castles by level range

   b. For each matching castle:

      i. Save State
         - Record viewport center (x, y)
         - Record zoom level

      ii. Inspect Castle
         - Click castle on screen
         - Wait for zoom-in animation (2s)
         - Screenshot zoomed view
         - OCR castle name from screenshot
         - Compare name with target (case-insensitive)

      iii. Process Result
         IF name matches:
            - RETURN success with castle info
         ELSE:
            - Zoom out to world view
            - Navigate back to saved (x, y)
            - Verify viewport restored
            - Continue to next castle

   c. Move to Next Viewport
      - Calculate movement (fixed arrow count)
      - Execute arrows (right/down/left per zigzag)
      - Wait for stabilization
      - Loop back to step 8a

9. Map exhausted → RETURN not found
```

---

## Core Modules

### 1. View Detection System (`view_detection.py`)

**Purpose**: Detect and switch between WORLD and TOWN views, detect minimap viewport.

**Key Classes:**
- `ViewDetector`: Detects current view state and minimap viewport
- `ViewSwitcher`: Handles view switching via button clicks

**Critical Functions:**

```python
detect_current_view(adb) → ViewState
# Returns: WORLD, TOWN, or UNKNOWN
# Uses button template matching (TM_CCORR_NORMED algorithm)

switch_to_view(adb, target_state) → bool
# Switches to target view, retries up to 4 times

detect_from_frame(frame) → ViewDetectionResult
# Returns: state, confidence, minimap_present, minimap_viewport
```

**Minimap Viewport Detection:**
```python
MinimapViewport:
  - x, y: Top-left corner in minimap coords (0-226)
  - width, height: Viewport dimensions
  - area: width × height (KEY METRIC for zoom detection)
  - center_x, center_y: Center position
  - top_left, top_right, bottom_left, bottom_right: Corner coords
```

**Button Template Matching:**
- Uses 3 templates: `world_button.png`, `town_button.png`, `town_button_zoomed_out.png`
- Algorithm: `cv2.TM_CCORR_NORMED` (98%+ accuracy)
- **CRITICAL**: Button shows DESTINATION, not current state
  - Button shows "WORLD" → Currently in TOWN
  - Button shows "TOWN" → Currently in WORLD
- Detection automatically inverts label to return CURRENT state

**Viewport Detection Method:**
- Color detection: Cyan HSV(22-26, 180-230, 160-240)
- Finds cyan rectangle in minimap (226×226 at screen pos 2334, 0)
- Returns bounding box and center

**Files:**
- `view_detection.py` - Main module
- `button_matcher.py` - Template matching utilities
- `templates/ground_truth/` - Button templates

---

### 2. Navigation System (`minimap_navigator.py`)

**Purpose**: Calculate movements and zoom adjustments using calibrated data.

**Key Classes:**
- `CalibrationCleaner`: Loads and processes calibration data
- `MinimapNavigator`: Main navigation calculator
- `ZoomLevelData`: Data structure for zoom level info

**Critical Functions:**

```python
detect_zoom_level(viewport_area, tolerance=10) → int
# Input: Viewport area in pixels
# Output: Zoom level (0-39, with gaps)
# Example: area=207 → level=8

calculate_zoom_adjustment(current_area, target_area) → dict
# Returns: {'zoom_in': N, 'zoom_out': M, 'current_level': X, 'target_level': Y}
# Example: current=207, target=1000 → {'zoom_out': 22, ...}

calculate_movement(zoom_level, current_pos, target_pos) → dict
# Input: Positions in minimap coords (0-226)
# Returns: {'right': N, 'left': M, 'up': P, 'down': Q}
# Example: (113,139) → (150,180) at zoom 15 = {right: 4, down: 5}

get_zoom_data(zoom_level) → ZoomLevelData
# Returns calibration data for specific zoom level
# Includes viewport_area and arrow deltas (right_dx, left_dx, up_dy, down_dy)
```

**Zoom Level Details:**
- **Total Unique Levels**: 33 (from 0-39 with gaps)
- **Missing Levels**: [1, 6, 9, 10, 14, 17, 25] (removed duplicates)
- **Range**:
  - Level 0: 85 pixels (0.17%) - Most zoomed IN
  - Level 39: 2059 pixels (4.03%) - Most zoomed OUT
- **Higher level = MORE zoomed OUT**

**Arrow Deltas (CRITICAL - Asymmetric):**
```python
# Example Level 0:
right_dx = +4   # Move RIGHT 4 pixels on minimap
left_dx = -7    # Move LEFT 7 pixels (NOT -4!)
up_dy = -4      # Move UP 4 pixels
down_dy = +7    # Move DOWN 7 pixels (NOT +4!)

# Asymmetry is INTENTIONAL - game behavior is asymmetric
```

**Files:**
- `minimap_navigator.py` - Main module
- `zoom_calibration_matrix_clean.json` - Calibration data (33 levels)
- `MINIMAP_NAVIGATION_SYSTEM.md` - Detailed documentation

---

### 3. Calibration System (`calibrate_navigation.py`)

**Purpose**: One-time calibration to map zoom levels and arrow movements.

**Process** (21.7 minutes):
1. Auto-switch to WORLD view
2. Zoom out until minimap appears
3. For each zoom level (0-39):
   - Record viewport dimensions and area
   - Test RIGHT arrow → measure dx, dy
   - Test LEFT arrow → measure dx, dy
   - Test DOWN arrow → measure dx, dy
   - Test UP arrow → measure dx, dy
   - Zoom out for next level
4. Detect max zoom (3 consecutive unchanged areas)
5. Save to `zoom_calibration_matrix.json`

**Output Data:**
```json
{
  "level": 0,
  "viewport": {
    "width": 5, "height": 17, "area": 85,
    "center_x": 113, "center_y": 139,
    "corners": {...}
  },
  "arrow_deltas": {
    "right": {"dx": 4, "dy": 0},
    "left": {"dx": -7, "dy": 0},
    "down": {"dx": -4, "dy": 7},
    "up": {"dx": -4, "dy": -4}
  }
}
```

**Data Cleaning:**
- Raw output: 40 levels (some duplicates from failed zooms)
- Cleaned output: 33 unique levels
- Removed: [1, 6, 9, 10, 14, 17, 25]

**Files:**
- `calibrate_navigation.py` - Calibration script
- `zoom_calibration_matrix.json` - Raw output (DO NOT USE)
- `zoom_calibration_matrix_clean.json` - Cleaned data (USE THIS)
- `calibration_log.txt` - Detailed execution log

---

### 4. Control Layer

#### ADB Control (`find_player.py`)

**Purpose**: Communication with BlueStacks emulator.

```python
class ADBController:
    def screenshot(file_path) → None
    # Captures screenshot via ADB screencap

    def tap(x, y) → None
    # Clicks at screen coordinates (0-2560, 0-1440)

    def swipe(x1, y1, x2, y2, duration_ms) → None
    # Swipe gesture (unused in current system)
```

**Configuration:**
- ADB Path: `C:\Program Files\BlueStacks_nxt\hd-adb.exe`
- Device: `emulator-5554`
- Screen: 2560×1440 (constant)

#### Keyboard Control (Win32 API)

**Arrow Keys** (`send_arrow_proper.py`):
```python
send_arrow(direction: 'left'|'right'|'up'|'down') → None
# Uses Win32 keybd_event
# REQUIRES foreground focus
# VK codes: LEFT=0x25, UP=0x26, RIGHT=0x27, DOWN=0x28
```

**Zoom Keys** (`send_zoom.py`):
```python
send_zoom(direction: 'in'|'out') → None
# Uses Win32 keybd_event
# 'in' = Shift+A
# 'out' = Shift+Z
# REQUIRES foreground focus
```

**CRITICAL**: Window must have foreground focus for keyboard input.

---

### 5. Castle Detection System (`castle_scanner.py`)

**Purpose**: Detect castles in screenshots and read castle names.

**Key Classes:**

```python
class CastleDetector:
    """Detect castles using template matching."""

    def __init__(self, template_dir, ideal_zoom_level):
        # Load castle templates
        # Try existing templates first
        # Create new templates at ideal zoom if needed

    def detect_castles(self, frame, level_range) → List[CastleMatch]:
        # Input: Screenshot frame, tuple(min_level, max_level)
        # Returns: List of detected castles with positions and levels
        # Uses cv2.matchTemplate with threshold
        # Filters results by level range

    def _match_template(self, frame, template) → List[Tuple[x, y, confidence]]
        # Template matching implementation
        # Returns all matches above threshold

    def _extract_level(self, castle_crop) → int
        # Extract castle level from castle image
        # Uses OCR or template matching on level badge
```

**Castle Match Structure:**
```python
@dataclass
class CastleMatch:
    screen_x: int           # Click position on main screen
    screen_y: int           # Click position on main screen
    minimap_x: int          # Position in minimap coordinates
    minimap_y: int          # Position in minimap coordinates
    level: int              # Castle level (e.g., 20)
    confidence: float       # Detection confidence (0.0-1.0)
```

**Template Management:**
- **Existing Templates**: `castle_*.png` from previous extraction
- **New Templates**: Extract at ideal zoom level if existing don't work
- **Multi-Scale Matching**: If zoom differs from template zoom

```python
class CastleNameReader:
    """OCR for reading castle names after zoom-in."""

    def read_castle_name(self, frame) → Optional[str]:
        # Input: Screenshot of zoomed-in castle view
        # Output: Castle name string or None if failed
        # Uses pytesseract or similar OCR
        # Preprocessing: grayscale, threshold, denoise

    def _locate_name_region(self, frame) → Tuple[x, y, w, h]
        # Find where castle name appears in zoomed view
        # Returns bounding box for OCR

    def _preprocess_for_ocr(self, crop) → np.ndarray
        # Image preprocessing for better OCR
        # Grayscale, threshold, denoise, resize
```

**Castle Name Detection:**
- After clicking castle, game zooms to castle view
- Name appears in consistent location (need to locate)
- OCR reads name text
- Case-insensitive comparison with target

**Files:**
- `castle_scanner.py` - Detection and OCR module
- `castle_*.png` - Castle templates (existing)
- OCR engine: pytesseract or similar

---

### 6. Search Orchestration (`find_castle_by_level.py`)

**Purpose**: Main search logic coordinating all systems.

**Main Function:**

```python
def find_castle(
    level_min: int,
    level_max: int,
    target_name: str,
    ideal_zoom_level: int = 20,  # From documentation
    fixed_arrow_count: int = 5,   # Arrows per viewport movement
    max_viewports: int = 1000     # Safety limit
) → SearchResult:
    """
    Search for castle with level in range and matching name.

    Args:
        level_min: Minimum castle level (e.g., 20)
        level_max: Maximum castle level (e.g., 21)
        target_name: Castle owner name (case-insensitive)
        ideal_zoom_level: Zoom level for search
        fixed_arrow_count: Arrows to move per viewport
        max_viewports: Maximum viewports to scan

    Returns:
        SearchResult with found status and details
    """
```

**Search Algorithm:**

```python
1. Initialize all systems
   - Load calibration data
   - Initialize detector, navigator, OCR

2. Setup initial state
   - Switch to WORLD view
   - Zoom to ideal_zoom_level
   - Navigate to minimap (0, 0) - top-left

3. Zigzag search:
   direction = 'right'  # Start moving right
   row = 0
   viewports_scanned = 0

   while viewports_scanned < max_viewports:
       # Capture viewport
       screenshot = adb.screenshot()
       viewport = detector.detect_viewport(screenshot)

       # Find castles
       castles = castle_detector.detect_castles(
           screenshot,
           level_range=(level_min, level_max)
       )

       # Check each castle
       for castle in castles:
           # Save position
           saved_viewport = viewport.center
           saved_zoom = nav.detect_zoom_level(viewport.area)

           # Click castle
           adb.tap(castle.screen_x, castle.screen_y)
           time.sleep(2.0)  # Wait for zoom animation

           # Read name
           zoomed_screenshot = adb.screenshot()
           name = ocr.read_castle_name(zoomed_screenshot)

           # Check match
           if name and name.lower() == target_name.lower():
               return SearchResult(
                   found=True,
                   castle_name=name,
                   level=castle.level,
                   viewport_position=saved_viewport,
                   clicks_attempted=clicks_so_far,
                   viewports_scanned=viewports_scanned
               )

           # Zoom back
           zoom_out_to_world()
           navigate_to_position(saved_viewport)
           verify_viewport_restored()

       # Move to next viewport
       if direction == 'right':
           for _ in range(fixed_arrow_count):
               send_arrow('right')

           # Check if at right edge (minimap x > threshold)
           if viewport.center_x > 200:  # Near right edge
               # Move down
               for _ in range(fixed_arrow_count):
                   send_arrow('down')
               direction = 'left'  # Switch direction
               row += 1

       else:  # direction == 'left'
           for _ in range(fixed_arrow_count):
               send_arrow('left')

           # Check if at left edge
           if viewport.center_x < 26:  # Near left edge
               # Move down
               for _ in range(fixed_arrow_count):
                   send_arrow('down')
               direction = 'right'  # Switch direction
               row += 1

       viewports_scanned += 1
       time.sleep(1.0)  # Viewport stabilization

   # Not found
   return SearchResult(
       found=False,
       clicks_attempted=total_clicks,
       viewports_scanned=viewports_scanned
   )
```

**Zigzag Pattern Visualization:**
```
(0,0) → → → → → → → → → → → (226,Y)
                            ↓
(0,Y) ← ← ← ← ← ← ← ← ← ← ←
↓
→ → → → → → → → → → → → → →
                            ↓
← ← ← ← ← ← ← ← ← ← ← ← ← ←
...
```

**Position Restoration:**
```python
def restore_viewport_position(
    adb, nav, saved_center, saved_zoom
) → bool:
    """Restore exact viewport position after castle inspection."""

    # Zoom out to world view
    while True:
        screenshot = adb.screenshot()
        result = detector.detect_from_frame(screenshot)
        if result.minimap_present:
            break
        send_zoom('out')
        time.sleep(1.5)

    # Get current position
    current_center = result.minimap_viewport.center

    # Navigate back to saved position
    movements = nav.calculate_movement(
        saved_zoom,
        (current_center.x, current_center.y),
        saved_center
    )

    # Execute movements
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

    # Verify restoration
    screenshot = adb.screenshot()
    result = detector.detect_from_frame(screenshot)
    current_after = result.minimap_viewport.center

    distance = ((current_after.x - saved_center[0])**2 +
                (current_after.y - saved_center[1])**2)**0.5

    return distance < 10  # Within 10 pixels
```

**Search Result:**
```python
@dataclass
class SearchResult:
    found: bool                              # Castle found?
    castle_name: Optional[str]               # Name if found
    level: Optional[int]                     # Level if found
    viewport_position: Optional[Tuple[int, int]]  # Where found
    clicks_attempted: int                    # Total castles clicked
    viewports_scanned: int                   # Total viewports checked
    time_elapsed: float                      # Search duration
    error_message: Optional[str]             # Error if failed
```

**Files:**
- `find_castle_by_level.py` - Main search script
- Integrates all other modules

---

## Complete Workflow

### End-to-End Example

**User Command:**
```bash
python find_castle_by_level.py --level-min 20 --level-max 21 --name "yagamilight"
```

**Execution Flow:**

```
[1] INITIALIZATION (5 seconds)
    - Load zoom_calibration_matrix_clean.json
    - Initialize ADB, detector, navigator, OCR
    - Bring BlueStacks to foreground

[2] VIEW SETUP (3 seconds)
    - Screenshot current view
    - Detect view state (TOWN detected)
    - Click WORLD button
    - Wait for transition
    - Verify WORLD view active
    - Verify minimap present

[3] ZOOM SETUP (10 seconds)
    - Detect current viewport area: 85 pixels
    - Identify current zoom: Level 0
    - Calculate adjustment: Need 20 zoom-outs
    - Execute: send_zoom('out') × 20
    - Verify target zoom reached: Level 20

[4] POSITION SETUP (5 seconds)
    - Get current position: (113, 139)
    - Calculate movement to (0, 0): 16 LEFT, 35 UP
    - Execute arrow movements
    - Verify position: (3, 2) ✓

[5] SEARCH LOOP (Variable time)

    Viewport #1 (0, 0):
      - Screenshot
      - Detect castles: Found 3 castles
      - Filter by level 20-21: 1 castle matches
      - Save position: (3, 2), zoom 20
      - Click castle at (1200, 800)
      - Wait 2s for zoom
      - OCR name: "PlayerOne"
      - No match, continue
      - Zoom out to world
      - Navigate back to (3, 2)
      - Move right 5 arrows

    Viewport #2 (45, 2):
      - Screenshot
      - Detect castles: Found 4 castles
      - Filter by level 20-21: 2 castles match

      Castle 1:
        - Click, OCR: "SomePlayer"
        - No match, continue

      Castle 2:
        - Click, OCR: "YagamiLight"  ← MATCH!
        - Return SUCCESS

[6] RESULT
    SearchResult(
        found=True,
        castle_name="YagamiLight",
        level=20,
        viewport_position=(45, 2),
        clicks_attempted=3,
        viewports_scanned=2,
        time_elapsed=45.2
    )
```

---

## File Structure

```
xclash/
├── ARCHITECTURE.md                    ← This file
├── MINIMAP_NAVIGATION_SYSTEM.md       ← Navigation docs
├── README.md                          ← Project overview
│
├── Core Modules:
│   ├── find_player.py                 ← ADB control
│   ├── view_detection.py              ← View/minimap detection
│   ├── button_matcher.py              ← Template matching
│   ├── minimap_navigator.py           ← Navigation calculations
│   ├── send_arrow_proper.py           ← Arrow key control
│   ├── send_zoom.py                   ← Zoom control
│   ├── castle_scanner.py              ← Castle detection & OCR
│   └── find_castle_by_level.py        ← Main search script
│
├── Calibration:
│   ├── calibrate_navigation.py        ← Calibration script
│   ├── zoom_calibration_matrix.json   ← Raw data (40 levels)
│   ├── zoom_calibration_matrix_clean.json  ← Clean data (33 levels)
│   └── calibration_log.txt            ← Calibration log
│
├── Templates:
│   ├── templates/ground_truth/
│   │   ├── world_button.png
│   │   ├── town_button.png
│   │   └── town_button_zoomed_out.png
│   └── templates/castles/
│       ├── castle_20.png
│       ├── castle_21.png
│       └── ...
│
└── Configuration:
    └── config.json                    ← System config (if needed)
```

---

## Dependencies

### Python Packages
```python
# Core
opencv-python (cv2)          # Image processing, template matching
numpy                        # Array operations
pytesseract                  # OCR (optional, for name reading)

# Windows API
pywin32 (win32gui, win32api, win32con)  # Keyboard input, window control

# Utilities
pathlib                      # File path handling
dataclasses                  # Data structures
json                         # Config and calibration data
time                         # Wait times and timing
```

### External Tools
```
ADB: C:\Program Files\BlueStacks_nxt\hd-adb.exe
BlueStacks: Android emulator
Clash of Clans: Game client
```

### System Requirements
- **OS**: Windows (for Win32 API)
- **Screen**: 2560×1440 (BlueStacks resolution)
- **Python**: 3.10+
- **BlueStacks**: Latest version

---

## Key Design Principles

### 1. Separation of Concerns
- **View Detection**: Separate from navigation
- **Calibration**: One-time process, data-driven
- **Navigation**: Uses calibration, no hard-coded values
- **Search**: Orchestrates all components, stateless

### 2. Data-Driven Design
- Calibration data drives all movements
- No magic numbers in navigation code
- Template-based detection (no pixel hunting)
- Configurable parameters (zoom level, arrow count)

### 3. Error Recovery
- Retry logic for failed operations
- Position verification after movements
- View state verification after switches
- Zoom restoration after castle clicks

### 4. Modularity
- Each module can be tested independently
- Clear interfaces between components
- Minimal coupling
- Reusable utilities

### 5. Documentation First
- Comprehensive docs for complex systems
- Architecture documented before implementation
- Calibration process documented
- Critical gotchas documented

---

## Performance Characteristics

### Time Estimates

**One-Time Setup:**
- Calibration: 21.7 minutes (already done)

**Per Search:**
- Initialization: ~5 seconds
- View setup: ~3 seconds
- Zoom setup: ~10 seconds (depends on current zoom)
- Position setup: ~5 seconds
- Per viewport: ~10-30 seconds (depends on castle count)
- Per castle click: ~3-5 seconds (click + zoom + OCR + restore)

**Example Search:**
- 50 viewports × 15 sec = 12.5 minutes
- 20 castle clicks × 4 sec = 1.3 minutes
- Total: ~14 minutes (typical)

### Accuracy Expectations

- **View Detection**: 98%+ (TM_CCORR_NORMED)
- **Zoom Detection**: 100% (area-based matching with tolerance)
- **Navigation**: ±5 pixels (arrow asymmetry + game behavior)
- **Castle Detection**: 85-95% (depends on template quality)
- **Name OCR**: 80-90% (depends on font, preprocessing)

---

## Future Enhancements

### Potential Improvements

1. **Parallel Castle Checking**
   - Remember castle positions across searches
   - Skip previously checked castles
   - Database of castle positions

2. **Adaptive Search Pattern**
   - Skip low-density areas
   - Focus on high-density clusters
   - Learn optimal zoom level per area

3. **Better Template Matching**
   - Multi-scale template matching
   - Feature-based matching (SIFT/ORB)
   - CNN-based castle detection

4. **Improved OCR**
   - Custom-trained OCR model
   - Multiple OCR engines (ensemble)
   - Better preprocessing pipeline

5. **Position Caching**
   - Cache viewport screenshots
   - Detect position without full scan
   - Resume interrupted searches

### DO NOT Implement Unless Needed

- Sub-pixel navigation accuracy
- Real-time castle tracking
- Predictive search algorithms
- Machine learning for optimization

---

## Troubleshooting

### Common Issues

**"Minimap not detected"**
- Ensure WORLD view (not TOWN)
- Verify screen resolution 2560×1440
- Check button templates exist

**"Navigation inaccurate"**
- Verify calibration data loaded
- Check zoom level is correct
- Ensure viewport position detected

**"Castle detection fails"**
- Verify templates at correct zoom level
- Check template quality
- Adjust detection threshold

**"OCR returns wrong name"**
- Improve preprocessing (threshold, denoise)
- Verify name region location
- Try different OCR engine

**"Search takes too long"**
- Reduce search area
- Increase arrow count per viewport
- Skip low-probability areas

---

## Version History

- **2025-11-05**: Initial architecture design
  - Complete system design documented
  - All modules specified
  - Data flows mapped
  - Integration points defined

---

**END OF ARCHITECTURE DOCUMENT**

---

## Quick Reference

**To run a search:**
```bash
python find_castle_by_level.py --level-min 20 --level-max 21 --name "yagamilight"
```

**To verify system:**
```bash
python view_detection.py --test         # Test view detection
python minimap_navigator.py             # Test navigation
python castle_scanner.py --test         # Test castle detection (when implemented)
```

**To recalibrate (if needed):**
```bash
python calibrate_navigation.py          # 21.7 minutes
# Then clean the data as documented
```

**Key files to understand:**
1. `ARCHITECTURE.md` (this file) - System overview
2. `MINIMAP_NAVIGATION_SYSTEM.md` - Navigation details
3. `view_detection.py` - View/minimap detection
4. `minimap_navigator.py` - Navigation calculations
5. `find_castle_by_level.py` - Main search (to be implemented)
