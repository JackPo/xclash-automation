# Handshake Icon Extraction - 4K Resolution

## Overview
Successfully extracted the handshake icon from the Union button using Gemini 2.0 Flash's object detection with iterative refinement.

## Source Image
- **File**: `templates/ground_truth/current_screenshot_4k.png`
- **Resolution**: 3840x2160 (4K)

## Extraction Method
Used Gemini 2.0 Flash vision API with iterative segmentation approach:
- 2 iterations of progressively tighter bounding boxes
- All crops extracted from original 4K image (maintaining global coordinates)
- Manual adjustment of final template for optimal size

## API Configuration
```python
from google import genai
from google.genai import types

config = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(thinking_budget=0),
    response_mime_type="application/json"
)

client.models.generate_content(
    model="gemini-2.0-flash-exp",
    contents=[prompt, image],
    config=config
)
```

## Coordinate System
- Gemini returns normalized coordinates in range [0, 1000]
- Format: `[y0, x0, y1, x1]` (NOT [x0, y0, x1, y1])
- Descaling formula: `pixel_coord = normalized_coord * image_dimension / 1000`

### Descaling Example
For 4K image (3840x2160) with normalized coords [820, 776, 929, 855]:
```python
y_min = 820 * 2160 / 1000 = 1771
x_min = 776 * 3840 / 1000 = 2979
y_max = 929 * 2160 / 1000 = 2006
x_max = 855 * 3840 / 1000 = 3283
```

## Extraction Results

### Iteration 1: Initial Detection
- **Prompt**: "the handshake icon on top of the Union button"
- **Normalized coords**: [820, 776, 929, 855]
- **Global 4K coords**: (2979, 1771) to (3283, 2006)
- **Size**: 304x235 pixels
- **File**: `templates/ground_truth/handshake_iter1.png`

### Iteration 2: Refined Detection
- **Input**: Iteration 1 crop (304x235)
- **Prompt**: "the handshake icon"
- **Relative coords**: (119, 9)
- **Size (original Gemini)**: 105x127 pixels
- **Global 4K coords**: (3098, 1780)
- **Manual adjustments**:
  - Added 10px to left (x: 3098 → 3088)
  - Added 40px to right (width: 105 → 145)
  - **Final size**: 155x127 pixels
- **Final global coords**: (3088, 1780) to (3243, 1907)
- **File**: `templates/ground_truth/handshake_iter2.png` ✓ **FINAL TEMPLATE**

## Final Template Specifications

### File Location
`templates/ground_truth/handshake_iter2.png`

### Dimensions
- **Width**: 155 pixels
- **Height**: 127 pixels
- **Aspect ratio**: ~1.22:1

### Global 4K Coordinates
- **Top-left**: (3088, 1780)
- **Bottom-right**: (3243, 1907)
- **Center (for clicking)**: (3165, 1843)

### Center Calculation
```python
center_x = 3088 + 155/2 = 3088 + 77.5 = 3165.5 ≈ 3165
center_y = 1780 + 127/2 = 1780 + 63.5 = 1843.5 ≈ 1843
```

## Coordinate Transformation Chain

### From Iteration 1 to Global
```
Global coords = Iteration 1 offset + Iteration 2 relative coords + manual adjustments
X: 2979 + 119 - 10 = 3088
Y: 1771 + 9 = 1780
```

### Verification
All crops were extracted from the original 4K screenshot, ensuring coordinate accuracy for ADB clicking.

## Implementation Script
`gemini_segment_masks.py` - Gemini 2.0 Flash segmentation with proper coordinate descaling

### Key Features
- Handles [y0, x0, y1, x1] coordinate format
- Descales from [0-1000] normalized range to actual pixels
- Returns both normalized and pixel coordinates
- JSON mode for reliable parsing

## Usage for Template Matching

### At 4K Resolution (3840x2160)
```python
template = cv2.imread('templates/ground_truth/handshake_iter2.png')
# Template size: 155x127
# Expected location: around (3088, 1780)
```

### Click Coordinates (4K)
```python
# Center of icon for ADB tap
click_x = 3165
click_y = 1843
```

### Scaling to 2560x1440 (Current Runtime Resolution)
```python
scale_x = 2560 / 3840 = 0.6667
scale_y = 1440 / 2160 = 0.6667

# Template needs to be resized
template_1440p_width = int(155 * 0.6667) = 103
template_1440p_height = int(127 * 0.6667) = 85

# Click coordinates at 1440p
click_x_1440p = int(3165 * 0.6667) = 2110
click_y_1440p = int(1843 * 0.6667) = 1229
```

## Notes
- Gemini detection is non-deterministic (different results on each run)
- Manual adjustment was necessary to capture the full icon
- Final template includes minimal padding around the handshake graphic
- Coordinate math is verified correct - descaling formula matches Google's documentation

## Related Files
- `gemini_segment_masks.py` - Extraction script
- `validate_crop.py` - Helper for cropping regions
- `iter1_handshake.json` - Iteration 1 raw response
- `iter2_handshake.json` - Iteration 2 raw response
- `iterative_extraction_summary.json` - Full coordinate chain
