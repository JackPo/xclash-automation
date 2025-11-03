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

**Last Updated**: 2025-11-02
**Status**: Player data confirmed visible on screen but NOT in accessible file system. Likely stored in memory/network only. Zoom functionality working with minitouch.
