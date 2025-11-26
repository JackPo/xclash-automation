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

### Step 3: Use Read Tool to Find Button Boundaries

```python
# Use Read tool to examine temp_corner_500x500.png
# Identifies exact x_start, y_start where button begins
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

All templates extracted from 3840x2160 screenshots at **240x240 pixels (square)**:

### town_button.png
- **Size**: 240x240 (square)
- **Extracted from**: (260, 260) to (500, 500) in 500x500 corner
- **Shows**: Castle icon with "Town" text
- **When it appears**: Currently in WORLD view (button shows where you CAN GO)

### town_button_zoomed_out.png
- **Size**: 240x240 (square)
- **Extracted from**: (260, 260) to (500, 500) in 500x500 corner
- **Shows**: Map icon with "Town" text (zoomed out view with minimap visible)
- **When it appears**: Currently in WORLD view with minimap visible

### world_button.png
- **Size**: 240x240 (square)
- **Extracted from**: (260, 260) to (500, 500) in 500x500 corner
- **Shows**: Map icon with "World" text
- **When it appears**: Currently in TOWN view (button shows where you CAN GO)

**All templates are identical 240x240 size for consistent matching**

## Template Matching

### Button Detection Logic

The button shows your DESTINATION, not current state:
- Button shows "WORLD" → You are IN TOWN
- Button shows "TOWN" → You are IN WORLD

### Coordinate System

**Templates are at 4K scale (3840x2160)**:
- Button at bottom-right: extract last 240x240 pixels (all templates are square)
- Click position: (3780, 2040) - scales from 2560x1440 → 3840x2160
- X fraction: 0.75 (75% across button width)
- Y fraction: 0.50 (50% down button height)

### Template Scores

All templates achieve near-perfect scores with excellent separation:
- **Best match**: 0.9999-1.0000 (99.99%-100%)
- **Second best**: 0.9613-0.9665 (96.13%-96.65%)
- **Separation**: 3.35%-3.87% (excellent discrimination)

## Key Lessons Learned

1. **NEVER use auto-crop when extracting templates**
2. **Always work with full 3840x2160 screenshots**
3. **Use Read tool to identify exact button boundaries** - don't guess coordinates
4. **Extract to absolute corner (500, 500)** in the 500x500 region
5. **Buttons are NOT square** - they vary from 210x240 to 240x260
6. **Templates must match the native game resolution** for accurate detection

## Next Steps

1. Update button_matcher.py to work with 4K templates
2. Scale click coordinates from 2560x1440 to 3840x2160
3. Test detection accuracy with new templates
4. Update all template matching code to use 4K coordinates
