# XClash Player Finder - OCR Grid Scanner

Automatically scans the XClash world map in a grid pattern to find a specific player using Tesseract OCR.

## Prerequisites

1. **BlueStacks must be running** with XClash open
2. **Open the world map** in XClash
3. **Manually adjust zoom level** so you can see numbers below castle icons
4. BlueStacks ADB connection enabled (should already be configured from hunt-player.ps1)

## Quick Start

### 1. Find a Player

```bash
# Use full Python path until PATH is updated (or restart terminal)
"C:\Users\mail\AppData\Local\Programs\Python\Python312\python.exe" find_player.py "PlayerName"

# After restarting terminal:
python find_player.py "PlayerName"
```

### 2. Test OCR First

Before running a full scan, test that OCR is working on your current view:

```bash
python test_config.py ocr
```

This will:
- Take a screenshot of the current game view
- Run OCR on it
- Display all detected text with confidence scores
- Look for player names and numbers in the output

### 3. Test Navigation

Test navigation commands interactively:

```bash
python test_config.py nav
```

Commands: `up`, `down`, `left`, `right`, `tl` (top-left), `ss` (screenshot), `quit`

## How It Works

1. **Navigate to Top-Left**: Automatically swipes left and up multiple times to reach the map's top-left corner
2. **Grid Scan Pattern**:
   - Scans left-to-right across the top row
   - Moves down one step
   - Scans right-to-left across the next row (zigzag pattern)
   - Repeats until entire grid is covered
3. **OCR Each View**: Takes screenshot and uses Tesseract to read all visible text
4. **Search**: Looks for player name (case-insensitive)
5. **Early Exit**: Stops immediately when player is found

## Configuration

Edit the `Config` class in `find_player.py` to tune these settings:

### Critical Settings to Adjust

#### Navigation Distances
```python
HORIZONTAL_SCROLL_DISTANCE = 1500  # How far to scroll left/right
VERTICAL_SCROLL_DISTANCE = 800     # How far to scroll up/down
```

**How to tune:**
1. Run `python test_config.py nav`
2. Use `right` command and see how far the map moves
3. Adjust distances so each scroll moves about 70-80% of screen width/height
   (slight overlap prevents missing players at boundaries)

#### Grid Size
```python
HORIZONTAL_STEPS = 10  # Number of columns to scan
VERTICAL_STEPS = 8     # Number of rows to scan
```

**How to tune:**
- Increase if your map is larger than expected
- Decrease to scan faster if map is smaller

#### Initial Position
```python
INITIAL_LEFT_SWIPES = 15   # Swipes to reach left edge
INITIAL_UP_SWIPES = 15     # Swipes to reach top edge
```

**How to tune:**
1. Run `python test_config.py nav`
2. Use `tl` command to test going to top-left
3. Increase if you don't reach the edge
4. Decrease to save time if you overshoot

### OCR Settings

```python
OCR_CONFIDENCE_THRESHOLD = 30  # Minimum confidence (0-100)
```

- Lower = more results but more false positives
- Higher = fewer results but more accurate
- Run `python test_config.py ocr` to see what confidence levels you're getting

### Timing (if map animations are slow)

```python
DELAY_AFTER_SWIPE = 0.8      # Wait after scrolling
DELAY_AFTER_SCREENSHOT = 0.3  # Wait after screenshot
DELAY_BETWEEN_SCANS = 0.2    # Wait between scans
```

Increase if map doesn't settle before screenshots.

## Usage Examples

### Basic Search
```bash
python find_player.py "Angelbear666"
```

### Debug Mode (saves all screenshots)
```bash
python find_player.py "PlayerName" --debug
```

Saves screenshots to `screenshots/` directory for review.

### Test OCR on Current Screen
```bash
python find_player.py "PlayerName" --test-ocr
```

Only OCRs current view without any navigation.

## Troubleshooting

### "Player not found" but you know they're there

**Possible causes:**
1. **Zoom level wrong** - Manually adjust zoom so numbers are visible below castles
2. **OCR confidence too high** - Lower `OCR_CONFIDENCE_THRESHOLD`
3. **Grid too small** - Increase `HORIZONTAL_STEPS` or `VERTICAL_STEPS`
4. **Scroll distances wrong** - Map overlap missing player position

**Solution:**
```bash
# Test OCR at player's location
python test_config.py ocr

# Check if player name appears in OCR results
# If not, try different zoom level
```

### Navigation not reaching top-left

**Solution:**
1. Test navigation: `python test_config.py nav`
2. Manually use `up` and `left` commands
3. Count how many swipes needed to reach edge
4. Update `INITIAL_LEFT_SWIPES` and `INITIAL_UP_SWIPES`

### OCR detecting too much garbage

**Solution:**
- Increase `OCR_CONFIDENCE_THRESHOLD` (try 40-50)
- Run `python test_config.py ocr` to verify

### Map scrolls too fast/slow

**Solution:**
- Adjust `SCROLL_DURATION` (milliseconds for swipe animation)
- Adjust `DELAY_AFTER_SWIPE` (seconds to wait for map to settle)

## Files

- `find_player.py` - Main player finder script
- `test_config.py` - Configuration and testing helper
- `PLAYER_FINDER_README.md` - This file

## Requirements

- Python 3.12+
- pytesseract
- Pillow
- Tesseract OCR (already installed)
- BlueStacks with ADB access

## TODO: Zoom Adjustment

Currently, you need to manually adjust the zoom level before running the script. Future enhancement: automatically detect and set optimal zoom level.

## Notes

- The script uses a **zigzag pattern** (left-to-right, then right-to-left) to minimize scrolling time
- Screenshots are temporary unless `--debug` flag is used
- Case-insensitive search
- Stops immediately when player is found
- Grid covers approximately 10x8 views (80 screenshots total)
- Each scan takes ~1-2 seconds depending on delays
