---
name: screenshot-detection
description: Take screenshots and detect UI elements. Use when finding click positions, extracting templates, detecting icons, or when user asks "where is", "find the", "click on", "extract template", "detect", "locate". Decides between template matching (if template exists) and Gemini detection (for new elements).
allowed-tools: Read, Write, Bash, Glob, Grep
---

# Screenshot & Detection Skill

Detect UI elements in game screenshots using template matching or Gemini vision.

## Decision Flowchart

```
Need to find/click something?
│
├─ Template exists in templates/ground_truth/?
│   │
│   ├─ YES → Use template matching (fast, reliable)
│   │        See: TEMPLATE_MATCHING.md
│   │
│   └─ NO → Use Gemini detection
│           See: GEMINI_DETECTION.md
│
After Gemini detection:
└─ Extract template → Save to ground_truth → Create matcher class
```

## Core Rules

### Rule 1: NEVER Analyze Screenshots Directly

Claude's image analysis is unreliable for game UI. Always use Gemini:

```bash
python calibration/detect_object.py screenshot.png "description of element"
```

### Rule 2: ALWAYS Use WindowsScreenshotHelper

ADB screenshots have different pixel values and WILL NOT match templates.

```python
from utils.windows_screenshot_helper import WindowsScreenshotHelper

win = WindowsScreenshotHelper()
frame = win.get_screenshot_cv2()  # BGR numpy array, 3840x2160
```

### Rule 3: Template Matching Method

Always use `cv2.TM_SQDIFF_NORMED`:
- **Lower score = better match**
- Score ~0.00 = perfect match
- Threshold typically 0.03-0.1

### Rule 4: Template Naming

Save to `templates/ground_truth/` with format: `<element>_4k.png`

## Quick Reference

### Take Screenshot

```python
from utils.windows_screenshot_helper import WindowsScreenshotHelper
import cv2

win = WindowsScreenshotHelper()
frame = win.get_screenshot_cv2()
cv2.imwrite("screenshot.png", frame)
```

### Check if Template Exists

```bash
ls templates/ground_truth/ | grep -i "element_name"
```

### Template Matching (Fixed Position)

```python
import cv2

template = cv2.imread('templates/ground_truth/icon_4k.png', cv2.IMREAD_GRAYSCALE)
frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

# Extract ROI at known position
roi = frame_gray[y:y+h, x:x+w]
result = cv2.matchTemplate(roi, template, cv2.TM_SQDIFF_NORMED)
score = cv2.minMaxLoc(result)[0]

is_present = score < 0.05  # threshold
```

### Template Matching (Search Region)

```python
import cv2

template = cv2.imread('templates/ground_truth/button_4k.png', cv2.IMREAD_GRAYSCALE)
frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

# Search in region
roi = frame_gray[y1:y2, x1:x2]
result = cv2.matchTemplate(roi, template, cv2.TM_SQDIFF_NORMED)
min_val, _, min_loc, _ = cv2.minMaxLoc(result)

if min_val < 0.05:
    found_x = x1 + min_loc[0]
    found_y = y1 + min_loc[1]
```

### Gemini Detection (New Element)

```bash
# Save screenshot first
python -c "from utils.windows_screenshot_helper import WindowsScreenshotHelper; import cv2; cv2.imwrite('screenshot.png', WindowsScreenshotHelper().get_screenshot_cv2())"

# Run detection
python calibration/detect_object.py screenshot.png "the treasure map icon"

# Outputs: detect_crop.png (template), detect_debug.png (visualization)
```

### Extract Template from Coordinates

```python
# After Gemini gives (x, y, w, h):
roi = frame[y:y+h, x:x+w]
cv2.imwrite('templates/ground_truth/element_4k.png', roi)
```

## Threshold Guidelines

| Element Type | Threshold | Notes |
|-------------|-----------|-------|
| Static icons | 0.03-0.05 | Consistent appearance |
| Animated elements | 0.08-0.1 | Frame variance |
| Text elements | 0.02-0.03 | Very consistent |
| Buttons with states | 0.05-0.08 | Slight variations |
| Full dialogs | 0.05 | Unique content |

## Workflow: Adding New Detection

1. **Check for existing template**
   ```bash
   ls templates/ground_truth/ | grep -i "keyword"
   ```

2. **If template exists**: Create matcher class (see TEMPLATE_MATCHING.md)

3. **If no template**:
   - Take screenshot with WindowsScreenshotHelper
   - Run Gemini detection
   - If inaccurate, refine prompt (see GEMINI_DETECTION.md)
   - Extract and save template
   - Create matcher class

4. **Test the matcher**
   ```python
   matcher = MyMatcher()
   frame = win.get_screenshot_cv2()
   is_present, score = matcher.is_present(frame)
   print(f"Present: {is_present}, Score: {score:.4f}")
   ```

## Files

- `TEMPLATE_MATCHING.md` - Matcher class patterns and examples
- `GEMINI_DETECTION.md` - Gemini workflow and prompt refinement

## See Also

- `utils/view_state_detector.py` - View detection implementation
- `calibration/detect_object.py` - Gemini detection script
- `templates/ground_truth/` - All template images
