# Resolution and Template Extraction Guide

## Critical Discovery: Native 4K Resolution

**BlueStacks Native Resolution: 3840x2160 (4K)**

### NEVER Use Auto-Crop for Template Extraction

When extracting templates, ALWAYS disable auto-crop:

```python
config = Config()
config.AUTO_CROP = False  # CRITICAL: Disable auto-crop
adb = ADBController(config)
```

### Why This Matters

- **Old method (WRONG)**: Auto-crop enabled → screenshots cropped to 2560x1440 → templates at wrong scale
- **Correct method**: Auto-crop disabled → full 3840x2160 screenshots → templates at native 4K scale

## Template Extraction Process

### Step 1: Capture Full 4K Screenshot

```python
from find_player import ADBController, Config
import cv2

config = Config()
config.AUTO_CROP = False  # MUST disable auto-crop

adb = ADBController(config)
adb.screenshot('temp_full_4k.png')
frame = cv2.imread('temp_full_4k.png')
h, w = frame.shape[:2]  # Should be 3840x2160
```

### Step 2: Extract 500x500 Corner Region

```python
# Extract 500x500 from absolute bottom-right corner
size = 500
x1 = w - size  # 3840 - 500 = 3340
y1 = h - size  # 2160 - 500 = 1660

corner = frame[y1:h, x1:w]
cv2.imwrite('temp_corner_500x500.png', corner)
```

### Step 3: Use Image Agent to Find Button Boundaries

```python
# Use Task tool with image agent to examine temp_corner_500x500.png
# Agent identifies exact x_start, y_start where button begins
# Button always goes to corner at (500, 500)
```

### Step 4: Extract Template

```python
# Example: Agent says button starts at (290, 240)
x_start = 290
y_start = 240
x_end = 500
y_end = 500

button = corner[y_start:y_end, x_start:x_end]
cv2.imwrite('templates/ground_truth/button_name.png', button)
```

## Current Templates (Native 4K)

All templates extracted from 3840x2160 screenshots:

### town_button.png
- **Size**: 240x240 (square)
- **Extracted from**: (260, 260) to (500, 500) in 500x500 corner
- **Shows**: Castle icon with "Town" text
- **When it appears**: Currently in WORLD view (button shows where you CAN GO)

### town_button_zoomed_out.png
- **Size**: 210x240 (taller than wide)
- **Extracted from**: (290, 260) to (500, 500) in 500x500 corner
- **Shows**: Map icon with "Town" text (zoomed out view)
- **When it appears**: Currently in WORLD view with minimap visible

### world_button.png
- **Size**: 210x260 (taller than wide)
- **Extracted from**: (290, 240) to (500, 500) in 500x500 corner
- **Shows**: Map icon with "World" text
- **When it appears**: Currently in TOWN view (button shows where you CAN GO)

## Template Matching

### Button Detection Logic

The button shows your DESTINATION, not current state:
- Button shows "WORLD" → You are IN TOWN
- Button shows "TOWN" → You are IN WORLD

### Coordinate System

**Important**: Templates are at 4K scale, but button_matcher.py needs updating for 4K coordinates.

**Old system (2560x1440)**:
- Button at bottom-right: extract last 160x160 pixels
- Click position: (2460, 1315)

**New system (3840x2160)**:
- Button at bottom-right: extract last ~240x240 pixels (varies by button)
- Click position: TBD (needs scaling from old coordinates)

## Key Lessons Learned

1. **NEVER use auto-crop when extracting templates**
2. **Always work with full 3840x2160 screenshots**
3. **Use image agents to identify exact button boundaries** - don't guess coordinates
4. **Extract to absolute corner (500, 500)** in the 500x500 region
5. **Buttons are NOT square** - they vary from 210x240 to 240x260
6. **Templates must match the native game resolution** for accurate detection

## Next Steps

1. Update button_matcher.py to work with 4K templates
2. Scale click coordinates from 2560x1440 to 3840x2160
3. Test detection accuracy with new templates
4. Update all template matching code to use 4K coordinates
