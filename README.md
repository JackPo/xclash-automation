# XClash - Clash of Clans Automation

Automation scripts for Clash of Clans using BlueStacks Android emulator.

## 🚀 Quick Start (Main Scripts)

### Handshake Auto-Clicker
The primary active script - auto-clicks handshake icons every 3 seconds:

**Option 1: Daemon (runs continuously)** ⭐ EASIEST
```bash
python scripts/handshake_daemon.py

# Custom interval (e.g., every 5 seconds)
python scripts/handshake_daemon.py --interval 5

# Press Ctrl+C to stop
```

**Option 2: One-shot (run via Windows Task Scheduler)**
```bash
python scripts/handshake_simple.py
```

Setup Windows Task Scheduler:
1. Open Task Scheduler
2. Create Basic Task: "Clash Handshake Clicker"
3. Trigger: Repeat every 3 seconds
4. Action: `C:\Users\mail\AppData\Local\Programs\Python\Python312\python.exe`
5. Arguments: `C:\Users\mail\xclash\scripts\handshake_simple.py`
6. Start in: `C:\Users\mail\xclash`

### Setup BlueStacks (One-time)
Configure BlueStacks to 4K resolution:
```bash
python scripts/setup_bluestacks.py
```

## 📁 Project Structure

```
xclash/
├── scripts/              # Main executable scripts
│   ├── handshake_daemon.py         # Daemon - runs continuously ⭐
│   ├── handshake_simple.py         # One-shot clicker (Task Scheduler)
│   ├── setup_bluestacks.py         # Configure BlueStacks to 4K
│   ├── run_handshake_clicker.py    # Config-based handshake clicker
│   └── benchmark_handshake_timing.py
│
├── utils/                # Reusable utility modules
│   ├── adb_helper.py              # ADB operations (screenshot, tap, etc.)
│   ├── handshake_icon_matcher.py  # Handshake detection
│   ├── view_detection.py          # World/Town view switching
│   ├── minimap_navigator.py       # Minimap & zoom control
│   ├── windows_screenshot_helper.py
│   ├── button_matcher.py
│   ├── game_utils.py
│   ├── send_zoom.py               # Zoom in/out (Shift+A/Z)
│   └── send_arrow_proper.py       # Arrow key input
│
├── deprecated/           # Old/test scripts (80+ archived files)
│
└── templates/            # Template images for matching
    └── ground_truth/     # Production templates (4K resolution)
        ├── handshake_icon_4k.png
        └── minimap_base_4k.png
```

## ⚙️ Configuration

- **ADB Path:** `C:\Program Files\BlueStacks_nxt\hd-adb.exe`
- **Device:** Auto-detected (usually `emulator-5554`)
- **Resolution:** 3840x2160 (4K) - **ALL templates are 4K**
- **Python:** `C:\Users\mail\AppData\Local\Programs\Python\Python312\python.exe`

## 🛠️ Development Notes

- **All coordinates are 4K (3840x2160)** - don't use other resolutions
- **Use `utils/adb_helper.py`** for all ADB operations
- **Templates go in `templates/ground_truth/`** with `_4k.png` suffix
- **Deprecated code in `deprecated/`** - reference only, don't modify

---

# Archive: Old Player Finder Documentation

<details>
<summary>Click to expand old three-phase player finder docs (mostly deprecated)</summary>

## 🎯 Original Project Goal (Archived)

Find specific players on the XClash world map using a smart three-phase approach:
1. **Phase 1**: Interactive calibration to discover game mechanics
2. **Phase 2**: Scan map for all Level 20 castles (filter by level)
3. **Phase 3**: Check player names only at Level 20 locations (targeted search)

## 📋 Current Status

**PHASE 1: CALIBRATION (IN PROGRESS)**

### ✅ Completed Setup
- **Tesseract OCR v5.4.0** installed and configured
- **Python 3.12** environment with pytesseract + Pillow
- **ADB connection** to BlueStacks (127.0.0.1:5556)
- **Interactive calibration tool** created with 4 discovery modes
- **Continuous logging system** to prevent state loss
- **Documentation** - PHASE1_CALIBRATION.md with full details

### 🎯 Current Focus: Phase 1 Calibration

**What we're doing NOW:**
- Interactive discovery of UI elements (World toggle, zoom buttons)
- Testing zoom levels to find which shows castle levels vs player names
- Measuring map boundaries (swipes to reach edges)
- Documenting all findings continuously

**Why calibration first?**
- Can't automate what we don't understand
- Need to know: zoom mechanics, map size, UI locations
- Building knowledge base for future automation
- All findings logged so we never lose progress

### 🚧 TODO (After Calibration)
- Complete Phase 1 interactive calibration session
- Generate map_config.json from findings
- Implement Phase 2 automated Level 20 scanner
- Implement Phase 3 player name checker

## 🚀 Quick Start - Phase 1 Calibration

### Prerequisites (Already Completed ✅)

- ✅ Windows 10/11
- ✅ BlueStacks running XClash on 127.0.0.1:5556
- ✅ Python 3.12 installed
- ✅ Tesseract OCR v5.4.0 installed
- ✅ pytesseract + Pillow packages installed

### Start Calibration

```bash
python calibrate_interactive.py
# or double-click: calibrate_phase1.bat
```

### What Happens

You'll enter an interactive menu with 4 modes:
1. **Discovery** - OCR current screen, find UI elements
2. **Zoom Explorer** - Test zoom levels, document what's visible
3. **Navigation Test** - Measure map size with swipes
4. **Button Finder** - Locate buttons by testing clicks
5. **Quit** - Save findings to calibration_findings/

### Example Session

```
Select mode (1-5): 1
[Discovery Mode]
📸 Taking screenshot...
✅ Found 47 text elements

📍 BOTTOM RIGHT:
  [85%] at (2320, 1350): 'WORLD'
  [82%] at (2100, 1300): 'Alliance'

🔍 Important keywords found:
  - WORLD at (2320, 1350)

Select mode (1-5): 2
[Zoom Explorer Mode]
Instructions: Manually adjust zoom, type 'capture'...

Zoom Level 1 > capture
📸 Capturing...
❓ What can you see? castle levels
✅ Logged zoom level 1

Select mode (1-5): 5
💾 Saving findings...
✅ Final findings saved to: calibration_findings/final_findings.json
```

### Output

All discoveries saved to `calibration_findings/`:
- `calibration_log.txt` - Timestamped main log
- `zoom_levels_findings.txt` - Zoom documentation
- `navigation_findings.txt` - Map measurements
- `ui_elements_findings.txt` - Button locations
- `final_findings.json` - Structured summary
- `screenshots/` - Visual evidence

### Next Steps After Calibration

Once calibration complete:
1. Review findings in `calibration_findings/`
2. Extract parameters to create `map_config.json`
3. Move to Phase 2 (automated Level 20 scanning)

## 📁 Project Structure

```
xclash/
├── 🎯 PHASE 1: CALIBRATION (CURRENT)
│   ├── calibrate_interactive.py     ★ Main interactive tool
│   ├── calibrate_phase1.bat         Quick launcher
│   └── PHASE1_CALIBRATION.md        Complete guide
│
├── 🔮 PHASE 2: Level 20 Scanner (Future)
│   ├── find_level20.py              Automated Level 20 finder
│   ├── find_level20.bat
│   └── LEVEL20_FINDER_README.md
│
├── 🔮 PHASE 3: Player Name Checker (Future)
│   └── find_player_at_level20.py    Check names at Level 20 locations
│
├── 🔧 Supporting Code
│   ├── find_player.py               ADB, Config, OCR base classes
│   ├── game_utils.py                World view, UI helpers
│   └── test_config.py               Testing utilities
│
├── 📋 Documentation
│   ├── README.md                    ★ This file - project overview
│   ├── PHASE1_CALIBRATION.md        ★ Phase 1 complete guide
│   ├── LEVEL20_FINDER_README.md     Phase 2 guide (future)
│   ├── PLAYER_FINDER_README.md      Phase 3 guide (future)
│   └── investigation.md             Research notes
│
├── ⚙️ Configuration (Generated)
│   └── map_config.json              After Phase 1 complete
│
└── 📊 Output (Generated)
    └── calibration_findings/        ★ Phase 1 output
        ├── calibration_log.txt
        ├── zoom_levels_findings.txt
        ├── navigation_findings.txt
        ├── ui_elements_findings.txt
        ├── final_findings.json
        └── screenshots/

★ = Focus here for Phase 1
```

## 🔧 Three-Phase Architecture

```
╔══════════════════════════════════════════════════════════════╗
║ PHASE 1: CALIBRATION (Interactive Discovery)                ║
║ Current Status: Tool created, ready to run                   ║
╠══════════════════════════════════════════════════════════════╣
║ Human + Tool → Explore game mechanics                        ║
║              → Test zoom levels                              ║
║              → Measure map boundaries                        ║
║              → Locate UI elements                            ║
║                                                              ║
║ Output: calibration_findings/ + final_findings.json         ║
╚══════════════════════════════════════════════════════════════╝
                            ↓
╔══════════════════════════════════════════════════════════════╗
║ PHASE 2: FIND ALL LEVEL 20 CASTLES (Automated)              ║
║ Status: Not started (needs Phase 1 complete)                 ║
╠══════════════════════════════════════════════════════════════╣
║ Load calibration config                                      ║
║ → Set zoom to "castle level visible"                         ║
║ → Grid scan entire map                                       ║
║ → OCR to find "20"                                           ║
║ → Save screenshots + coordinates                             ║
║                                                              ║
║ Output: {RUN_ID}_level20/ with all Level 20 locations       ║
╚══════════════════════════════════════════════════════════════╝
                            ↓
╔══════════════════════════════════════════════════════════════╗
║ PHASE 3: FIND SPECIFIC PLAYER (Automated)                   ║
║ Status: Not started (needs Phase 2 complete)                 ║
╠══════════════════════════════════════════════════════════════╣
║ Load Level 20 results from Phase 2                           ║
║ For each Level 20 coordinate:                                ║
║   → Navigate to location                                     ║
║   → Zoom to "player name visible"                            ║
║   → OCR for specific player name                             ║
║   → If found → REPORT & EXIT                                 ║
║                                                              ║
║ Output: Player location or "not found"                       ║
╚══════════════════════════════════════════════════════════════╝
```

### Why Three Phases?

**The Problem**: Can't see both castle levels AND player names at same zoom.

**The Solution**:
- Phase 1: Learn how the game works (one-time)
- Phase 2: Filter by castle level (reduces search by ~90%)
- Phase 3: Check names only on Level 20s (targeted search)

Much more efficient than scanning entire map at name-visible zoom!

## 🔍 How the Scanning Works

### Coordinate System

```
(0,0) ─────── (0,9)
  │             │
  │    MAP      │
  │             │
(7,0) ─────── (7,9)
```

- Grid based on screen-widths × screen-heights
- Each position has (row, col) coordinates
- Zigzag pattern for efficiency:
  - Row 0: Left → Right
  - Row 1: Right → Left
  - Row 2: Left → Right
  - etc.

### OCR Detection

**Zoomed Out (Phase 1):**
- Can see: Castle levels ("20", "19", etc.)
- Cannot see: Player names

**Zoomed In (Phase 2):**
- Can see: Player names
- Cannot see: Multiple castles

This is why we need two phases!

## 📊 Configuration

### BlueStacks Connection

```python
# In find_player.py Config class
ADB_PATH = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
DEVICE = "127.0.0.1:5556"  # Your actual port
```

### Map Boundaries (avoid UI overlap)

```python
MAP_LEFT = 400
MAP_RIGHT = 2160
MAP_TOP = 200
MAP_BOTTOM = 1240
```

### Timing Adjustments

```python
SCROLL_DURATION = 300           # Swipe animation speed (ms)
DELAY_AFTER_SWIPE = 0.8        # Wait for map to settle (sec)
DELAY_AFTER_SCREENSHOT = 0.3   # Wait after capture (sec)
```

## 🐛 Troubleshooting

### "unable to connect to 127.0.0.1:5555"

**Fix:** Update device port in `find_player.py`:
```python
DEVICE = "127.0.0.1:5556"  # Your actual port
```

Check with: `adb devices`

### "Map config not found"

**Fix:** Run calibration first:
```bash
python calibrate_map.py
```

### Not Finding Level 20s

1. **Check zoom level** - Must see castle level numbers (not names)
2. **Test OCR:** `python test_config.py ocr`
3. **Verify World view:** `python game_utils.py`

### OCR Not Working

1. Check Tesseract path:
```python
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

2. Test: `"C:\Program Files\Tesseract-OCR\tesseract.exe" --version`

## 📚 Documentation Files

- **README.md** (this file) - Project overview
- **LEVEL20_FINDER_README.md** - Detailed Phase 1 usage guide
- **PLAYER_FINDER_README.md** - Original full-map scanner
- **investigation.md** - Research notes on game data

## 🎮 Game Requirements

### Before Calibration
1. ✅ BlueStacks running
2. ✅ XClash open
3. ✅ On World map (or script will switch)
4. ✅ Map can be at any position

### Before Level 20 Scan
1. ✅ Calibration completed (`map_config.json` exists)
2. ✅ BlueStacks running with XClash
3. ✅ World map visible
4. ⚠️ **Zoom level set to show castle levels** (manual for now)

## 💾 Git Workflow

```bash
# Commit current work
git add .
git commit -m "feat: Level 20 castle finder with calibration system

- Add map calibration tool (one-time setup)
- Implement Phase 1: Level 20 detection
- Add World view detection and auto-switching
- Create coordinate tracking system
- Add comprehensive documentation
- Update device port to 5556"

# Future commits
git commit -m "feat: Add Phase 2 player name detection"
git commit -m "fix: Improve OCR accuracy for castle levels"
```

## 🔬 Technical Details

### OCR Engine
- **Tesseract 5.4.0** (open-source OCR)
- Confidence threshold: 30% (configurable)
- Processes full screenshots (not icon-based)

### ADB Commands Used
```bash
# Screenshot
adb shell screencap -p /sdcard/screenshot.png
adb pull /sdcard/screenshot.png

# Swipe (for scrolling)
adb shell input swipe x1 y1 x2 y2 duration

# Tap (for UI elements)
adb shell input tap x y
```

### Screen Resolution
- BlueStacks default: 2560 × 1440
- Adjustable in Config if different

## ⚡ Performance

- **Calibration**: ~5-10 minutes (one-time)
- **Level 20 scan**: ~2-3 minutes for 80-100 views
- **Disk space per run**: ~5-15MB (depends on findings)
- **OCR speed**: ~1-2 seconds per screenshot

## 🎯 Next Steps

1. **Test calibration** - Run end-to-end with real game
2. **Fine-tune UI positions** - World toggle, zoom buttons
3. **Implement auto-zoom** - Detect and set optimal zoom level
4. **Phase 2** - Navigate to Level 20s and check names
5. **Optimize** - Parallel OCR, faster navigation

## 📞 Support

Check these first:
1. `python test_config.py ocr` - Test OCR
2. `python test_config.py nav` - Test navigation
3. `python game_utils.py` - Test World view detection
4. `adb devices` - Verify connection

## 📝 Version History

- **v0.1** - Initial player finder (full map scan)
- **v0.2** - Two-phase approach with Level 20 filtering
- **v0.3** - Map calibration system (current)
- **v0.4** - World view detection and game utilities
- **v1.0** - (Future) Complete Phase 2 implementation

## 🤝 Contributing

This is a personal project for automating game tasks. Feel free to adapt for your own use cases.

## ⚠️ Disclaimer

This tool is for educational and personal use. Use responsibly and in accordance with game terms of service.

---

## 📝 Summary: Where We Are Now

### ✅ What's Ready

**Phase 1 Interactive Calibration Tool:**
- 4 discovery modes (Discovery, Zoom Explorer, Navigation Test, Button Finder)
- Continuous logging system (never lose progress)
- Screenshot organization with metadata
- All findings saved to calibration_findings/

**Documentation:**
- `README.md` - Project overview (this file)
- `PHASE1_CALIBRATION.md` - Complete Phase 1 guide
- All learnings and architecture documented

**Environment:**
- BlueStacks connected (127.0.0.1:5556)
- Tesseract OCR v5.4.0 installed
- Python 3.12 + packages ready

### 🎯 Next Step: Run Calibration

```bash
python calibrate_interactive.py
```

This will interactively guide you through discovering:
- UI element locations (World toggle, zoom buttons)
- Zoom level mechanics (which zoom for levels vs names)
- Map boundaries (swipes to edges)
- Navigation parameters

**All findings are logged automatically** - you can stop and resume anytime.

### 🔮 After Calibration

Once Phase 1 complete, we'll:
1. Review `calibration_findings/final_findings.json`
2. Create `map_config.json` with parameters
3. Build Phase 2 automated Level 20 scanner
4. Build Phase 3 player name checker

### 🏗️ Design Philosophy

**"Never lose state"** - Everything documented continuously
**"No assumptions"** - Pure discovery through experimentation
**"Human-in-loop"** - Interactive for calibration, automated for scanning
**"Build incrementally"** - Each phase builds on previous findings

---

**Ready to start? Run `python calibrate_interactive.py` 🎯**
</details>
