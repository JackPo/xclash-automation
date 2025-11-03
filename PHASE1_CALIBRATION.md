# PHASE 1: CALIBRATION - Interactive Discovery

**Status: IN PROGRESS**
**Last Updated: 2025-11-02**

---

## Overview

This is the foundational phase where we discover how XClash's world map works through interactive experimentation. We're building the knowledge base that all future automation will rely on.

### The Big Picture: Three-Phase Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: CALIBRATION (Current)                              │
│ - Discover UI elements                                       │
│ - Find zoom controls and levels                              │
│ - Measure map boundaries                                     │
│ - Document what's visible at each zoom                       │
│ → Output: calibration_findings/ + final_findings.json       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: FIND LEVEL 20 CASTLES                              │
│ - Load calibration data                                      │
│ - Set zoom to "castle level visible" mode                    │
│ - Grid scan entire map                                       │
│ - OCR to find "20" (castle level)                            │
│ - Save screenshots + coordinates of all Level 20s            │
│ → Output: {RUN_ID}_level20/ + results.json                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: FIND SPECIFIC PLAYER                               │
│ - Load Level 20 results from Phase 2                         │
│ - For each Level 20 coordinate:                              │
│   - Navigate to location                                     │
│   - Zoom to "player name visible" mode                       │
│   - OCR for specific player name                             │
│   - If found → REPORT & EXIT                                 │
│ → Output: Player location or "not found"                     │
└─────────────────────────────────────────────────────────────┘
```

### Why This Matters

**The Core Problem**: You can't see both castle levels AND player names at the same zoom level.

**The Solution**:
1. Filter by castle level first (Phase 2) - reduces search space by ~90%
2. Then check player names only on Level 20 castles (Phase 3) - targeted search

This is much more efficient than scanning the entire map at name-visible zoom.

---

## Current Status & Learnings

### ✅ What We Know

**System Setup:**
- BlueStacks running on `127.0.0.1:5556` (not 5555!)
- ADB connection: `C:\Program Files\BlueStacks_nxt\hd-adb.exe`
- Screen resolution: 2560 × 1440
- XClash package: `com.xman.na.gp`
- Tesseract OCR v5.4.0 installed
- Python 3.12 with pytesseract + Pillow

**Key Insights:**
- **Zoom Trade-off**: Castle levels visible when zoomed out, player names visible when zoomed in (MUTUALLY EXCLUSIVE)
- **World vs Town**: Lower right button toggles between views (says "WORLD" when in Town, says "TOWN" when in World - paradoxical!)
- **Map Persistence**: Map layout is static but player positions change
- **OCR Viability**: Tesseract can read both numbers (castle levels) and text (player names) with good accuracy
- **Coordinate System Needed**: Must establish reproducible grid for navigation

**Previous Investigation:**
- Already tried file-based approach (hunt-player.ps1) - player positions NOT in accessible files
- Data exists only in memory and network traffic
- OCR approach confirmed as viable solution

### ❓ What We Need to Discover (Phase 1 Goals)

#### Critical Questions:

1. **World View Detection**
   - Where exactly is World/Town toggle button?
   - How to programmatically detect current view?
   - Can we OCR the button text reliably?

2. **Zoom Mechanics**
   - Where are zoom in/out controls? (Buttons? Pinch gesture coordinates?)
   - How many discrete zoom levels exist?
   - Which zoom level for castle levels?
   - Which zoom level for player names?
   - Can we detect current zoom level?

3. **Map Navigation**
   - Starting from random position, how many swipes to reach:
     - Left edge?
     - Right edge?
     - Top edge?
     - Bottom edge?
   - Map dimensions in "screen-widths"?
   - Optimal swipe distance (pixels) for 70-80% overlap?

4. **OCR Validation**
   - At "castle level" zoom: What does OCR detect?
   - At "player name" zoom: What does OCR detect?
   - Confidence thresholds?
   - False positive patterns?

5. **UI Interference**
   - What UI elements block the map?
   - Safe navigation area coordinates?
   - Do menus auto-dismiss or need closing?

---

## Goal

Learn everything about the XClash game interface through interactive experimentation. Document all findings so we never lose this knowledge.

### What We're Discovering

#### 1. World Map View
- ❓ Where is the World/Town toggle button?
- ❓ How to detect if we're in World view?
- ❓ Button coordinates?

#### 2. Zoom Controls
- ❓ Where are zoom in/out buttons?
- ❓ How many zoom levels exist?
- ❓ At each zoom level, what can we see?
  - **Zoomed out**: Castle levels visible? Names visible?
  - **Medium zoom**: What's visible?
  - **Zoomed in**: Names visible? Levels visible?
- ❓ Best zoom for finding Level 20s?
- ❓ Best zoom for reading player names?

#### 3. Map Navigation
- ❓ How many swipes to reach each edge?
- ❓ Map dimensions (width × height in screen-widths)?
- ❓ Optimal swipe distance?

#### 4. UI Elements
- ❓ What text appears in different views?
- ❓ Where are important buttons?
- ❓ What interferes with OCR?

### Quick Start

```bash
python calibrate_interactive.py
# or double-click: calibrate_phase1.bat
```

### Calibration Modes

#### Mode 1: Discovery
**Purpose**: OCR current screen and identify UI elements

**What it does**:
- Takes screenshot
- Runs OCR on full screen
- Shows all detected text with coordinates
- Groups by screen region (top-left, top-right, etc.)
- Highlights important keywords (WORLD, TOWN, ZOOM, etc.)

**Use when**: Starting fresh, need to see what's on screen

#### Mode 2: Zoom Explorer
**Purpose**: Document what's visible at each zoom level

**Workflow**:
1. Manually adjust zoom in game
2. Type `capture` to screenshot and OCR
3. Tell the tool what you can see (levels? names? both?)
4. Repeat for each zoom level
5. Type `done` when finished

**What it logs**:
- OCR text at each zoom level
- Numbers detected (castle levels)
- Your description of what's visible
- Screenshots with metadata

**Use when**: Need to understand zoom mechanics

#### Mode 3: Navigation Test
**Purpose**: Measure map size and test navigation

**Commands**:
```
left N    - Swipe left N times
right N   - Swipe right N times
up N      - Swipe up N times
down N    - Swipe down N times
record DIRECTION COUNT - Record edge reached
ss        - Take screenshot
done      - Finish
```

**Workflow**:
1. Swipe in a direction until you reach edge
2. Count the swipes
3. Record: `record left 15`
4. Repeat for all four directions

**What it logs**:
- Swipes to each edge
- Navigation parameters

**Use when**: Measuring map boundaries

#### Mode 4: Button Finder
**Purpose**: Locate UI buttons by testing clicks

**Commands**:
```
click X Y [LABEL]        - Test click at coordinates
record ELEMENT X Y       - Save button location
ss                       - Screenshot
done                     - Finish
```

**Workflow**:
1. Click coordinates to test: `click 2350 1350 world_toggle`
2. Check before/after screenshots
3. If correct, record: `record world_toggle 2350 1350`
4. Repeat for other buttons

**What it logs**:
- Button locations with coordinates
- Before/after screenshots

**Use when**: Finding World toggle, zoom buttons, etc.

### Output Files

All findings saved to `calibration_findings/`:

```
calibration_findings/
├── calibration_log.txt          # Main log with timestamps
├── zoom_levels_findings.txt     # Zoom level details
├── navigation_findings.txt      # Navigation measurements
├── ui_elements_findings.txt     # Button locations
├── final_findings.json          # Structured summary
└── screenshots/                 # All test screenshots
    ├── 001_discovery.png
    ├── 002_zoom_level_1.png
    ├── 003_zoom_level_2.png
    └── ...
```

### Calibration Workflow

**Suggested Order**:

1. **Discovery** - Get oriented, see what's on screen
2. **Button Finder** - Find World toggle, verify we're on World map
3. **Zoom Explorer** - Test all zoom levels, document visibility
4. **Navigation Test** - Measure map size
5. **Final Review** - Check all findings, quit to save

### Example Session

```
=== Starting Calibration ===

Mode 1: Discovery
> Takes screenshot
> Found: "WORLD" at (2300, 1350)
> Found: "ALLIANCE" at (100, 150)
> Found: Numbers: 20, 18, 15 (castle levels visible!)

Mode 2: Zoom Explorer
> Manually zoom out fully
> capture
> "What can you see?" → "castle levels only"
> Logged: zoom level 1 = castle levels visible

> Manually zoom in
> capture
> "What can you see?" → "player names visible"
> Logged: zoom level 2 = player names visible

Mode 3: Navigation Test
> left 20
> "At edge? yes"
> record left 20
> Logged: left edge = 20 swipes

Mode 4: Button Finder
> click 2350 1350 world
> Check screenshots - map changed? yes!
> record world_toggle 2350 1350
> Logged: world_toggle at (2350, 1350)

Mode 5: Quit
> Save final_findings.json
> ✅ Complete!
```

### Expected Findings

By the end of Phase 1, we should know:

```json
{
  "world_toggle": {"x": 2350, "y": 1350},
  "zoom_in": {"x": ???, "y": ???},
  "zoom_out": {"x": ???, "y": ???},
  "zoom_levels": {
    "level_1": {
      "description": "fully zoomed out",
      "castle_levels_visible": true,
      "player_names_visible": false
    },
    "level_2": {
      "description": "zoomed in",
      "castle_levels_visible": false,
      "player_names_visible": true
    }
  },
  "navigation": {
    "left_edge": 15,
    "right_edge": 15,
    "top_edge": 10,
    "bottom_edge": 10
  }
}
```

### Tips

1. **Don't rush** - Take time to explore each mode
2. **Take notes** - Tool logs automatically, but add your observations
3. **Screenshot everything** - All screenshots saved for review
4. **Test multiple times** - Verify findings are consistent
5. **Document unknowns** - If something unclear, note it in logs

### Troubleshooting

**OCR not detecting text?**
- Check zoom level - text might be too small
- Try Discovery mode to see what OCR finds
- Check screenshot quality in calibration_findings/screenshots/

**Swipes not working?**
- Verify BlueStacks is running
- Check device connection: `adb devices` should show 127.0.0.1:5556
- Map area might be blocked by UI

**Can't find buttons?**
- Use Discovery mode first to see text locations
- Try Button Finder with different coordinates
- Check screenshots to see what changed

### Next Phases

**Phase 2: Find Level 20s** (After calibration complete)
- Use calibration data
- Scan map at correct zoom level
- Find all Level 20 castles

**Phase 3: Find Players** (After Phase 2)
- Navigate to Level 20 locations
- Zoom to see names
- Search for specific player

### Current Status Log

*Document your findings here as you go:*

```
=== Session: 2025-11-02 ===

STATUS: Phase 1 interactive tool created, ready for testing

Discovery Mode:
- Tool ready to OCR screen and find UI elements
- Will detect keywords: WORLD, TOWN, ZOOM, etc.
- TODO: Run first discovery scan

Zoom Explorer:
- Tool ready to capture each zoom level
- TODO: Manually test zoom levels and document
- Expected: Level visible when zoomed out, names when zoomed in

Navigation:
- Tool ready with interactive swipe commands
- TODO: Measure swipes to each edge
- Current estimates (unverified):
  - Horizontal scroll: 1500px
  - Vertical scroll: 800px
  - Initial guesses: 15 left, 15 up to reach top-left

UI Elements:
- TODO: Use Button Finder to locate:
  - World/Town toggle (estimated: 2350, 1350)
  - Zoom in button
  - Zoom out button

Next Steps:
1. Run calibrate_interactive.py
2. Start with Discovery mode
3. Use Button Finder for World toggle
4. Use Zoom Explorer to document zoom levels
5. Use Navigation Test to measure map
6. Save final_findings.json
```

---

## Technical Implementation

### Tools Created

**Primary Tool:**
- `calibrate_interactive.py` - Interactive calibration with 4 modes
  - Mode 1: Discovery (OCR screen, find UI)
  - Mode 2: Zoom Explorer (test zoom levels)
  - Mode 3: Navigation Test (measure map)
  - Mode 4: Button Finder (locate buttons)

**Supporting Files:**
- `calibrate_phase1.bat` - Quick launcher
- `PHASE1_CALIBRATION.md` - This documentation
- `find_player.py` - Contains Config and ADBController classes
- `game_utils.py` - World view detection helpers (for future phases)

**Logging System:**
- `CalibrationLogger` class handles all documentation
- Continuous logging prevents state loss
- All findings timestamped
- Screenshots organized with metadata

### File Structure

```
xclash/
├── Phase 1 (Current)
│   ├── calibrate_interactive.py     # Main tool
│   ├── calibrate_phase1.bat         # Launcher
│   └── PHASE1_CALIBRATION.md        # This file
│
├── Phase 2 (Future - after calibration)
│   ├── find_level20.py              # Scan for Level 20s
│   ├── find_level20.bat
│   └── LEVEL20_FINDER_README.md
│
├── Phase 3 (Future - after Phase 2)
│   └── find_player_at_level20.py    # Check names at Level 20 locations
│
├── Supporting Code
│   ├── find_player.py               # ADB, Config, OCR classes
│   ├── game_utils.py                # World view, UI helpers
│   └── test_config.py               # Testing utilities
│
├── Configuration (Generated)
│   └── map_config.json              # After Phase 1 complete
│
└── Output (Generated during runs)
    ├── calibration_findings/        # Phase 1 output
    │   ├── calibration_log.txt
    │   ├── zoom_levels_findings.txt
    │   ├── navigation_findings.txt
    │   ├── ui_elements_findings.txt
    │   ├── final_findings.json
    │   └── screenshots/
    │
    └── {RUN_ID}_level20/            # Phase 2 output (future)
        ├── r0_c0.png
        └── results.json
```

### Design Principles

1. **Never Lose State** - Continuous logging to disk
2. **Screenshot Everything** - Visual verification of findings
3. **No Assumptions** - Pure discovery through experimentation
4. **Human-in-Loop** - Interactive, not fully automated (for calibration)
5. **Build Knowledge Incrementally** - Each finding logged immediately
6. **Reproducible** - All parameters documented for future automation

### Data Flow

```
Human + Game → Interactive Tool → Findings
                     ↓
            Continuous Logging
                     ↓
         calibration_findings/
                     ↓
         final_findings.json
                     ↓
         map_config.json (manual conversion)
                     ↓
         Phase 2 Automation (uses config)
```

### What Happens After Phase 1?

Once calibration complete:
1. Review `final_findings.json`
2. Extract key parameters:
   - World toggle coordinates
   - Zoom button coordinates
   - Which zoom level for castle levels vs names
   - Map dimensions (swipes to edges)
3. Create `map_config.json` with these values
4. Phase 2 tools will load this config for automated scanning

### Why This Approach?

**Alternative (Bad)**: Hardcode coordinates, guess parameters, run automated scan
- Result: Scan misses areas, wrong zoom, can't find anything
- No way to debug what went wrong

**Our Approach (Good)**: Interactive discovery first
- Result: Know exactly how everything works
- Documented evidence of all findings
- Can debug issues by reviewing logs/screenshots
- Automation built on solid foundation

---

**Remember**: This is pure exploration. No assumptions, just discovery and documentation!

## Ready to Start?

```bash
python calibrate_interactive.py
# or double-click: calibrate_phase1.bat
```

**Suggested first session:**
1. Mode 1 (Discovery) - Get oriented
2. Mode 4 (Button Finder) - Find World toggle
3. Mode 2 (Zoom Explorer) - Document 2-3 zoom levels
4. Mode 5 (Quit) - Save findings

**Don't try to complete everything in one session!** Calibration can be done incrementally. All progress is saved.
