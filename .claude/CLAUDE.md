# Claude Instructions for xclash Project

## ⚠️ CRITICAL: Image Analysis Rules

**NEVER read or analyze screenshot images directly.** Always use Gemini via `calibration/detect_object.py`:

```bash
# Detect objects in screenshots
python calibration/detect_object.py screenshot.png "description of what to find"

# Examples:
python calibration/detect_object.py check.png "the World button in lower right"
python calibration/detect_object.py check.png "the back button with arrow icon"
```

**Why**: Claude's image analysis is unreliable for game UI detection. Gemini provides accurate bounding boxes and coordinates.

**Template extraction workflow**:
1. Take screenshot with `WindowsScreenshotHelper` (NOT adb_helper)
2. Use `calibration/detect_object.py` to find the element and get coordinates
3. Extract template using the returned bounding box
4. Save to `templates/ground_truth/`

**Correlation-based template extraction (for consistent framing)**:

When extracting multiple similar templates (e.g., Attack, Rally, Scout buttons), use an existing well-framed template as reference to get consistent framing across all:

```python
import cv2

frame = cv2.imread('screenshot.png')
reference_template = cv2.imread('templates/ground_truth/rally_button_4k.png')  # Well-framed reference

# Define search region: expected position +/- 100px on all sides
expected_x, expected_y = 1639, 1658  # Rough position from Gemini
w, h = reference_template.shape[1], reference_template.shape[0]

region_x = expected_x - 100
region_y = expected_y - 100
region_w = w + 200
region_h = h + 200

region = frame[region_y:region_y+region_h, region_x:region_x+region_w]

# Find highest correlation match
result = cv2.matchTemplate(region, reference_template, cv2.TM_CCORR_NORMED)
min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

# Convert to full frame coordinates
best_x = region_x + max_loc[0]
best_y = region_y + max_loc[1]

print(f'Best correlation: {max_val:.4f} at ({best_x}, {best_y})')

# Extract with correct framing
new_template = frame[best_y:best_y+h, best_x:best_x+w]
cv2.imwrite('templates/ground_truth/new_button_4k.png', new_template)
```

**Why this works**: Similar UI elements (hexagon buttons, tabs, icons) share structural features. Even if the icon inside differs, the hexagon border/shape correlates well. This finds the optimal crop position that matches the reference framing.

**When to use**:
- Extracting multiple buttons in a row (Attack, Rally, Scout)
- Ensuring consistent padding/centering across related templates
- When Gemini gives rough coordinates but framing looks off

**Tip**: If buttons are on the same row, find the best Y position for one, then use that Y for all others (only search horizontally).

**Full workflow: Extract templates + create masks (tried and true pattern)**:

1. **Take first screenshot** with panel open (background A)
2. **Use Gemini** to roughly locate buttons: `python calibration/detect_object.py screenshot.png "the Attack button"`
3. **Use correlation matching** with a well-framed reference template to find exact positions
4. **Extract templates** at those positions, save to `ground_truth/`
5. **Take second screenshot** with different background (pan map, switch view)
6. **Use Gemini again** to roughly locate buttons in new screenshot
7. **Correlation match again** using the templates you just extracted
8. **Create masks** by comparing the two extractions:

```python
import cv2
import numpy as np

# Load both extractions (same button, different backgrounds)
img1 = cv2.imread('templates/ground_truth/button_4k.png')
img2 = cv2.imread('screenshots/debug/button_new_bg.png')

# Create mask: identical pixels = opaque (white), different = background (black)
diff = cv2.absdiff(img1, img2)
diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
mask = (diff_gray < 10).astype(np.uint8) * 255

cv2.imwrite('templates/ground_truth/button_mask_4k.png', mask)
print(f'Opaque: {100*np.sum(mask==255)/mask.size:.1f}%')  # Should be 50-70%
```

**Why this works**: The hexagon/icon stays the same, only the background changes. Comparing pixels reveals which are part of the actual UI element (consistent) vs transparent background (varies).

**Masked Template Extraction** (for icons with transparent backgrounds):

When an icon has transparency (background shows through), standard template matching fails because the background changes. Use masked matching instead:

1. **Capture two screenshots** with different backgrounds behind the icon:
   - Take screenshot in WORLD view
   - Pan viewport or switch to TOWN view
   - Take second screenshot

2. **Extract icon region** from both screenshots at the same coordinates

3. **Create mask** by comparing pixels:
   ```python
   import cv2
   import numpy as np

   diff = cv2.absdiff(icon1, icon2)
   diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
   mask = (diff_gray < 10).astype(np.uint8) * 255  # threshold=10
   ```
   - **White pixels (255)**: Identical = opaque icon pixels (MATCH these)
   - **Black pixels (0)**: Different = transparent background (IGNORE these)

4. **Save both files**:
   - `templates/ground_truth/<name>_4k.png` - the template image
   - `templates/ground_truth/<name>_mask_4k.png` - the mask

5. **Use masked matching** with `TM_CCORR_NORMED`:
   ```python
   result = cv2.matchTemplate(roi, template, cv2.TM_CCORR_NORMED, mask=mask)
   score = cv2.minMaxLoc(result)[1]  # max_val for CCORR
   # score ~1.0 = match, threshold typically > 0.99
   ```

**Templates with masks**:
- `search_button_4k.png` + `search_button_mask_4k.png` - Magnifying glass icon (19, 1432) 119x118 - used to verify search panel opened
- `title_active_icon_4k.png` + `title_active_icon_mask_4k.png` - Title scroll icon (203, 216) 69x62
- `rally_button_4k.png` + `rally_button_mask_4k.png` - Rally button hexagon (153x177) - works on any background

**IMPORTANT: Search button templates**:
- `search_button_4k.png` - The **magnifying glass** icon on left sidebar (verifies search panel opened)
- `rally_search_button_4k.png` - The **"Search" text button** at bottom of Elite Zombie panel (368x126) - click this to search for zombie

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

This is an automation project for X-Clash using BlueStacks Android emulator.

Key components:
- ADB path: `C:\Program Files\BlueStacks_nxt\hd-adb.exe`
- Device: `emulator-5554` (auto-detected, may vary)
- Screen resolution: **3840x2160 (4K)** - FINAL resolution for all automation
- Python path: `C:\Users\mail\AppData\Local\Programs\Python\Python312\python.exe`
- OCR: Qwen2.5-VL-3B-Instruct on GPU (4-bit quantized)

## Directory Structure

**IMPORTANT**: Keep the root directory clean. Only essential files belong in root.

**Directory organization:**
- `screenshots/debug/` - All debug screenshots and test captures
- `scripts/one_off/` - One-off extraction scripts and test utilities
- `scripts/flows/` - Reusable automation flows
- `logs/` - Daemon and other runtime logs
  - `logs/current_daemon.log` - Always points to current running daemon output
  - `logs/daemon_YYYYMMDD_HHMMSS.log` - Timestamped daemon logs
  - `logs/old/` - Archived old logs
- `calibration/` - Calibration data and network captures
  - `calibration/network/` - .pcapng network capture files
- `templates/ground_truth/` - All template images for matching
- `utils/` - Reusable utilities and matchers
- `config.py`, `config_local.py` - Configuration files

## ⚠️ CRITICAL: Configuration Files

**TWO config files exist - know the difference:**

| File | Purpose | Git Status |
|------|---------|------------|
| `config.py` | **Defaults & universal settings** (positions, thresholds, template sizes) | Tracked |
| `config_local.py` | **User overrides** (API keys, personal preferences) | **Gitignored** |

**RULE: User-specific settings go in `config_local.py`, NOT `config.py`**

Settings that belong in `config_local.py`:
- `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY` - API credentials
- `IDLE_THRESHOLD` - Personal idle time preference
- `RALLY_JOIN_ENABLED` - Feature toggles
- Any setting the user wants different from defaults

Settings that belong in `config.py`:
- Template positions (BARRACKS_POSITIONS, HOSPITAL_ICON_POSITION)
- Template sizes (BARRACKS_TEMPLATE_SIZE, HOSPITAL_ICON_SIZE)
- Match thresholds (BARRACKS_MATCH_THRESHOLD, HOSPITAL_MATCH_THRESHOLD)
- Universal constants that apply to everyone

**How it works**: `config.py` loads first, then `config_local.py` overrides any values it defines.

**Root directory should stay clean**:
- Use `screenshots/`, `templates/`, `logs/`, and `data/` for artifacts
- Keep docs indexed in `docs/README.md`
- Avoid creating new ad-hoc files in the root

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

### ⚠️ CRITICAL: BlueStacks Right Sidebar Must Be ON

**The BlueStacks right sidebar (with media controls, shake, etc.) MUST be enabled.**

`WindowsScreenshotHelper` crops 30 pixels from the right edge (`RIGHT_BORDER=30`) to remove the sidebar. If the sidebar is OFF, this cropping shifts ALL coordinates by ~64 scaled pixels, causing:
- Template matching to fail (scores 0.13+ instead of ~0.00)
- All click coordinates to be wrong
- View detection returning UNKNOWN

**To verify sidebar is ON:**
1. Open BlueStacks Settings → Display
2. Ensure "Show sidebar" or equivalent is enabled
3. The sidebar should be visible on the right edge of the BlueStacks window

**Symptoms of sidebar being OFF:**
- Templates that were working suddenly fail
- Everything seems shifted ~50-60 pixels horizontally
- `detect_view()` returns UNKNOWN when World/Town button is visible

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

**Shaded Button Templates (popup dismissal, same position 3600,1920 size 240x240):**
- `world_button_shaded_4k.png` - Light shading when popups are blocking
- `world_button_shaded_dark_4k.png` - Dark shading when modal dialogs (Union Duel) are blocking

Used by `utils/shaded_button_helper.py` to detect and dismiss startup popups. When the game loads,
popups often block the screen. The World/Town button appears shaded/dimmed. Clicking it repeatedly
dismisses popups until the button returns to normal (detected by `view_state_detector`).

**Icon Detection Templates (fixed positions):**
- `handshake_icon_4k.png` - Alliance/handshake icon (position: 3088,1780, size: 155x127, threshold: 0.04)
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
- `back_button_union_4k.png` - Back button (position: 1345,2002, size: 107x111, threshold: 0.06)

**Royal City Panel Templates (4K):**

When clicking on a Royal City (via Mark or map), a panel opens with action buttons. The panel can be in two states:
- **Occupied**: Shows alliance tab, allows title application
- **Unoccupied**: Shows "Unoccupied" tab, no title application possible

| Template | Size | Position (top-left) | Click Center | Notes |
|----------|------|---------------------|--------------|-------|
| `royal_city_unoccupied_tab_4k.png` | 570x55 | (1630, 330) | - | Detects unoccupied state |
| `royal_city_attack_button_4k.png` | 153x177 | (1634, 1609) | (1710, 1697) | Red X icon |
| `rally_button_4k.png` + mask | 153x177 | (1839, 1658) | (1916, 1746) | Blue flag icon (masked) |
| `royal_city_scout_button_4k.png` | 153x177 | (2045, 1609) | (2121, 1697) | Blue binoculars icon |

**Usage in title flow:**
1. Navigate to Royal City via `go_to_mark_flow`
2. Check for `royal_city_unoccupied_tab_4k.png` - if found, city is unoccupied → cannot apply title
3. If occupied, proceed with title application

**Union Gifts Flow Templates:**
- `union_button_4k.png` - Union button on bottom bar (click: 3165, 2033)
- `union_rally_gifts_button_4k.png` - Union Rally Gifts menu item (click: 2175, 1193)
- `loot_chest_tab_4k.png` - Loot Chest tab (click: 1622, 545)
- `rare_gifts_tab_4k.png` - Rare Gifts tab (click: 2202, 548)
- `claim_all_button_4k.png` - Claim All button (Loot Chest: 1879,2051, Rare Gifts: 2217,2049)

**Anchor Templates:**
- `dog_house_4k.png` - Dog house for town view alignment verification (position: 1605,882, size: 172x197, threshold: 0.1)

**Barracks State Templates (bubble icons, size 81x87, threshold 0.08):**
- `stopwatch_barrack_4k.png` - Timer icon for TRAINING state
- `white_soldier_barrack_4k.png` - White soldier for PENDING state (81x87)
- `yellow_soldier_barrack_4k.png` - Yellow soldier v1 (purple hat) for READY state
- `yellow_soldier_barrack_v2_4k.png` - Yellow soldier v2 (purple hat, different frame)
- `yellow_soldier_barrack_v3_4k.png` - Yellow soldier v3 (red hat)
- `yellow_soldier_barrack_v4_4k.png` - Yellow soldier v4 (orange hat)
- `yellow_soldier_barrack_v5_4k.png` - Yellow soldier v5 (yellow/orange hat)

**CRITICAL Barracks Config (DO NOT CHANGE without full recalibration):**
```python
BARRACKS_POSITIONS = [
    (2891, 1317),  # Barrack 1
    (2768, 1237),  # Barrack 2
    (3005, 1237),  # Barrack 3
    (2883, 1157),  # Barrack 4
]
BARRACKS_TEMPLATE_SIZE = (81, 87)  # width, height - MUST match template files
BARRACKS_MATCH_THRESHOLD = 0.08   # Animation causes score variance 0.00-0.08
```

**Barracks Detection Logic:**
Detection matches ALL templates (stopwatch, yellow, white) and picks the BEST match
(lowest score for SQDIFF). This prevents false TRAINING detection when white soldier
matches better than stopwatch. Order of checking doesn't matter - best score wins.

NOTE: Different soldier types have different face icons! Multiple yellow soldier
templates are needed to match all variants. Both barracks_state_matcher and
hospital_state_matcher use the same yellow soldier templates.

**Soldier Tile Templates (barracks panel, fixed Y=810-967, size 148x157):**
- `soldier_lv3_4k.png` - Level 3 soldier tile
- `soldier_lv4_4k.png` - Level 4 soldier tile
- `soldier_lv5_4k.png` - Level 5 soldier tile
- `soldier_lv6_4k.png` - Level 6 soldier tile
- `soldier_lv7_4k.png` - Level 7 soldier tile
- `soldier_lv8_4k.png` - Level 8 soldier tile

**Soldier Training Panel Templates:**
- `soldier_training_header_4k.png` - "Soldier Training" header text (position: 1678,315, size: 480x54, threshold: 0.02)
- `train_button_4k.png` - Train button without timer (position: 1969,1397, size: 369x65, click: 2153,1462, threshold: 0.02)

**Soldier Tile Detection:**
- Y-axis is FIXED for all soldier levels (Y=810 to Y=967, height 157)
- Search across X-axis using template matching (TM_SQDIFF_NORMED)
- Threshold: 0.03 for positive match

**Tavern Quest Flow Templates:**
- `tavern_button_4k.png` - Clipboard button on left sidebar (position: 62,1192, size: 48x48, click: 80,1220, threshold: 0.02)
- `tavern_my_quests_active_4k.png` - My Quests tab when active (position: 1505,723, size: 299x65)
- `tavern_my_quests_4k.png` - My Quests tab when inactive
- `tavern_ally_quests_active_4k.png` - Ally Quests tab when active (position: 2054,723, size: 299x65)
- `tavern_ally_quests_4k.png` - Ally Quests tab when inactive
- `claim_button_4k.png` - Claim button (size: 333x88, threshold: 0.02, column search X: 2100-2500)
- `assist_button_4k.png` - Assist button for ally quests (size: 249x102)

**When extracting new templates:**
1. Use `WindowsScreenshotHelper` to capture screenshot
2. Crop the template region
3. Save to `templates/ground_truth/`
4. Use descriptive name with `_4k` suffix
5. Document coordinates and size in this file

## Centralized Template Matching

**ALL template matching MUST use `utils/template_matcher.py`** - ONE function: `match_template()`

```python
from utils.template_matcher import match_template

# Fixed position matching (icon at known location)
found, score, center = match_template(
    frame,
    "handshake_iter2.png",              # Template name (looks in templates/ground_truth/)
    search_region=(3088, 1780, 155, 127),  # x, y, width, height
    threshold=0.04                       # TM_SQDIFF_NORMED threshold
)
# Returns: (bool, float, tuple) - (is_match, score, center_coords)

# Search-based matching (find template anywhere in frame)
found, score, center = match_template(
    frame,
    "claim_button_4k.png",
    threshold=0.02
)
# Returns: (bool, float, tuple) - (is_match, score, CENTER_coords)

# Search within a region
found, score, center = match_template(
    frame,
    "claim_button_4k.png",
    search_region=(2100, 0, 400, 2160),  # x, y, w, h
    threshold=0.02
)
```

**CRITICAL - match_template returns CENTER coordinates:**
```python
# CORRECT - click the returned center directly:
found, score, center = match_template(frame, "button_4k.png")
if found:
    adb.tap(*center)  # center is already the click position!

# WRONG - do NOT add half template size:
found, score, center = match_template(frame, "button_4k.png")
if found:
    click = (center[0] + w//2, center[1] + h//2)  # WRONG! Double offset!
    adb.tap(*click)
```

**Benefits:**
- **ONE function**: `match_template()` handles both fixed-position and search-based matching
- **Auto mask detection**: If `<template>_mask_4k.png` exists, uses masked matching automatically
- **Cached templates**: Templates loaded once and cached (no repeated cv2.imread)
- **Consistent API**: Same interface everywhere, returns CENTER coordinates (ready to click)

**Matching methods:**
- `TM_SQDIFF_NORMED`: Default for unmasked templates. Score 0.0 = perfect match. Threshold is MAX allowed score.
- `TM_CCORR_NORMED`: Used for masked templates. Score 1.0 = perfect match. Threshold is MIN allowed score.

**Creating masked templates:**
When an icon has transparency (background shows through), create a mask:
1. Capture icon with TWO different backgrounds
2. Compare pixels: identical = opaque (white in mask), different = transparent (black in mask)
3. Save as `<name>_4k.png` and `<name>_mask_4k.png`
4. `template_matcher.py` auto-detects and uses the mask

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
- UNKNOWN → dismiss floating panels:
  1. Check for grass (WORLD indicator) → click grass to dismiss popup
  2. Check for ground (TOWN indicator) → click ground to dismiss popup
  3. If neither found → click back button (actual menu/dialog)

## Robust Flow Recovery

Use `utils/return_to_base_view.py` at the end of flows to ensure reliable return to TOWN/WORLD:

```python
from utils.return_to_base_view import return_to_base_view
from utils.adb_helper import ADBHelper
from utils.windows_screenshot_helper import WindowsScreenshotHelper

adb = ADBHelper()
win = WindowsScreenshotHelper()
success = return_to_base_view(adb, win, debug=True)
```

**Recovery Strategy** (5 attempts max, then restart and retry):
1. Click back button while visible (max 5 clicks per attempt)
2. Check if in TOWN/WORLD view - if yes, done
3. If stuck in unknown state, click back button location (1407, 2055) to dismiss popups
4. If still stuck after 5 attempts, kill xclash and restart:
   - Force stop `com.xman.na.gp`
   - Wait 2s, start app
   - Wait 30s for load
   - Run `setup_bluestacks.py`
   - **Recursively call return_to_base_view** to verify and retry if needed

**Returns**: `True` when successfully reached TOWN/WORLD (keeps trying until success)

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

### 5. Traditional OCR Tools (DEPRECATED)
**Status**: Abandoned as of 2025-11-30

**Do not use** for game UI text extraction:
- **Tesseract OCR**: Inconsistent, requires preprocessing, fails on stylized fonts
- **EasyOCR**: Slow (~5s per image), inaccurate on small UI text
- **PaddleOCR**: Complex dependencies, mediocre accuracy
- **Windows OCR API**: Can't handle decorative game fonts
- **`deprecated/stamina_extractor.py`**: Old Tesseract-based extractor (moved to deprecated/)

**Use instead**: `utils/qwen_ocr.py` - Qwen2.5-VL-3B vision model on GPU

## Stamina Confirmation

Use `utils/stamina_reader.py` for multi-read stamina validation:

```python
from utils.stamina_reader import StaminaReader

reader = StaminaReader()

# In daemon loop - add each OCR reading:
confirmed, stamina = reader.add_reading(ocr_value)
if confirmed:
    # stamina is the MODE of 3 consistent readings
    do_something_with_stamina(stamina)
    reader.reset()  # Reset after triggering action
```

**Why this exists**: OCR occasionally misreads stamina (e.g., reads 23 when it's 5). Using the LAST value would trigger rallies incorrectly. StaminaReader:
- Requires 3 readings
- Checks consistency: max-min ≤ 10 (resets if too spread)
- Returns MODE (most common value), not last value

**Example**: With readings [5, 5, 23], returns (False, None) because max-min=18>10. With [23, 22, 23], returns (True, 23) because max-min=1≤10 and MODE=23

**Why Qwen wins**: Vision-language models understand context, not just pixel patterns. They read stylized game text reliably without preprocessing.

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

## OCR with Qwen2.5-VL-3B

The daemon uses **Qwen2.5-VL-3B-Instruct** for OCR, running on GPU with 4-bit quantization.

### Why Qwen Instead of Traditional OCR

**Traditional OCR tools failed miserably:**
- **Tesseract**: Inconsistent results, required heavy preprocessing, still failed on game fonts
- **EasyOCR**: Slow, inaccurate on stylized game text
- **PaddleOCR**: Complex setup, mediocre results on small UI text
- **Windows OCR API**: Couldn't handle the game's decorative fonts

**Qwen2.5-VL-3B** is a vision-language model that actually understands what it's looking at. It reads game UI text reliably without any preprocessing.

### GPU Configuration (GTX 1080 / Pascal Architecture)

**CRITICAL**: GTX 1080 (Pascal) runs float16 at 1/64th speed. Must use float32 for compute:

```python
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
import torch

# 4-bit quantization with float32 compute (REQUIRED for Pascal GPUs)
quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float32,  # NOT float16!
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
)

model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2.5-VL-3B-Instruct",
    quantization_config=quantization_config,
    device_map="cuda",
)
```

**Performance:**
- Model load: ~5 seconds (first time only, singleton pattern)
- Inference: ~1-2 seconds per image
- VRAM usage: ~4GB with 4-bit quantization

### Usage

```python
from utils.qwen_ocr import QwenOCR
from utils.windows_screenshot_helper import WindowsScreenshotHelper

win = WindowsScreenshotHelper()
frame = win.get_screenshot_cv2()

ocr = QwenOCR()  # Singleton - loads model once

# Extract text
text = ocr.extract_text(frame, region=(x, y, w, h))

# Extract number (for stamina, etc)
number = ocr.extract_number(frame, region=(69, 203, 96, 60))
```

### Stamina Region
- Coordinates (4K): (69, 203) size 96x60
- Returns integer or None if extraction fails

### Dependencies

```bash
pip install transformers torch bitsandbytes accelerate
```

**Note**: `bitsandbytes` is required for 4-bit quantization. Install it explicitly.

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

**Daemon Logging:**

Both log files have **identical content** (all logger output):
- `logs/daemon_YYYYMMDD_HHMMSS.log` - Timestamped log file (archived)
- `logs/current_daemon.log` - Latest daemon output (overwritten each restart)

All daemon output (iteration status, flow triggers, errors) goes through Python logger to both files.

```bash
# Check current daemon output
cat logs/current_daemon.log

# Search for specific events
grep "BAG FLOW\|triggering" logs/current_daemon.log
```

### Flow Coordination

The daemon uses `_run_flow()` and `_run_flow_sync()` to prevent flows from interrupting each other:

- **`active_flows` set**: Tracks currently running flows
- **`critical_flow_active` flag**: When True, blocks non-critical flows
- **`_can_run_flow()` helper**: Pre-check before clicking to avoid UI interference

**CRITICAL**: All flows must check `_can_run_flow()` BEFORE clicking any UI elements. This prevents:
- Rally join from interrupting bag flow
- Soldier upgrade from interrupting treasure map
- Any flow from clicking while another flow has the UI open

**Flow coordination pattern**:
```python
# CORRECT: Check BEFORE clicking
if not self._can_run_flow():
    self.logger.debug("Skipping - another flow is active")
else:
    self.adb.tap(x, y)  # Only click if no flow active
    self._run_flow_sync("flow_name", flow_func, critical=True)

# WRONG: Click first, check later (causes interruptions)
self.adb.tap(x, y)  # BAD - already clicked!
self._run_flow_sync(...)  # Too late to prevent interference
```

### Idle Detection Modes

The daemon supports two idle detection modes, controlled by `USE_BLUESTACKS_IDLE` in `config.py`:

| Mode | Config Value | Behavior |
|------|--------------|----------|
| **BlueStacks-specific** | `USE_BLUESTACKS_IDLE = True` (default) | Only tracks input while BlueStacks is focused. Typing in Chrome does NOT reset idle timer. |
| **System-wide** | `USE_BLUESTACKS_IDLE = False` | Any keyboard/mouse input anywhere resets idle timer. |

**BlueStacks-specific mode** (recommended):
- Idle time increases when user is typing/clicking in OTHER windows (Chrome, VS Code, etc.)
- Idle time resets to 0 only when user clicks/types IN the BlueStacks window
- Useful when multitasking - automation runs even while working in other apps

**System-wide mode** (legacy):
- Any keyboard/mouse input anywhere resets the idle timer
- Automation only runs when user is completely away from keyboard

The daemon logs both values: `idle:` (system-wide) and `bs:` (BlueStacks-specific).

### Disconnection Dialog Handling

When user opens the game on mobile, BlueStacks gets disconnected and shows a "Tip: Disconnected from the server. Error Code:7" dialog. The daemon handles this gracefully:

1. **Detection**: Template matches full dialog (Tip header + message text)
2. **5-minute wait**: Gives user time to manage things on mobile
3. **Auto-dismiss**: Clicks Confirm after wait to reconnect automation

**Templates**:
- `disconnection_dialog_4k.png` - Full dialog for detection (980x350)
- `confirm_button_4k.png` - Confirm button click position (1912, 1289)

**Config**: `DISCONNECTION_WAIT_SECONDS = 300` (5 minutes, in icon_daemon.py)

### Idle Return-to-Town (Every 5 Iterations)

When user is idle for 5+ minutes, every 5 daemon iterations (~10 seconds):
1. If not in TOWN, navigates to TOWN using `go_to_town()`
2. If in TOWN, checks dog house alignment. If misaligned, resets view (WORLD → TOWN)
3. Counter resets when user becomes active or critical flow is running

This ensures most scanning happens in TOWN view where harvest bubbles and barracks are visible.

### Harvest Action Requirements

Harvest actions (corn, gold, iron, gem, cabbage, equipment) require ALL of:
1. **TOWN view** - must see World button (not in WORLD/CHAT)
2. **5+ minutes idle** - won't trigger while user is active
3. **Dog house aligned** - town view must not be panned

**Immediate actions** (no idle/alignment check):
- Handshake flow
- Treasure map (digging) flow
- Harvest box flow

### Elite Zombie Rally (Stamina-based)

When stamina >= 118 AND user idle for 5+ minutes:
1. Navigate to WORLD view
2. Click magnifying glass → **POLL** for `rally_search_button_4k.png` (verify panel opened)
3. Click Elite Zombie tab → **VERIFY** `elite_zombie_tab_4k.png`
4. Click plus button N times (increase level, configurable via ELITE_ZOMBIE_PLUS_CLICKS)
5. **VERIFY** `rally_search_button_4k.png` visible, then click (use detected location)
6. **POLL** for `rally_button_4k.png` → click detected location
7. **POLL** for `team_up_button_4k.png` (verify rally screen loaded)
8. Select LEFTMOST idle hero (with Zz icon)
9. **VERIFY** and click `team_up_button_4k.png`

**Template Verification**:
- Each step verifies expected UI element before clicking
- Uses `_poll_for_template()` with timeout for screen transitions
- Clicks detected template location (not fixed coords) when possible
- Calls `return_to_base_view()` on any failure

**Templates Used**:
- `rally_search_button_4k.png` (368x126, threshold 0.05) - "Search" text button at bottom of panel
- `elite_zombie_tab_4k.png` (284x97, threshold 0.1)
- `rally_button_4k.png` (153x177, threshold 0.08)
- `team_up_button_4k.png` (368x134, threshold 0.05)

**Hero Selection:**
- Elite Zombie: Uses **leftmost** idle hero (`hero_selector.find_leftmost_idle()`)
- Treasure Map: Uses **rightmost** idle hero (`hero_selector.find_rightmost_idle()`)

### Hero Upgrade Arms Race Flow (Event-Based)

**Trigger**: During Arms Race "Enhance Hero" event, in the last N minutes (configurable), if user was idle since the START of the Enhance Hero block.

**Pattern**: "During event X + in last N minutes + idle since block start"

**Flow sequence**:
1. Click Fing Hero button at (2272, 2038)
2. Wait for hero grid to load (3x4 grid of hero tiles)
3. Scan all 12 tiles for red notification dots (red pixel counting method)
4. For each tile with red dot:
   - Click tile center
   - Check if upgrade button is available (green) or unavailable (gray)
   - If available: click upgrade button at (1919, 1829), then return to base view
   - If unavailable: click back to return to hero grid
5. Use `return_to_base_view()` to exit and get back to TOWN/WORLD

**Red Dot Detection**:
- Method: Count red pixels in upper-right 40x40 region of each tile
- Red in BGR: B<100, G<100, R>150
- Threshold: 50+ red pixels = has dot
- Verified: tiles WITH dot have 800+ red pixels, tiles WITHOUT have 0

**Hero Grid Layout (4K)**:
| Tile | Position | Size | Click Center |
|------|----------|------|--------------|
| r1_c1 | (1374, 211) | 246x404 | (1497, 413) |
| r1_c2 | (1651, 211) | 249x404 | (1775, 413) |
| r1_c3 | (1931, 211) | 250x404 | (2056, 413) |
| r1_c4 | (2208, 211) | 245x404 | (2330, 413) |
| r2_c1 | (1374, 639) | 246x397 | (1497, 837) |
| r2_c2 | (1651, 639) | 249x397 | (1775, 837) |
| r2_c3 | (1931, 639) | 250x397 | (2056, 837) |
| r2_c4 | (2208, 639) | 245x397 | (2330, 837) |
| r3_c1 | (1374, 1067) | 246x397 | (1497, 1265) |
| r3_c2 | (1651, 1067) | 249x397 | (1775, 1265) |
| r3_c3 | (1931, 1067) | 250x397 | (2056, 1265) |
| r3_c4 | (2208, 1067) | 245x397 | (2330, 1265) |

**Templates**:
- `heroes_button_4k.png` - Fing Hero button (123x177 at 2211,1950, click: 2272,2038)
- `upgrade_button_available_4k.png` - Green upgrade button (407x121)
- `upgrade_button_unavailable_4k.png` - Gray upgrade button (365x126)

**Additional conditions**:
- Must be in TOWN view
- Dog house must be aligned
- Triggers once per Enhance Hero block (4-hour event window)

### Soldier Training Arms Race Flow (Continuous During Event)

**Trigger**: During "Soldier Training" Arms Race event OR on VS promotion days, idle 5+ min, any PENDING barrack detected

**Pattern**: "Continuous loop during Soldier Training event or VS day"

**VS Event Override**: On days listed in `VS_SOLDIER_PROMOTION_DAYS` (e.g., `[2]` for Day 2), soldier promotions run ALL DAY regardless of which 4-hour event is active. The daemon shows `[VS:Promo]` in the log when this override is active.

**Flow sequence** (for each PENDING barrack):
1. Click barrack bubble to open soldier training panel
2. **VERIFY**: Poll for `soldier_training_header_4k.png` (up to 3s timeout)
3. Detect highest unlocked soldier level using bottom-half template matching
4. Calculate target level = highest - 1
5. Scroll horizontally (if needed) to find target level tile
6. Click target level tile
7. **VERIFY**: Check `train_button_4k.png` is visible
8. Click Train button at (2153, 1462)
9. Handle resource replenishment if "Replenish All" button appears
10. **CLEANUP**: Always call `return_to_base_view()` in finally block

**After promotion**:
- Soldiers train → barracks becomes READY
- Daemon releases soldiers → barracks becomes PENDING
- Daemon promotes again → continuous loop during event

**Soldier Tile Detection**:
- Uses bottom-half templates: `half_soldier_lv{3-8}_4k.png` (79x148 pixels)
- Fixed Y region: 890-969 (TM_SQDIFF_NORMED, threshold 0.02)
- Horizontal scanning to detect visible levels in panel
- Scroll direction: swipe FROM detected tile center TO THE RIGHT to reveal left content

**Scroll Logic**:
- To see lower levels (Lv3, Lv4): swipe right from rightmost visible tile
- To see higher levels (Lv7, Lv8): swipe left from leftmost visible tile
- Max 3 scroll attempts before giving up

**Requirements**:
- Arms Race event = "Soldier Training" OR current day in `VS_SOLDIER_PROMOTION_DAYS`
- Idle 5+ minutes
- TOWN view detected
- Dog house aligned (not panned)
- At least 1 PENDING barrack

**Testing**:
```bash
# Detect highest unlocked level only
python scripts/flows/soldier_upgrade_flow.py --detect-only

# Scroll to find target and click it
python scripts/flows/soldier_upgrade_flow.py --scroll-and-select

# Full upgrade flow (with promote)
python scripts/flows/soldier_upgrade_flow.py
```

**Config**:
- `ARMS_RACE_SOLDIER_TRAINING_ENABLED = True` (default)
- `VS_SOLDIER_PROMOTION_DAYS = [2]` - Days when soldier promotion runs all day (Day 2 = Thursday)
- No cooldown, no block limitation - runs continuously during event or VS day

### Non-Arms-Race Soldier Training (Timed)

**Trigger**: NOT during Soldier Training event AND NOT VS promotion day, READY barracks detected, 5+ min idle, TOWN view, dog house aligned

**Pattern**: "ONE code path via `soldier_training_flow` with automatic Arms Race timing"

**Flow sequence**:
1. Daemon detects READY barracks (no cooldown - triggers immediately when conditions met)
2. Calls `soldier_training_flow` which:
   - Collects from READY barracks (click yellow bubbles)
   - Trains PENDING barracks via `train_soldier_at_barrack()`
3. `train_soldier_at_barrack()` calculates time until next "Soldier Training" Arms Race event
4. If training would exceed that time → uses `barracks_training_flow` with `target_hours` to finish just before event
5. If training fits within time → uses max training time

**Arms Race Timing Logic** (`train_soldier_at_barrack()`):
```python
time_until = get_time_until_soldier_training()
if time_until and time_until.total_seconds() > 0:
    max_hours = (time_until.total_seconds() - 300) / 3600  # 5 min buffer
    max_hours = max(0.5, max_hours)  # Minimum 30 min training
    # Use barracks_training_flow with target_hours
else:
    # During Soldier Training event - use max time (upgrade flow handles this)
```

**Key files**:
- `scripts/flows/soldier_training_flow.py`: `train_soldier_at_barrack()` with timing logic
- `scripts/flows/barracks_training_flow.py`: Slider adjustment for precise timing

**Config**:
- No cooldown - triggers immediately when READY barracks detected and conditions met
- Requires: 5+ min idle, TOWN view, dog house aligned

### Beast Training Arms Race Flow (Mystic Beast)

**Trigger**: During "Mystic Beast Training" Arms Race event, in the last 60 minutes, idle 2+ min

**Pattern**: "Dynamic target based on actual progress check"

**See full documentation**: `docs/BEAST_TRAINING_LOGIC.md`

**Key Numbers** (depends on zombie mode):

| Mode | Stamina/Action | Points/Action | Actions for 30k |
|------|----------------|---------------|-----------------|
| elite (default) | 20 | 2,000 | 15 rallies |
| gold/food/iron_mine | 10 | 1,000 | 30 attacks |

Same total stamina (300), but zombie mode = 2x more actions.

**Zombie Mode**:

Configurable mode to use regular zombie attacks instead of elite zombie rallies:

```python
# In config.py
ZOMBIE_MODE_CONFIG = {
    "elite": {"stamina": 20, "points": 2000, "flow": "elite_zombie"},
    "gold": {"stamina": 10, "points": 1000, "flow": "zombie_attack", "zombie_type": "gold"},
    "food": {"stamina": 10, "points": 1000, "flow": "zombie_attack", "zombie_type": "food"},
    "iron_mine": {"stamina": 10, "points": 1000, "flow": "zombie_attack", "zombie_type": "iron_mine"},
}
```

**WebSocket API for Zombie Mode**:
```bash
# Set gold mode for 24 hours
echo '{"cmd": "set_zombie_mode", "args": {"mode": "gold", "hours": 24}}' | websocat ws://127.0.0.1:9876

# Check current mode
echo '{"cmd": "get_zombie_mode"}' | websocat ws://127.0.0.1:9876

# Clear mode (revert to elite)
echo '{"cmd": "clear_zombie_mode"}' | websocat ws://127.0.0.1:9876
```

**Zombie Mode State** (`data/daemon_schedule.json`):
```json
{
  "zombie_mode": {
    "mode": "gold",
    "expires": "2025-01-04T06:00:00+00:00",
    "set_at": "2025-01-03T06:00:00+00:00"
  }
}
```

Mode auto-expires after set duration, reverting to elite.

**Two-Phase Flow**:

1. **Hour Mark Check** (1 hour into event):
   - Open Events → Arms Race panel
   - OCR current points
   - Calculate `actions_needed = ceil((30000 - current_points) / points_per_action)`
   - Set `beast_training_target_rallies`

2. **Rally/Attack Execution** (continuous):
   - While `rally_count < target`:
     - If stamina ≥ threshold (20 elite, 10 zombie): do rally/attack
     - If stamina < threshold and use_count < 4: click Use button for free 50 stamina

**State Tracking** (`data/daemon_schedule.json`):
```json
{
  "arms_race": {
    "beast_training_rally_count": 4,      // Done this block
    "beast_training_target_rallies": 6    // Target for this block
  }
}
```

**Config**:
- `ARMS_RACE_BEAST_TRAINING_ENABLED = True`
- `ARMS_RACE_BEAST_TRAINING_LAST_MINUTES = 60` - Only act in last 60 min
- `ARMS_RACE_BEAST_TRAINING_USE_MAX = 4` - Max Use button clicks per block
- `ZOMBIE_MODE_CONFIG` - Mode definitions (stamina, points, flow)

### Rally Join Flow (Union War)

**Trigger**: Handshake icon detected → opens Union War panel → `rally_join_flow`

**Flow sequence**:
1. Validate Union War panel state (heading + Team Intelligence tab)
2. Find all plus buttons in rightmost column
3. For each rally (top to bottom):
   - OCR monster icon to get name and level
   - Check against `RALLY_MONSTERS` config:
     - `auto_join`: Must be True
     - `max_level`: Level must be <= max_level
     - `track_daily_limit`: If True, check exhaustion tracker
   - If exhausted → skip to next rally
4. Click plus button for matching rally
5. **Poll for Team Up panel** (up to 5 seconds, not fixed sleep)
6. Select leftmost idle hero (must have Zz icon)
7. Click Team Up button
8. **Poll for daily limit dialog** (2 seconds):
   - If dialog appears → click Cancel → mark exhausted (if track_daily_limit=True)
9. Return to base view

**Daily Limit Detection**:
- Template: `daily_rally_limit_dialog_4k.png` (983x527) - "Tip" header + full text about daily rally rewards
- Threshold: 0.05 (tight - template includes unique text to avoid false positives on other "Tip" dialogs)
- When detected: clicks Cancel button, marks monster exhausted until server reset (02:00 UTC)
- `track_daily_limit: False` monsters (like Zombie Overlord) are never tracked

**Config** (`config.py`):
```python
RALLY_MONSTERS = [
    {"name": "Zombie Overlord", "auto_join": True, "max_level": 130, "track_daily_limit": False},
    {"name": "Elite Zombie", "auto_join": True, "max_level": 25, "track_daily_limit": True},
    {"name": "Union Boss", "auto_join": True, "max_level": 9999, "track_daily_limit": False},
    {"name": "Nightfall Servant", "auto_join": True, "max_level": 25, "track_daily_limit": True},
    {"name": "Undead Boss", "auto_join": True, "max_level": 25, "track_daily_limit": True},
    {"name": "Klass", "auto_join": True, "max_level": 30, "track_daily_limit": True},
]
```

**Templates**:
- `team_up_button_4k.png` - Team Up button (region 1700,1550 420x180, threshold 0.05)
- `daily_rally_limit_dialog_4k.png` - Daily limit dialog with full text (983x527, threshold 0.05)
- `cancel_button_4k.png` - Cancel button (region 1450,1200 420x180, click 1670,1291)

**Files**:
- `scripts/flows/rally_join_flow.py` - Main flow
- `utils/rally_exhaustion_tracker.py` - Daily limit tracking
- `utils/rally_monster_validator.py` - OCR and validation

### Royal City Flow (Scheduled)

**Trigger**: Scheduled execution (e.g., "at 6AM tomorrow, attack Royal City")

**Prerequisite**: Must use `go_to_mark_flow` first to navigate to the Royal City location on the map.

**Flow sequence** (`scripts/flows/royal_city_flow.py`):
1. **Find and click star** in center of screen to open Royal City panel
   - Template: `star_single_4k.png` (search region 1400,600 1100x1000, threshold 0.15)
2. **Verify city is UNCLAIMED** - only unclaimed cities can be attacked/scouted
   - Template: `royal_city_unoccupied_tab_4k.png` (570x55)
   - If OCCUPIED: abort flow (can't attack your own alliance's city)
3. **Perform action** based on argument:

| Action | Button Template | What Happens |
|--------|-----------------|--------------|
| `scout` | `royal_city_scout_button_4k.png` | Just clicks Scout, done |
| `attack` | `royal_city_attack_button_4k.png` | Opens troop selection |
| `rally` | `rally_button_4k.png` | Opens rally setup |

4. **For attack/rally only**:
   - Select rightmost idle hero (with Zz icon) using `HeroSelector`
   - Click March button at (1912, 1648) or template match
5. `return_to_base_view()` to exit

**Templates** (all 153x177 with masks for TM_CCORR_NORMED):
- `royal_city_attack_button_4k.png` + `royal_city_attack_button_mask_4k.png`
- `royal_city_scout_button_4k.png` + `royal_city_scout_button_mask_4k.png`
- `rally_button_4k.png` + `rally_button_mask_4k.png`
- `royal_city_unoccupied_tab_4k.png` (no mask needed)
- `star_single_4k.png` (TM_SQDIFF_NORMED, threshold 0.15)

**Button relative offsets** (from Attack button position):
```python
# In config.py
ROYAL_CITY_BUTTON_OFFSETS = {
    'attack': (0, 0),      # Reference point
    'rally': (205, 49),    # Attack + (205, 49)
    'scout': (411, 0),     # Attack + (411, 0)
}
ROYAL_CITY_BUTTON_SIZE = (153, 177)
```

**Usage**:
```bash
# Scout only (fast)
python scripts/flows/royal_city_flow.py scout --debug

# Attack with rightmost idle hero
python scripts/flows/royal_city_flow.py attack --debug

# Rally (sets up rally, others can join)
python scripts/flows/royal_city_flow.py rally --debug
```

**Scheduling**: This flow will be called by the daemon scheduler at specified times. User specifies when (e.g., "6AM tomorrow") and the scheduler queues the flow for execution.

**Files**:
- `scripts/flows/royal_city_flow.py` - Main flow
- `scripts/flows/go_to_mark_flow.py` - Navigation to marked location (prerequisite)

### Currently Detected Icons

| Icon | Matcher | Threshold | Click Position | Flow |
|------|---------|-----------|----------------|------|
| Handshake | `handshake_icon_matcher.py` | 0.04 | (3165, 1843) | `handshake_flow` |
| Treasure Map | `treasure_map_matcher.py` | 0.05 | (2175, 1621) | `treasure_map_flow` ✓ |
| Harvest Box | `harvest_box_matcher.py` | 0.1 | (2177, 1618) | `harvest_box_flow` ✓ |
| Corn | `corn_harvest_matcher.py` | 0.05 | (1932, 1297) | `corn_harvest_flow` |
| Gold | `gold_coin_matcher.py` | 0.06 | (1395, 835) | `gold_coin_flow` |
| Iron | `iron_bar_matcher.py` | 0.08 | (1639, 377) | `iron_bar_flow` |
| Gem | `gem_matcher.py` | 0.06 | (1405, 696) | `gem_flow` |
| Healing | `healing_bubble_matcher.py` | 0.06 | (3340, 364) | `healing_flow` |
| Elite Zombie | Stamina OCR | stamina >= 118 | N/A | `elite_zombie_flow` ✓ |
| Hero Upgrade | Enhance Hero event | last N min + idle | (2272, 2038) | `hero_upgrade_arms_race_flow` |
| Bag | Idle trigger | 5 min idle + 1 hr cooldown | (3725, 1624) | `bag_flow` |
| Snowman Party | Chat message | `snowman_chat_matcher.py` | N/A | `snowman_flow` (scaffolding) |
| Royal City | Scheduled | User-specified time | N/A | `royal_city_flow` ✓ |

### Snowman Party Flow (Scaffolding - Claim Step TBD)

**Trigger**: "Snowman Party" chat message detected (not yet in daemon)

**Flow sequence**:
1. Detect "Snowman Party" yellow chat bubble (search-based, center of screen)
2. Click chat message to navigate to snowman location
3. Wait for snowman to appear, verify arrival (template matching)
4. (PLACEHOLDER) Click claim bubble above snowman - template not yet extracted
5. Return to base view

**Templates**:
- `snowman_party_chat_4k.png` - Yellow chat bubble (772x80, search center screen)
- `snowman_4k.png` - Snowman character (254x212, search center screen)
- `snowman_claim_bubble_4k.png` - TBD when user gets bubble

**Matchers**:
- `snowman_chat_matcher.py` - Search region X=1100-2800, full Y
- `snowman_matcher.py` - Search region center screen

### Hospital Healing Flow

**Trigger**: Hospital bubble detected (HELP_READY, HEALING, or SOLDIERS_WOUNDED state)

**Key Concept**: Hospital panel shows multiple rows of different soldier types. Each row has a slider that adds to total healing time. To heal in 1-hour batches, we must:
1. Reset ALL sliders to minimum first
2. Fill ONLY the bottom row (highest level soldiers) up to 1 hour
3. Leave other rows at minimum

**Flow sequence** (`scripts/flows/hospital_healing_flow.py`):
1. Verify hospital panel is open (header template match)
2. Scroll through entire panel, reset ALL sliders to minimum
3. Check initial healing time (should be ~0 after reset)
4. Select bottom row only (`buttons[-1]` = highest level soldiers)
5. Drag slider to max, check time
6. If over 1 hour: binary search (8 iterations) to find ~1 hour position
7. Click Healing button
8. Return to base view

**Panel Helper** (`utils/hospital_panel_helper.py`):
- `find_plus_buttons()` - Detects all plus buttons in panel (Y=550-1200, X=2150-2350)
- `drag_slider_to_min/max()` - Drags slider to position
- `reset_all_sliders()` - Resets all visible sliders
- `scroll_panel_down()` - Scrolls to reveal more rows

**Templates**:
- `hospital_header_4k.png` - Panel header verification
- `hospital_plus_button_4k.png` - Plus button (79x77)
- `hospital_minus_button_4k.png` - Minus button (79x80)
- `hospital_slider_circle_4k.png` - Slider handle

**Config**:
- `HOSPITAL_ICON_POSITION = (3312, 344)` - Bubble detection location
- `HOSPITAL_CLICK_POSITION = (3342, 377)` - Click to open panel
- `HEALING_BUTTON_CLICK = (2148, 1477)` - Healing button position
- `MAX_SAFE_HEAL_SECONDS = 5400` - 90 minute safety limit

### Tavern Quest Flow (Not Yet Integrated)

**Trigger**: Tavern button detected on left sidebar (TBD - not yet in daemon)

**Entry**: Click tavern button at (80, 1220) to open Tavern menu

**Double-Pass Strategy**:
After clicking any Claim button, the UI can get glitchy. To avoid missing claims:
1. Click Claim → dismiss popup → exit tavern completely (return_to_base_view)
2. Re-enter tavern and run the flow again
3. Do this twice back-to-back to ensure nothing is missed

**Tab Detection**:
- Match `tavern_my_quests_active_4k.png` OR `tavern_ally_quests_active_4k.png` to verify in Tavern
- Both tabs must be visible (one active, one inactive) for validation

**My Quests Flow** (per pass):
1. Navigate to TOWN
2. Click tavern button to open
3. If not on My Quests tab, click (1654, 755) to switch
4. Column-restricted Claim button search (X: 2100-2500, full Y scan)
5. If Claim found: click it, dismiss popup, EXIT tavern (return_to_base_view)
6. If no Claim: scroll down, rescan. Stop after 2 consecutive scrolls with no claims.

**Ally Quests Flow**: TBD by user (more complex logic, not just clicking all Assist)

**Cleanup**: `return_to_base_view()` after each pass

**Templates**:
- `tavern_button_4k.png` - Clipboard icon (position: 62,1192, click: 80,1220)
- `tavern_my_quests_active_4k.png` / `tavern_my_quests_4k.png` - Tab states (position: 1505,723)
- `tavern_ally_quests_active_4k.png` / `tavern_ally_quests_4k.png` - Tab states (position: 2054,723)
- `claim_button_4k.png` - Claim button (column X: 2100-2500, threshold: 0.02)
- `assist_button_4k.png` - Assist button for ally quests (TBD)

### Bag Flow (Idle-Triggered)

**Trigger**: TOWN view + 5 min idle + 1 hour cooldown

**Flow sequence**:
1. Navigate to TOWN view via `go_to_town()`
2. Click bag button (3725, 1624)
3. Run `bag_special_flow` - claim chests from Special tab (7 templates)
4. Run `bag_hero_flow` - claim chests from Hero tab (2 templates)
5. Run `bag_resources_flow` - claim diamonds from Resources tab
6. Close bag and return to base view

**Critical flow**: Runs with `critical=True` to block daemon's idle recovery from closing bag.

**Template matching**:
- Tab detection: 0.01 threshold (strict - prevents false "already active")
- Item detection: 0.01 threshold (strict - prevents false positives)
- Dialog elements (Use button, slider): 0.1 threshold (looser)
- `bag_use_item_subflow` polls for Bag header before returning (not fixed timeout)

**Special Tab Templates** (7):
- `bag_chest_special_4k.png` - Open chest with blue gems
- `bag_golden_chest_4k.png` - Golden wooden chest
- `bag_green_chest_4k.png` - Green crystal chest
- `bag_purple_gold_chest_4k.png` - Purple crystal chest
- `bag_chest_blue_4k.png` - Blue/cyan crystal chest
- `bag_chest_purple_4k.png` - Purple chest with gold trim
- `bag_chest_question_4k.png` - Mystery chest with question mark

**Hero Tab Templates** (2):
- `bag_hero_chest_4k.png` - Green gem chest (blue background)
- `bag_hero_chest_purple_4k.png` - Green gem chest (purple background)

**Resources Tab Templates**:
- `bag_diamond_icon_4k.png` - Diamond icon

**Tab Templates** (unified coordinates - same region for active/inactive):
- `bag_button_4k.png` - Bag button verification
- `bag_tab_4k.png` - Verify bag menu opened (header)

| Tab | Region (x, y, w, h) | Active Template | Inactive Template |
|-----|---------------------|-----------------|-------------------|
| Special | (1525, 2033, 163, 96) | `bag_special_tab_active_4k.png` | `bag_special_tab_4k.png` |
| Hero | (2158, 2015, 207, 127) | `bag_hero_tab_active_4k.png` | `bag_hero_tab_4k.png` |
| Resources | (1732, 2018, 179, 111) | `bag_resources_tab_active_4k.png` | `bag_resources_tab_4k.png` |

### Matcher Thresholds

Thresholds are defined in each matcher file (single source of truth):
- `TM_SQDIFF_NORMED`: Lower score = better match. Threshold is maximum allowed score.
- Typical thresholds: 0.04-0.06 for icons, 0.1 for larger templates
- Edit thresholds in `utils/*_matcher.py` files, NOT in `icon_daemon.py`
- Scores should be ~0.00 for perfect matches (captured with Windows screenshot)
