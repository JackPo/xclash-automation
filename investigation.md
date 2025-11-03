# XClash Player Position Investigation

## Goal
Find where player positions are stored on screen in the XClash game running on BlueStacks emulator, specifically looking for players like "Angelbear666" and "manhammer00" (also "DVCxPanda" is the user's own username).

## Environment Setup
- Game: XClash (package: com.xman.na.gp)
- Emulator: BlueStacks
- Device: 127.0.0.1:5555 (emulator-5554)
- Working Directory: C:\Users\mail\xclash

## ADB Connection
- Located ADB: `C:\Program Files\BlueStacks_nxt\hd-adb.exe`
- Connected successfully to device 127.0.0.1:5555
- Game process ID: 3119 (com.xman.na.gp)
- Game activity: com.q1.ext.Q1UnityActivity

## Files Pulled from Device

### 1. Screenshot
- **File**: `screenshot.png` (2560 x 1440, 2.3MB)
- **Content**: Map view showing:
  - Multiple castle buildings scattered across the map
  - Small white text labels under buildings (player names)
  - Chat at bottom showing player coordinates like "X:573 Y:426"
  - Should contain "DVCxPanda", "Angelbear666", and other player names under castles

### 2. Game Settings
- **File**: `gamesetting.json` (41 bytes)
- **Content**: `{"en_model_base":{"en_ettrkey_lang":"3"}}`
- **Finding**: Just language settings, no player data

### 3. Documents Directory
- **Path**: `/sdcard/Android/data/com.xman.na.gp/files/Documents/`
- **Files Pulled**:
  - `q1_apm_log/log/data/log_2025-10-27-11-28_2.data`
  - `q1_apm_log/log/data/log_2025-11-01-15-31_3.data`
  - `q1_apm_log/log/cache/dth_data_trans_hub_cache.mmap`
  - `q1_apm_log/log/cache/log_data_trans_hub_cache.mmap`
- **Finding**: Binary log files, likely analytics/APM data

### 4. NewCaching Directory Files
- **Path**: `/sdcard/Android/data/com.xman.na.gp/files/NewCaching/`

#### files2.txt (1.9MB)
- **Type**: JSON text data
- **Content**: File manifest with asset paths, hashes, and metadata
- **Format**: List of game assets (art, effects, UI, sounds, etc.)
- **Finding**: No player position data, just asset management

#### ncfiles.txt (644KB)
- **Type**: JSON text data
- **Content**: Another file manifest, similar structure to files2.txt
- **Finding**: No player position data

#### launch_data/ directory
- **Files**:
  - `main5.bytes/__data` (108KB)
  - `mscorlib.bytes/__data` (2.4MB)
  - `newtonsoft.json.bytes/__data`
  - `script.bytes/__data` (14MB)
  - `system.bytes/__data`
  - `system.core.bytes/__data`
- **Type**: Binary data files (.NET assemblies and scripts)
- **Finding**: Game code/libraries, not runtime player data

#### exec_o_0.asset/ directory
- **Files**:
  - `d5ccc485b6b7f1bfbb7c700fdeac2794/__data`
  - `cc9e6ab0b967a7df1c44ff3122af2b9a/__data`
  - `2fdc33b9d412481af10cdd4b576be075/__data`
- **Type**: Binary data
- **Finding**: Unity asset bundles, static game resources

## Search Attempts

### Exact String Searches
```bash
# Searched for player names (case-insensitive)
grep -ri "Angelbear666" .     # No results
grep -ri "manhammer00" .      # No results
grep -ri "DVCxPanda" .        # No results
grep -ri "angelbear" .        # No results
grep -ri "manhammer" .        # No results
```

**Finding**: Player names are NOT stored in any of the pulled files.

### Binary Data Inspection
```bash
strings exec_o_0/*/\__data | grep -i "angelbear"  # No results
```

**Finding**: Player names not in static asset bundles either.

## Cache and Database Checks

### External Cache
- **Path**: `/sdcard/Android/data/com.xman.na.gp/cache/`
- **Status**: Empty directory (no files)

### Internal Databases
```bash
run-as com.xman.na.gp ls /data/data/com.xman.na.gp/databases/
```
- **Status**: Permission denied (app not debuggable)
- **Finding**: Cannot access internal app data

### Logcat Monitoring
```bash
logcat -d | grep -i 'angelbear\|manhammer'
```
- **Finding**: No player names in logcat at time of capture

## Key Findings

### Where Player Data Is NOT:
1. ❌ **Static asset files** (files2.txt, ncfiles.txt)
2. ❌ **Game settings** (gamesetting.json)
3. ❌ **Unity asset bundles** (exec_o_0.asset)
4. ❌ **Launch data** (compiled game code)
5. ❌ **External cache** (empty)
6. ❌ **Logcat output** (at time of check)
7. ❌ **Accessible file system** (searched recursively)

### Where Player Data LIKELY Is:
1. ✅ **Game memory** (runtime data, not persisted to disk)
2. ✅ **Network responses** (received from game servers in real-time)
3. ✅ **Internal database** (/data/data/ - but access denied)
4. ✅ **Rendered on screen** (visible in screenshot under castle icons)

## Analysis: Player Position Data Source

The player positions visible on screen (names under castles) are most likely:

1. **Fetched from Server**: Game makes API calls to get nearby player positions
2. **Stored in Memory**: Data held in RAM while game is running
3. **Rendered Directly**: Unity engine renders text labels from memory
4. **Not Persisted**: Data not saved to accessible files between sessions

### Evidence:
- This is a multiplayer game with real-time map updates
- Player positions change as players move around
- No persistent storage of other players' locations found
- Game uses Unity engine which keeps game state in memory
- Chat messages show coordinates being transmitted

## Potential Approaches to Extract Player Positions

### 1. Memory Dumping (Advanced)
- Use memory forensics tools
- Dump process memory (PID 3119)
- Search memory dump for player data structures
- **Complexity**: High, requires root access

### 2. Network Traffic Capture
- Use packet sniffing (tcpdump, Wireshark)
- Intercept API calls between game and server
- Parse JSON/protobuf responses containing player data
- **Complexity**: Medium-High, may be encrypted

### 3. OCR (Screenshot Analysis)
- Take periodic screenshots
- Use OCR to extract text labels under castles
- Parse player names and infer positions from screen coordinates
- **Complexity**: Medium
- **Accuracy**: Moderate (depends on OCR quality)

### 4. Frida/Game Hacking (Memory Hooking)
- Use Frida to hook Unity functions
- Intercept player position data as it's rendered
- Extract coordinates directly from game memory
- **Complexity**: High, requires reverse engineering

### 5. Accessibility Services
- Create Android accessibility service
- Read UI elements and their positions
- Extract text labels programmatically
- **Complexity**: Medium

## Recommended Next Steps

1. **Network capture**: Monitor game traffic to see player position API calls
2. **Screenshot + OCR**: Automated screenshot capture with text extraction
3. **Check Unity memory**: Use tools like GameGuardian or CheatEngine
4. **Monitor logcat continuously**: Run hunt-player.ps1 script with -Logcat flag

## Files Created in Investigation
- `screenshot.png` - Current game state screenshot
- `gamesetting.json` - Game settings (minimal)
- `files2.txt` - Asset manifest
- `ncfiles.txt` - Asset manifest
- `Documents/` - Analytics logs
- `launch_data/` - Game code bundles
- `exec_o_0/` - Unity asset bundles
- `investigation.md` - This document

## Related Scripts
- `C:\Users\mail\hunt-player.ps1` - PowerShell script for hunting player names in game files
  - Can monitor external storage directories
  - Has logcat filtering capability
  - Case-insensitive search across multiple encodings

---

## Zoom Functionality (WORKING)

### Implementation: `discover_zoom_adb.py`
Successfully implemented zoom in/out using **minitouch** for true multi-touch pinch gestures.

**How it works:**
- Uses minitouch to simulate two-finger pinch gestures via ADB
- Pinch-in (fingers move together) = zoom out
- Pinch-out (fingers move apart) = zoom in
- Takes screenshots and runs OCR after each zoom step

**Requirements:**
- minitouch installed at `/data/local/tmp/minitouch` (use `setup_minitouch.py`)
- ADB connection to BlueStacks

**Usage:**
```bash
python discover_zoom_adb.py
```

**Configuration:**
- Zoom sensitivity: Fingers start 560px apart, end 200px apart (reduced for gentler zoom)
- Movement steps: 3 steps per zoom
- Wait time: 15ms between steps, 1 second after zoom
- Minitouch coordinate space: 32767x32767

**Test Results:**
- ✅ Successfully zooms in/out on game map
- ✅ OCR detects 500-700 chars at close zoom, 0-100 at far zoom
- ✅ Player names readable at close/medium zoom levels

**Failed Approaches (Removed):**
- ADB swipe gestures (too simple, not true pinch)
- Keyboard shortcuts via pyautogui (window activation issues)
- Manual intervention approaches

---

## Optimal Zoom Strategy for Castle Level Detection

### Problem: "Request Too Large" with OCR
**Finding**: Screenshot size remains constant (2560x1440, ~2.3MB), but OCR processing payload varies dramatically with zoom level:
- **Close zoom**: OCR detects 500-700 characters (many castles, many labels)
- **Far zoom**: OCR detects 0-100 characters (few castles, few labels)
- **Issue**: At close zoom, processing full screenshots creates large API payloads causing "request too large" errors

### Goal: Find Optimal Zoom for Castle Level Scanning
**Objective**: Identify the zoom level that is:
1. **Dense** - Shows maximum number of castles per screen
2. **Readable** - Castle level numbers (15, 20, 25, etc.) are OCR-detectable
3. **Efficient** - Allows systematic panning to scan entire global map

### Visual Analysis of Zoom Levels
Based on 40+ screenshots in `zoom_discovery_adb/`:

**Castle Level Numbers Visibility**:
- ✅ **Visible at multiple zoom levels** (initial, zoom_out_10, zoom_out_20, zoom_out_30)
- ✅ Numbers like "20", "17", "15", "21", "28", "25" clearly visible even when zoomed out
- ✅ Contradicts earlier assumption that levels aren't visible when zoomed out

**Visual Density vs Zoom**:
- **Close zoom (initial_00.png)**: 8-10 castles visible, high detail
- **Medium zoom (zoom_out_10.png)**: 5-7 castles visible, numbers still clear
- **Far zoom (zoom_out_30.png)**: 2-3 castles visible, numbers still readable but less dense

**Global Map/Minimap Status**:
- ❓ **Unknown** - No minimap visible in upper right in screenshots examined (initial, zoom_out_10-30)
- Need to check extreme zoom levels (zoom_out_35-40) to see if minimap appears
- Alternative: Use grid-based navigation (already implemented in `find_level20.py`)

### Strategy: Testable Chunks

#### Phase 1: Analyze Existing Zoom Data ✅ COMPLETE
**Goal**: Process 40+ existing screenshots to find optimal zoom level

**Scripts created**:
1. ✅ `test_zoom_ocr.py` - Test OCR on single screenshot
   - Input: One screenshot path
   - Output: Count of castle level numbers detected (15-30 range)
   - Test: Successfully tested on initial_00, zoom_out_15, zoom_out_30

2. ✅ `analyze_all_zooms.py` - Analyze all zoom screenshots
   - Input: All files in `zoom_discovery_adb/`
   - Output: CSV with zoom_level, castle_count, ocr_confidence
   - Result: Analyzed 61 screenshots

**RESULTS**:
- ✅ **OPTIMAL ZOOM LEVEL: zoom_out_10** (+10 steps out from initial)
  - **10 castles detected** (highest density across all zoom levels!)
  - **65.8% OCR confidence** (good accuracy)
  - **Best balance** of coverage and reliability
- Other notable levels:
  - zoom_out_15: Only 2 castles but 90% confidence (too few castles)
  - zoom_out_30: 6 castles, 75.5% confidence (good but less dense)
  - zoom_in levels: Generally poor performance (0-7 castles, lower confidence)

#### Phase 2: Check for Global Minimap ⏳
**Goal**: Determine if minimap exists and at what zoom level

**Scripts to create**:
3. `check_minimap.py` - Detect minimap in screenshots
   - Input: Extreme zoom screenshots (zoom_out_30-40)
   - Output: Report which zoom levels show minimap in upper right
   - Fallback: If no minimap, use grid-based navigation

#### Phase 3: Set Optimal Zoom ⏳
**Goal**: Programmatically zoom game to optimal level

**Scripts to create**:
4. `set_optimal_zoom.py` - Zoom to target level
   - Input: Target zoom level (from Phase 1 analysis)
   - Uses: `discover_zoom_adb.py` minitouch logic
   - Verification: Takes screenshot + runs OCR to confirm

#### Phase 4: Scan Map for Target Level Castles ⏳
**Goal**: Find all castles of a specific level (e.g., level 20)

**Existing tool**: `find_level20.py` already implements this!
- Navigates in grid pattern
- Uses Tesseract OCR to detect "20"
- Saves screenshots + coordinates
- **Action**: Validate it works at optimal zoom level

### Expected Outcomes
1. **Optimal zoom level identified** (likely zoom_out_15-20)
2. **Minimap status documented** (exists or use grid navigation)
3. **Systematic scanning working** (find all level 20+ castles)
4. **Coordinate mapping** (if minimap exists, map screen coords to global coords)

### Related Files
- `discover_zoom_adb.py` - Working zoom control via minitouch
- `find_level20.py` - Grid-based level 20 castle scanner
- `zoom_discovery_adb/` - 40+ zoom screenshots at various levels
- `test_zoom_ocr.py` - (to be created)
- `analyze_all_zooms.py` - (to be created)
- `check_minimap.py` - (to be created)
- `set_optimal_zoom.py` - (to be created)

---

## Castle Detection and Level Extraction (IN PROGRESS)

### Approach: Color-Based Castle Detection + Individual OCR

**Problem**: Need to detect individual castles on map and read their level numbers (1-30).

**Solution**:
1. Use OpenCV color detection (HSV) to find white/gray castle icons
2. Extract cutout of castle + number label below
3. OCR each cutout individually for better accuracy

### Implementation: `detect_castles_and_numbers.py`

**Castle Detection Parameters**:
- HSV color range: [0,0,180] to [180,40,255] (white/gray castles)
- Size filter: 35-70px width and height
- Aspect ratio: 0.7-1.4 (roughly square)
- Area filter: >500px² (exclude small specks)
- Edge margin: 100px (exclude UI elements at screen edges)

**Cutout Extraction**:
- Start: Top of castle (cy)
- Height: Castle height + 50px (ch + 50) to include full label
- Width: Castle width + 10px (cw + 10) with 5px left margin
- Saves: Original cutout only (no scaled versions)

**OCR Configuration**:
- Scale: 4x upscaling before OCR (not saved to disk)
- PSM mode: 8 (single word/number)
- Character whitelist: 0-9 only
- Validation: Level must be 1-30

**Current Results** (as of last run):
- Detected: 32 castles (filtered from 39 after edge exclusion)
- Successfully OCR'd: 13 castles (40.6% success rate)
- Issue: OCR incorrectly reading many numbers as "2"

**Known Issues**:
- OCR accuracy varies (many false reads as "Level 2")
- Need better OCR configuration or preprocessing
- Confidence scores low (15-73%)

**Files Generated**:
- `rightnow_castle_detection.png` - Debug image showing detected castles
- `castle_cutouts/castle_XXX_x_y.png` - Individual castle cutouts

### Related Scripts:
- `detect_castles_and_numbers.py` - Main detection script
- `goto_zoom_level.py` - Navigate to specific zoom level using minitouch

**Next Steps**:
- Improve OCR accuracy (currently 40.6% success rate)
- Test different PSM modes and preprocessing
- Build castle database with coordinates and levels
- Scan entire map by panning and collecting all castles

---

## OCR Testing and Failure Analysis (2025-11-03)

### Comprehensive OCR Testing Results

After extensive testing of multiple OCR solutions, results were disappointing:

**Test Setup**:
- 32 castle cutouts with ground truth labels (manually verified with Claude vision API)
- Ground truth saved in `castle_database.csv`
- Test scripts: `test_ocr_methods.py`, `test_paddle_rec_only.py`, `test_easyocr_improved.py`

**Results**:
1. **EasyOCR (original)**: 43.8% accuracy (14/32) - BEST PERFORMER
   - Method: 3x scaling, allowlist=0-9
   - Time: 0.111s per image
   - Preprocessing: Simple PIL resize

2. **PaddleOCR (full pipeline)**: 40.6% accuracy (13/32)
   - Method: Default detection + recognition
   - Time: 1.290s per image (much slower)
   - Issue: Detection stage failing on small isolated digits

3. **Tesseract (optimized)**: 28.1% accuracy (9/32)
   - Method: Multiple PSM modes, 6x scaling
   - Configuration: `--psm 7/8/10 --oem 3 -c tessedit_char_whitelist=0123456789`
   - Issue: Low confidence on small text

4. **PaddleOCR (rec-only)**: 18.8% accuracy (6/32)
   - Method: TextRecognition class, Otsu preprocessing
   - Attempted to bypass detection stage
   - Issue: Worse than full pipeline

5. **EasyOCR + Otsu preprocessing**: 9.4% accuracy (3/32) - WORST
   - Method: Otsu thresholding before OCR
   - Issue: Preprocessing destroyed text quality

**Key Finding**: Traditional OCR is FAILING at a task simpler than MNIST digit recognition!
- Castle level numbers are clear, high-contrast text (black on white pill)
- Constrained domain: Only numbers 1-30
- Yet best accuracy is only 43.8%

### Decision: Build Custom CNN

**Rationale**:
- OCR is overengineered for this simple task
- We have 32 labeled samples (can expand with data collection)
- Problem is simpler than MNIST (only 30 classes vs 10)
- Expected CNN accuracy: 90-95%+

**Plan**:
1. **Data Collection** (IN PROGRESS):
   - Calibrate zoom level to match original screenshot
   - Pan around map, capture 10-20 screenshots
   - Run castle detection on all screenshots
   - Label with Claude vision API (ground truth)
   - Expected: 100-300+ samples total

2. **Dataset Preparation**:
   - Split: 70% train / 15% validation / 15% test
   - Data augmentation: rotation, brightness, noise
   - Target: ~100 samples per class if possible

3. **CNN Architecture**:
   - Simple 3-4 layer CNN (LeNet/MobileNet style)
   - Input: Grayscale 64x32 label region
   - Output: 30 classes (levels 1-30)
   - Loss: CrossEntropyLoss
   - Optimizer: Adam

4. **Integration**:
   - Save model weights
   - Update `detect_castles_and_numbers.py`
   - Replace OCR with CNN inference
   - Target: <10ms per prediction

### Current Status: Zoom Calibration (BLOCKED)

**Goal**: Calibrate game zoom to match original screenshot (where 32 castles were found)

**Method**: Automated pinch gestures via adb to zoom in/out until castle sizes match

**Issue**: Zoom gestures not working
- Created `auto_calibrate_zoom.py` to automatically adjust zoom
- Script runs indefinitely but zoom doesn't change
- Verified we're on world map view (not home base)
- Suspect: Pinch gesture parameters may be incorrect for this zoom level

**Scripts Created**:
- `calibrate_zoom.py` - Manual zoom checker (compares castle sizes)
- `auto_zoom.py` - Zoom in/out N steps
- `auto_calibrate_zoom.py` - Fully automated calibration loop (BLOCKED)

**Next Steps**:
1. Debug pinch gesture parameters manually
2. Test zoom in/out directly via adb to verify gestures work
3. Once gestures work, resume automated calibration
4. Proceed with data collection plan

### Files from OCR Testing Phase

**Test Scripts**:
- `test_ocr_methods.py` - Tests Tesseract, EasyOCR, PaddleOCR
- `test_paddle_rec_only.py` - PaddleOCR recognition-only mode
- `test_easyocr_improved.py` - EasyOCR with Otsu preprocessing
- `test_easyocr_scales.py` - Test different scaling factors
- `template_matching_ocr.py` - Attempted template matching (0% accuracy)

**Data Files**:
- `castle_database.csv` - Ground truth labels (32 castles, 100% accurate)
- `ocr_performance.csv` - OCR test results comparison
- `castle_cutouts/` - 32 castle cutouts with labels
- `dataset/` - Folder for expanded dataset (in progress)

**Debug Images**:
- `OCR_INPUT_*.png` - Various preprocessed images sent to OCR
- `debug_*.png` - Preprocessing pipeline outputs
- `test_scaled*.png` - Scaled versions for testing

---

**Last Updated**: 2025-11-03
**Status**: OCR testing complete - all methods failed (<50% accuracy). Decided to build custom CNN instead. Currently blocked on zoom calibration for data collection. Need to debug adb pinch gestures before proceeding.
