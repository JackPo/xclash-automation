# Gemini Detection Workflow

Use Gemini for detecting UI elements when no template exists.

## Basic Usage

```bash
# Step 1: Save screenshot
python -c "from utils.windows_screenshot_helper import WindowsScreenshotHelper; import cv2; cv2.imwrite('screenshot.png', WindowsScreenshotHelper().get_screenshot_cv2())"

# Step 2: Run detection
python calibration/detect_object.py screenshot.png "description of element"

# Output files:
# - detect_crop.png    : Cropped template (save to ground_truth)
# - detect_debug.png   : Visualization with bounding box
```

## Coordinate Format

Gemini returns normalized coordinates `[ymin, xmin, ymax, xmax]` in range 0-1000.

### Descaling to Pixels (4K: 3840x2160)

```python
# Gemini output: [ymin, xmin, ymax, xmax] normalized 0-1000
bbox = [450, 520, 510, 580]  # Example

# Descale to 4K pixels
x1 = int(bbox[1] * 3840 / 1000)  # xmin
y1 = int(bbox[0] * 2160 / 1000)  # ymin
x2 = int(bbox[3] * 3840 / 1000)  # xmax
y2 = int(bbox[2] * 2160 / 1000)  # ymax

# Width and height
w = x2 - x1
h = y2 - y1

# Click center
click_x = (x1 + x2) // 2
click_y = (y1 + y2) // 2
```

## Auto-Refinement Strategy

When initial detection fails or is inaccurate, refine the prompt iteratively.

### Iteration 1: Basic Description

```bash
python calibration/detect_object.py screenshot.png "the treasure map icon"
```

### Iteration 2: Add Location Context

```bash
python calibration/detect_object.py screenshot.png "the treasure map icon in the lower left area of the screen"
```

### Iteration 3: Add Visual Details

```bash
python calibration/detect_object.py screenshot.png "the small bouncing parchment scroll icon with brown color, located in the lower left quadrant near the barracks"
```

### Prompt Engineering Tips

| Issue | Solution |
|-------|----------|
| Wrong element detected | Add location: "in the upper right", "on the left sidebar" |
| Box too large | Add size hint: "small icon", "tiny button" |
| Misses animated elements | Describe static features: "the scroll shape", "circular icon" |
| Confuses similar elements | Add distinguishing features: "with the red dot", "green not gray" |

## Full Workflow Example

### 1. Take Screenshot

```python
from utils.windows_screenshot_helper import WindowsScreenshotHelper
import cv2

win = WindowsScreenshotHelper()
frame = win.get_screenshot_cv2()
cv2.imwrite("screenshot.png", frame)
```

### 2. Run Gemini Detection

```bash
python calibration/detect_object.py screenshot.png "the claim button with green background"
```

### 3. Verify Detection

Check `detect_debug.png` to see if bounding box is correct.

If wrong:
- Refine prompt with more details
- Re-run detection
- Max 3 iterations before asking user

### 4. Extract Template

```python
import cv2

frame = cv2.imread("screenshot.png")

# Use coordinates from Gemini (already descaled by detect_object.py)
x, y, w, h = 2100, 1400, 333, 88  # Example

# Extract and save
template = frame[y:y+h, x:x+w]
cv2.imwrite("templates/ground_truth/claim_button_4k.png", template)
print(f"Saved template: {w}x{h} pixels")
```

### 5. Create Matcher Class

Use Pattern 1 (fixed) or Pattern 2 (search) from TEMPLATE_MATCHING.md.

## detect_object.py Details

Location: `calibration/detect_object.py`

### Features

- Uses `gemini-2.0-flash` model with object detection
- Returns bounding box `[ymin, xmin, ymax, xmax]` normalized 0-1000
- Automatically crops and saves `detect_crop.png`
- Saves visualization to `detect_debug.png`

### API Key

Requires `GOOGLE_API_KEY` in `config_local.py`:

```python
GOOGLE_API_KEY = "your-api-key-here"
```

## Common Issues

### "No object detected"

- Prompt too vague → add visual details
- Element not visible → check screenshot manually
- Element is animated → describe static frame

### Bounding box too large

- Add "small" or "icon" to prompt
- Specify exact location: "the 50x50 pixel icon at..."
- Describe only the core element, not surrounding UI

### Wrong element detected

- Add negative context: "not the chat bubble, the scroll icon"
- Specify color: "the brown parchment, not the white one"
- Use landmarks: "below the stamina bar", "next to the bag icon"

## When Gemini Fails

After 3 refinement attempts:

1. Ask user to describe the element more precisely
2. Ask user to mark the element on screenshot
3. User provides exact coordinates manually
4. Extract template from user-provided region
