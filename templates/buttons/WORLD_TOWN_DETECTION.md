# World/Town View Detection System

## ⚠️ CRITICAL: Button Shows DESTINATION, Not Current State

**The button displays where you CAN GO, not where you ARE:**
- When **IN World view** → button shows **"TOWN"** (you can switch to town)
- When **IN Town view** → button shows **"WORLD"** (you can switch to world)

**The API handles this automatically:**
- `ViewState.WORLD` = you ARE CURRENTLY in World view (button shows TOWN)
- `ViewState.TOWN` = you ARE CURRENTLY in Town view (button shows WORLD)

## Quick Start

```python
from view_detection import detect_current_view, switch_to_view, ViewState
from find_player import ADBController, Config

config = Config()
adb = ADBController(config)

# Detect where you currently are
current = detect_current_view(adb)
print(f"Currently in: {current.value}")  # e.g., "WORLD"

# Switch to a specific view
success = switch_to_view(adb, ViewState.TOWN)
```

See `view_detection.py` for full API documentation.

## How It Works

### Detection
1. **Captures screenshot** from BlueStacks via ADB
2. **Matches templates** against button in lower-right corner (2160, 1190) to (2560, 1440)
3. **Inverts the match**:
   - If `world_button_template.png` matches (button shows "WORLD") → returns TOWN (current state)
   - If `town_button_template.png` matches (button shows "TOWN") → returns WORLD (current state)
4. **Returns current view** with confidence score

### Switching
1. **Detects current state**
2. **Clicks at (2460, 1315)** - this is x_frac=0.75, y_frac=0.5 of the button
3. **Toggles between states** - same position works for both WORLD→TOWN and TOWN→WORLD
4. **Waits and verifies** state changed

## Template Files

### world_button_template.png
- **Shows**: Button displaying "WORLD" icon (map with terrain)
- **Matches when**: You're currently in TOWN (button shows where you can go)
- **After inversion**: Returns TOWN as current state
- **Accuracy**: 99.96% match on correct images
- **Size**: 400x250 pixels

### town_button_template.png
- **Shows**: Button displaying "TOWN" icon (castle/fortress)
- **Matches when**: You're currently in WORLD (button shows where you can go)
- **After inversion**: Returns WORLD as current state
- **Accuracy**: 100% match on correct images
- **Size**: 400x250 pixels

## Detection Threshold: 97%

- **Correct matches**: 99-100% (well above threshold)
- **Cross-matches**: ~77% (well below threshold)
- **Why 77% cross-match?**: Templates share similar button frame/background, but differ in icons
- **97% threshold**: Safely distinguishes correct from incorrect matches

## Button Details

**Location**: Fixed at (2160, 1190) to (2560, 1440)
**Size**: 400x250 pixels
**Resolution**: 2560x1440 (constant)
**Position**: Lower-right corner of game UI

**Visual appearance**:
- Shows two icons side-by-side: TOWN (left, castle) and WORLD (right, map)
- Currently active destination is highlighted
- Clicking at x_frac=0.75 (right side) toggles between states

## Click Position

**Single position works for both directions:**
- Click at: **(2460, 1315)**
- Calculation: `x = 2160 + 400 * 0.75`, `y = 1190 + 250 * 0.5`
- This toggles: WORLD ↔ TOWN

## Test Images

Test screenshots for validation:
- `screenshot_check.png` - Currently in WORLD view (button shows TOWN)
- `screenshot_town.png` - Currently in TOWN view (button shows WORLD)
- `corner_check.png` - Cropped WORLD view
- `corner_town.png` - Cropped TOWN view

## Implementation Files

- **`button_matcher.py`**: Template matching with automatic inversion
- **`view_detection.py`**: High-level API (ViewDetector, ViewSwitcher, convenience functions)
- **`.claude/claude.MD`**: Complete game controls documentation
- **`test/`**: Test scripts validating detection and switching

## Common Issues

### "UNKNOWN" state returned
- **Cause**: Match score below 97% threshold
- **Fix**: Check button is visible, no dialogs blocking it, templates are correct

### Clicking doesn't switch views
- **Cause**: Button position wrong or game blocking input
- **Fix**: Verify button at (2160, 1190), check ADB connection

### Confusion about state names
- **Remember**: `ViewState.WORLD` = currently IN world (button shows TOWN)
- **Why?**: Button shows destination, API inverts to current state

## History

**2025-01-04**:
- Fixed inversion logic - ViewState now correctly represents CURRENT view
- Verified templates: world_button_template matches button showing "WORLD", inverted to return TOWN
- Confirmed toggle at x_frac=0.75 works bidirectionally
- 99-100% detection accuracy, 100% switching success rate
