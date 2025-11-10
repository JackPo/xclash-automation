# BlueStacks Resolution Setup for XClash

## Critical Discovery

BlueStacks physical display is **3840x2160 (4K)**, NOT 2560x1440!

## Why Text Looks Sharp

The display renders at **native 4K resolution (3840x2160)** with no scaling:
- 50% more horizontal pixels than expected (3840 vs 2560)
- 50% more vertical pixels than expected (2160 vs 1440)
- 2.25x total pixel count vs 2560x1440
- Text rendered at full 4K = extremely sharp

## The Resolution Pipeline

```
BlueStacks Physical Display: 3840x2160 (4K native)
         ↓
ADB Screenshot: 3840x2160 PNG
         ↓
Auto-Crop (find_player.py): Extract center 2560x1440 region
         ↓
Templates/Coordinates: All calibrated for 2560x1440
```

## Correct Setup Commands

```bash
# Reset to native 4K resolution
adb shell wm size reset      # Returns to 3840x2160
adb shell wm density reset   # Returns to 560 DPI

# Verify
adb shell wm size     # Should show: Physical size: 3840x2160
adb shell wm density  # Should show: Physical density: 560
```

## What NOT To Do

❌ **NEVER** run `adb shell wm size 3088x1440` - this DOWNSCALES from 4K and makes text blurry!
❌ **NEVER** run `adb shell wm size 2560x1440` - same problem, downscaling from native 4K!

✅ **ALWAYS** use `wm size reset` to return to native 3840x2160

## Why The Mistake Happened

- I assumed physical display was 2560x1440
- I tried to "supersample" by setting 3088x1440
- This actually **downscaled** from native 4K (3840x2160)
- Downscaling = blurry rendering

## Auto-Crop Configuration

In `find_player.py`:

```python
class Config:
    # Screen dimensions (for templates/coordinates)
    SCREEN_WIDTH = 2560
    SCREEN_HEIGHT = 1440

    # Actual render resolution (BlueStacks native 4K)
    RENDER_WIDTH = 3840
    RENDER_HEIGHT = 2160

    # Auto-crop screenshots from 3840x2160 to 2560x1440
    AUTO_CROP = True
```

Auto-crop logic:
- Takes 3840x2160 screenshot
- Crops center region to 2560x1440
- X offset: (3840 - 2560) // 2 = 640 pixels from each side
- Y offset: (2160 - 1440) // 2 = 360 pixels from top/bottom

## Benefits

1. **Extremely sharp text** - rendered at native 4K resolution
2. **Better OCR accuracy** - high-resolution text is easier to read
3. **Improved template matching** - more detail in images
4. **No scaling artifacts** - native resolution, no interpolation

## After BlueStacks Restart

Resolution settings persist in BlueStacks configuration. If they ever reset:

```bash
python setup_bluestacks.py  # Will run wm size reset
```

## Verification

Check current settings:
```bash
adb shell wm size      # Should be: Physical size: 3840x2160
adb shell wm density   # Should be: Physical density: 560
```

Take a screenshot and verify dimensions:
```python
from find_player import ADBController, Config
import cv2

config = Config()
adb = ADBController(config)

# Raw screenshot (before auto-crop)
adb.screenshot('test.png')
img = cv2.imread('test.png')
print(f"After auto-crop: {img.shape[1]}x{img.shape[0]}")  # Should be 2560x1440
```

## Summary

- BlueStacks native resolution: **3840x2160 (4K)**
- Templates/coordinates: **2560x1440**
- Auto-crop: Extract center 2560x1440 from 3840x2160 screenshots
- Result: Sharp 4K rendering with 2560x1440 coordinate system
