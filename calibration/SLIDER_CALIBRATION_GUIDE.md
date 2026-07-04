# Slider Calibration Guide

How to find the exact left/right boundaries of a slider track.

## DON'T: Color-based detection

**DO NOT** use green/color pixel detection to find slider boundaries. The colored fill doesn't extend to the actual clickable edge - you'll be off by 30+ pixels.

## DO: Edge Detection + Contour Analysis

The slider track is a rectangle with a visible border. Use Canny edge detection:

```python
import cv2
import numpy as np

def find_slider_track_bounds(frame, search_region=None):
    """
    Find slider track boundaries using edge detection.

    Args:
        frame: BGR screenshot (numpy array)
        search_region: Optional (x, y, w, h) to crop before analysis

    Returns:
        (left_x, right_x, center_y) or None if not found
    """
    if search_region:
        x, y, w, h = search_region
        crop = frame[y:y+h, x:x+w]
        offset_x, offset_y = x, y
    else:
        crop = frame
        offset_x, offset_y = 0, 0

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    # Edge detection
    edges = cv2.Canny(gray, 50, 150)

    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter for wide, short rectangles (slider track shape)
    candidates = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # Slider tracks are wide (>200px) and short (<100px height)
        if w > 200 and 20 < h < 100:
            candidates.append({
                'left': x + offset_x,
                'right': x + w + offset_x,
                'center_y': y + h//2 + offset_y,
                'width': w
            })

    if not candidates:
        return None

    # Return the widest candidate
    best = max(candidates, key=lambda c: c['width'])
    return (best['left'], best['right'], best['center_y'])
```

## Calibration Process

1. Take screenshot with slider visible
2. Run edge detection to get initial boundaries
3. **Test iteratively**:
   - Click left edge → verify slider goes to minimum
   - Click right edge → verify slider goes to maximum
   - If not reaching max, add 5px to right edge, test again
   - Fine-tune until exact

Edge detection gets within ~5 pixels. Final tuning via iterative clicking.

## Soldier Training Slider (4K)

Calibrated 2026-01-04:

```python
SLIDER_Y = 1175      # Y coordinate of track center
SLIDER_MIN_X = 1604  # Left edge (clickable minimum)
SLIDER_MAX_X = 2137  # Right edge (clickable maximum)
```
