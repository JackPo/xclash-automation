# Object Detection with Gemini - Ground Truth Template Extraction

## Overview

This guide explains how to extract ground truth templates from screenshots using Gemini's object detection API. This is the **correct** way to get bounding boxes for UI elements.

## Quick Start

```bash
python detect_object.py <image_path> "<description of what to find>"
```

### Example

```bash
python detect_object.py treasure_check.png "the bouncing treasure map scroll icon overlaying on top of the barracks building"
```

## Critical Requirements

### 1. Use the Correct Model

**MUST use `gemini-3-pro-preview`** for accurate object detection.

Other models (gemini-2.5-flash, gemini-2.0-flash-exp) return garbage coordinates.

```python
model="gemini-3-pro-preview"
```

### 2. Use JSON Response Mode

```python
config = types.GenerateContentConfig(
    response_mime_type="application/json"
)
```

### 3. Prompt Format

Follow the official documentation format exactly:

```python
prompt = f"""Detect {object_description}.
The box_2d should be [ymin, xmin, ymax, xmax] normalized to 0-1000."""
```

### 4. Coordinate Format

Gemini returns coordinates in this format:
- `[ymin, xmin, ymax, xmax]` - **Y comes first, not X!**
- Normalized to 0-1000 range
- Must descale to actual pixel coordinates

### 5. Descaling Formula

```python
width, height = image.size  # e.g., 3840x2160

# Gemini returns: [ymin, xmin, ymax, xmax] normalized to 0-1000
box = [713, 546, 788, 587]

abs_y1 = int(box[0] / 1000 * height)  # ymin
abs_x1 = int(box[1] / 1000 * width)   # xmin
abs_y2 = int(box[2] / 1000 * height)  # ymax
abs_x2 = int(box[3] / 1000 * width)   # xmax
```

## Full Working Example

```python
from google import genai
from google.genai import types
from PIL import Image
import json
import cv2

API_KEY = 'your-api-key'

client = genai.Client(api_key=API_KEY)

# Load image
image = Image.open("screenshot.png")
width, height = image.size

# Prompt - be specific about what you're looking for
prompt = """Detect the bouncing treasure map scroll icon overlaying on top of the barracks building.
The box_2d should be [ymin, xmin, ymax, xmax] normalized to 0-1000."""

config = types.GenerateContentConfig(
    response_mime_type="application/json"
)

response = client.models.generate_content(
    model="gemini-3-pro-preview",  # MUST use this model
    contents=[image, prompt],
    config=config
)

# Parse response
bounding_boxes = json.loads(response.text)
# Example response: [{"box_2d": [713, 546, 788, 587]}]

box = bounding_boxes[0]["box_2d"]

# Descale coordinates
abs_y1 = int(box[0] / 1000 * height)
abs_x1 = int(box[1] / 1000 * width)
abs_y2 = int(box[2] / 1000 * height)
abs_x2 = int(box[3] / 1000 * width)

print(f"Pixel coords: ({abs_x1}, {abs_y1}) to ({abs_x2}, {abs_y2})")

# Crop the detected region
img_cv = cv2.imread("screenshot.png")
cropped = img_cv[abs_y1:abs_y2, abs_x1:abs_x2]
cv2.imwrite("templates/ground_truth/my_template.png", cropped)
```

## Output Files

The `detect_object.py` script produces:

| File | Description |
|------|-------------|
| `detect_debug.png` | Screenshot with green box showing detection |
| `detect_crop.png` | Cropped region (your template) |
| `detect_result.json` | Full detection results with coordinates |

## Saving as Ground Truth Template

After running detection, copy the crop to ground_truth:

```bash
cp detect_crop.png templates/ground_truth/<name>_4k.png
```

## Common Mistakes

### WRONG: Using the wrong model
```python
model="gemini-2.5-flash"  # Returns bad coordinates
```

### WRONG: Forgetting JSON mode
```python
# Without response_mime_type, parsing is unreliable
response = client.models.generate_content(
    model="gemini-3-pro-preview",
    contents=[image, prompt]
)
```

### WRONG: Swapping X and Y
```python
# WRONG - X is not first!
abs_x1 = int(box[0] / 1000 * width)
abs_y1 = int(box[1] / 1000 * height)

# CORRECT - Y comes first
abs_y1 = int(box[0] / 1000 * height)
abs_x1 = int(box[1] / 1000 * width)
```

### WRONG: Vague prompts
```python
# Too vague - Gemini will find the wrong thing
prompt = "find the treasure map"

# Better - be specific about location and appearance
prompt = "the bouncing treasure map scroll icon overlaying on top of the barracks building"
```

## Tips for Good Detection

1. **Be specific** - Describe exactly what the element looks like and where it is
2. **Mention context** - "above the Hero button", "on top of the barracks"
3. **Describe appearance** - "small parchment scroll", "bouncing icon"
4. **Verify results** - Always check `detect_debug.png` to see where the box landed

## Reference

- Official docs: https://ai.google.dev/gemini-api/docs/image-understanding
- Script location: `detect_object.py`
- Templates folder: `templates/ground_truth/`
