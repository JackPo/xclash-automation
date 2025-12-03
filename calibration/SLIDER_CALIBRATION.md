# Soldier Training Slider Time Calibration

## Date: 2024-12-02/03

## Goal

Automate soldier training quantity selection by building a linear model that maps slider X position to training time.

## The Problem

The barracks training panel has a slider that controls how many soldiers to train. The slider position determines the training time. We needed to:
1. Find the slider circle position via template matching
2. Map X position to training time
3. Calculate where to drag the slider for a target training time

## Key Findings

### 1. ADB Coords = Visual Coords (1:1 Mapping)
Empirical testing confirmed that ADB swipe coordinates match Windows screenshot coordinates exactly. No scaling or offset conversion needed.

### 2. MUST Drag FROM Circle's Actual Position
The slider only moves if you swipe starting FROM the circle's current position. Swiping from arbitrary positions does NOT work.

```python
# WRONG - slider won't move
adb.swipe(arbitrary_x, SLIDER_Y, target_x, SLIDER_Y)

# CORRECT - find circle first, then drag from it
frame = win.get_screenshot_cv2()
circle_x = find_slider_circle(frame)  # Template matching
adb.swipe(circle_x, SLIDER_Y, target_x, SLIDER_Y)
```

### 3. Time is PERFECTLY Linear with X Position
R² = 0.999997 - essentially perfect linear relationship!

## Calibration Algorithm

1. **Find circle** via template matching (`slider_circle_4k.png`)
2. **Drag to MIN (far left)** - swipe FROM circle position TO X=1500
3. **Find circle again** via template matching → record as `min_x`
4. **OCR the time** from train button → record as `min_time`
5. **Find circle** via template matching
6. **Drag to MAX (far right)** - swipe FROM circle position TO X=2200
7. **Find circle again** via template matching → record as `max_x`
8. **OCR the time** → record as `max_time`
9. **Loop 30 times:**
   - Pick random target_x between min_x and max_x
   - Find circle via template matching
   - Drag FROM circle TO target_x
   - Find circle again → record actual_x
   - OCR the time → record time_seconds
   - Store (actual_x, time_seconds)
10. **Linear regression** on all data points
11. **Output**: slope, intercept, R², save to JSON

## Slider Coordinates (4K Resolution)

| Parameter | Value | Notes |
|-----------|-------|-------|
| SLIDER_Y | 1170 | Y center of slider circle |
| MIN X | ~1600 | Circle center at MIN (leftmost) |
| MAX X | ~2132 | Circle center at MAX (rightmost) |
| SLIDER_WIDTH | ~532 | Range = max_x - min_x |

## Train Button Time OCR

| Parameter | Value |
|-----------|-------|
| Button Position | (1969, 1399) |
| Time Region Offset | (50, 80) |
| Time Region Size | 280 x 45 |
| Absolute Position | (2019, 1479) to (2299, 1524) |

## Calibration Results (2024-12-03)

```
Data points collected: 14
X range: 1600 to 2132
Time range: 0s to 97736s (0 to 27:08:56)

LINEAR MODEL:
  time_seconds = 183.627743 * x + -293869.64

  R² (coefficient of determination): 0.999997
  RMSE (root mean square error): 52.50 seconds

INVERSE FORMULA (to calculate target X for a given time):
  target_x = (target_seconds - (-293869.64)) / 183.627743
  target_x = (target_seconds + 293869.64) / 183.627743
```

### Quick Reference Examples

| Target Time | Seconds | Target X |
|-------------|---------|----------|
| 1 hour | 3600 | 1620 |
| 2 hours | 7200 | 1640 |
| 4 hours | 14400 | 1679 |
| 8 hours | 28800 | 1757 |

## Raw Data Points

From calibration run:

| # | Actual X | Time | Seconds |
|---|----------|------|---------|
| MIN | 1600 | 00:00:00 | 0 |
| MAX | 2132 | 27:08:56 | 97736 |
| 1 | 1733 | 06:45:57 | 24357 |
| 2 | 1834 | 11:54:53 | 42893 |
| 3 | 1696 | 04:53:37 | 17617 |
| 4 | 1614 | 00:40:51 | 2451 |
| 5 | 1713 | 05:44:40 | 20680 |
| 6 | 1801 | 10:12:45 | 36765 |
| 7 | 2000 | 20:22:58 | 73378 |
| 8 | 2052 | 23:01:16 | 82876 |
| 9 | 2011 | 20:56:10 | 75370 |
| 10 | 2075 | 24:12:45 | 87165 |
| 11 | 1706 | 05:24:15 | 19455 |
| 12 | 1830 | 11:42:07 | 42127 |

## Files

- `calibrate_slider_time.py` - The calibration script
- `slider_time_calibration.json` - Calibration results with all data points
- `calibrate_slider_deprecated.py` - Old ADB calibration script (deprecated)

## Usage in Code

```python
# Constants from calibration
TIME_SLOPE = 183.627743
TIME_INTERCEPT = -293869.64

def calculate_target_x(target_seconds):
    """Given target time in seconds, return X position to drag slider to."""
    return int((target_seconds - TIME_INTERCEPT) / TIME_SLOPE)

# Example: To train for 4 hours
target_x = calculate_target_x(4 * 3600)  # Returns 1679
```

## Template

The slider circle template is stored at:
`templates/ground_truth/slider_circle_4k.png`

Size: 55x55 pixels

Template matching uses `cv2.TM_SQDIFF_NORMED` with threshold < 0.1 (scores around 0.01 indicate good match).

## Process Notes

1. QwenOCR is slow (~2-5 seconds per OCR call on GPU)
2. Template matching is fast (<100ms)
3. Full calibration takes 5-10 minutes for 30 samples
4. Some samples may fail if the training panel closes or screen changes
5. 14 valid data points were sufficient for R²=0.999997

## Why This Approach Works

The slider is a simple linear control:
- MIN position = 0 training time (1 soldier)
- MAX position = full queue training time
- Time scales linearly between them

This makes sense because each soldier takes the same amount of time to train, and the slider just controls quantity.

---

## Integration with Arms Race

The calibration is used by `barracks_training_flow.py` to time training for the Soldier Training Arms Race event.

### Full Workflow Example

```python
from utils.arms_race import get_time_until_soldier_training
from utils.adb_helper import ADBHelper
from scripts.flows.barracks_training_flow import barracks_training_flow

# 1. Get time until Soldier Training event
time_until = get_time_until_soldier_training()
target_hours = time_until.total_seconds() / 3600
print(f"Target: {target_hours:.2f} hours")

# 2. Run the flow (training panel must be open)
adb = ADBHelper()
success = barracks_training_flow(
    adb,
    soldier_level=4,
    target_hours=target_hours,
    debug=True
)
```

### Prerequisites

1. **OCR Server Running**:
   ```bash
   python services/ocr_server.py
   ```
   The server loads Qwen2.5-VL-3B on GPU and handles time OCR requests.

2. **Training Panel Open**: Click a PENDING barrack bubble before running the flow.

### Flow Logic

1. Finds and clicks the target soldier level tile (scrolls if needed)
2. Pushes slider to MAX to determine maximum time
3. Calculates target X position using calibration formula
4. Drags slider to target position
5. Fine-tunes with minus button to get just UNDER target
6. Clicks Train button

The "just under" behavior ensures training completes before the event ends, not after.
